"""Coordinador de datos para O2 Cloud."""

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import O2CloudAPIError, O2CloudAuthError, O2CloudClient
from .const import COORDINATOR_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class O2CloudCoordinator(DataUpdateCoordinator):
    """Coordinador para actualizar datos de O2 Cloud."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: O2CloudClient,
        config_entry,
    ):
        """Inicializar coordinador."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=COORDINATOR_UPDATE_INTERVAL),
        )
        self.client = client
        self.config_entry = config_entry
        self.session_valid = True
        self.last_quota_update: Optional[float] = None

    async def _async_update_data(self) -> Dict[str, Any]:
        """Obtener datos actualizados."""
        try:
            # Obtener información de cuota
            quota_data = await self.client.get_storage_space(
                include_soft_deleted=self.config_entry.options.get(
                    "include_soft_deleted", False
                )
            )

            self.session_valid = True
            self.last_quota_update = self.hass.loop.time()

            # Parsear respuesta de O2 Cloud
            # La API devuelve algo como: {"quota": int, "used": int}
            # o {"total": int, "used": int}
            return {
                "total_bytes": quota_data.get("quota") or quota_data.get("total", 0),
                "used_bytes": quota_data.get("used", 0),
                "last_update": self.last_quota_update,
                "session_valid": True,
            }

        except O2CloudAuthError as err:
            _LOGGER.warning("Authentication failed, triggering reauth: %s", err)
            self.session_valid = False
            # ConfigEntryAuthFailed hace que HA inicie automáticamente el flujo de
            # reautenticación para volver a introducir credenciales frescas.
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err

        except O2CloudAPIError as err:
            _LOGGER.error("API error: %s", err)
            raise UpdateFailed(f"API error: {err}") from err

        except Exception as err:
            _LOGGER.error("Unexpected error: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err

    @property
    def is_session_valid(self) -> bool:
        """Retornar si la sesión es válida."""
        return self.session_valid
