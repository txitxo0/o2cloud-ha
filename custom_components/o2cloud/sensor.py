"""sensor platform for O2 Cloud Backup."""

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
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

# Bytes unit compatible with different Home Assistant versions.
try:
    from homeassistant.const import UnitOfDataSize

    _BYTES_UNIT = UnitOfDataSize.BYTES
except ImportError:  # HA < 2023.1
    _BYTES_UNIT = "B"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]

    sensors = [
        O2CloudTotalBytes(coordinator, config_entry),
        O2CloudUsedBytes(coordinator, config_entry),
        O2CloudFreeBytes(coordinator, config_entry),
        O2CloudUsedPercent(coordinator, config_entry),
        O2CloudLastUpdateSensor(coordinator, config_entry),
    ]

    async_add_entities(sensors)


class O2CloudSensorBase(CoordinatorEntity):
    """Base class for O2 Cloud sensors."""

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


class O2CloudTotalBytes(O2CloudSensorBase, SensorEntity):
    """Total capacity sensor."""

    _attr_unique_id = "o2cloud_total_bytes"
    _attr_native_unit_of_measurement = _BYTES_UNIT
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:cloud"
    _attr_translation_key = "total_bytes"

    @property
    def native_value(self) -> float | None:
        """Return value."""
        if self.coordinator.data:
            return self.coordinator.data.get("total_bytes")
        return None


class O2CloudUsedBytes(O2CloudSensorBase, SensorEntity):
    """Used capacity sensor."""

    _attr_unique_id = "o2cloud_used_bytes"
    _attr_native_unit_of_measurement = _BYTES_UNIT
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:cloud-check"
    _attr_translation_key = "used_bytes"

    @property
    def native_value(self) -> float | None:
        """Return value."""
        if self.coordinator.data:
            return self.coordinator.data.get("used_bytes")
        return None


class O2CloudFreeBytes(O2CloudSensorBase, SensorEntity):
    """Free capacity sensor."""

    _attr_unique_id = "o2cloud_free_bytes"
    _attr_native_unit_of_measurement = _BYTES_UNIT
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:cloud-upload"
    _attr_translation_key = "free_bytes"

    @property
    def native_value(self) -> float | None:
        """Return value."""
        if self.coordinator.data:
            total = self.coordinator.data.get("total_bytes", 0)
            used = self.coordinator.data.get("used_bytes", 0)
            return total - used
        return None


class O2CloudUsedPercent(O2CloudSensorBase, SensorEntity):
    """Used percentage sensor."""

    _attr_unique_id = "o2cloud_used_percent"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:percent"
    _attr_translation_key = "used_percent"

    @property
    def native_value(self) -> float | None:
        """Return value."""
        if self.coordinator.data:
            total = self.coordinator.data.get("total_bytes", 0)
            used = self.coordinator.data.get("used_bytes", 0)
            if total > 0:
                return round((used / total) * 100, 2)
        return None


class O2CloudLastUpdateSensor(O2CloudSensorBase, SensorEntity):
    """Last update sensor."""

    _attr_unique_id = "o2cloud_last_update"
    _attr_icon = "mdi:clock"
    _attr_translation_key = "last_update"

    @property
    def native_value(self) -> str | None:
        """Return value."""
        if self.coordinator.data:
            import datetime

            timestamp = self.coordinator.data.get("last_update")
            if timestamp:
                return datetime.datetime.fromtimestamp(timestamp).isoformat()
        return None
