# Changelog

Versions are the thing to cite. A count produced under one release is not
reproducible against another, so the release actually used should be named in
the text and, where a version DOI exists, cited by it.

Releases earlier than those below are on the repository's releases page; this
file begins where the record is precise enough to be worth writing down.

## 1.0.1 — 2026-08-22

First tagged release.

- **Corrected the national-bibliography data provider ID.** The declared value
  `iss-ndl-opacnational` names no provider; the NDL spells it
  `iss-ndl-opac-national`. SRU matches an unrecognised `dpid` value against
  nothing and returns zero records with no diagnostic, so
  `ndl_search_national_bibliography` reported a well-formed, well-credited and
  entirely credible absence for every query put to it between 19 and 20 August
  2026. The same string appears in the notification filed with the library, so
  this is a correction to what was declared.
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
- `mediation.py` 2.3.0: the envelope reports whether it was deposited.
- httpx request-URL logging muted; a search term travels in that URL.
