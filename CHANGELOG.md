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
- **`install.ps1` rewritten for the package layout.** It installs the wheel into
  the shared venv and registers the console script, rather than copying three
  files into `mcp-servers\\ndl_mcp` and registering a path. The vendoring step
  is now a *verification* step: `mediation.py` and `ledger.py` are checked
  byte-for-byte against the installed `cinii_mcp` copies and the install stops
  if they differ, instead of silently overwriting this repository's copies with
  whatever is on the machine.
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
