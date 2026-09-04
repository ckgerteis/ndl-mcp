# Changelog

Versions are the thing to cite. A count produced under one release is not
reproducible against another, so the release actually used should be named in
the text and, where a version DOI exists, cited by it.

Releases earlier than those below are on the repository's releases page; this
file begins where the record is precise enough to be worth writing down.

## 1.1.0 — 2026-08-23

**Not released.** No tag was cut and no Zenodo record exists for this version, so
it is citable by commit alone. Tagging waits on confirmation that this
repository's Zenodo webhook is live: a release that mints nothing spends a
version number and returns nothing citable for it.

### Since 2026-09-04, still under 1.1.0 (unreleased)

- **Released on GitHub as a package.** `.github/workflows/release.yml` runs
  on a `vX.Y.Z` tag: tests on three OSes, wheel and sdist, one Claude
  Desktop `.mcpb` bundle per platform, then a GitHub release carrying all of
  them. Installable pinned to the tag with `pip install
  "git+https://github.com/ckgerteis/ndl-mcp@vX.Y.Z"` or `uvx --from`
  the same URL. The release is what fires the Zenodo webhook. Nothing is
  published to a package index.
- **Suite install.** `install.py` is the cross-platform port of `install.ps1`
  (Windows, macOS, Linux; same behaviour, importable). The family is also
  installable as one package, `bibliograph-mcp`, whose `bibliograph install`
  registers all six with one receipts folder.
- **A malformed answer is `API_ERROR`, not `TRANSPORT_ERROR`.** `_error_diag`
  labelled every exception that was neither an HTTP status nor an XML parse
  failure as a transport failure — including a `numberOfRecords` that would
  not parse as an integer, raised after NDL had answered. The reader was told
  the service was unreachable when it had in fact replied. Only `httpx`
  transport exceptions are `TRANSPORT_ERROR` now; anything else raised after
  a response is `API_ERROR` with the exception type named.
- `tests/smoke_stdio.py`: stdio handshake, `tools/list` checked against the
  README table, optional live call. Vendored byte-identical across the six.
- `response-schema.json`'s self-description said 2.2.0 and named four
  servers; it now says 2.3.0 and names six. Text only; the schema is unchanged.
- Module docstring banner corrected from v1.0.1 to v1.1.0.

- **A receipts folder, and one chain per server.** `ledger.py` 1.1.0 adds
  `MCP_RECEIPT_DIR`: point it at a directory and each server writes its own
  `<server>.jsonl` inside it. `MCP_RECEIPT_LOG` still names a single file and is
  honoured when `MCP_RECEIPT_DIR` is unset, so nothing existing breaks.
- **Why, precisely.** Appending is read-the-last-hash-then-write and `_LOCK` is a
  `threading.Lock`, which holds within one process and not between several. Six
  servers are six processes. Six of them writing 150 lines to one file produced
  **fourteen forks** — two lines claiming the same predecessor, over and over.
  That was measured, not inferred, and it means the family's shared log was never
  safe to verify as one chain. One writer per file removes the race rather than
  mitigating it.
- **`verify_chain()` now types its failures.** It reported everything as
  `prev_hash mismatch`. It distinguishes a **fork** (concurrent writers; every
  line still present, and the file is several chains rather than one), a
  **missing** line, a **reordering**, and **tamper** (a line that does not hash to
  its own content). Only the last is a claim about honesty, and a reader given one
  label for all four cannot tell a misconfiguration from interference.
- **`verify_dir()` and a manifest.** One pass over a receipts folder returns
  per-file verdicts, line counts, first and last timestamps and terminal hashes,
  plus combined totals by server, script and session. `<dist>-ledger manifest
  <dir>` writes it to `manifest.json`. That file is what a disclosure cites: one
  description of the deposit rather than six assertions to reconcile.
- `<dist>-ledger` gains `verify-dir` and `manifest`, and `verify` now exits
  non-zero when a chain does not verify.
