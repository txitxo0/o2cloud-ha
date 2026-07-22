#!/usr/bin/env python3
"""
O2 Cloud credentials extractor (with real verification).

Usage:
    python extract_o2_credentials.py

What it does:
1. Opens a real browser and waits for you to log in manually.
2. Listens to the SPA's real traffic to /sapi/ and captures a COMPLETE
   authenticated request (URL + real headers, including the cookie the
   browser actually sends, not just the cookies visible to JS).
3. Replays that SAME request from Python (aiohttp) to check whether the
   session is replicable outside the browser.
4. Only prints the credentials JSON if the replay works; otherwise it
   reports that the session is bound to the browser.

The JSON is shown in the terminal to copy and paste into the integration
(no file is saved).

Requires: pip install playwright  (and: python -m playwright install chromium)
"""

import asyncio
import json
import socket
import ssl
import sys
from urllib.parse import parse_qs, urlparse

import aiohttp

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("[ERROR] Playwright not installed. Install with: pip install playwright")
    sys.exit(1)


SAPI_MARKER = "cloud.o2online.es/sapi/"


def _build_connector() -> aiohttp.TCPConnector:
    """Build the aiohttp connector used to replay the request.

    - Force IPv4: the host also resolves to IPv6, but many machines have no
      working IPv6 route and aiohttp's happy-eyeballs surfaces a confusing
      "connection refused" instead of falling back.
    - Verify TLS against the OS trust store (via ``truststore`` when available)
      so corporate MITM proxies / custom root CAs are trusted, exactly like the
      browser does. Falls back to the default certifi bundle otherwise.
    """
    try:
        import truststore

        ssl_ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        ssl_ctx = ssl.create_default_context()
    return aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl_ctx)


def _parse_cookie_header(cookie_header: str) -> dict:
    """Parse a Cookie header into a dictionary."""
    cookies = {}
    for part in (cookie_header or "").split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        name, value = item.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


async def _launch_browser(p):
    """Open a system Chromium (Edge/Chrome) or Playwright's own."""
    errors = []
    for opts in (
        {"channel": "msedge", "headless": False},
        {"channel": "chrome", "headless": False},
        {"headless": False},
    ):
        try:
            return await p.chromium.launch(**opts)
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))
    print("[ERROR] Could not open a compatible Chromium browser:")
    for err in errors:
        print(f"   - {err}")
    print("   Try: python -m playwright install chromium")
    return None


_DROP_HEADERS = {
    "content-length",
    "host",
    "connection",
    "accept-encoding",  # avoid br/zstd that aiohttp does not always decode
    "sec-fetch-dest",
    "sec-fetch-mode",
    "sec-fetch-site",
    "sec-fetch-user",
    "upgrade-insecure-requests",
    "priority",
}


def _sanitize_headers(headers: dict) -> dict:
    """Remove HTTP/2 pseudo-headers and headers that break the replay."""
    clean = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk.startswith(":"):  # HTTP/2 pseudo-headers (:method, :authority, ...)
            continue
        if lk in _DROP_HEADERS:
            continue
        clean[k] = v
    return clean


async def _replay_request(url: str, headers: dict) -> tuple[bool, int, str]:
    """Replay an exact request from aiohttp (with the real cookie)."""
    send_headers = _sanitize_headers(headers)
    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(
        timeout=timeout, connector=_build_connector()
    ) as session:
        async with session.get(
            url, headers=send_headers, allow_redirects=False
        ) as resp:
            body = await resp.text()
            ok = resp.status < 400 and not ('"error"' in body and "SEC-" in body)
            return ok, resp.status, body


