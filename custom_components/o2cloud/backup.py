"""Soporte de backup para O2 Cloud."""

import json
import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
from time import time
from typing import Any, Concatenate, override

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    OnProgressCallback,
)
from homeassistant.core import HomeAssistant

from .client import (
    O2CloudAPIError,
    O2CloudAuthError,
    O2CloudClient,
    O2CloudTimeoutError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CACHE_TTL = 300
METADATA_SUFFIX = ".metadata.json"
BACKUP_SUFFIX = ".tar"


def _as_int(value: Any, default: int = 0) -> int:
    """Convertir un id (número o string) a int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _media_folder_id(item: dict[str, Any]) -> int:
    """Obtener el id de carpeta de un item de media (campo folderid o folder)."""
    return _as_int(item.get("folderid", item.get("folder")))


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Retornar lista de agentes de backup."""
    agents = []
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        if "client" in data:
            agents.append(O2CloudBackupAgent(hass, entry_id, data))
    return agents


def handle_backup_errors(
    func: Callable[Concatenate["O2CloudBackupAgent", ...], Coroutine[Any, Any, Any]],
):
    """Decorator para manejar errores de backup."""

    @wraps(func)
    async def wrapper(
        self: "O2CloudBackupAgent", *args, **kwargs
    ) -> Any:
        try:
            return await func(self, *args, **kwargs)
        except O2CloudAuthError as err:
            _LOGGER.error("Authentication error: %s", err)
            raise BackupAgentError("Error de autenticación") from err
        except O2CloudAPIError as err:
            _LOGGER.error("API error: %s", err)
            raise BackupAgentError("Error de API") from err
        except O2CloudTimeoutError as err:
            _LOGGER.error("Timeout: %s", err)
            raise BackupAgentError("Timeout en la operación") from err
        except Exception as err:
            _LOGGER.error("Unexpected error: %s", err)
            raise BackupAgentError(f"Error inesperado: {err}") from err

    return wrapper


class O2CloudBackupAgent(BackupAgent):
    """Agente de backup para O2 Cloud."""

    domain = DOMAIN

    def __init__(
        self, hass: HomeAssistant, entry_id: str, data: dict[str, Any]
    ) -> None:
        """Inicializar agente de backup."""
        super().__init__()
        self._hass = hass
        self._entry_id = entry_id
        self._client: O2CloudClient = data["client"]
        self._folder_name = data.get("folder_name", "homeassistant")
        self._folder_id: int | None = None

        self.name = "O2 Cloud Backup"
        self.unique_id = entry_id
        
        self._cache_backups: dict[str, AgentBackup] = {}
        self._cache_expiration = 0.0

    async def _get_folder_id(self) -> int:
        """Resolver (y cachear) el id numérico de la carpeta de backups."""
        if self._folder_id is None:
            self._folder_id = await self._client.resolve_folder_id(
                self._folder_name
            )
            _LOGGER.debug(
                "Carpeta de backups '%s' resuelta a id %s",
                self._folder_name,
                self._folder_id,
            )
        return self._folder_id


    @handle_backup_errors
    @override
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """Listar backups en O2 Cloud."""
        _LOGGER.debug("Listando backups en O2 Cloud")

        if time() <= self._cache_expiration:
            return list(self._cache_backups.values())

        folder_id = await self._get_folder_id()
        media = await self._client.get_all_media()

        backups: dict[str, AgentBackup] = {}
        for item in media:
            name = item.get("name") or ""
            if not name.endswith(METADATA_SUFFIX):
                continue
            if _media_folder_id(item) != folder_id:
                continue
            url = item.get("url")
            if not url:
                continue
            try:
                raw = await self._client.download_bytes(url)
                backup = AgentBackup.from_dict(json.loads(raw))
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "No se pudo leer metadatos de backup '%s': %s", name, err
                )
                continue
            backups[backup.backup_id] = backup

        self._cache_backups = backups
        self._cache_expiration = time() + CACHE_TTL
        return list(backups.values())

    @handle_backup_errors
    @override
    async def async_get_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AgentBackup:
        """Obtener información de un backup específico."""
        backups = await self.async_list_backups()
        for backup in backups:
            if backup.backup_id == backup_id:
                return backup
        raise BackupNotFound(f"Backup {backup_id} no encontrado")

    @handle_backup_errors
    @override
    async def async_delete_backup(
        self, backup_id: str, **kwargs: Any
    ) -> None:
        """Eliminar un backup (archivo .tar y sus metadatos)."""
        folder_id = await self._get_folder_id()
        tar_name = f"{backup_id}{BACKUP_SUFFIX}"
        metadata_name = f"{backup_id}{METADATA_SUFFIX}"

        _LOGGER.debug("Eliminando backup %s de O2 Cloud", backup_id)

        media = await self._client.get_all_media()
        deleted = False
        for item in media:
            name = item.get("name") or ""
            if name not in (tar_name, metadata_name):
                continue
            if _media_folder_id(item) != folder_id:
                continue
            try:
                await self._client.delete_file(item.get("id"))
                deleted = True
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Error al eliminar %s: %s", name, err)

        # Invalidar cache
        self._cache_backups.pop(backup_id, None)
        self._cache_expiration = 0.0

        if deleted:
            _LOGGER.info("Backup %s eliminado de O2 Cloud", backup_id)

    @handle_backup_errors
    @override
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        on_progress: OnProgressCallback,
        **kwargs: Any,
    ) -> None:
        """Subir un backup a O2 Cloud (streaming directo, sin fichero temporal)."""
        _LOGGER.info(
            "Iniciando subida de backup '%s' (%d bytes) a O2 Cloud",
            backup.name,
            backup.size,
        )

        folder_id = await self._get_folder_id()
        tar_name = f"{backup.backup_id}{BACKUP_SUFFIX}"
        metadata_name = f"{backup.backup_id}{METADATA_SUFFIX}"

        # 1) Subir el .tar en streaming, reportando progreso por chunk.
        async def _progress_stream() -> AsyncIterator[bytes]:
            bytes_uploaded = 0
            stream = await open_stream()
            async for chunk in stream:
                yield chunk
                bytes_uploaded += len(chunk)
                # on_progress es SÍNCRONO (no await).
                on_progress(bytes_uploaded=bytes_uploaded)

        media_id = await self._client.upload_metadata(
            tar_name, backup.size, folder_id
        )
        await self._client.upload_stream(media_id, backup.size, _progress_stream())

        _LOGGER.debug("Backup subido, guardando metadatos")

        # 2) Subir los metadatos completos del AgentBackup (JSON en memoria).
        meta_bytes = json.dumps(backup.as_dict()).encode("utf-8")

        async def _meta_stream() -> AsyncIterator[bytes]:
            yield meta_bytes

        meta_media_id = await self._client.upload_metadata(
            metadata_name, len(meta_bytes), folder_id
        )
        await self._client.upload_stream(
            meta_media_id, len(meta_bytes), _meta_stream()
        )

        _LOGGER.info(
            "Backup '%s' subido correctamente a O2 Cloud (%d bytes)",
            backup.name,
            backup.size,
        )

        # Registrar el backup en cache para que las verificaciones
        # posteriores (async_get_backup / async_list_backups) lo encuentren
        # a pesar de la latencia de consistencia del listado remoto.
        self._cache_backups[backup.backup_id] = backup
        self._cache_expiration = time() + CACHE_TTL

    @override
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Descargar un backup de O2 Cloud."""
        await self.async_get_backup(backup_id)
        folder_id = await self._get_folder_id()
        tar_name = f"{backup_id}{BACKUP_SUFFIX}"

        _LOGGER.info("Descargando backup '%s' de O2 Cloud", backup_id)

        try:
            media = await self._client.get_all_media()
        except O2CloudAuthError as err:
            raise BackupAgentError("Error de autenticación") from err
        except (O2CloudAPIError, O2CloudTimeoutError) as err:
            raise BackupAgentError("Error al descargar backup") from err

        url = None
        for item in media:
            if (item.get("name") or "") != tar_name:
                continue
            if _media_folder_id(item) != folder_id:
                continue
            url = item.get("url")
            break

        if not url:
            raise BackupNotFound(
                f"Backup {backup_id} no encontrado en O2 Cloud"
            )

        async for chunk in self._client.download(url):
            yield chunk