- **`install.ps1` installs this server by default, not the family.** These are
  six independent packages — none imports another, none depends on another, and
  each installs alone. The installer defaulted to all six, so cloning one
  repository and running it would have registered five servers nobody asked for
  and fetched them from GitHub. It now resolves the default from the repository
  it sits in; `-All` opts into the family and `-Servers` names a subset.
- The verification step now **asserts that `ledger.py` and `mediation.py` are
  byte-identical across everything it installed** and stops if they are not.
  Nothing else enforces that invariant at install time, and two envelope
  versions in one environment is precisely the sort of thing that would be found
  later, in a deposit.
- **`install.ps1` installs the family.** Vendored byte-identical into all six
  repositories: it installs any or all of the six into one environment, asks once
  for the receipts folder and the session slug, and registers every server against
  the same pair. It prefers a sibling checkout to the network, carries across
  credentials already registered rather than asking again, and stops rather than
  guessing where the registered servers disagree about either value.
- **`src/` layout. Breaking: the server is started by console script, not by
  path.** `server.py`, `mediation.py` and `ledger.py` move to `src/ndl_mcp/` and install as a
  package. The flat layout installed them as *top-level* modules, so any two
  servers of this family in one environment overwrote each other — and
  `pip check` reported nothing wrong. The later install simply won, silently,
  and the survivor answered under the wrong server's name. All six now coexist:
  verified by installing every wheel into one environment and driving each
  through `initialize` and `tools/list`.
- **Claude Desktop entries must change.** Replace
  `"command": "…\\python.exe", "args": ["…\\server.py"]` with
  `"command": "…\\Scripts\\ndl-mcp.exe"`. An existing entry keeps working
  against an existing flat deployment and will fail against this one.
- `python -m ndl_mcp` and a `ndl-mcp-ledger` console script are installed
  alongside it.
- **The server reports its build.** `initialize` was answered with an empty
  `serverInfo.version`. It now carries `__version__` where the SDK accepts one
  (mcp 2.x `MCPServer`). Under mcp 1.x, whose `FastMCP` takes no `version`, the
  field still reports the SDK's version rather than the server's — the argument
  is passed only where it is accepted.
- **Two of the six tools had never worked.** `build_cql` expressed several
  providers as `(dpid="a" OR dpid="b") AND field="x"`. NDL rejects that outright
  — SRU diagnostic `info:srw/diagnostic/1/1`, "illegal query syntax" — so
  `ndl_search_articles`, which spans the two periodical indexes, and
  `ndl_search_all`, which spans all five providers, returned `API_ERROR` for
  every query ever put to them. The four single-provider paths were unaffected,
  which is exactly why it survived: the server looked as though it worked.
  Found by running the tools against the live API on 23 August 2026.
- **"Record does not exist" is NDL's way of saying zero, not a fault**, and the
  passthrough that treats it so is now verified rather than merely read. Every
  provider answers that way for a term with no hits. The server reports
  `total: 0` with `ZERO_CONJUNCTION`, not `API_ERROR` — which is the distinction
  the envelope exists to preserve. `ndl_get_record` verified against a live
  identifier at the same time. Only the backoff path remains unexercised.
- **NDL's idiom is a repeated `dpid`, joined by AND, and it means union.** It
  reads backwards and it is what the interface accepts. Verified against the
  live API: `anywhere="労働運動" AND dpid="iss-ndl-opac"` returns 19,251,
  `dpid="zassaku"` alone returns 34,931, and the two together return 54,182 —
  the sum, so a union rather than an intersection, deduplicated where a record
  sits in more than one provider. `ndl_search_articles` now answers 34,931 for
  that term and `ndl_search_all` 82,644 for `title="戦後"`, where both
  previously answered nothing at all.
- **`install.ps1` is now the family installer** described above, replacing the
  NDL-only script. The NDL notification step survives inside it and runs whenever
  `ndl` is among the servers being installed. The old vendoring step, which
  copied `mediation.py` and `ledger.py` over this repository's copies from
  whatever was on the machine, is gone: each package now carries its own and the
  installer asserts they match across everything it installed rather than
  overwriting anything.
