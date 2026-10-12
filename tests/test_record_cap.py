"""No more records are shown than were asked for, and never more than 100
(stress test, 12 October 2026; NDL undertaking: at most 100 records per
search).

maximumRecords was capped on the request, but the records in the response were
displayed as they came: a 200 carrying 500 records came back with 500 items.
"""
import asyncio
import json
import re
from pathlib import Path

import httpx
import pytest

from ndl_mcp import server as S

BOOK = (Path(__file__).parent / "fixtures" / "sru_book_jpno.xml").read_text(encoding="utf-8")


def _many(n):
    rec = re.search(r"    <record>.*?</record>\n", BOOK, re.S).group(0)
    body = BOOK.replace(rec, rec * n)
    return body.replace("<numberOfRecords>1</numberOfRecords>", f"<numberOfRecords>{n}</numberOfRecords>")


@pytest.fixture
def ndl(monkeypatch):
    box = {"body": ""}
    orig = httpx.AsyncClient.__init__

    def init(self, *a, **k):
        k["transport"] = httpx.MockTransport(lambda req: httpx.Response(200, text=box["body"]))
        orig(self, *a, **k)
    monkeypatch.setattr(httpx.AsyncClient, "__init__", init)
    monkeypatch.setattr(S, "MIN_REQUEST_INTERVAL", 0)
    monkeypatch.setattr(S, "_last_request_at", 0.0)
    return box


@pytest.mark.parametrize("count,sent,shown", [(100, 500, 100), (5, 40, 5), (20, 3, 3)])
def test_items_are_capped_at_the_count_asked_for(ndl, count, sent, shown):
    ndl["body"] = _many(sent)
    env = json.loads(asyncio.run(S.ndl_search_books(S.SearchInput(title="x", count=count))))
    assert env["result"]["returned"] == shown and len(env["items"]) == shown
