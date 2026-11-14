"""binary_sensor platform for O2 Cloud Backup."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CLOUD_PROVIDERS,
    CONF_PROVIDER,
    CONF_UNIQUE_ENTITIES,
    DEFAULT_PROVIDER,
    DOMAIN,
)
from .coordinator import O2CloudCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]

    sensors = [
        O2CloudSessionValid(coordinator, config_entry),
    ]

    async_add_entities(sensors)


class O2CloudSensorBase(CoordinatorEntity):
    """Base class for O2 Cloud binary sensors."""

    def __init__(self, coordinator: O2CloudCoordinator, config_entry: ConfigEntry):
        """Initialize sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_has_entity_name = True
        if config_entry.data.get(CONF_UNIQUE_ENTITIES):
            self._attr_unique_id = f"{config_entry.entry_id}_{self._attr_unique_id}"

    @property
    def device_info(self):
        """Return device info."""
        provider = CLOUD_PROVIDERS[
            self.config_entry.data.get(CONF_PROVIDER, DEFAULT_PROVIDER)
        ]
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": provider["name"],
            "manufacturer": provider["manufacturer"],
        }


class O2CloudSessionValid(O2CloudSensorBase, BinarySensorEntity):
    """Session status sensor."""

    _attr_unique_id = "o2cloud_session_valid"
    _attr_icon = "mdi:check-circle"
    _attr_translation_key = "session_valid"

    @property
    def is_on(self) -> bool:
        """Return whether it is active."""
        return self.coordinator.is_session_valid

    @property
    def available(self) -> bool:
        """Availability."""
        return True
