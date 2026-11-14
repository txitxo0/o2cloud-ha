"""Tests for O2 OAuth authorization."""

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from o2pkg.oauth import (
    OAUTH_PROVIDERS,
    REDIRECT_URI,
    authorization_header,
    build_login_url,
    exchange_tokens,
    parse_callback,
    rotated_tokens,
)


def test_login_url_uses_pkce_and_matching_state():
    url, verifier, state = build_login_url()
    query = parse_qs(urlsplit(url).query)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    assert query["code_challenge"] == [challenge]
    assert query["state"] == [state]
    assert (
        parse_callback(
            f"{REDIRECT_URI}?{urlencode({'code': 'code', 'state': state})}", state
        )
        == "code"
    )


@pytest.mark.parametrize("provider", ["o2", "movistar"])
def test_provider_login_and_callback(provider):
    settings = OAUTH_PROVIDERS[provider]
    url, verifier, state = build_login_url(provider)
    query = parse_qs(urlsplit(url).query)
    assert url.startswith(settings["authorize_url"] + "?")
    assert query["client_id"] == [settings["client_id"]]
    assert query["redirect_uri"] == [settings["redirect_uri"]]
    callback = (
        settings["redirect_uri"] + "?" + urlencode({"code": "code", "state": state})
    )
    assert parse_callback(callback, state, provider) == "code"
    other = "movistar" if provider == "o2" else "o2"
    with pytest.raises(ValueError):
        parse_callback(callback, state, other)


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/ui/html/clientoauth.html?code=abc&state=state",
        f"{REDIRECT_URI}?code=abc&state=wrong",
        f"{REDIRECT_URI}?code=abc",
        f"{REDIRECT_URI}?code=abc&state=state&state=other",
        f"{REDIRECT_URI}?code=abc&state=%C3%B1",
    ],
)
def test_invalid_callback_is_rejected(url):
    with pytest.raises(ValueError):
        parse_callback(url, "state")


def test_sapi_header_and_rotated_tokens():
    tokens = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": "3600",
        "last_refresh_date": 1700000000000,
    }
    encoded = authorization_header(tokens).split(" ", 1)[1]
    assert json.loads(base64.b64decode(encoded))["data"]["refreshtoken"] == "refresh"
    rotated = base64.b64encode(
        json.dumps({"data": {"refreshtoken": "new"}}).encode()
    ).decode()
    assert rotated_tokens("oauth " + rotated, tokens)["refresh_token"] == "new"
    assert rotated_tokens("oauth invalid", tokens) == tokens


@pytest.mark.parametrize("refresh", [False, True])
@pytest.mark.parametrize("provider", ["o2", "movistar"])
async def test_token_exchange_request(refresh, provider):
    settings = OAUTH_PROVIDERS[provider]

    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def json(self, **kwargs):
            return {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            }

    class Session:
        def post(self, url, **kwargs):
            assert url == settings["token_url"]
            assert (
                base64.b64decode(kwargs["headers"]["Authorization"].split()[1])
                .decode()
                .startswith(settings["client_id"] + ":")
            )
            if refresh:
                assert kwargs["data"]["grant_type"] == "refresh_token"
                assert kwargs["data"]["refresh_token"] == "old-refresh"
            else:
                assert kwargs["data"]["grant_type"] == "authorization_code"
                assert kwargs["data"]["code_verifier"] == "verifier"
                assert kwargs["data"]["redirect_uri"] == settings["redirect_uri"]
            return Response()

    tokens = await exchange_tokens(
        Session(),
        **(
            {"refresh_token": "old-refresh"}
            if refresh
            else {"code": "code", "verifier": "verifier"}
        ),
        provider=provider,
    )
    assert tokens["access_token"] == "new-access"
    assert tokens["refresh_token"] == "new-refresh"
