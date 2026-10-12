"""A Retry-After that is not a usable number of seconds falls back to the
default backoff (stress test, 12 October 2026).

min(float("nan"), 30.0) is nan, and asyncio.sleep(nan) never returns on
Python 3.10-3.12 (3.13 raises ValueError instead). The sleep happened inside
_rate_lock, so one such header hung every later NDL call. No request is made
to NDL here: httpx is mocked.
"""
import asyncio

import httpx
import pytest

from ndl_mcp import server as S


RETRY_AFTER = {"value": "nan"}


@pytest.fixture
def ndl(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": RETRY_AFTER["value"]})
        return httpx.Response(200, text="<ok/>")

    orig = httpx.AsyncClient.__init__

    def init(self, *a, **k):
        k["transport"] = httpx.MockTransport(handler)
        orig(self, *a, **k)
    monkeypatch.setattr(httpx.AsyncClient, "__init__", init)
    monkeypatch.setattr(S, "BACKOFF_SECONDS", 0.01)
    monkeypatch.setattr(S, "MIN_REQUEST_INTERVAL", 0)
    monkeypatch.setattr(S, "_last_request_at", 0.0)
    return calls


@pytest.mark.parametrize("value", ["nan", "-nan", "inf", "-5", "1e309", "Wed, 21 Oct 2026 07:28:00 GMT", ""])
def test_unusable_retry_after_falls_back_and_retries_once(ndl, value):
    RETRY_AFTER["value"] = value
    body = asyncio.run(asyncio.wait_for(S._sru_request({"query": "x"}), 5))
    assert body == "<ok/>"
    assert len(ndl) == 2

