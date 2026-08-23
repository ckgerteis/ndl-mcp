"""
NDL Search MCP Server (v1.0.1)
==============================
An MCP server for searching 国立国会図書館サーチ (NDL Search), operated by the
National Diet Library of Japan, over the SRU searchRetrieve interface.

Built to the undertakings given to the NDL when continuous use was registered
on 19 August 2026 (電子情報部 電子情報流通課). The library has since confirmed
that registration is no longer required, only welcome; the undertakings are kept
anyway, because they are the right way to treat a public service and because
they are the specification this server was written against, not commentary:

  * requests are issued serially — one connection, never concurrent
  * a minimum interval of MIN_REQUEST_INTERVAL seconds is held between requests
  * a single search is capped at MAX_RECORDS records; there is no auto-pagination
  * the harvesting interface (OAI-PMH) is not used and is not implemented
  * every response carries credit to the NDL Search API, and provider credit
    where the API提供対象データプロバイダ一覧 makes it a condition
  * retrieved metadata is displayed, not accumulated; nothing is cached

Only five NDL-created data providers are reachable, the set registered in 2026.
A request for any other dpid is refused in process rather than sent — a declared
scope a reader can check is worth more than a wide one nobody can.

The metadata this server retrieves is NDL-created throughout, and deliberately
so. 国立国会図書館ウェブサイトのコンテンツ利用規約 places NDL website content —
書誌データ included — under 公共データ利用規約（第1.0版）(PDL1.0), read with
「国以外の者」 as 「国立国会図書館以外の者」, and then carves out as third-party
rights 「書誌データ、書影等のうち、国立国会図書館以外の者が作成したもの」,
naming NDL Search metadata created by others as an instance of it. Records
aggregated from the other ~110 providers reach the user under conditions the NDL
does not set and this server cannot assert. Restricting to NDL-created sets is
what makes a single attribution line truthful.

There is no credential. The NDL search APIs are open — no application ID, no
key, no token. The application filed with the library is a permission and
notification procedure, not a credential grant. See README.md.

Requires mediation.py and ledger.py beside it, vendored byte-identical from
cinii-mcp; install.ps1 copies them rather than reproducing them.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Optional
from xml.etree import ElementTree as ET

import httpx
from pydantic import BaseModel, ConfigDict, Field
try:  # mcp SDK 1.x
    from mcp.server.fastmcp import FastMCP as _MCPServer
except ModuleNotFoundError:  # mcp SDK 2.x removed mcp.server.fastmcp
    from mcp.server.mcpserver import MCPServer as _MCPServer

from . import mediation as M

__version__ = "1.1.0"

# httpx logs every request URL at INFO. There is no credential in an NDL request,
# so nothing leaks — but a search term travels in that URL, and the line lands on
# the stderr Claude Desktop captures. Mute it, as the rest of the family does.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ==============================================================================
# Configuration
# ==============================================================================

SRU_BASE = "https://ndlsearch.ndl.go.jp/api/sru"
TIMEOUT = 30.0
USER_AGENT = "ndl-mcp/1.0 (scholarly research; +https://github.com/ckgerteis/ndl-mcp)"

# Filed with the NDL: a minimum one-second interval, requests issued serially.
MIN_REQUEST_INTERVAL = 1.0

# NDL answers 429 even inside that interval, so a 429 buys a single backoff.
BACKOFF_SECONDS = 10.0

# Filed with the NDL: a ceiling on the records returned by a single search.
# Deliberately far below the NDL's own limit of 500 — no mechanical bulk retrieval.
MAX_RECORDS = 100

MATCHING_MODE = "metadata_conjunction"

ATTRIBUTION = (
    "Data via 国立国会図書館サーチ (NDL Search), National Diet Library, Japan, "
    "retrieved through the NDL Search API. "
    "本サービスは国立国会図書館サーチのAPIを利用しています。"
)

COVERAGE_NOTE = (
    "NDL Search aggregates records from some 117 providers; this server queries "
    "only the five NDL-created sets this server declares. "
    "Absence here is absence from those sets, not from the NDL's holdings as a "
    "whole, and still less from NDL Search. Outside this server's declared scope "
    "in particular: the Digital Collections proper (ndl-dl, ndl-dl-online), the "
    "web archive (warp), the foreign-language Japan-related books set (ndl-boj), "
    "and the in-process national bibliography (iss-ndl-opac-inprocess)."
)

# ==============================================================================
# Data providers
# ==============================================================================
#
# The set registered with the NDL in August 2026. All five are
# marked ○ in BOTH the 非営利 and 営利 columns of the API提供対象データプロバイダ
# 一覧 — no usage application, whatever the use — and all five carry the NDL's
# own bibliographic-data condition. Adding to this table widens what this server
# declares about itself, so update the README, NDL-API-NOTIFICATION.txt and this
# comment in the same commit. The library no longer requires notification of a
# change; a reader still requires an accurate description.
#
# On the licence: the 一覧 records these sets as 「CC BY」 by way of 国立国会図書館
# ウェブサイトのコンテンツ利用規約, which places them under 公共データ利用規約
# （第1.0版）(PDL1.0) and states that condition to be *compatible with* CC BY 4.0.
# PDL1.0 is the governing instrument; CC BY 4.0 is the compatibility claim. The
# credit lines below say so rather than asserting a licence the NDL has not
# granted.
#
# On 国立国会図書館デジタルコレクション proper (ndl-dl, ndl-dl-online, ndl-dl-doi):
# the 一覧 marks them ○ for 非営利 and △ for 営利, so scholarly use needs no usage
# application. They are absent because they were not named in the notification of
# 19 August 2026, and because their metadata carries no open licence —
# displayable, not redistributable. Adding them is a filing, not an application.
#
# Set algebra, from 国立国会図書館作成書誌のデータプロバイダ詳細. It matters
# because a union over these dpids is not a sum:
#   iss-ndl-opac  ⊃ iss-ndl-opac-national, ndl-boj, iss-ndl-opac-bib
#   iss-ndl-opac  ∌ iss-ndl-opac-inprocess, zassaku, zassaku-online,
#                   ndl-dl, ndl-dl-online
#   zassaku       ∌ zassaku-online
#   ndl-dl-open   ⊆ ndl-dl ∪ ndl-dl-online, and so disjoint from iss-ndl-opac
# Since 2024-01 iss-ndl-opac also carries serial-issue-level records the pre-2024
# set did not; iss-ndl-opac-bib is the same set without them.

PROVIDERS: dict[str, dict[str, Optional[str]]] = {
    "iss-ndl-opac": {
        "ja": "国立国会図書館蔵書",
        "en": "NDL holdings",
        "credit": "国立国会図書館蔵書 (PDL1.0; CC BY 4.0 compatible)",
        "subset_of": None,
    },
    # NB: the 一覧 spells this dpid with a hyphen before "national". The
    # registration of 19 Aug 2026 and v1.0.0 of this file both wrote
    # "iss-ndl-opacnational", which names no provider: SRU matches nothing and
    # ndl_search_national_bibliography returned a clean, credible zero for every
    # query put to it. Corrected 20 Aug 2026. The set intended was always the
    # national bibliography, as named; only the identifier was wrong.
    "iss-ndl-opac-national": {
        "ja": "国立国会図書館全国書誌情報",
        "en": "Japanese National Bibliography",
        "credit": "国立国会図書館全国書誌情報 (PDL1.0; CC BY 4.0 compatible)",
        "subset_of": "iss-ndl-opac",
    },
    "zassaku": {
        "ja": "国立国会図書館雑誌記事索引",
        "en": "NDL Japanese Periodicals Index",
        "credit": "国立国会図書館雑誌記事索引 (PDL1.0; CC BY 4.0 compatible)",
        "subset_of": None,
    },
    "zassaku-online": {
        "ja": "国立国会図書館雑誌記事索引オンライン資料編",
        "en": "NDL Japanese Periodicals Index (online materials)",
        "credit": "国立国会図書館雑誌記事索引オンライン資料編 (PDL1.0; CC BY 4.0 compatible)",
        "subset_of": None,
    },
    "ndl-dl-open": {
        "ja": "国立国会図書館デジタルコレクション（オープンデータ）",
        "en": "NDL Digital Collections (Open Data)",
        "credit": "国立国会図書館デジタルコレクション（オープンデータ） (PDL1.0; CC BY 4.0 compatible)",
        "subset_of": None,
    },
}

BOOK_DPIDS = ["iss-ndl-opac"]
BIBLIOGRAPHY_DPIDS = ["iss-ndl-opac-national"]
ARTICLE_DPIDS = ["zassaku", "zassaku-online"]
DIGITAL_OPEN_DPIDS = ["ndl-dl-open"]

# ndl_search_all unions the declared set. iss-ndl-opac-national is kept in it
# although it is a subset of iss-ndl-opac: the union is unchanged by it, and the
# provider credit it contributes is the one a reader of a 全国書誌 record needs.
ALL_DPIDS = list(PROVIDERS.keys())


def provider_credit(dpids: list[str]) -> str:
    """The provider-level credit line required alongside the API attribution."""
    names = [PROVIDERS[d]["credit"] for d in dpids if d in PROVIDERS]
    if not names:
        return ATTRIBUTION
    return ATTRIBUTION + " Provider: " + "; ".join(names) + "."


# ==============================================================================
# Rate limiting — serial requests, minimum interval
# ==============================================================================
#
# The lock is what makes the "no concurrent access" undertaking true: it is held
# across the wait AND the request, so two tool calls cannot be in flight at once.

_rate_lock = asyncio.Lock()
_last_request_at = 0.0


# ==============================================================================
# HTTP
# ==============================================================================


async def _sru_request(params: dict[str, Any]) -> str:
    """Issue one SRU request. Serialised; never concurrent; never paginated.

    NDL publishes no rate figure — 「具体的な数値の目安をお示しすることができません」 —
    but it enforces one, and answers HTTP 429 when it is exceeded. Observed on
    19 August 2026 at well under one request per second sustained, so the filed
    one-second floor is a minimum and not a guarantee. On 429 the server backs
    off once, honouring Retry-After, and then gives up rather than pressing.
    """
    global _last_request_at
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    headers = {"User-Agent": USER_AGENT, "Accept": "application/xml"}
    async with _rate_lock:
        for attempt in (0, 1):
            wait = MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    resp = await client.get(SRU_BASE, params=clean, headers=headers)
            finally:
                _last_request_at = time.monotonic()
            if resp.status_code != 429 or attempt == 1:
                break
            retry_after = resp.headers.get("Retry-After")
            try:
                pause = min(float(retry_after), 30.0) if retry_after else BACKOFF_SECONDS
            except ValueError:
                pause = BACKOFF_SECONDS
            await asyncio.sleep(pause)
    resp.raise_for_status()
    return resp.text


def _error_diag(exc: Exception) -> dict:
    """Classify a failure as API_ERROR (the service answered) or TRANSPORT_ERROR."""
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code == 429:
            return M.diag(
                "error",
                "RATE_LIMITED",
                "NDL Search declined this request as too frequent (HTTP 429), after one backoff.",
                "Wait a minute and repeat the search. The result is unknown, not empty — "
                "do not read this as an absence in the index.",
            )
        return M.diag(
            "error",
            "API_ERROR",
            f"NDL Search returned HTTP {exc.response.status_code} for this query.",
            "Check the query syntax; retry once before treating it as an outage.",
        )
    if isinstance(exc, ET.ParseError):
        return M.diag(
            "error",
            "API_ERROR",
            "NDL Search returned a response that could not be parsed as XML.",
            "The service may be returning an error page; retry once.",
        )
    return M.diag(
        "error",
        "TRANSPORT_ERROR",
        f"Could not reach NDL Search: {type(exc).__name__}.",
        "Network or timeout failure; the query was not answered.",
    )


# ==============================================================================
# CQL
# ==============================================================================
#
# NDL's SRU rejects a query outright when a search term contains the bare tokens
# AND or OR (仕様書 3.2). That is a property of the corpus a historian will hit —
# English-language titles — so it is caught here and reported as a typed
# diagnostic rather than sent and returned as a parse failure.

_RESERVED = re.compile(r"(?:^|\s)(AND|OR|NOT)(?:\s|$)")

# Index name -> whether NDL matches it partially. Kept for the record; the server
# does not offer indexes outside this table.
CQL_INDEXES = {
    "title": "partial",
    "creator": "partial",
    "publisher": "partial",
    "subject": "partial",
    "description": "partial",
    "anywhere": "partial",
    "ndc": "prefix",
    "isbn": "exact",
    "issn": "exact",
    "jpno": "exact",
    "from": "exact",
    "until": "exact",
    "dpid": "exact",
}


def _cql_value(value: str) -> str:
    """Quote a CQL literal. NDL takes double quotes; escape any inside."""
    return '"' + value.replace('"', '\\"') + '"'


def reserved_word_hits(values: dict[str, Optional[str]]) -> list[str]:
    """Names of fields whose value carries a bare AND / OR / NOT."""
    return [
        name
        for name, value in values.items()
        if isinstance(value, str) and _RESERVED.search(value)
    ]


def build_cql(fields: dict[str, Optional[Any]], dpids: list[str]) -> str:
    """Assemble the CQL string actually sent.

    Several providers are expressed as REPEATED dpid clauses joined by AND, not
    as an OR group. That reads backwards and is what NDL accepts: repeating dpid
    unions the providers and deduplicates across them.

        anywhere="X" AND dpid="iss-ndl-opac" AND dpid="zassaku"   ->  54,182
        dpid="iss-ndl-opac" AND anywhere="X"                      ->  19,251
        dpid="zassaku"      AND anywhere="X"                      ->  34,931

    The obvious construction is rejected outright. Every parenthesised form was
    tried against the live API on 23 August 2026 and each returned SRU diagnostic
    info:srw/diagnostic/1/1, "illegal query syntax":

        (dpid="a" OR dpid="b") AND anywhere="X"
        anywhere="X" AND (dpid="a" OR dpid="b")
        dpid="a" OR dpid="b" AND anywhere="X"

    Until this was corrected, every tool that searches more than one provider —
    ndl_search_articles over the two periodical indexes, and ndl_search_all over
    all five — returned API_ERROR for every query ever put to it. The
    single-provider tools were unaffected, which is why it survived: the server
    looked as though it worked.
    """
    clauses: list[str] = []
    for name, value in fields.items():
        if value is None or value == "":
            continue
        clauses.append(f"{name}={_cql_value(str(value))}")
    clauses.extend(f"dpid={_cql_value(d)}" for d in dpids)
    return " AND ".join(clauses)


# ==============================================================================
# DC-NDL parsing
# ==============================================================================

NS = {
    "srw": "http://www.loc.gov/zing/srw/",
    "diag": "http://www.loc.gov/zing/srw/diagnostic/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "dcndl": "http://ndl.go.jp/dcndl/terms/",
    "foaf": "http://xmlns.com/foaf/0.1/",
}

_RDF_DATATYPE = f"{{{NS['rdf']}}}datatype"
_RDF_RESOURCE = f"{{{NS['rdf']}}}resource"

_YEAR_RE = re.compile(r"(1[0-9]{3}|20[0-9]{2})")


def _text(elem: Optional[ET.Element]) -> Optional[str]:
    if elem is None:
        return None
    txt = "".join(elem.itertext())
    txt = txt.strip()
    return txt or None


def _first(parent: ET.Element, path: str) -> Optional[str]:
    return _text(parent.find(path, NS))


def _identifier(res: ET.Element, name: str) -> Optional[str]:
    """dcterms:identifier carries its kind in rdf:datatype, not in the tag."""
    suffix = "/" + name
    for node in res.findall("dcterms:identifier", NS):
        datatype = node.attrib.get(_RDF_DATATYPE, "")
        if datatype.endswith(suffix):
            return _text(node)
    return None


def _creators(res: ET.Element) -> list[dict[str, Optional[str]]]:
    """Structured creators first; fall back to the flat dc:creator strings."""
    names = [
        _text(agent.find("foaf:name", NS))
        for agent in res.findall("dcterms:creator/foaf:Agent", NS)
    ]
    names = [n for n in names if n]
    if not names:
        names = [t for t in (_text(n) for n in res.findall("dc:creator", NS)) if t]
    return [{"ja": n, "en": None} for n in names]


def _year(res: ET.Element) -> Optional[int]:
    for path in ("dcterms:issued", "dcterms:date"):
        raw = _first(res, path)
        if raw:
            match = _YEAR_RE.search(raw)
            if match:
                return int(match.group(1))
    return None


def _permalink(res: ET.Element) -> Optional[str]:
    node = res.find("rdfs:seeAlso", NS)
    if node is not None:
        link = node.attrib.get(_RDF_RESOURCE)
        if link:
            return link
    about = res.attrib.get(f"{{{NS['rdf']}}}about")
    return about or None


def _record_type(res: ET.Element) -> str:
    material = (_first(res, "dcndl:materialType") or "").lower()
    if "雑誌" in material or "article" in material or "記事" in material:
        return "article"
    if "図書" in material or "book" in material:
        return "book"
    return "article" if _first(res, "dcndl:sourceTitle") else "book"


def _resource_to_item(res: ET.Element) -> dict[str, Any]:
    pages = _first(res, "dcterms:extent")
    return M.make_item(
        title_ja=_first(res, "dcterms:title") or _first(res, "dc:title"),
        title_en=None,
        title_romanized=_first(res, "dc:title/rdf:Description/dcndl:transcription"),
        authors=_creators(res),
        journal_ja=_first(res, "dcndl:sourceTitle") or _first(res, "dcndl:seriesTitle"),
        journal_en=None,
        volume=_first(res, "dcndl:volume"),
        issue=_first(res, "dcndl:number"),
        pages=pages,
        year=_year(res),
        doi=_identifier(res, "DOI"),
        crid=_identifier(res, "NDLBibID"),
        naid=_identifier(res, "JPNO"),
        url_ja=_permalink(res),
        url_en=None,
        matched_in="metadata",
        record_type=_record_type(res),
    )


def _parse_sru(xml_text: str) -> tuple[int, list[dict[str, Any]], Optional[dict]]:
    """Return (total, items, diagnostic-or-None) from one SRU response."""
    root = ET.fromstring(xml_text)

    node = root.find("srw:diagnostics/diag:diagnostic", NS)
    if node is None:
        node = root.find("srw:diagnostics", NS)
    if node is not None:
        message = _text(node) or "NDL Search returned a diagnostic without a message."
        # NDL reports an empty result set as a diagnostic ("Record does not exist"),
        # not as numberOfRecords=0. Reading that as a service error would tell a
        # reader the search failed when in fact it succeeded and found nothing —
        # the one confusion a search tool must not create. Pass it through as zero.
        if "record does not exist" in message.lower():
            return 0, [], None
        return 0, [], M.diag(
            "error", "API_ERROR", f"NDL Search diagnostic: {message}",
            "The query was rejected. Check index names and quoting.",
        )

    total = int(_first(root, "srw:numberOfRecords") or 0)
    # NDL emits more than one BibResource per record: the bibliographic one, and a
    # manifestation stub carrying an rdf:about and nothing else. Taking every
    # BibResource doubles the result set with blanks. Keep the ones with a title.
    items = []
    for res in root.findall(".//dcndl:BibResource", NS):
        if not (_first(res, "dcterms:title") or _first(res, "dc:title")):
            continue
        items.append(_resource_to_item(res))
    return total, items, None


# ==============================================================================
# Server + inputs
# ==============================================================================

# mcp 1.x's FastMCP takes no `version`; 2.x's MCPServer does. Passed where it is
# accepted, because a server that answers `initialize` with an empty version
# string cannot be cited by the disclosure that has to name the build it ran.
try:
    mcp = _MCPServer("ndl", version=__version__)
except TypeError:  # mcp SDK 1.x
    mcp = _MCPServer("ndl")


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, description="Title words (partial match).")
    creator: Optional[str] = Field(default=None, description="Author or editor (partial match).")
    publisher: Optional[str] = Field(default=None, description="Publisher (partial match).")
    subject: Optional[str] = Field(default=None, description="Subject heading (partial match).")
    anywhere: Optional[str] = Field(default=None, description="Free keyword across the simple-search fields.")
    ndc: Optional[str] = Field(default=None, description="NDC / NDLC classification (prefix match).")
    isbn: Optional[str] = Field(default=None, description="ISBN, 10 or 13 digit.")
    issn: Optional[str] = Field(default=None, description="ISSN.")
    from_year: Optional[str] = Field(default=None, description="Earliest publication date, YYYY or YYYY-MM or YYYY-MM-DD.")
    to_year: Optional[str] = Field(default=None, description="Latest publication date, same forms.")
    count: int = Field(default=20, ge=1, le=MAX_RECORDS, description=f"Records to return, 1-{MAX_RECORDS}.")
    start: int = Field(default=1, ge=1, description="First record position.")


class GetRecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ndl_bib_id: Optional[str] = Field(default=None, description="NDL bibliographic ID.")
    jpno: Optional[str] = Field(default=None, description="Japanese national bibliography number (全国書誌番号).")


def _fields(params: SearchInput) -> dict[str, Optional[str]]:
    return {
        "title": params.title,
        "creator": params.creator,
        "publisher": params.publisher,
        "subject": params.subject,
        "anywhere": params.anywhere,
        "ndc": params.ndc,
        "isbn": params.isbn,
        "issn": params.issn,
        "from": params.from_year,
        "until": params.to_year,
    }


def _input_terms(fields: dict[str, Optional[str]]) -> str:
    return " ".join(str(v) for v in fields.values() if v)


# ==============================================================================
# The one search path
# ==============================================================================


async def _search(operation: str, params: SearchInput, dpids: list[str]) -> str:
    fields = _fields(params)
    terms = _input_terms(fields)
    attribution = provider_credit(dpids)

    for dpid in dpids:
        if dpid not in PROVIDERS:
            env = M.build_envelope(
                server="ndl", operation=operation, input_terms=terms, normalized=terms,
                params={}, matching_mode=MATCHING_MODE, total=0, start=1, items=[],
                diagnostics=[M.diag(
                    "error", "DPID_NOT_PERMITTED",
                    f"Provider '{dpid}' is outside the set declared to the NDL and was not requested.",
                    "Declared providers: " + ", ".join(PROVIDERS) + ". "
                    "ndl_data_providers.json beside this file carries the full 一覧 "
                    "with each provider's application and licence conditions. Widening "
                    "the set means updating what this server says about itself, not "
                    "obtaining permission.",
                )],
                attribution=ATTRIBUTION, coverage_note=COVERAGE_NOTE,
            )
            return M.emit(env)

    if not terms:
        env = M.build_envelope(
            server="ndl", operation=operation, input_terms="", normalized="",
            params={}, matching_mode=MATCHING_MODE, total=0, start=1, items=[],
            diagnostics=[M.diag(
                "warning", "ZERO_CONJUNCTION",
                "No search term was given, and NDL Search will not accept a provider-only query.",
                "Supply at least one of title, creator, publisher, subject or anywhere.",
            )],
            attribution=attribution, coverage_note=COVERAGE_NOTE,
        )
        return M.emit(env)

    offending = reserved_word_hits(fields)
    if offending:
        env = M.build_envelope(
            server="ndl", operation=operation, input_terms=terms, normalized=terms,
            params={}, matching_mode=MATCHING_MODE, total=0, start=1, items=[],
            diagnostics=[M.diag(
                "error", "RESERVED_WORD_IN_QUERY",
                "NDL Search rejects a query whose terms contain a bare AND, OR or NOT; "
                f"found in: {', '.join(offending)}.",
                "Remove or replace the word; the query was not sent.",
            )],
            attribution=attribution, coverage_note=COVERAGE_NOTE,
        )
        return M.emit(env)

    cql = build_cql(fields, dpids)
    request = {
        "operation": "searchRetrieve",
        "version": "1.2",
        "query": cql,
        "recordSchema": "dcndl",
        "recordPacking": "xml",
        "maximumRecords": min(params.count, MAX_RECORDS),
        "startRecord": params.start,
        "onlyBib": "true",
    }

    try:
        total, items, diagnostic = _parse_sru(await _sru_request(request))
    except Exception as exc:  # noqa: BLE001
        total, items, diagnostic = 0, [], _error_diag(exc)

    diags: list[dict] = []
    if diagnostic:
        diags.append(diagnostic)
    else:
        if M.detect_script(terms) == "latin":
            diags.append(M.diag(
                "warning", "SCRIPT_LATIN_QUERY",
                "The term sent was in Latin script. NDL Search indexes Japanese-language "
                "records in Japanese script; a romanised term will under-return.",
                "Send the Japanese form of the term.",
            ))
        if total == 0:
            diags.append(M.diag(
                "warning", "ZERO_CONJUNCTION",
                "No record matched all of the fields given, which are combined with AND.",
                "Drop the narrowest field and search again before concluding the work is absent.",
            ))
        else:
            diags.append(M.diag("info", "OK", f"{total} record(s) on metadata match.", None))

    env = M.build_envelope(
        server="ndl", operation=operation, input_terms=terms, normalized=terms,
        params=request,
        matching_mode=MATCHING_MODE, total=total, start=params.start,
        items=items, diagnostics=diags,
        attribution=attribution, coverage_note=COVERAGE_NOTE,
    )
    return M.emit(env)


# ==============================================================================
# Tools
# ==============================================================================

_ANN = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


@mcp.tool(name="ndl_search_books", annotations={"title": "Search NDL holdings (books)", **_ANN})
async def ndl_search_books(params: SearchInput) -> str:
    """Search 国立国会図書館蔵書 for books and monographs.

    Fields are combined with AND; title, creator, publisher and subject match
    partially. Returns the unified response envelope. Records are displayed, not
    stored.
    """
    return await _search("search_books", params, BOOK_DPIDS)


@mcp.tool(name="ndl_search_national_bibliography", annotations={"title": "Search the Japanese National Bibliography", **_ANN})
async def ndl_search_national_bibliography(params: SearchInput) -> str:
    """Search 国立国会図書館全国書誌情報.

    The national bibliography is the authority for Japanese imprint data — use it
    when a publication date, publisher or edition statement has to be right rather
    than merely plausible.
    """
    return await _search("search_national_bibliography", params, BIBLIOGRAPHY_DPIDS)


@mcp.tool(name="ndl_search_articles", annotations={"title": "Search the NDL periodicals index", **_ANN})
async def ndl_search_articles(params: SearchInput) -> str:
    """Search 国立国会図書館雑誌記事索引, including the online-materials set.

    The index covers Japanese periodical articles, including many not in CiNii or
    J-STAGE. It indexes articles, not their full text.
    """
    return await _search("search_articles", params, ARTICLE_DPIDS)


@mcp.tool(name="ndl_search_digital_open", annotations={"title": "Search NDL Digital Collections (Open Data)", **_ANN})
async def ndl_search_digital_open(params: SearchInput) -> str:
    """Search 国立国会図書館デジタルコレクション（オープンデータ）.

    The open-data set only. The wider Digital Collections (ndl-dl, ndl-dl-online)
    are marked ○ for 非営利 use and so need no usage application, but they were
    outside the set this server declares and their metadata carries no open
    licence — displayable, not redistributable. Adding them is a documentation
    change here, not an application to the library.
    """
    return await _search("search_digital_open", params, DIGITAL_OPEN_DPIDS)


@mcp.tool(name="ndl_search_all", annotations={"title": "Search all declared NDL sets", **_ANN})
async def ndl_search_all(params: SearchInput) -> str:
    """Search all five declared provider sets at once.

    Use when the material type is unknown. For a bibliographic check, the narrower
    tools return a cleaner set.
    """
    return await _search("search_all", params, ALL_DPIDS)


@mcp.tool(name="ndl_get_record", annotations={"title": "Fetch one NDL record by identifier", **_ANN})
async def ndl_get_record(params: GetRecordInput) -> str:
    """Retrieve a single record by NDL bibliographic ID or 全国書誌番号 (JP number).

    A fetch, not a search: the envelope omits `searched_for` because no term was
    chosen. Exactly one identifier is required.
    """
    given = {"jpno": params.jpno, "ndl_bib_id": params.ndl_bib_id}
    supplied = {k: v for k, v in given.items() if v}
    attribution = provider_credit(ALL_DPIDS)

    if len(supplied) != 1:
        env = M.build_envelope(
            server="ndl", operation="get_record", input_terms="", normalized="",
            params={}, matching_mode=MATCHING_MODE, total=0, start=1, items=[],
            diagnostics=[M.diag(
                "error", "ZERO_CONJUNCTION",
                "Give exactly one identifier: jpno or ndl_bib_id.",
                None,
            )],
            attribution=attribution,
        )
        return M.emit(env)

    key, value = next(iter(supplied.items()))
    index = "jpno" if key == "jpno" else "anywhere"
    cql = f"{index}={_cql_value(value)}"
    request = {
        "operation": "searchRetrieve", "version": "1.2", "query": cql,
        "recordSchema": "dcndl", "recordPacking": "xml",
        "maximumRecords": 1, "startRecord": 1, "onlyBib": "true",
    }

    try:
        total, items, diagnostic = _parse_sru(await _sru_request(request))
    except Exception as exc:  # noqa: BLE001
        total, items, diagnostic = 0, [], _error_diag(exc)

    if diagnostic:
        diags = [diagnostic]
    elif items:
        diags = [M.diag("info", "OK", "Resolved to one record.", None)]
    else:
        diags = [M.diag(
            "warning", "ZERO_CONJUNCTION",
            f"No record matched {key}={value}.",
            "Check the identifier; NDL bibliographic IDs are matched as free text.",
        )]

    env = M.build_envelope(
        server="ndl", operation="get_record", input_terms=value, normalized=value,
        params=request,
        matching_mode=MATCHING_MODE, total=total, start=1,
        items=items[:1], diagnostics=diags, attribution=attribution,
    )
    return M.emit(env)


def main() -> None:
    """Console-script entry point (`ndl-mcp`)."""
    mcp.run()


if __name__ == "__main__":
    main()
