"""Soporte de backup para O2 Cloud."""

from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
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

from .const import DOMAIN
from .client import (
    O2CloudClient,
    O2CloudAuthError,
    O2CloudAPIError,
    O2CloudTimeoutError,
)

_LOGGER = logging.getLogger(__name__)

CACHE_TTL = 300
METADATA_SUFFIX = ".metadata.json"
BACKUP_SUFFIX = ".tar"


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
        self._folder_id = data.get("folder_id", "root")

        self.name = "O2 Cloud Backup"
        self.unique_id = entry_id
        
        self._cache_backups: dict[str, AgentBackup] = {}
        self._cache_expiration = time()

    @handle_backup_errors
    @override
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """Listar backups en O2 Cloud."""
        # Buscar archivos .metadata.json en la carpeta de backups
        # Por ahora retorna lista vacía hasta implementar lista completa
        _LOGGER.debug("Listando backups en O2 Cloud")
        
        if time() <= self._cache_expiration:
            return list(self._cache_backups.values())
        
        # TODO: Implementar listado de metadatos desde O2 Cloud
        # Cuando O2 Cloud API lo permita
        
        return []

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
        """Eliminar un backup."""
        backup = await self.async_get_backup(backup_id)
        
        # Nombre del archivo de backup
        backup_filename = f"{backup.name}{BACKUP_SUFFIX}"
        metadata_filename = f"{backup.name}{METADATA_SUFFIX}"
        
        _LOGGER.debug("Eliminando backup %s de O2 Cloud", backup_filename)
        
        # Eliminar archivo de backup
        try:
            await self._client.delete_file(backup_filename)
        except Exception as err:
            _LOGGER.warning("Error al eliminar backup: %s", err)
        
        # Eliminar archivo de metadatos
        try:
            await self._client.delete_file(metadata_filename)
        except Exception as err:
            _LOGGER.warning("Error al eliminar metadatos: %s", err)
        
        # Invalidar cache
        self._cache_expiration = time()
        
        _LOGGER.info("Backup %s eliminado de O2 Cloud", backup.name)

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
        """Subir un backup a O2 Cloud."""
        _LOGGER.info(
            "Iniciando subida de backup '%s' (%d bytes) a O2 Cloud",
            backup.name,
            backup.size,
        )
        
        # Crear archivo temporal para el backup
        with TemporaryDirectory() as tmp_dir:
            tmp_file = Path(tmp_dir) / f"{backup.name}{BACKUP_SUFFIX}"
            
            # Escribir stream a archivo temporal
            bytes_written = 0
            async for chunk in await open_stream():
                tmp_file.write_bytes(tmp_file.read_bytes() + chunk)
                bytes_written += len(chunk)
                await on_progress(bytes_uploaded=bytes_written)
            
            # Subir archivo a O2 Cloud
            await self._client.upload_file(
                file_path=str(tmp_file),
                folder_id=self._folder_id,
                remote_name=f"{backup.name}{BACKUP_SUFFIX}",
            )
            
            _LOGGER.debug("Backup subido, guardando metadatos")
            
            # Guardar metadatos
            metadata = {
                "backup_id": backup.backup_id,
                "name": backup.name,
                "size": backup.size,
                "date": backup.date,
                "version": backup.version,
            }
            
            metadata_file = Path(tmp_dir) / f"{backup.name}{METADATA_SUFFIX}"
            metadata_file.write_text(json.dumps(metadata))
            
            await self._client.upload_file(
                file_path=str(metadata_file),
                folder_id=self._folder_id,
                remote_name=f"{backup.name}{METADATA_SUFFIX}",
            )
            
            _LOGGER.info(
                "Backup '%s' subido correctamente a O2 Cloud (%d bytes)",
                backup.name,
                bytes_written,
            )
        
        # Invalidar cache
        self._cache_expiration = time()

    @handle_backup_errors
    @override
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Descargar un backup de O2 Cloud."""
        backup = await self.async_get_backup(backup_id)
        backup_filename = f"{backup.name}{BACKUP_SUFFIX}"
        
        _LOGGER.info("Descargando backup '%s' de O2 Cloud", backup.name)
        
        # TODO: Implementar descarga cuando O2 Cloud API lo permita
        # Por ahora solo retorna error
        raise BackupNotFound(f"Descarga de backup {backup_id} no implementada")
        
        # Esto solo está aquí para cumplir con el tipo de retorno
        yield b""

