"""Backup support for O2 Cloud."""

import asyncio
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
from .const import CONF_MAX_UPLOAD_SIZE_MB, DEFAULT_MAX_UPLOAD_SIZE_MB, DOMAIN

_LOGGER = logging.getLogger(__name__)

CACHE_TTL = 300
METADATA_SUFFIX = ".metadata.json"
BACKUP_SUFFIX = ".tar"
# O2 rejects single files over ~4 GiB (MED-1020). Larger backups are split
# into ``<backup_id>.tar.partNNN`` pieces and reassembled on download.
PART_INFIX = ".tar.part"


def _as_int(value: Any, default: int = 0) -> int:
    """Convert an id (number or string) to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _part_name(backup_id: str, index: int) -> str:
    """Name of the Nth split part of a backup's .tar."""
    return f"{backup_id}{PART_INFIX}{index:03d}"


class _StreamSplitter:
    """Slice a single byte stream into consecutive fixed-size sub-streams.

    Each ``part(n)`` call yields exactly ``n`` bytes pulled from the source
    (or fewer if the source ends), buffering any overflow that crosses a
    chunk boundary for the next part.
    """

    def __init__(self, source: AsyncIterator[bytes]) -> None:
        self._source = source
        self._leftover = b""
        self._done = False

    async def _next_chunk(self) -> bytes:
        if self._leftover:
            chunk = self._leftover
            self._leftover = b""
            return chunk
        if self._done:
            return b""
        try:
            return await self._source.__anext__()
        except StopAsyncIteration:
            self._done = True
            return b""

    async def part(self, size: int) -> AsyncIterator[bytes]:
        """Yield exactly ``size`` bytes (or until the source is exhausted)."""
        remaining = size
        while remaining > 0:
            chunk = await self._next_chunk()
            if not chunk:
                return
            if len(chunk) > remaining:
                self._leftover = chunk[remaining:]
                chunk = chunk[:remaining]
            remaining -= len(chunk)
            yield chunk



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
        except (BackupAgentError, BackupNotFound):
            # Already-typed backup errors (e.g. BackupNotFound) must reach the
            # backup manager unchanged; do not mask them as "Unexpected error".
            raise
        except O2CloudAuthError as err:
            _LOGGER.error("Authentication error in %s: %s", func.__name__, err)
            raise BackupAgentError(f"Authentication error: {err}") from err
        except O2CloudAPIError as err:
            _LOGGER.error("API error in %s: %s", func.__name__, err)
            raise BackupAgentError(f"API error: {err}") from err
        except O2CloudTimeoutError as err:
            _LOGGER.error("Timeout in %s: %s", func.__name__, err)
            raise BackupAgentError(f"Timeout during operation: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error in %s", func.__name__)
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
        # Seed the lock in the initial data dict; it migrates to the current
        # dict automatically via _lock after any config-entry reload.
        if "_backup_lock" not in data:
            data["_backup_lock"] = asyncio.Lock()

        self.name = "O2 Cloud Backup"
        self.unique_id = entry_id

    @property
    def _current_data(self) -> dict[str, Any]:
        """Always return the live entry data dict.

        HA's backup manager caches BackupAgent instances across operations.
        After a re-auth / config-entry reload async_setup_entry replaces the
        dict entirely, so we must look it up fresh each time instead of
        caching a reference at __init__ time.
        """
        return self._hass.data.get(DOMAIN, {}).get(self._entry_id, {})

    @property
    def _client(self) -> O2CloudClient:
        return self._current_data["client"]

    @property
    def _folder_name(self) -> str:
        return self._current_data.get("folder_name", "homeassistant")

    @property
    def _lock(self) -> asyncio.Lock:
        """Shared single-flight lock; created on demand after a reload."""
        data = self._current_data
        if "_backup_lock" not in data:
            data["_backup_lock"] = asyncio.Lock()
        return data["_backup_lock"]

    def _part_size_bytes(self) -> int:
        """Max bytes per uploaded file; larger backups are split into parts."""
        mb = self._current_data.get(CONF_MAX_UPLOAD_SIZE_MB, DEFAULT_MAX_UPLOAD_SIZE_MB)
        return _as_int(mb, DEFAULT_MAX_UPLOAD_SIZE_MB) * 1024 * 1024

    async def _get_folder_id(self) -> int:
        """Resolve (and cache) the numeric id of the backups folder."""
        data = self._current_data
        folder_id = data.get("_resolved_folder_id")
        if folder_id is None:
            folder_id = await self._client.resolve_folder_id(self._folder_name)
            data["_resolved_folder_id"] = folder_id
            _LOGGER.debug(
                "Backups folder '%s' resolved to id %s",
                self._folder_name,
                folder_id,
            )
        return folder_id


    @handle_backup_errors
    @override
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups on O2 Cloud."""
        # Serialize concurrent listings: the first caller populates the cache
        # and the rest read it, instead of every poll triggering a full
        # (paginated, multi-thousand item) enumeration of the account.
        async with self._lock:
            data = self._current_data
            if time() <= data.get("_backup_cache_exp", 0.0):
                return list(data.get("_backup_cache", {}).values())

            _LOGGER.debug("Listing backups on O2 Cloud")
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

            data["_backup_cache"] = backups
            data["_backup_cache_exp"] = time() + CACHE_TTL
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
        part_prefix = f"{backup_id}{PART_INFIX}"

        _LOGGER.debug("Deleting backup %s from O2 Cloud", backup_id)

        media = await self._client.get_all_media()
        deleted = False
        for item in media:
            name = item.get("name") or ""
            if name not in (tar_name, metadata_name) and not name.startswith(
                part_prefix
            ):
                continue
            if _media_folder_id(item) != folder_id:
                continue
            try:
                await self._client.delete_file(item.get("id"))
                deleted = True
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Error deleting %s: %s", name, err)

        # Invalidate cache
        data = self._current_data
        data.get("_backup_cache", {}).pop(backup_id, None)
        data["_backup_cache_exp"] = 0.0

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

        # 1) Upload the .tar, reporting cumulative progress per chunk.
        #    on_progress is SYNCHRONOUS (no await).
        bytes_uploaded = 0

        async def _with_progress(
            source: AsyncIterator[bytes],
        ) -> AsyncIterator[bytes]:
            nonlocal bytes_uploaded
            async for chunk in source:
                yield chunk
                bytes_uploaded += len(chunk)
                on_progress(bytes_uploaded=bytes_uploaded)

        part_size = self._part_size_bytes()
        if backup.size <= part_size:
            # Small enough for a single file.
            media_id = await self._client.upload_metadata(
                tar_name, backup.size, folder_id
            )
            _LOGGER.debug(
                "Upload metadata saved for backup '%s' (media_id=%s, folder_id=%s)",
                backup.backup_id,
                media_id,
                folder_id,
            )
            await self._client.upload_stream(
                media_id, backup.size, _with_progress(await open_stream())
            )
        else:
            # Over O2's per-file limit: split into fixed-size parts.
            n_parts = -(-backup.size // part_size)  # ceil division
            _LOGGER.info(
                "Backup '%s' (%d bytes) exceeds part size %d; "
                "uploading in %d parts",
                backup.backup_id,
                backup.size,
                part_size,
                n_parts,
            )
            splitter = _StreamSplitter(await open_stream())
            for index in range(n_parts):
                this_size = min(part_size, backup.size - index * part_size)
                part_name = _part_name(backup.backup_id, index)
                part_media_id = await self._client.upload_metadata(
                    part_name, this_size, folder_id
                )
                _LOGGER.debug(
                    "Uploading part %d/%d '%s' (%d bytes, media_id=%s)",
                    index + 1,
                    n_parts,
                    part_name,
                    this_size,
                    part_media_id,
                )
                await self._client.upload_stream(
                    part_media_id,
                    this_size,
                    _with_progress(splitter.part(this_size)),
                )

        _LOGGER.debug("Backup uploaded, saving metadata")

        # 2) Upload the full AgentBackup metadata (in-memory JSON).
        meta_bytes = json.dumps(backup.as_dict()).encode("utf-8")

        async def _meta_stream() -> AsyncIterator[bytes]:
            yield meta_bytes

        meta_media_id = await self._client.upload_metadata(
            metadata_name, len(meta_bytes), folder_id
        )
        _LOGGER.debug(
            "Backup metadata file prepared for '%s' (media_id=%s)",
            backup.backup_id,
            meta_media_id,
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
        _data = self._current_data
        cache = _data.setdefault("_backup_cache", {})
        cache[backup.backup_id] = backup
        _data["_backup_cache_exp"] = time() + CACHE_TTL

    @override
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup from O2 Cloud."""
        await self.async_get_backup(backup_id)
        folder_id = await self._get_folder_id()
        tar_name = f"{backup_id}{BACKUP_SUFFIX}"
        part_prefix = f"{backup_id}{PART_INFIX}"

        _LOGGER.info("Downloading backup '%s' from O2 Cloud", backup_id)

        try:
            media = await self._client.get_all_media()
        except O2CloudAuthError as err:
            raise BackupAgentError("Authentication error") from err
        except (O2CloudAPIError, O2CloudTimeoutError) as err:
            raise BackupAgentError("Error downloading backup") from err

        # A backup is stored either as a single <id>.tar or, when it exceeded
        # the per-file limit, as ordered <id>.tar.partNNN pieces.
        single_url = None
        parts: list[tuple[str, str]] = []
        for item in media:
            name = item.get("name") or ""
            if _media_folder_id(item) != folder_id:
                continue
            url = item.get("url")
            if not url:
                continue
            if name == tar_name:
                single_url = url
            elif name.startswith(part_prefix):
                parts.append((name, url))

        if single_url:
            async for chunk in self._client.download(single_url):
                yield chunk
            return

        if parts:
            for _name, url in sorted(parts):
                async for chunk in self._client.download(url):
                    yield chunk
            return

        raise BackupNotFound(f"Backup {backup_id} not found on O2 Cloud")


