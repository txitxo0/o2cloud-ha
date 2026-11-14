"""Tests for O2CloudClient media listing (pagination + off-loop JSON parsing).

These tests import only ``client.py`` (and ``const.py``), which do not depend
on Home Assistant, so they run in a plain Python environment.
"""

import asyncio
import json
import sys
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

import pytest
from o2pkg.client import O2CloudAPIError, O2CloudClient
from o2pkg.oauth import authorization_header


class _FakeResponse:
    """Minimal async-context-manager stand-in for an aiohttp response."""

    def __init__(
        self, status: int, body: object, content_type: str = "application/json"
    ):
        self.status = status
        self._body = body
        self.headers = {"content-type": content_type}
        self.cookies = SimpleCookie()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def text(self) -> str:
        return self._body if isinstance(self._body, str) else json.dumps(self._body)

    async def json(self, **kwargs):
        return self._body if not isinstance(self._body, str) else json.loads(self._body)


class _FakeSession:
    """Records requests and returns queued responses (like session.request)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        if "cookies" in kwargs:
            kwargs["cookies"] = dict(kwargs["cookies"])
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
    session = _FakeSession(
        [_FakeResponse(200, _page(first)), _FakeResponse(200, _page(second))]
    )
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


async def test_oauth_rotation_is_persisted():
    tokens = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": "3600",
        "last_refresh_date": 1700000000000,
    }
    rotated = {**tokens, "refresh_token": "new"}
    response = _FakeResponse(200, _page([]))
    response.headers["Authorization"] = authorization_header(rotated)
    session = _FakeSession([response])
    saved = []
    client = O2CloudClient("", {}, "ua", session, tokens, saved.append, "device")

    await client.get_all_media()

    assert saved == [rotated]
    assert session.requests[0][2]["headers"]["Authorization"] == authorization_header(
        tokens
    )


async def test_oauth_401_refreshes_and_retries(monkeypatch):
    tokens = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": "3600",
        "last_refresh_date": 1700000000000,
    }
    refreshed = {**tokens, "access_token": "new", "refresh_token": "new-refresh"}
    login = _FakeResponse(200, {"responsetime": 1700000000000})
    login.cookies["validationkey"] = "session-key"
    login.cookies["JSESSIONID"] = "session-id"
    session = _FakeSession(
        [
            _FakeResponse(401, {}),
            _FakeResponse(401, {}),
            login,
            _FakeResponse(200, _page([])),
        ]
    )
    saved = []
    client = O2CloudClient("", {}, "ua", session, tokens, saved.append, "device")

    async def refresh(session, *, refresh_token):
        assert refresh_token == "refresh"
        return refreshed

    monkeypatch.setattr(sys.modules["o2pkg.client"], "exchange_tokens", refresh)
    await client.get_all_media()

    assert saved == [refreshed]
    assert session.requests[2][2]["headers"]["Authorization"] == authorization_header(
        refreshed
    )
    assert parse_qs(urlparse(session.requests[3][1]).query)["validationkey"] == [
        "session-key"
    ]
    assert session.requests[3][2]["cookies"]["JSESSIONID"] == "session-id"


async def test_oauth_401_opens_sapi_session_without_refresh(monkeypatch):
    tokens = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": "3600",
        "last_refresh_date": 1700000000000,
    }
    login = _FakeResponse(200, {"responsetime": 1700000000000})
    login.cookies["validationkey"] = "session-key"
    login.cookies["JSESSIONID"] = "session-id"
    session = _FakeSession(
        [_FakeResponse(401, {}), login, _FakeResponse(200, _page([]))]
    )
    client = O2CloudClient("", {}, "ua", session, tokens, None, "device")

    async def unexpected_refresh(*args, **kwargs):
        pytest.fail("SAPI login should be tried before refreshing")

    monkeypatch.setattr(
        sys.modules["o2pkg.client"], "exchange_tokens", unexpected_refresh
    )
    await client.get_all_media()
    assert urlparse(session.requests[1][1]).path == "/sapi/login/oauth"
    assert parse_qs(urlparse(session.requests[2][1]).query)["validationkey"] == [
        "session-key"
    ]
    assert session.requests[2][2]["cookies"]["JSESSIONID"] == "session-id"


@pytest.mark.parametrize("body", [{"error": {"code": "invalid"}}, {"data": {}}])
async def test_sapi_login_does_not_accept_http_200_error(body):
    tokens = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": "3600",
        "last_refresh_date": 1700000000000,
    }
    login = _FakeResponse(200, body)
    login.cookies["JSESSIONID"] = "session-id"
    session = _FakeSession([_FakeResponse(401, {}), login])
    client = O2CloudClient("", {}, "ua", session, tokens, None, "device")
    with pytest.raises(O2CloudAPIError, match="SAPI OAuth login"):
        await client.get_all_media()
    assert len(session.requests) == 2


async def test_oauth_401_retries_rotated_tokens_without_refresh(monkeypatch):
    tokens = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": "3600",
        "last_refresh_date": 1700000000000,
    }
    rotated = {**tokens, "access_token": "new", "refresh_token": "new-refresh"}
    response = _FakeResponse(401, {})
    response.headers["Authorization"] = authorization_header(rotated)
    session = _FakeSession([response, _FakeResponse(200, _page([]))])
    saved = []
    client = O2CloudClient("", {}, "ua", session, tokens, saved.append, "device")

    async def unexpected_refresh(*args, **kwargs):
        pytest.fail("Rotated tokens should be tried before refreshing")

    monkeypatch.setattr(
        sys.modules["o2pkg.client"], "exchange_tokens", unexpected_refresh
    )
    await client.get_all_media()
    assert saved == [rotated]
    assert session.requests[1][2]["headers"]["Authorization"] == authorization_header(
        rotated
    )


async def test_streaming_upload_is_not_replayed_after_refresh(monkeypatch):
    tokens = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": "3600",
        "last_refresh_date": 1700000000000,
    }
    refreshed = {**tokens, "access_token": "new", "refresh_token": "new-refresh"}
    login = _FakeResponse(200, {"responsetime": 1700000000000})
    login.cookies["JSESSIONID"] = "session-id"
    session = _FakeSession([_FakeResponse(401, {}), _FakeResponse(401, {}), login])
    saved = []
    client = O2CloudClient("", {}, "ua", session, tokens, saved.append, "device")

    async def refresh(session, *, refresh_token):
        return refreshed

    async def stream():
        yield b"data"

    monkeypatch.setattr(sys.modules["o2pkg.client"], "exchange_tokens", refresh)
    with pytest.raises(O2CloudAPIError, match="streaming upload must be retried"):
        await client.upload_stream("123", 4, stream())
    assert saved == [refreshed]
    assert len(session.requests) == 3