async def extract_credentials():
    """Extract and verify O2 Cloud credentials."""
    async with async_playwright() as p:
        browser = await _launch_browser(p)
        if browser is None:
            return None

        context = await browser.new_context()
        page = await context.new_page()

        # Keep the Request objects so we can read all_headers() (async).
        sapi_requests = []

        def _on_request_finished(request):
            if SAPI_MARKER in request.url and "validationkey=" in request.url.lower():
                sapi_requests.append(request)

        page.on("requestfinished", _on_request_finished)

        print("[INFO] Opening O2 Cloud. Log in manually (phone + password + SMS).")
        print("[INFO] Once you reach your files, the capture is automatic.")
        print()

        try:
            await page.goto("https://cloud.o2online.es", wait_until="domcontentloaded")
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] Error during initial navigation: {e}")

        print(
            "[INFO] Waiting for login and capture of an authenticated /sapi request..."
        )

        # Wait up to 5 min for at least one SAPI request with validationkey to appear.
        for _ in range(150):
            if sapi_requests:
                break
            await asyncio.sleep(2)

        if not sapi_requests:
            print("[ERROR] No /sapi request with validationkey was captured.")
            print("        Make sure you enter the files/storage section.")
            await browser.close()
            return None

        # Force some extra traffic in case it did not navigate to media yet.
        try:
            await page.goto(
                "https://cloud.o2online.es/#/files", wait_until="domcontentloaded"
            )
            await page.wait_for_timeout(4000)
        except Exception:  # noqa: BLE001
            pass

        print(f"[INFO] /sapi requests captured: {len(sapi_requests)}")

        verified = None
        for request in reversed(sapi_requests):
            try:
                all_headers = await request.all_headers()
            except Exception:  # noqa: BLE001
                continue

            resp = await request.response()
            status = resp.status if resp else None
            if status is None or status >= 400:
                continue

            cookie_header = all_headers.get("cookie", "")
            cookie_count = len(_parse_cookie_header(cookie_header))
            url = request.url
            parsed = urlparse(url)
            key = (parse_qs(parsed.query).get("validationkey") or [""])[0]

            print(
                f"[DEBUG] status={status} cookies={cookie_count} key={key[:16]}... path={parsed.path}"
            )

            if not cookie_header:
                continue

            # DECISIVE EXPERIMENT: replay the same request from aiohttp.
            ok, replay_status, body = await _replay_request(url, all_headers)
            print(f"[DEBUG] replay aiohttp -> status={replay_status} ok={ok}")
            if not ok:
                snippet = body[:160].replace("\n", " ")
                print(f"[DEBUG] body: {snippet}")

            if ok:
                verified = {
                    "url": url,
                    "validation_key": key,
                    "cookie_header": cookie_header,
                    "user_agent": all_headers.get("user-agent", ""),
                }
                break

        if not verified:
            print()
            print("=" * 70)
            print("[RESULT] The session is NOT replicable outside the browser.")
            print("=" * 70)
            print("The browser authenticates, but when replaying the SAME request with")
            print("the same cookies from Python, the server rejects it. This indicates")
            print(
                "additional verification (TLS/device fingerprint) not replicable with aiohttp."
            )
            await browser.close()
            return None

        # Success: gather full cookies (including HttpOnly) from the context.
        all_cookies = await context.cookies()
        o2_cookies = {
            c["name"]: c["value"]
            for c in all_cookies
            if c.get("domain", "").lstrip(".").endswith("o2online.es")
        }
        o2_cookies.update(_parse_cookie_header(verified["cookie_header"]))

        credentials = {
            "validation_key": verified["validation_key"],
            "user_agent": verified["user_agent"],
            "cookies": o2_cookies,
            "cookie_header": verified["cookie_header"],
        }

        creds_json = json.dumps(credentials, indent=2)
        print()
        print("=" * 70)
        print("[OK] CREDENTIALS VERIFIED")
        print("=" * 70)
        print("Copy the ENTIRE JSON block below and paste it into the integration")
        print("(Settings > Devices and services > O2 Cloud):")
        print()
        print("----------------------- COPY FROM HERE -----------------------")
        print(creds_json)
        print("------------------------ COPY UNTIL HERE -----------------------")
        print()

        await browser.close()
        return credentials


async def main():
    print()
    print("O2 CLOUD CREDENTIALS EXTRACTOR")
    print("=" * 70)
    credentials = await extract_credentials()

    if credentials:
        return 0

    print("[ERROR] No verified credentials were obtained.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n[WARN] Cancelled by user")
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"\n[ERROR] Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
