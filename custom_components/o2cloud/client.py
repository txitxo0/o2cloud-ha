"""API client for O2 Cloud."""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp

from .const import (
    API_BASE_URL,
    REQUEST_TIMEOUT,
    UPLOAD_BASE_URL,
    UPLOAD_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

# Page size when listing media (the API paginates 1000 at a time).
MEDIA_PAGE_SIZE = 1000
# Chunk size for streaming downloads.
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


def _compact_iso(timestamp: Optional[float] = None) -> str:
    """Date in compact ISO format (YYYYMMDDThhmmss) expected by the API."""
    dt = (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if timestamp is not None
        else datetime.now(timezone.utc)
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
        cookies: Dict[str, str],
        user_agent: str,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        """Initialize client."""
        self.validation_key = validation_key
        self.cookies = cookies if cookies else {}
        self.user_agent = user_agent
        self.session = session
        self._own_session = session is None
        
        # Log for debugging
        _LOGGER.debug(
            "O2CloudClient initialized with %d cookies, validation_key: %s...",
            len(self.cookies),
            validation_key[:10] if validation_key else "None"
        )

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

    def _get_headers(self) -> Dict[str, str]:
        """Get standard headers.

        Note: kept minimal on purpose. Forwarding Accept-Encoding with
        br/zstd or HTTP/2 pseudo-headers causes 400 responses from the backend.
        """
        return {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://cloud.o2online.es/",
            "X-Requested-With": "XMLHttpRequest",
        }

    def _build_query_params(self, **kwargs) -> str:
        """Build query parameters with validationkey."""
        params = {**kwargs, "validationkey": self.validation_key}
        return urlencode(params)

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
    ) -> Dict[str, Any]:
        """Make HTTP request.

        When ``parse_in_executor`` is set, a JSON body is parsed in a worker
        thread instead of on the event loop. This is important for large
        responses (e.g. listing tens of thousands of media items): parsing
        them inline would block the loop for seconds and starve other tasks.
        """
        if not self.session:
            raise RuntimeError("Session not initialized")

        headers = self._get_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        try:
            _LOGGER.debug(f"Making {method} request to {url} with {len(self.cookies)} cookies")
            
            async with self.session.request(
                method,
                url,
                headers=headers,
                cookies=self.cookies,
                timeout=aiohttp.ClientTimeout(total=kwargs.pop("timeout", REQUEST_TIMEOUT)),
                **kwargs,
            ) as resp:
                _LOGGER.debug(f"Response status: {resp.status}")

                if resp.status in (401, 403):
                    text = await resp.text()
                    _LOGGER.error(
                        "Auth failed (status %s) on %s %s: %s",
                        resp.status,
                        method,
                        url,
                        text[:200],
                    )
                    raise O2CloudAuthError(f"Authentication failed: {resp.status}")

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

        except asyncio.TimeoutError:
            raise O2CloudTimeoutError("Request timeout")
        except aiohttp.ClientError as e:
            raise O2CloudConnectionError(f"Connection error: {e}")

    async def get_storage_space(self, include_soft_deleted: bool = False) -> Dict[str, Any]:
        """Get storage space."""
        query = self._build_query_params(
            action="get-storage-space",
            softdeleted="true" if include_soft_deleted else "false",
        )
        url = f"{API_BASE_URL}media?{query}"

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

    async def get_all_folders(self) -> List[Dict[str, Any]]:
        """List ALL folders (flat list with id/name/parentid)."""
        query = self._build_query_params(action="get")
        url = f"{API_BASE_URL}media/folder?{query}"
        result = await self._make_request("POST", url)
        data = self._unwrap_data(result)
        if isinstance(data, dict) and isinstance(data.get("folders"), list):
            return data["folders"]
        return []

    async def get_all_media(self) -> List[Dict[str, Any]]:
        """List ALL files (paginated). Includes download url."""
        all_items: List[Dict[str, Any]] = []
        offset = 0
        while True:
            query = self._build_query_params(
                action="get",
                limit=MEDIA_PAGE_SIZE,
                offset=offset,
            )
            url = f"{API_BASE_URL}media?{query}"
            payload = {
                "data": {"fields": ["name", "size", "etag", "folderid", "url"]}
            }
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
        url = f"{API_BASE_URL}media/folder?{query}"
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
        mtime: Optional[float] = None,
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
        meta_url = f"{API_BASE_URL}upload/file?{query}"
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
        upload_url = f"{UPLOAD_BASE_URL}?{query}"
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
        remote_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a file from disk (reads in executor, uploads in streaming)."""
        loop = asyncio.get_running_loop()
        if not remote_name:
            remote_name = os.path.basename(file_path)

        file_size = await loop.run_in_executor(None, os.path.getsize, file_path)
        mtime = await loop.run_in_executor(None, os.path.getmtime, file_path)

        media_id = await self.upload_metadata(
            remote_name, file_size, folder_id, mtime
        )

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
        async with self.session.get(
            url,
            headers=self._get_headers(),
            cookies=self.cookies,
            timeout=aiohttp.ClientTimeout(total=UPLOAD_TIMEOUT),
        ) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise O2CloudAPIError(
                    f"Download error {resp.status}: {text[:200]}"
                )
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
    ) -> Dict[str, Any]:
        """Delete (move to trash) a file by its id."""
        query = self._build_query_params(
            action="softdelete" if soft_delete else "delete",
            id=str(file_id),
        )
        url = f"{API_BASE_URL}media?{query}"
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

    pass


class O2CloudAuthError(O2CloudException):
    """Authentication error."""

    pass


class O2CloudAPIError(O2CloudException):
    """API error."""

    pass


class O2CloudTimeoutError(O2CloudException):
    """Timeout error."""

    pass


class O2CloudConnectionError(O2CloudException):
    """Connection error."""

    pass
