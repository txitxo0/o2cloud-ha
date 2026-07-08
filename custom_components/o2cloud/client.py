"""Cliente API para O2 Cloud."""

import asyncio
import json
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import aiohttp

from .const import (
    API_BASE_URL,
    REQUEST_TIMEOUT,
    UPLOAD_BASE_URL,
    UPLOAD_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class O2CloudClient:
    """Cliente para interactuar con la API de O2 Cloud."""

    def __init__(
        self,
        validation_key: str,
        cookies: Dict[str, str],
        user_agent: str,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        """Inicializar cliente."""
        self.validation_key = validation_key
        self.cookies = cookies if cookies else {}
        self.user_agent = user_agent
        self.session = session
        self._own_session = session is None
        
        # Log para debugging
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
        """Cerrar sesión."""
        if self._own_session and self.session:
            await self.session.close()

    def _get_headers(self) -> Dict[str, str]:
        """Obtener headers estándar.

        Nota: se mantienen mínimos a propósito. Reenviar Accept-Encoding con
        br/zstd o pseudo-headers HTTP/2 provoca respuestas 400 del backend.
        """
        return {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://cloud.o2online.es/",
            "X-Requested-With": "XMLHttpRequest",
        }

    def _build_query_params(self, **kwargs) -> str:
        """Construir parámetros de query con validationkey."""
        params = {**kwargs, "validationkey": self.validation_key}
        return urlencode(params)

    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Hacer request HTTP."""
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
                    _LOGGER.error(f"Auth failed (status {resp.status}): {text[:200]}")
                    raise O2CloudAuthError(f"Authentication failed: {resp.status}")

                if resp.status >= 400:
                    text = await resp.text()
                    raise O2CloudAPIError(f"API error {resp.status}: {text}")

                if resp.status == 204:
                    return {}

                content_type = resp.headers.get("content-type", "")
                if "application/json" in content_type:
                    return await resp.json()
                else:
                    return {"data": await resp.text()}

        except asyncio.TimeoutError:
            raise O2CloudTimeoutError("Request timeout")
        except aiohttp.ClientError as e:
            raise O2CloudConnectionError(f"Connection error: {e}")

    async def get_storage_space(self, include_soft_deleted: bool = False) -> Dict[str, Any]:
        """Obtener espacio de almacenamiento."""
        query = self._build_query_params(
            action="get-storage-space",
            softdeleted="true" if include_soft_deleted else "false",
        )
        url = f"{API_BASE_URL}media?{query}"

        result = await self._make_request("GET", url)

        # _make_request puede devolver el JSON ya parseado o {"data": texto_crudo}.
        # La API real responde: {"data": {quota,...}, "responsetime": ...}
        if isinstance(result, dict) and isinstance(result.get("data"), str):
            try:
                result = json.loads(result["data"])
            except json.JSONDecodeError:
                return result

        if isinstance(result, dict) and isinstance(result.get("data"), dict):
            return result["data"]
        return result

    async def list_folder(
        self,
        parent_id: str,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """Listar contenido de carpeta."""
        query = self._build_query_params(
            action="list",
            parentid=parent_id,
            limit=limit,
        )
        url = f"{API_BASE_URL}media/folder?{query}"

        return await self._make_request("GET", url)

    async def create_folder(
        self,
        parent_id: str,
        folder_name: str,
    ) -> Dict[str, Any]:
        """Crear carpeta."""
        query = self._build_query_params(action="save")
        url = f"{API_BASE_URL}media/folder?{query}"

        payload = {
            "parentid": parent_id,
            "name": folder_name,
        }

        return await self._make_request(
            "POST",
            url,
            json=payload,
        )

    async def upload_file(
        self,
        file_path: str,
        folder_id: str,
        remote_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Subir archivo a O2 Cloud."""
        if not remote_name:
            import os
            remote_name = os.path.basename(file_path)

        # Primer paso: obtener ID de upload
        query = self._build_query_params(action="init")
        init_url = f"{UPLOAD_BASE_URL}?{query}"

        init_resp = await self._make_request("POST", init_url)
        upload_id = init_resp.get("uploadid") or init_resp.get("uploadId")

        if not upload_id:
            raise O2CloudAPIError("No upload ID received from server")

        # Segundo paso: subir archivo
        import os
        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as f:
            files = {
                "file": (remote_name, f, "application/octet-stream"),
            }

            params = {
                "uploadid": upload_id,
                "folderid": folder_id,
            }
            query = self._build_query_params(**params)
            upload_url = f"{UPLOAD_BASE_URL}?{query}"

            result = await self._make_request(
                "POST",
                upload_url,
                data=files,
                timeout=UPLOAD_TIMEOUT,
            )

        return {
            "file_name": remote_name,
            "file_size": file_size,
            "upload_id": upload_id,
            "timestamp": result.get("timestamp"),
        }

    async def delete_file(
        self,
        file_id: str,
        soft_delete: bool = True,
    ) -> Dict[str, Any]:
        """Eliminar archivo."""
        query = self._build_query_params(
            action="delete",
            softdelete="true" if soft_delete else "false",
        )
        url = f"{API_BASE_URL}media/file?{query}"

        payload = {"fileid": file_id}

        return await self._make_request("POST", url, json=payload)

    async def test_connection(self) -> bool:
        """Probar conexión y validez de sesión."""
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
    """Excepción base para O2 Cloud."""

    pass


class O2CloudAuthError(O2CloudException):
    """Error de autenticación."""

    pass


class O2CloudAPIError(O2CloudException):
    """Error de API."""

    pass


class O2CloudTimeoutError(O2CloudException):
    """Error de timeout."""

    pass


class O2CloudConnectionError(O2CloudException):
    """Error de conexión."""

    pass