- **The installer no longer carries a receipt path of its own.** Until now it
  defaulted `MCP_RECEIPT_LOG` to a path inside the author's Dropbox folder —
  correct for one machine, wrong for every other, and a private folder layout
  published in a public repository. It also set `MCP_RECEIPT_SESSION` to
  `ndl-mcp`, where the rest of the family uses a project slug; the slug groups a
  project's queries, so NDL was filing itself out of the group it belongs to.
  Both are now asked for once and applied to every server installed.
- **README gained the install and Claude Desktop sections it never had.** The
  file documented the undertakings, the providers and the rate limit in detail
  and never said how to install the thing.
- **The installer no longer carries a receipt-log path of its own.** Until now
  it defaulted `MCP_RECEIPT_LOG` to a path inside the author's Dropbox folder —
  correct for one machine, wrong for every other, and a private folder layout
  published in a public repository. It now reads `MCP_RECEIPT_LOG` and
  `MCP_RECEIPT_SESSION` from the servers already registered in
  `claude_desktop_config.json`, which is the only way to be sure of joining the
  chain in use rather than a compiled-in guess at it. `MCP_RECEIPT_SESSION` was
  also being set to `ndl-mcp`, where the rest of the family uses a project slug;
  the slug is what groups a project's queries in the deposit, so NDL was
  labelling itself out of the group it belongs to.
- Order of preference: `-ReceiptLog` / `-ReceiptSession`, then the value the
  registered servers share, then whatever a previous run registered for `ndl`,
  then nothing. Disagreement between registered servers stops the install rather
  than resolving to one of them. Nothing found anywhere leaves the variables
  unset and says so, which matches the documented default: the ledger is off
  unless `MCP_RECEIPT_LOG` is set. All five paths were exercised against
  synthetic configurations.

## 1.0.1 — 2026-08-22

**Never tagged.** This version was merged to `main` and no release was cut for
it; it has no tag and no DOI.

- **Corrected the national-bibliography data provider ID.** The declared value
  `iss-ndl-opacnational` names no provider; the NDL spells it
  `iss-ndl-opac-national`. SRU matches an unrecognised `dpid` value against
  nothing and returns zero records with no diagnostic, so
  `ndl_search_national_bibliography` reported a well-formed, well-credited and
  entirely credible absence for every query put to it between 19 and 20 August
  2026. The same string appears in the 2026 registration; the set intended was
  always the national bibliography, as named, and only the identifier was wrong.
- **Licence.** Credit lines said CC BY 4.0. The grant is 公共データ利用規約
  （第1.0版）(PDL1.0), which the NDL states to be *compatible with* CC BY 4.0.
  Credit lines and README now say so.
- Docstring, `COVERAGE_NOTE` and README said four declared providers; the
  notification declared five, `ndl-dl-open` included.
- `ndl_search_digital_open` no longer claims `ndl-dl` and `ndl-dl-online`
  require a usage application. They are ○ for 非営利; they are out of scope
  because they were not notified and carry no open licence.
- `install.ps1` pointed `MCP_RECEIPT_LOG` at its own file rather than the shared
  log. A hash chain is per-file, so that would have created a second,
  independent chain. Now defaults to the shared log, with `-ReceiptLog` to
  override.
- **Registration with the NDL is now recommended rather than enforced.** The
  library confirmed in August 2026 that notification of continuous use is no
  longer required, though still welcome. `install.ps1` previously refused to
  register the server without a filing date; it now prints the form, offers to
  open it, records the date when given, and continues either way. The README
  makes the case for registering anyway: a national library that can see
  researchers using its API has an argument for keeping it open.
- `mediation.py` 2.3.0: the envelope reports whether it was deposited.
- httpx request-URL logging muted; a search term travels in that URL.
