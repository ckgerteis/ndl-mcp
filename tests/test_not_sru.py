"""A 200 that is not an SRU response is an outage, not an empty result.

Stress test, 12 October 2026: an HTML maintenance page, a bare <error>, or an
empty <response/> served with status 200 parsed as well-formed XML and came
back as ZERO_CONJUNCTION, "No record matched", which tells a reader the index
holds nothing when the search was never answered.
"""
from pathlib import Path

import pytest

from ndl_mcp.server import _parse_sru

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("body", [
    "<html><body><h1>503 Service Unavailable</h1></body></html>",
    "<error>rate limited</error>",
    "<response/>",
    '<searchRetrieveResponse xmlns="http://example.org/not-srw"><numberOfRecords>3'
    "</numberOfRecords></searchRetrieveResponse>",
    # the right root, but without the count SRU requires
    '<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/"><version>1.2</version>'
    "</searchRetrieveResponse>",
])
def test_non_sru_body_is_an_error_not_zero(body):
    total, items, diag = _parse_sru(body)
    assert diag is not None and diag["level"] == "error" and diag["code"] == "API_ERROR"
    assert (total, items) == (0, [])


@pytest.mark.parametrize("name", ["sru_book_jpno.xml", "sru_article_zassaku.xml"])
def test_real_responses_still_parse(name):
    total, items, diag = _parse_sru((FIXTURES / name).read_text(encoding="utf-8"))
    assert diag is None and total >= 1 and items


def test_record_does_not_exist_is_still_zero():
    body = ('<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">'
            "<version>1.2</version><numberOfRecords>0</numberOfRecords>"
            '<diagnostics><diagnostic xmlns="http://www.loc.gov/zing/srw/diagnostic/">'
            "<message>Record does not exist</message></diagnostic></diagnostics>"
            "</searchRetrieveResponse>")
    assert _parse_sru(body) == (0, [], None)
