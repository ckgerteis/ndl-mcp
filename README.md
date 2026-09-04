# ndl-mcp

An MCP server for searching 国立国会図書館サーチ (NDL Search), operated by the National Diet Library of Japan, over the SRU `searchRetrieve` interface.

Third in a series with [`cinii-mcp`](https://github.com/ckgerteis/cinii-mcp) and [`jstage-mcp`](https://github.com/ckgerteis/jstage-mcp), and sharing their response envelope: typed query and script, matching mode, graduated breadth, per-item `matched_in`, typed diagnostics, a loggable receipt, attribution.

## What this is for

The National Diet Library receives everything published in Japan, and this reaches five of its own catalogues: general holdings, the Japanese National Bibliography, the periodicals index, that index's online-materials companion, and the open-data digital collections.

Use the national bibliography when an imprint fact has to be right — a date, a publisher, an edition statement — because it is the authority other catalogues copy from. The periodicals index reaches article-level records for Japanese magazines and journals going back well beyond what CiNii or J-STAGE hold, which is where prewar and early postwar material becomes searchable. Single records resolve by JP number or NDL bibliographic ID.

Requests are issued one at a time, at a measured pace, under the undertakings filed with the library.

## Before you run this

**There is no credential.** The NDL search APIs are open. No API key, no application ID, no token, nothing to paste into a config file. If you are waiting for something to arrive before you can use this, you are waiting for something that is not coming.

**Registering is recommended.** The author filed a notification of continuous use on 19 August 2026 through the [form](https://form2.ndl.go.jp/form/pub/ndl07/api) described in [APIのご利用について](https://ndlsearch.ndl.go.jp/help/api). The library replied that registration is **no longer required, though still welcome**. A formal 利用申請 remains necessary only for revenue-generating use.

Register anyway. It costs a few minutes, it tells the library who is using the interface and for what, and a national library that can see its API being used by researchers has an argument for keeping it funded and open that it does not otherwise have. Scholarly infrastructure survives on evidence of use.

`install.ps1` records the date to `NDL-API-NOTIFICATION.txt` when you pass it:

```powershell
.\install.ps1 -NotificationFiled 2026-08-19
```

Run it without the flag and it prints the form URL, offers to open it, and continues with the install.

## Install

Three routes. All three give you the same server; pick by how much you want to see of it.

### One click: the Claude Desktop bundle

Download the `.mcpb` for your platform from the [latest release](https://github.com/ckgerteis/ndl-mcp/releases/latest) and open it; Claude Desktop installs it. Claude Desktop asks only for a receipts folder at install time. The bundle carries every library it needs, but not Python itself: a Python 3.10+ interpreter must be on the machine (`python` on Windows, `python3` on macOS and Linux).

### From GitHub, pinned to a release

```bash
pip install "git+https://github.com/ckgerteis/ndl-mcp@v1.1.0"
# or, without an environment of your own:
uvx --from "git+https://github.com/ckgerteis/ndl-mcp@v1.1.0" ndl-mcp
```

installs the `ndl-mcp` console script and `ndl-mcp-ledger`. The tag is the thing to cite; `@main` gets whatever is current. Then register it in Claude Desktop (below), or let `install.py` do that.

### The whole family

```bash
pip install "git+https://github.com/ckgerteis/bibliograph-mcp@v1.0.0" && bibliograph install
```

installs all six servers and registers them together — one receipts folder, credentials asked for once. See [bibliograph-mcp](https://github.com/ckgerteis/bibliograph-mcp). From a checkout of this repository, `python install.py` does the same for this server alone, `python install.py --all` for the six, on Windows, macOS and Linux; `install.ps1` remains for Windows.

### From source

```bash
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/python -c "import ndl_mcp; print(ndl_mcp.__version__)"
```

That import fails loudly if the package or one of its vendored modules is
missing. Do not use `ndl-mcp --help` as the check: unknown arguments are
ignored, the server starts, reads end-of-input and exits 0, so it reports
success whatever the state of the code.

### Installing more than this one

Six independent packages. None imports another, none depends on another, and
each installs and answers on its own — `pip install .` in this directory is a
complete install of this server and nothing else.

They do share three things: a response envelope, a query ledger, and — if you
run more than one — a receipts folder. `install.ps1` is vendored byte-identical
into all six and handles that on Windows; `install.py` is its cross-platform port. **Both install this server by default**, because
cloning one repository is not a request for five more.

```powershell
.\install.ps1                        # this server
.\install.ps1 -All                   # all six
.\install.ps1 -Servers ndl,cinii           # a chosen subset
```

Whatever subset you name is registered against one receipts folder, asked for
once. The script prefers a sibling checkout to the network, carries across
credentials already registered rather than asking again, leaves servers it was
not asked about alone, and stops rather than guessing where the servers already
registered disagree about the folder or the session slug. It also asserts that
`ledger.py` and `mediation.py` are byte-identical across everything it
installed, so two envelope versions cannot end up in one environment unnoticed.

### Claude Desktop

`install.ps1` writes this entry for you. By hand, add it to
`%APPDATA%\Claude\claude_desktop_config.json` under `mcpServers`, pointing at
the console script in the environment you installed into. On macOS or Linux use
the absolute path to `.venv/bin/ndl-mcp`. There is no credential to supply.

```json
{
  "mcpServers": {
    "ndl": {
      "command": "C:\\path\\to\\.venv\\Scripts\\ndl-mcp.exe",
      "env": {
        "MCP_RECEIPT_DIR": "C:\\path\\to\\receipts",
        "MCP_RECEIPT_SESSION": "project-or-article-slug"
      }
    }
  }
}
```

**Changed in 1.1.0.** Earlier versions were registered by path —
`"command": "…\\python.exe", "args": ["…\\server.py"]`. That entry will not
start this version, because `server.py` is now a module inside a package rather
than a script beside its imports. Replace it with the console script above.

Restart Claude Desktop. The six tools should appear under "ndl" in the tool
list.

## What the server will not do

The undertakings below were filed with the NDL. They are implemented, not aspired to, and the installer's smoke test asserts the first three:

| Undertaking | Implementation |
|---|---|
| Requests issued serially; no concurrent access | `_rate_lock` is held across the wait *and* the request |
| Minimum one-second interval | `MIN_REQUEST_INTERVAL = 1.0` |
| A cap on records per search; no bulk retrieval | `MAX_RECORDS = 100`, a fifth of the NDL's own 500; no auto-pagination |
| The harvesting interface is not used | OAI-PMH is not implemented |
| Credit on every response | `ATTRIBUTION` plus `provider_credit()` on every envelope |
| Metadata displayed, not accumulated | no cache, no local store |

Change any of them and you change what this server declares about itself. Update this table, the module comment in `src/ndl_mcp/server.py`, and `NDL-API-NOTIFICATION.txt` in the same commit, so the description a reader checks stays true to what the code does.

## Providers

Only the five sets declared in the notification of 19 August 2026 are reachable. All are NDL-created, all are marked ○ in both the 非営利 and 営利 columns of the provider list, and none requires a usage application. Their metadata is governed by 公共データ利用規約（第1.0版）(PDL1.0), which the NDL states to be compatible with CC BY 4.0 — PDL1.0 is the licence, CC BY 4.0 the compatibility claim:

| dpid | 名称 |
|---|---|
| `iss-ndl-opac` | 国立国会図書館蔵書 |
| `iss-ndl-opac-national` | 国立国会図書館全国書誌情報 |
| `zassaku` | 国立国会図書館雑誌記事索引 |
| `zassaku-online` | 国立国会図書館雑誌記事索引オンライン資料編 |
| `ndl-dl-open` | 国立国会図書館デジタルコレクション（オープンデータ） |

`ndl-dl` and `ndl-dl-online` — the wider Digital Collections — are marked ○ for 非営利 and △ only for 営利 on the [provider list](https://ndlsearch.ndl.go.jp/help/api/provider), so scholarly use needs no usage application. They are out of scope here because they sit outside the set this server declares, and because their metadata carries no open licence — displayable, not redistributable. Adding them is a documentation change in this repository, not an application to the library. A request naming them is refused in process, with a `DPID_NOT_PERMITTED` diagnostic, rather than sent.

## Tools

| Tool | Set searched |
|---|---|
| `ndl_search_books` | 蔵書 |
| `ndl_search_national_bibliography` | 全国書誌情報 |
| `ndl_search_articles` | 雑誌記事索引 (both sets) |
| `ndl_search_digital_open` | デジタルコレクション（オープンデータ） |
| `ndl_search_all` | all five |
| `ndl_get_record` | one record by `jpno` or `ndl_bib_id` |

Search fields: `title`, `creator`, `publisher`, `subject`, `anywhere`, `ndc`, `isbn`, `issn`, `from_year`, `to_year`. They are combined with **AND**; title, creator, publisher and subject match partially, `ndc` by prefix, identifiers exactly.

`ndl_get_record` is a fetch, so its envelope omits `searched_for` — no term was chosen.

## Two things that will bite

**A bare `and` or `or` between words makes NDL reject the whole query, in any case.** Not "returns nothing" — rejects. `NOT` is not reserved and is left alone.

This was measured against the live API on 27 August 2026, because the rule stated here until then was wrong in both directions. It claimed the check was case-sensitive and that `War and Peace` passes. It does not: `anywhere="War and Peace"` is refused where `anywhere="War Peace"` returns 5,025. What "passed" was the guard, not the library — and the query then came back as `API_ERROR` with a total of zero, which reads exactly like an absence. The same sentence also treated `NOT` as reserved, so the server declined in process a query NDL answers: `anywhere="cats NOT dogs"` returns 96 records.

Position matters, and the check follows what the API does rather than what would be tidy: `anywhere="and Peace"` is tolerated (14,375), `anywhere="Peace and"` is refused, `anywhere="cats and dogs"` is refused. So whitespace is required before the word, and whitespace or the end of the term after it. A word that merely contains the letters is untouched — Thailand, Andorra and notation all return records.

The server checks before sending and returns a `RESERVED_WORD_IN_QUERY` diagnostic naming the offending field, rather than letting the library answer with a parse failure. The remedy is usually to drop the conjunction: `"Civil Information and Education Section"` is refused, `"Civil Information Education Section"` returns 21,690.

**NDL enforces a rate limit it will not quantify, and answers HTTP 429.** The help page says only 「同時リクエスト数には制限を設けています」 and declines to publish a figure. In testing on 19 August 2026 a 429 arrived at well under one sustained request per second — so the one-second floor filed with the library is a minimum, not a guarantee. A 429 buys one backoff, honouring `Retry-After`, and then the server stops rather than pressing. It reports `RATE_LIMITED`, deliberately distinct from `API_ERROR`, because the two mean different things to a reader: a rate-limited search has an *unknown* result, not an empty one, and must never be written up as an absence.

**A romanised term will under-return.** NDL Search indexes Japanese-language records in Japanese script. A Latin-script query against a Japanese corpus is the romaji trap, and the envelope raises `SCRIPT_LATIN_QUERY` for it. The `searched_for` headline exists so that the term the assistant actually chose is visible at the top of the response rather than buried — that is the whole point of the field, and the reason a disclosure can report the terms a search used.

## Response format

Every tool returns the response envelope built by `mediation.py` and defined in [`response-schema.json`](response-schema.json), schema version 2.3.0. The module and the schema are vendored byte-identically across `cinii-mcp`, `jstage-mcp`, `korea-scholarship-mcp` and this server, so an envelope from one can be read by a consumer written for another.

Search operations carry `searched_for` — the term actually sent, its detected script, and the matching mode — hoisted to the top of the envelope so a relaying client cannot drop it. `ndl_get_record` omits it: a fetch is handed an identifier and chooses no term.

## Receipts

`mediation.emit()` writes each response envelope to an append-only, hash-chained ledger. Unset the receipt variables and nothing is written and nothing fails — which is exactly what happened here between 19 and 22 August 2026: the code called `emit()` at every exit while no variable was set in this server's environment, so three days of queries went unrecorded behind well-formed envelopes. Since schema 2.3.0 the envelope reports it: `RECEIPT_NOT_DEPOSITED` when nothing is configured, `RECEIPT_WRITE_FAILED` when it is and the write did not land.

**`MCP_RECEIPT_DIR` names a folder, and this server writes `ndl.jsonl` inside it.** One file per server, because appending is read-the-last-hash-then-write and the lock around it does not hold between processes: six servers pointed at one file will fork the chain when two answer at once. Measured — six processes, 150 lines, fourteen forks. `MCP_RECEIPT_LOG` still names a single file and is honoured when `MCP_RECEIPT_DIR` is unset.

`install.ps1` holds no path of its own. It asks for the folder, offering whatever the already-registered servers use and otherwise `%APPDATA%\Claude\mcp-receipts`, and registers every server it installs against the same one. `MCP_RECEIPT_SESSION` — the project slug that groups a project's queries — is taken from the registered servers or asked for, never invented per server. Where the registered servers disagree about either, the install stops and asks rather than putting NDL in one of two records. (Earlier revisions of this README said the installer defaulted to `%APPDATA%\Claude\mcp-receipts.jsonl`. It did not; the statement described an installer that no longer existed. What it did default to, until 1.1.0, was a path inside the author's own Dropbox folder, written into a public repository.)

Verify with `ndl-mcp-ledger verify-dir <folder>`, or write the citable manifest with `ndl-mcp-ledger manifest <folder>`. A failure is typed: a **fork** means concurrent writers and every line is still present; **tamper** means a line no longer hashes to its own content. The two are not the same finding and are no longer reported as though they were.

Note what the ledger holds and what it does not: the query, the normalised term, the parameters sent, the timestamp, a SHA-256 over query and parameters, and the identifiers of the records returned. It does not hold the bibliographic records themselves. Logging a query is not accumulating a database, and the undertaking against accumulation is not breached by keeping the receipt — but the distinction is worth stating rather than assuming, because the two look similar from outside.

## Why SRU only

The application declares SRU and OpenSearch. This server implements SRU alone, which is less than was declared and therefore safe — you may always use less than you told the library you would.

The reason is evidential. The OpenSearch response format is not documented in the 第1.4版 specification: no element table, no sample, and the appendices cover SRU and OAI-PMH only. Worse, the spec states that a malformed parameter returns a *zero-result* response rather than an error — 「引数（パラメータ）誤りの場合には検索結果ゼロ件となる」 — so a typo in a field name is indistinguishable from a genuine absence. For a tool whose purpose is to let a historian trust that nothing was found, that is disqualifying. SRU returns typed diagnostics and a documented DC-NDL record schema. Adding OpenSearch later needs no new notification; it needs a documented response format.

## Sources

- [国立国会図書館サーチ 外部提供インタフェース仕様書 第1.4版](https://ndlsearch.ndl.go.jp/file/help/api/specifications/ndlsearch_api_20260331.pdf) (2026-03-31)
- [APIのご利用について](https://ndlsearch.ndl.go.jp/help/api) — terms, credit requirement, concurrency, notification
- [API提供対象データプロバイダ一覧](https://ndlsearch.ndl.go.jp/help/api/provider) — dpid values and licence conditions

## Licence

MIT, for the server code. Metadata retrieved through this server is governed by 公共データ利用規約（第1.0版）(PDL1.0), read with 「国以外の者」 as 「国立国会図書館以外の者」; the NDL states that condition to be compatible with CC BY 4.0, which is a compatibility claim rather than a grant of CC BY 4.0 itself. The credit line the server emits is the attribution PDL1.0 requires, and it should survive into anything you publish from the results.

## What has been tested, and what has not

Verified against the live API on 19 August 2026:

- Japanese-script search across 蔵書 and 雑誌記事索引 — correct totals, correct records, correct years and identifiers.
- DC-NDL parsing, including the manifestation-stub filter. NDL returns two `BibResource` elements per record; taking both doubled the result set with blanks until the filter went in.
- `searched_for` reports the term chosen, not the assembled CQL, so its script detection is meaningful; the exact CQL is carried in `query.params` and is fixed by the receipt hash.
- The `DPID_NOT_PERMITTED` guard: a request naming `ndl-dl` is refused in process.
- `RESERVED_WORD_IN_QUERY`, as it then stood: `War AND Peace` caught, `War and Peace` passed **the guard**. What the library did with it afterwards was not checked, and the entry should not have been written as though it had been — see 27 August below.
- The rate limiter, involuntarily — see HTTP 429 above.

Verified against the live API on 23 August 2026, closing two rows that had been read rather than run:

- **The "Record does not exist" passthrough.** That string is not a fault. It is how NDL answers a search that matched nothing, and it answers that way for every provider — `zassaku`, `zassaku-online`, `iss-ndl-opac` and `ndl-dl-open` all return it for a term with no hits. The server maps it to `total: 0` with a `ZERO_CONJUNCTION` diagnostic rather than to `API_ERROR`, which is the distinction the whole envelope exists to preserve: a search that found nothing is not a search that failed.
- **`ndl_get_record`.** `jpno=71009951`, taken from a national-bibliography result, resolves to one record with an `OK` diagnostic.
- **The reserved-word rule, corrected.** `and` and `or` are refused by NDL in any case; `NOT` is not reserved at all. Measured across seventeen cases: `cats and dogs`, `cats AND dogs`, `cats And dogs`, `cats or dogs` and `cats OR dogs` all refused; `cats not dogs`, `cats NOT dogs`, `war not peace` and `title="not for sale"` all answered; `Thailand`, `Andorra` and `notation` unaffected. The guard now matches that behaviour exactly, having previously both missed every lowercase conjunction and refused a word the library accepts.
- **Multi-provider search**, after the CQL correction — `ndl_search_articles` returns 23,766 for `title="労働運動"`, matching `dpid="zassaku"` alone, because `zassaku-online` holds nothing under that title. The union total is a count, not a floor.

**Still not verified, and read rather than run:** the backoff path. Testing stopped at the 429 rather than continuing, because characterising an undisclosed rate limit by probing it is precisely the 継続して大量のアクセス the terms warn about, and the point of this server is not to be the thing the National Diet Library has to block. It will be exercised in ordinary use, a query at a time.

Verified on 4 September 2026 with `tests/smoke_stdio.py`, which starts the installed console script over stdio, performs the MCP handshake, checks `tools/list` against the tool table above, and with `RUN_LIVE=1 … <tool> '<json params>'` makes one live call: `ndl_search_books` for 軍艦島 answered 524 records with an `OK` diagnostic.
