"""Backup support for O2 Cloud."""

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
    """Convert an id (number or string) to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _media_folder_id(item: dict[str, Any]) -> int:
    """Get the folder id of a media item (folderid or folder field)."""
    return _as_int(item.get("folderid", item.get("folder")))


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return list of backup agents."""
    agents = []
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        if "client" in data:
            agents.append(O2CloudBackupAgent(hass, entry_id, data))
    return agents


def handle_backup_errors(
    func: Callable[Concatenate["O2CloudBackupAgent", ...], Coroutine[Any, Any, Any]],
):
    """Decorator to handle backup errors."""

    @wraps(func)
    async def wrapper(
        self: "O2CloudBackupAgent", *args, **kwargs
    ) -> Any:
        try:
            return await func(self, *args, **kwargs)
        except O2CloudAuthError as err:
            _LOGGER.error("Authentication error: %s", err)
            raise BackupAgentError("Authentication error") from err
        except O2CloudAPIError as err:
            _LOGGER.error("API error: %s", err)
            raise BackupAgentError("API error") from err
        except O2CloudTimeoutError as err:
            _LOGGER.error("Timeout: %s", err)
            raise BackupAgentError("Timeout during operation") from err
        except Exception as err:
            _LOGGER.error("Unexpected error: %s", err)
            raise BackupAgentError(f"Unexpected error: {err}") from err

    return wrapper


class O2CloudBackupAgent(BackupAgent):
    """Backup agent for O2 Cloud."""

    domain = DOMAIN

    def __init__(
        self, hass: HomeAssistant, entry_id: str, data: dict[str, Any]
    ) -> None:
        """Initialize backup agent."""
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
        """Resolve (and cache) the numeric id of the backups folder."""
        if self._folder_id is None:
            self._folder_id = await self._client.resolve_folder_id(
                self._folder_name
            )
            _LOGGER.debug(
                "Backups folder '%s' resolved to id %s",
                self._folder_name,
                self._folder_id,
            )
        return self._folder_id


    @handle_backup_errors
    @override
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups on O2 Cloud."""
        _LOGGER.debug("Listing backups on O2 Cloud")

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
                    "Could not read backup metadata '%s': %s", name, err
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
        """Get information about a specific backup."""
        backups = await self.async_list_backups()
        for backup in backups:
            if backup.backup_id == backup_id:
                return backup
        raise BackupNotFound(f"Backup {backup_id} not found")

    @handle_backup_errors
    @override
    async def async_delete_backup(
        self, backup_id: str, **kwargs: Any
    ) -> None:
        """Delete a backup (.tar file and its metadata)."""
        folder_id = await self._get_folder_id()
        tar_name = f"{backup_id}{BACKUP_SUFFIX}"
        metadata_name = f"{backup_id}{METADATA_SUFFIX}"

        _LOGGER.debug("Deleting backup %s from O2 Cloud", backup_id)

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
                _LOGGER.warning("Error deleting %s: %s", name, err)

        # Invalidate cache
        self._cache_backups.pop(backup_id, None)
        self._cache_expiration = 0.0

        if deleted:
            _LOGGER.info("Backup %s deleted from O2 Cloud", backup_id)

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
        """Upload a backup to O2 Cloud (direct streaming, no temp file)."""
        _LOGGER.info(
            "Starting upload of backup '%s' (%d bytes) to O2 Cloud",
            backup.name,
            backup.size,
        )

        folder_id = await self._get_folder_id()
        tar_name = f"{backup.backup_id}{BACKUP_SUFFIX}"
        metadata_name = f"{backup.backup_id}{METADATA_SUFFIX}"

        # 1) Upload the .tar via streaming, reporting progress per chunk.
        async def _progress_stream() -> AsyncIterator[bytes]:
            bytes_uploaded = 0
            stream = await open_stream()
            async for chunk in stream:
                yield chunk
                bytes_uploaded += len(chunk)
                # on_progress is SYNCHRONOUS (no await).
                on_progress(bytes_uploaded=bytes_uploaded)

        media_id = await self._client.upload_metadata(
            tar_name, backup.size, folder_id
        )
        await self._client.upload_stream(media_id, backup.size, _progress_stream())

        _LOGGER.debug("Backup uploaded, saving metadata")

        # 2) Upload the full AgentBackup metadata (in-memory JSON).
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
            "Backup '%s' uploaded successfully to O2 Cloud (%d bytes)",
            backup.name,
            backup.size,
        )

        # Register the backup in cache so that subsequent checks
        # (async_get_backup / async_list_backups) find it despite the
        # consistency latency of the remote listing.
        self._cache_backups[backup.backup_id] = backup
        self._cache_expiration = time() + CACHE_TTL

    @override
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup from O2 Cloud."""
        await self.async_get_backup(backup_id)
        folder_id = await self._get_folder_id()
        tar_name = f"{backup_id}{BACKUP_SUFFIX}"

        _LOGGER.info("Downloading backup '%s' from O2 Cloud", backup_id)

        try:
            media = await self._client.get_all_media()
        except O2CloudAuthError as err:
            raise BackupAgentError("Authentication error") from err
        except (O2CloudAPIError, O2CloudTimeoutError) as err:
            raise BackupAgentError("Error downloading backup") from err

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
                f"Backup {backup_id} not found on O2 Cloud"
            )

        async for chunk in self._client.download(url):
            yield chunk


