"""ndl_get_record stays inside the declared providers and returns only the
record asked for (stress test, 12 October 2026; ruling of the same day).

- The query carried no dpid clause, so NDL searched every provider, including
  iss-ndl-opac-bib and ndl-article-online, which this server undertook not to
  query.
- ndl_bib_id was matched as free text and the first hit was returned as
  "Resolved to one record" whatever its identifier.
- An identifier such as "a and b" went upstream unvalidated.
"""
import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import ValidationError

from ndl_mcp import server as S

BOOK = (Path(__file__).parent / "fixtures" / "sru_book_jpno.xml").read_text(encoding="utf-8")


@pytest.fixture
def ndl(monkeypatch):
    sent = []

    def handler(req):
        sent.append(parse_qs(req.url.query.decode()))
        return httpx.Response(200, text=BOOK)
    orig = httpx.AsyncClient.__init__

    def init(self, *a, **k):
        k["transport"] = httpx.MockTransport(handler)
        orig(self, *a, **k)
    monkeypatch.setattr(httpx.AsyncClient, "__init__", init)
    monkeypatch.setattr(S, "MIN_REQUEST_INTERVAL", 0)
    monkeypatch.setattr(S, "_last_request_at", 0.0)
    return sent


def _run(**kw):
    return json.loads(asyncio.run(S.ndl_get_record(S.GetRecordInput(**kw))))


@pytest.mark.parametrize("kw", [{"jpno": "71009951"}, {"ndl_bib_id": "000001185032"}])
def test_query_is_scoped_to_the_declared_providers(ndl, kw):
    _run(**kw)
    assert len(ndl) == 1
    cql = ndl[0]["query"][0]
    dpids = {c.split("=", 1)[1].strip('"') for c in cql.split(" AND ") if c.startswith("dpid=")}
    assert dpids == set(S.ALL_DPIDS)


@pytest.mark.parametrize("kw", [{"jpno": "71009951"}, {"ndl_bib_id": "000001185032"}])
def test_the_matching_record_is_returned(ndl, kw):
    env = _run(**kw)
    assert env["result"]["returned"] == 1 and env["diagnostics"][0]["code"] == "OK"


@pytest.mark.parametrize("kw,other", [({"jpno": "99999999"}, "71009951"),
                                      ({"ndl_bib_id": "999999999"}, "000001185032")])
def test_a_different_record_is_not_returned_as_the_one_asked_for(ndl, kw, other):
    env = _run(**kw)
    assert env["result"]["returned"] == 0 and env["result"]["total"] == 0
    d = env["diagnostics"][0]
    assert d["code"] == "ZERO_CONJUNCTION" and other in d["message"]


@pytest.mark.parametrize("kw", [{"ndl_bib_id": "a and b"}, {"jpno": '7" or dpid="ndl-article-online'},
                                {"jpno": "1" * 40}])
def test_an_identifier_that_is_not_one_is_refused(kw):
    with pytest.raises(ValidationError):
        S.GetRecordInput(**kw)


def test_an_empty_second_identifier_counts_as_absent(ndl):
    env = json.loads(asyncio.run(S.ndl_get_record(S.GetRecordInput(jpno="71009951", ndl_bib_id=" "))))
    assert env["result"]["returned"] == 1
