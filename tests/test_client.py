"""Tests for O2CloudClient media listing (pagination + off-loop JSON parsing).

These tests import only ``client.py`` (and ``const.py``), which do not depend
on Home Assistant, so they run in a plain Python environment.
"""

import asyncio
import json
from urllib.parse import parse_qs, urlparse

from o2pkg.client import O2CloudClient


class _FakeResponse:
    """Minimal async-context-manager stand-in for an aiohttp response."""

    def __init__(self, status: int, body: object, content_type: str = "application/json"):
        self.status = status
        self._body = body
        self.headers = {"content-type": content_type}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def text(self) -> str:
        return self._body if isinstance(self._body, str) else json.dumps(self._body)

    async def json(self):
        return self._body if not isinstance(self._body, str) else json.loads(self._body)


class _FakeSession:
    """Records requests and returns queued responses (like session.request)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return self._responses.pop(0)


def _page(items):
    """Build a SAPI media page payload: {"data": {"media": [...]}}."""
    return {"data": {"media": items}}


def _make_client(session):
    return O2CloudClient(
        validation_key="vkey",
        cookies={"JSESSIONID": "x"},
        user_agent="ua",
        session=session,
    )


async def test_get_all_media_paginates_until_short_page():
    """It should page in blocks of 1000 and stop on the first short page."""
    first = [{"name": f"a{i}.tar", "folder": 1} for i in range(1000)]
    second = [{"name": f"b{i}.tar", "folder": 1} for i in range(3)]
    session = _FakeSession([_FakeResponse(200, _page(first)),
                            _FakeResponse(200, _page(second))])
    client = _make_client(session)

    items = await client.get_all_media()

    assert len(items) == 1003
    # Two requests: offset 0 and offset 1000.
    assert len(session.requests) == 2
    offsets = [
        int(parse_qs(urlparse(url).query)["offset"][0])
        for _method, url, _kw in session.requests
    ]
    assert offsets == [0, 1000]


async def test_get_all_media_single_short_page_makes_one_request():
    """A single page shorter than the page size must not trigger a 2nd call."""
    session = _FakeSession([_FakeResponse(200, _page([{"name": "only.tar"}]))])
    client = _make_client(session)

    items = await client.get_all_media()

    assert len(items) == 1
    assert len(session.requests) == 1


async def test_get_all_media_parses_off_the_event_loop(monkeypatch):
    """The JSON body must be parsed via run_in_executor, not inline on the loop."""
    session = _FakeSession([_FakeResponse(200, _page([{"name": "x.tar"}]))])
    client = _make_client(session)

    loop = asyncio.get_running_loop()
    original = loop.run_in_executor
    offloaded = []

    def spy(executor, func, *args):
        offloaded.append(func)
        return original(executor, func, *args)

    monkeypatch.setattr(loop, "run_in_executor", spy)

    await client.get_all_media()

    # json.loads was dispatched to the executor (off the event loop).
    assert json.loads in offloaded
