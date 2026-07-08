#!/usr/bin/env python3
"""
Extractor de credenciales de O2 Cloud (con verificación real).

Uso:
    python extract_o2_credentials.py

Qué hace:
1. Abre un navegador real y espera a que inicies sesión manualmente.
2. Escucha el tráfico real de la SPA hacia /sapi/ y captura una request
   autenticada COMPLETA (URL + headers reales, incluyendo la cookie que el
   navegador envía de verdad, no solo las cookies visibles por JS).
3. Reproduce esa MISMA request desde Python (aiohttp) para comprobar si la
   sesión es replicable fuera del navegador.
4. Solo guarda las credenciales si la reproducción funciona; de lo contrario
   informa de que la sesión está atada al navegador (huella/dispositivo).

Requiere: pip install playwright  (y: python -m playwright install chromium)
"""

import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import aiohttp

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("[ERROR] Playwright no instalado. Instala con: pip install playwright")
    sys.exit(1)


OUTPUT_FILE = Path(__file__).parent / "o2_credentials.json"
STORAGE_STATE_FILE = Path(__file__).parent / "o2_storage_state.json"
SAPI_MARKER = "cloud.o2online.es/sapi/"


def _parse_cookie_header(cookie_header: str) -> dict:
    """Parsear un header Cookie en diccionario."""
    cookies = {}
    for part in (cookie_header or "").split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        name, value = item.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


async def _launch_browser(p):
    """Abrir un Chromium del sistema (Edge/Chrome) o el de Playwright."""
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
    print("[ERROR] No se pudo abrir un navegador Chromium compatible:")
    for err in errors:
        print(f"   - {err}")
    print("   Prueba: python -m playwright install chromium")
    return None


_DROP_HEADERS = {
    "content-length",
    "host",
    "connection",
    "accept-encoding",  # evitar br/zstd que aiohttp no siempre decodifica
    "sec-fetch-dest",
    "sec-fetch-mode",
    "sec-fetch-site",
    "sec-fetch-user",
    "upgrade-insecure-requests",
    "priority",
}


def _sanitize_headers(headers: dict) -> dict:
    """Quitar pseudo-headers HTTP/2 y cabeceras que rompen el replay."""
    clean = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk.startswith(":"):  # pseudo-headers HTTP/2 (:method, :authority, ...)
            continue
        if lk in _DROP_HEADERS:
            continue
        clean[k] = v
    return clean


async def _replay_request(url: str, headers: dict) -> tuple[bool, int, str]:
    """Reproducir una request exacta desde aiohttp (con la cookie real)."""
    send_headers = _sanitize_headers(headers)
    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=send_headers, allow_redirects=False) as resp:
            body = await resp.text()
            ok = resp.status < 400 and not ('"error"' in body and "SEC-" in body)
            return ok, resp.status, body


async def extract_credentials():
    """Extraer y verificar credenciales de O2 Cloud."""
    async with async_playwright() as p:
        browser = await _launch_browser(p)
        if browser is None:
            return None

        context = await browser.new_context()
        page = await context.new_page()

        # Guardamos los objetos Request para poder leer all_headers() (async).
        sapi_requests = []

        def _on_request_finished(request):
            if SAPI_MARKER in request.url and "validationkey=" in request.url.lower():
                sapi_requests.append(request)

        page.on("requestfinished", _on_request_finished)

        print("[INFO] Abriendo O2 Cloud. Inicia sesión manualmente (teléfono + contraseña + SMS).")
        print("[INFO] Cuando entres a tus archivos, la captura es automática.")
        print()

        try:
            await page.goto("https://cloud.o2online.es", wait_until="domcontentloaded")
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] Error navegando inicialmente: {e}")

        print("[INFO] Esperando login y captura de una request /sapi autenticada...")

        # Esperar hasta 5 min a que aparezca al menos una request SAPI con validationkey.
        for _ in range(150):
            if sapi_requests:
                break
            await asyncio.sleep(2)

        if not sapi_requests:
            print("[ERROR] No se capturó ninguna request /sapi con validationkey.")
            print("        Asegúrate de entrar a la sección de archivos/almacenamiento.")
            await browser.close()
            return None

        # Forzar algo de tráfico extra por si aún no navegó a media.
        try:
            await page.goto("https://cloud.o2online.es/#/files", wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)
        except Exception:  # noqa: BLE001
            pass

        print(f"[INFO] Requests /sapi capturadas: {len(sapi_requests)}")

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

            print(f"[DEBUG] status={status} cookies={cookie_count} key={key[:16]}... path={parsed.path}")

            if not cookie_header:
                continue

            # EXPERIMENTO DECISIVO: reproducir la misma request desde aiohttp.
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

        # Exportar el storage_state completo (incluye cookies HttpOnly) siempre.
        try:
            await context.storage_state(path=str(STORAGE_STATE_FILE))
            print(f"[INFO] Estado de sesión completo guardado en: {STORAGE_STATE_FILE.name}")
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] No se pudo guardar storage_state: {e}")

        if not verified:
            print()
            print("=" * 70)
            print("[RESULTADO] La sesion NO es replicable fuera del navegador.")
            print("=" * 70)
            print("El navegador se autentica, pero al reproducir la MISMA request con")
            print("las mismas cookies desde Python, el servidor la rechaza. Esto indica")
            print("verificacion adicional (huella TLS/dispositivo) no replicable con aiohttp.")
            await browser.close()
            return None

        # Éxito: reunir cookies completas (incluye HttpOnly) desde el contexto.
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

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(credentials, f, indent=2)

        print()
        print("=" * 70)
        print("[OK] CREDENCIALES VERIFICADAS Y GUARDADAS")
        print("=" * 70)
        print(f"Validation Key: {verified['validation_key']}")
        print(f"Cookies: {len(o2_cookies)}")
        print(f"Guardado en: {OUTPUT_FILE.name}")
        print()

        await browser.close()
        return credentials


async def main():
    print()
    print("EXTRACTOR DE CREDENCIALES O2 CLOUD")
    print("=" * 70)
    credentials = await extract_credentials()

    if credentials:
        print("[OK] Ahora valida en local con:")
        print("     python test_o2cloud_local.py --credentials .\\o2_credentials.json")
        return 0

    print("[ERROR] No se obtuvieron credenciales verificadas.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n[WARN] Cancelado por usuario")
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"\n[ERROR] Error fatal: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
