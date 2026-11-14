"""OAuth authorization for O2 Cloud's desktop client."""

import base64
import hashlib
import json
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import aiohttp

AUTHORIZE_URL = (
    "https://apiseg.telefonica.es/openid/connect/auth/oauth/v2/o2/cus/authorize"
)
TOKEN_URL = "https://apiseg.telefonica.es/openid/connect/auth/oauth/v2/o2/cus/token"
CLIENT_ID = "21ce2068-4966-45dc-8b7f-a4a25a3a462f"
CLIENT_SECRET = "aa892341-04b1-4fd5-be41-db60d4e900e7"
REDIRECT_URI = "https://cloud.o2online.es/ui/html/clientoauth.html"
OAUTH_PROVIDERS = {
    "o2": {
        "authorize_url": AUTHORIZE_URL,
        "token_url": TOKEN_URL,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    },
    "movistar": {
        "authorize_url": "https://apiseg.telefonica.es/openid/connect/cus/col/auth/oauth/v2/authorize",
        "token_url": "https://apiseg.telefonica.es/openid/connect/cus/col/auth/oauth/v2/token",
        "client_id": "b99e5095-7a36-42c1-83b6-6f05d0f13ea1",
        "client_secret": "e22fdd6b-636a-4bfc-bb4a-aa8ed6d131d8",
        "redirect_uri": "https://micloud.movistar.es/ui/html/clientoauth.html",
    },
}
DESKTOP_USER_AGENT = "omh windows client 32.1.3.0"
SAPI_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36 Edg/157.0.0.0"


def build_login_url(provider: str = "o2") -> tuple[str, str, str]:
    """Return the authorization URL and its private verifier and state."""
    verifier = secrets.token_urlsafe(32)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    state = secrets.token_urlsafe(12)
    settings = OAUTH_PROVIDERS[provider]
    params = {
        "response_type": "code",
        "client_id": settings["client_id"],
        "redirect_uri": settings["redirect_uri"],
        "scope": "openid",
        "nonce": secrets.token_urlsafe(12),
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "access_type": "offline",
        "lang": "es",
        "acr_values": "2",
    }
    return f"{settings['authorize_url']}?{urlencode(params)}", verifier, state


def parse_callback(url: str, expected_state: str, provider: str = "o2") -> str:
    """Extract a code only from the expected redirect and matching state."""
    parsed = urlsplit(url.strip())
    expected = urlsplit(OAUTH_PROVIDERS[provider]["redirect_uri"])
    if (parsed.scheme, parsed.netloc, parsed.path) != (
        expected.scheme,
        expected.netloc,
        expected.path,
    ):
        raise ValueError("Invalid callback URL")
    query = parse_qs(parsed.query)
    if (
        len(query.get("state", [])) != 1
        or not query["state"][0].isascii()
        or not secrets.compare_digest(query["state"][0], expected_state)
    ):
        raise ValueError("Invalid OAuth state")
    codes = query.get("code", [])
    if len(codes) != 1 or not codes[0] or len(codes[0]) > 512:
        raise ValueError("Invalid authorization code")
    return codes[0]


async def exchange_tokens(
    session, *, code=None, verifier=None, refresh_token=None, provider="o2"
):
    """Exchange an authorization code or refresh token with Telefonica."""
    settings = OAUTH_PROVIDERS[provider]
    data = {
        "client_id": settings["client_id"],
        "client_secret": settings["client_secret"],
    }
    if code:
        data.update(
            grant_type="authorization_code",
            code=code,
            code_verifier=verifier,
            redirect_uri=settings["redirect_uri"],
        )
    else:
        data.update(grant_type="refresh_token", refresh_token=refresh_token)
    basic = base64.b64encode(
        f"{settings['client_id']}:{settings['client_secret']}".encode()
    ).decode()
    async with session.post(
        settings["token_url"],
        data=data,
        headers={"User-Agent": DESKTOP_USER_AGENT, "Authorization": f"Basic {basic}"},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as response:
        if response.status != 200:
            raise OAuthError(response.status)
        tokens = await response.json(content_type=None)
    if not isinstance(tokens, dict) or not tokens.get("access_token"):
        raise OAuthError(0)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token") or refresh_token or "",
        "expires_in": str(tokens.get("expires_in", 3600)),
        "last_refresh_date": int(time.time() * 1000),
    }


def authorization_header(tokens):
    """Build the SAPI OAuth authorization header."""
    payload = {
        "data": {
            "accesstoken": tokens["access_token"],
            "refreshtoken": tokens["refresh_token"],
            "expiresin": str(tokens["expires_in"]),
            "lastrefreshdate": tokens["last_refresh_date"],
            "platform": "windows",
        }
    }
    return (
        "oauth "
        + base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    )


def rotated_tokens(header, current):
    """Merge tokens returned in a SAPI authorization header."""
    if not header.lower().startswith("oauth "):
        return current
    try:
        payload = json.loads(base64.b64decode(header[6:], validate=True))
        payload = payload.get("data", payload)
        if not isinstance(payload, dict):
            return current
        updated = dict(current)
        for target, names in {
            "access_token": ("accesstoken", "access_token"),
            "refresh_token": ("refreshtoken", "refresh_token"),
            "expires_in": ("expiresin", "expires_in"),
            "last_refresh_date": ("lastrefreshdate", "last_refresh_date"),
        }.items():
            value = next((payload[name] for name in names if payload.get(name)), None)
            if value is not None:
                updated[target] = (
                    int(value) if target == "last_refresh_date" else str(value)
                )
        if updated["last_refresh_date"] < 100000000000:
            updated["last_refresh_date"] *= 1000
        return updated
    except (ValueError, TypeError, KeyError, AttributeError):
        return current


class OAuthError(Exception):
    """OAuth token exchange failed without exposing response secrets."""
