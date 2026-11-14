"""API client for O2 Cloud."""

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiohttp

from .const import (
    CLOUD_PROVIDERS,
    DEFAULT_PROVIDER,
    REQUEST_TIMEOUT,
    UPLOAD_TIMEOUT,
)
from .oauth import OAuthError, authorization_header, exchange_tokens, rotated_tokens

_LOGGER = logging.getLogger(__name__)

# Page size when listing media (the API paginates 1000 at a time).
MEDIA_PAGE_SIZE = 1000
# Chunk size for streaming downloads.
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


def _compact_iso(timestamp: float | None = None) -> str:
    """Date in compact ISO format (YYYYMMDDThhmmss) expected by the API."""
    dt = (
        datetime.fromtimestamp(timestamp, tz=UTC)
        if timestamp is not None
        else datetime.now(UTC)
    )
    return dt.strftime("%Y%m%dT%H%M%S")


def _guess_content_type(name: str) -> str:
    """Guess basic content-type from the name."""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return {
        "json": "application/json",
        "txt": "text/plain",
    }.get(ext, "application/octet-stream")


def _as_int(value: Any, default: int = 0) -> int:
    """Convert an id (returned by the API as number or string) to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class O2CloudClient:
    """Client to interact with the O2 Cloud API."""

    def __init__(
        self,
        validation_key: str,
        cookies: dict[str, str],
        user_agent: str,
        session: aiohttp.ClientSession | None = None,
        oauth_tokens: dict | None = None,
        token_update=None,
        device_id: str = "",
        provider: str = DEFAULT_PROVIDER,
    ):
        """Initialize client."""
        self.validation_key = validation_key
        self.cookies = cookies if cookies else {}
        self.user_agent = user_agent
        self.session = session
        self._own_session = session is None
        self.oauth_tokens = oauth_tokens
        self.token_update = token_update
        self.device_id = device_id
        self.provider = provider
        settings = CLOUD_PROVIDERS[provider]
        self.host = settings["host"]
        self.upload_host = settings["upload_host"]
        self.api_base_url = f"https://{self.host}/sapi/"
        self.upload_base_url = f"https://{self.upload_host}/sapi/upload/file"
        self._oauth_lock = asyncio.Lock()

        _LOGGER.debug("O2CloudClient initialized with %d cookies", len(self.cookies))

    async def __aenter__(self):
        """Async context manager entry."""
        if self._own_session:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._own_session and self.session:
            await self.session.close()

    async def close(self):
        """Close session."""
        if self._own_session and self.session:
            await self.session.close()

    def _get_headers(self) -> dict[str, str]:
        """Get standard headers.

        Note: kept minimal on purpose. Forwarding Accept-Encoding with
        br/zstd or HTTP/2 pseudo-headers causes 400 responses from the backend.
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"https://{self.host}/",
            "X-Requested-With": "XMLHttpRequest",
        }
        if self.oauth_tokens:
            headers["Authorization"] = authorization_header(self.oauth_tokens)
            headers["X-deviceid"] = self.device_id
            headers["X-devicename"] = "PC Windows"
        return headers

    def _update_tokens(self, tokens):
        if tokens != self.oauth_tokens:
            self.oauth_tokens = tokens
            if self.token_update:
                self.token_update(tokens)

    def _build_query_params(self, **kwargs) -> str:
        """Build query parameters with validationkey."""
        params = dict(kwargs)
        if self.validation_key:
            params["validationkey"] = self.validation_key
        return urlencode(params)

    def _session_url(self, url: str) -> str:
        parts = urlsplit(url)
        if not self.validation_key or parts.hostname not in (
            self.host,
            self.upload_host,
        ):
            return url
        params = [
            (name, value)
            for name, value in parse_qsl(parts.query, keep_blank_values=True)
            if name != "validationkey"
        ]
        params.append(("validationkey", self.validation_key))
        return urlunsplit(parts._replace(query=urlencode(params)))

    async def _login_sapi(self) -> None:
        """Establish a SAPI session from the current OAuth tokens."""
        if not self.session:
            raise RuntimeError("Session not initialized")
        async with self.session.request(
            "GET",
            f"{self.api_base_url}login/oauth?action=login&responsetime=true",
            headers=self._get_headers(),
            cookies=self.cookies,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as response:
            self._update_tokens(
                rotated_tokens(
                    response.headers.get("Authorization", ""), self.oauth_tokens
                )
            )
            if response.status in (401, 403):
                raise O2CloudAuthError(response.status)
            if response.status != 200:
                raise O2CloudAPIError(
                    f"SAPI OAuth login failed: HTTP {response.status}"
                )
            try:
                result = await response.json(content_type=None)
            except (ValueError, aiohttp.ClientError) as err:
                raise O2CloudAPIError("SAPI OAuth login returned invalid JSON") from err
            if not isinstance(result, dict) or result.get("error"):
                raise O2CloudAPIError("SAPI OAuth login rejected the session")
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            cookies = {
                name: morsel.value
                for name, morsel in response.cookies.items()
                if name.lower() in ("jsessionid", "validationkey") and morsel.value
            }
            validation_key = (
                next(
                    (
                        value
                        for name, value in cookies.items()
                        if name.lower() == "validationkey"
                    ),
                    "",
                )
                or data.get("validationkey")
                or result.get("validationkey")
            )
            session_id = (
                next(
                    (
                        value
                        for name, value in cookies.items()
                        if name.lower() == "jsessionid"
                    ),
                    "",
                )
                or data.get("jsessionid")
                or result.get("jsessionid")
            )
            if not (validation_key or session_id) or not (
                result.get("responsetime")
                or data.get("responsetime")
                or response.headers.get("Authorization")
            ):
                raise O2CloudAPIError("SAPI OAuth login did not establish a session")
            if validation_key:
                self.validation_key = str(validation_key)
                self.cookies["validationkey"] = self.validation_key
            if session_id:
                self.cookies["JSESSIONID"] = str(session_id)

    @staticmethod
    def _unwrap_data(result: Any) -> Any:
        """Unwrap the SAPI {"data": ...} wrapper from responses."""
        if isinstance(result, dict) and isinstance(result.get("data"), str):
            try:
                result = json.loads(result["data"])
            except json.JSONDecodeError:
                return {}
        if isinstance(result, dict) and "data" in result:
            return result["data"]
        return result

    async def _make_request(
        self,
        method: str,
        url: str,
        *,
        parse_in_executor: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """Make HTTP request.

        When ``parse_in_executor`` is set, a JSON body is parsed in a worker
        thread instead of on the event loop. This is important for large
        responses (e.g. listing tens of thousands of media items): parsing
        them inline would block the loop for seconds and starve other tasks.
        """
        if self.oauth_tokens:
            async with self._oauth_lock:
                previous_tokens = self.oauth_tokens
                try:
                    return await self._request(
                        method,
                        self._session_url(url),
                        parse_in_executor=parse_in_executor,
                        **kwargs,
                    )
                except O2CloudAuthError as err:
                    if err.status != 401 or not self.oauth_tokens.get("refresh_token"):
                        raise
                    if self.oauth_tokens == previous_tokens:
                        try:
                            await self._login_sapi()
                        except O2CloudAuthError as login_err:
                            if login_err.status != 401:
                                raise
                            try:
                                tokens = await exchange_tokens(
                                    self.session,
                                    refresh_token=self.oauth_tokens["refresh_token"],
                                    provider=self.provider,
                                )
                            except OAuthError as refresh_err:
                                if refresh_err.args[0] in (400, 401):
                                    raise O2CloudAuthError(401) from refresh_err
                                raise O2CloudAPIError(
                                    "OAuth token refresh failed"
                                ) from refresh_err
                            self._update_tokens(tokens)
                            await self._login_sapi()
                    if not isinstance(
                        kwargs.get("data"), (type(None), bytes, str, dict)
                    ):
                        raise O2CloudAPIError(
                            "Session refreshed; streaming upload must be retried"
                        ) from err
                    return await self._request(
                        method,
                        self._session_url(url),
                        parse_in_executor=parse_in_executor,
                        **kwargs,
                    )
        return await self._request(
            method, url, parse_in_executor=parse_in_executor, **kwargs
        )

    async def _request(self, method, url, *, parse_in_executor=False, **kwargs):
        if not self.session:
            raise RuntimeError("Session not initialized")

        headers = self._get_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        try:
            _LOGGER.debug(
                "Making %s request to %s with %d cookies",
                method,
                urlsplit(url).path,
                len(self.cookies),
            )

            async with self.session.request(
                method,
                url,
                headers=headers,
                cookies=self.cookies,
                timeout=aiohttp.ClientTimeout(
                    total=kwargs.pop("timeout", REQUEST_TIMEOUT)
                ),
                **kwargs,
            ) as resp:
                _LOGGER.debug(f"Response status: {resp.status}")
                if self.oauth_tokens:
                    self._update_tokens(
                        rotated_tokens(
                            resp.headers.get("Authorization", ""), self.oauth_tokens
                        )
                    )

                if resp.status in (401, 403):
                    raise O2CloudAuthError(resp.status)

                if resp.status >= 400:
                    text = await resp.text()
                    raise O2CloudAPIError(f"API error {resp.status}: {text}")

                if resp.status == 204:
                    return {}

                content_type = resp.headers.get("content-type", "")
                if "application/json" in content_type:
                    if parse_in_executor:
                        text = await resp.text()
                        loop = asyncio.get_running_loop()
                        return await loop.run_in_executor(None, json.loads, text)
                    return await resp.json()
                else:
                    return {"data": await resp.text()}

        except TimeoutError:
            raise O2CloudTimeoutError("Request timeout")
        except aiohttp.ClientError as e:
            raise O2CloudConnectionError(f"Connection error: {e}")

    async def get_storage_space(
        self, include_soft_deleted: bool = False
    ) -> dict[str, Any]:
        """Get storage space."""
        query = self._build_query_params(
            action="get-storage-space",
            softdeleted="true" if include_soft_deleted else "false",
        )
        url = f"{self.api_base_url}media?{query}"

        result = await self._make_request("GET", url)

        # _make_request may return the already-parsed JSON or {"data": raw_text}.
        # The real API responds: {"data": {quota,...}, "responsetime": ...}
        if isinstance(result, dict) and isinstance(result.get("data"), str):
            try:
                result = json.loads(result["data"])
            except json.JSONDecodeError:
                return result

        if isinstance(result, dict) and isinstance(result.get("data"), dict):
            return result["data"]
        return result

    async def get_all_folders(self) -> list[dict[str, Any]]:
        """List ALL folders (flat list with id/name/parentid)."""
        query = self._build_query_params(action="get")
        url = f"{self.api_base_url}media/folder?{query}"
        result = await self._make_request("POST", url)
        data = self._unwrap_data(result)
        if isinstance(data, dict) and isinstance(data.get("folders"), list):
            return data["folders"]
        return []

    async def get_all_media(self) -> list[dict[str, Any]]:
        """List ALL files (paginated). Includes download url."""
        all_items: list[dict[str, Any]] = []
        offset = 0
        while True:
            query = self._build_query_params(
                action="get",
                limit=MEDIA_PAGE_SIZE,
                offset=offset,
            )
            url = f"{self.api_base_url}media?{query}"
            payload = {"data": {"fields": ["name", "size", "etag", "folderid", "url"]}}
            # Parse off the event loop: a full page can carry thousands of
            # items and json parsing is CPU-bound.
            result = await self._make_request(
                "POST", url, json=payload, parse_in_executor=True
            )
            data = self._unwrap_data(result)
            items = data.get("media", []) if isinstance(data, dict) else []
            all_items.extend(items)
            if len(items) < MEDIA_PAGE_SIZE:
                break
            offset += MEDIA_PAGE_SIZE
        return all_items

    async def create_folder(
        self,
        folder_name: str,
        parent_id: int,
    ) -> int:
        """Create folder and return its numeric id."""
        now = _compact_iso()
        query = self._build_query_params(action="save")
        url = f"{self.api_base_url}media/folder?{query}"
        payload = {
            "data": {
                "creationdate": now,
                "magic": False,
                "modificationdate": now,
                "name": folder_name,
                "parentid": int(parent_id),
            }
        }
        result = await self._make_request("POST", url, json=payload)
        data = self._unwrap_data(result)
        folder_id = None
        if isinstance(data, dict):
            folder_id = data.get("id") or (data.get("folder") or {}).get("id")
        if folder_id is None and isinstance(result, dict):
            folder_id = result.get("id")
        if folder_id is None:
            raise O2CloudAPIError(f"No id received when creating folder: {result}")
        return _as_int(folder_id)

    async def resolve_folder_id(self, folder: str) -> int:
        """Resolve a folder name to its numeric id.

        Accepts a numeric id (returns it as-is), "root"/"/"/"" (root) or
        a folder name under the root (creates it if it does not exist).
        """
        value = str(folder).strip()
        if value.isdigit():
            return int(value)

        folders = await self.get_all_folders()
        root_id = next(
            (_as_int(f.get("id")) for f in folders if f.get("name") == "/"),
            0,
        )
        if value in ("", "root", "/"):
            return root_id

        for f in folders:
            if f.get("name") == value and _as_int(f.get("parentid")) == root_id:
                return _as_int(f.get("id"))

        _LOGGER.info("Folder '%s' does not exist, creating it at the root", value)
        return await self.create_folder(value, root_id)

    async def upload_metadata(
        self,
        remote_name: str,
        size: int,
        folder_id: int,
        mtime: float | None = None,
    ) -> str:
        """Step 1: save metadata and return the media id."""
        now = _compact_iso(mtime)
        metadata = {
            "data": {
                "contenttype": _guess_content_type(remote_name),
                "creationdate": now,
                "folderid": int(folder_id),
                "modificationdate": now,
                "name": remote_name,
                "size": int(size),
            }
        }
        query = self._build_query_params(
            action="save-metadata",
            responsetime="true",
            lastupdate="true",
        )
        meta_url = f"{self.api_base_url}upload/file?{query}"
        meta_body = json.dumps(metadata).encode("utf-8")
        meta_result = await self._make_request(
            "POST",
            meta_url,
            data=meta_body,
            headers={"Content-Type": "application/octet-stream"},
        )
        meta_data = self._unwrap_data(meta_result)
        media_id = None
        if isinstance(meta_data, dict):
            media_id = meta_data.get("id") or (meta_data.get("file") or {}).get("id")
        if media_id is None and isinstance(meta_result, dict):
            media_id = meta_result.get("id")
        if not media_id:
            # save-metadata answers HTTP 200 even on rejection, embedding the
            # reason as {"error": {"code", "message"}}. Surface it clearly
            # instead of the cryptic "No media id received".
            error = meta_data.get("error") if isinstance(meta_data, dict) else None
            if isinstance(error, dict) and error.get("code"):
                raise O2CloudAPIError(
                    f"O2 rejected '{remote_name}' ({size} bytes): "
                    f"{error.get('message', 'unknown error')} "
                    f"[{error['code']}]"
                )
            raise O2CloudAPIError(
                f"No media id received in save-metadata: {meta_result}"
            )
        return str(media_id)

    async def upload_stream(
        self,
        media_id: str,
        size: int,
        stream: AsyncIterator[bytes],
    ) -> None:
        """Step 2: upload the raw bytes (streaming) to the upload host.

        Chunked transfer is used; O2 knows the size from the
        x-funambol-file-size header, so it does not need Content-Length.
        """
        query = self._build_query_params(
            action="save",
            id=str(media_id),
            lastupdate="true",
            acceptasynchronous="true",
        )
        upload_url = f"{self.upload_base_url}?{query}"
        headers = {
            "Content-Type": "application/octet-stream",
            "x-funambol-file-size": str(size),
            "x-funambol-id": str(media_id),
        }
        _LOGGER.debug(
            "Starting binary upload (media_id=%s, size=%d bytes)",
            media_id,
            size,
        )
        await self._make_request(
            "POST",
            upload_url,
            data=stream,
            headers=headers,
            timeout=UPLOAD_TIMEOUT,
        )
        _LOGGER.debug("Binary upload finished (media_id=%s)", media_id)

    async def upload_file(
        self,
        file_path: str,
        folder_id: int,
        remote_name: str | None = None,
    ) -> dict[str, Any]:
        """Upload a file from disk (reads in executor, uploads in streaming)."""
        loop = asyncio.get_running_loop()
        if not remote_name:
            remote_name = os.path.basename(file_path)

        file_size = await loop.run_in_executor(None, os.path.getsize, file_path)
        mtime = await loop.run_in_executor(None, os.path.getmtime, file_path)

        media_id = await self.upload_metadata(remote_name, file_size, folder_id, mtime)

        async def _file_stream() -> AsyncIterator[bytes]:
            f = await loop.run_in_executor(None, open, file_path, "rb")
            try:
                while True:
                    chunk = await loop.run_in_executor(
                        None, f.read, DOWNLOAD_CHUNK_SIZE
                    )
                    if not chunk:
                        break
                    yield chunk
            finally:
                await loop.run_in_executor(None, f.close)

        await self.upload_stream(media_id, file_size, _file_stream())

        return {
            "file_name": remote_name,
            "file_size": file_size,
            "media_id": media_id,
        }

    async def download(self, url: str) -> AsyncIterator[bytes]:
        """Download bytes in streaming from a signed media URL."""
        if not self.session:
            raise RuntimeError("Session not initialized")
        headers = self._get_headers()
        parts = urlsplit(url)
        trusted = parts.scheme == "https" and parts.hostname in (
            self.host,
            self.upload_host,
        )
        if not trusted:
            headers.pop("Authorization", None)
        async with self.session.get(
            url,
            headers=headers,
            cookies=self.cookies if trusted else {},
            timeout=aiohttp.ClientTimeout(total=UPLOAD_TIMEOUT),
        ) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise O2CloudAPIError(f"Download error {resp.status}: {text[:200]}")
            async for chunk in resp.content.iter_chunked(DOWNLOAD_CHUNK_SIZE):
                yield chunk

    async def download_bytes(self, url: str) -> bytes:
        """Download the full content of a URL (for small files)."""
        data = bytearray()
        async for chunk in self.download(url):
            data.extend(chunk)
        return bytes(data)

    async def delete_file(
        self,
        file_id: str,
        soft_delete: bool = True,
    ) -> dict[str, Any]:
        """Delete (move to trash) a file by its id."""
        query = self._build_query_params(
            action="softdelete" if soft_delete else "delete",
            id=str(file_id),
        )
        url = f"{self.api_base_url}media?{query}"
        return await self._make_request("POST", url)

    async def test_connection(self) -> bool:
        """Test connection and session validity."""
        try:
            _LOGGER.debug("Testing connection with %d cookies", len(self.cookies))
            result = await self.get_storage_space()
            _LOGGER.debug("Connection test successful: %s", result)
            return any(
                k in result for k in ("quota", "used", "total", "capacidadTotalCloud")
            )
        except Exception as e:
            _LOGGER.error(f"Connection test failed: {e}", exc_info=True)
            return False


class O2CloudException(Exception):
    """Base exception for O2 Cloud."""


class O2CloudAuthError(O2CloudException):
    """Authentication error."""

    def __init__(self, status):
        self.status = status
        super().__init__(f"Authentication failed: {status}")


class O2CloudAPIError(O2CloudException):
    """API error."""


class O2CloudTimeoutError(O2CloudException):
    """Timeout error."""


class O2CloudConnectionError(O2CloudException):
    """Connection error."""
