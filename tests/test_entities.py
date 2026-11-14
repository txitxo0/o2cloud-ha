"""Test entity identity across cloud providers without Home Assistant."""

import importlib
import sys
import types

import pytest


@pytest.fixture
def entity_modules(monkeypatch):
    modules = {
        name: types.ModuleType(name)
        for name in (
            "homeassistant",
            "homeassistant.components",
            "homeassistant.components.sensor",
            "homeassistant.components.binary_sensor",
            "homeassistant.config_entries",
            "homeassistant.core",
            "homeassistant.helpers",
            "homeassistant.helpers.entity_platform",
            "homeassistant.helpers.update_coordinator",
            "homeassistant.const",
            "o2pkg.coordinator",
        )
    }
    modules["homeassistant.components.sensor"].SensorEntity = type(
        "SensorEntity", (), {}
    )
    modules["homeassistant.components.sensor"].SensorStateClass = types.SimpleNamespace(
        TOTAL="total", TOTAL_INCREASING="total_increasing", MEASUREMENT="measurement"
    )
    modules["homeassistant.components.binary_sensor"].BinarySensorEntity = type(
        "BinarySensorEntity", (), {}
    )
    modules["homeassistant.config_entries"].ConfigEntry = object
    modules["homeassistant.core"].HomeAssistant = object
    modules["homeassistant.helpers.entity_platform"].AddEntitiesCallback = object
    modules["homeassistant.const"].UnitOfDataSize = types.SimpleNamespace(BYTES="B")
    modules["o2pkg.coordinator"].O2CloudCoordinator = object

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

    modules[
        "homeassistant.helpers.update_coordinator"
    ].CoordinatorEntity = CoordinatorEntity
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    for name in ("o2pkg.sensor", "o2pkg.binary_sensor"):
        sys.modules.pop(name, None)
    sensor = importlib.import_module("o2pkg.sensor")
    binary = importlib.import_module("o2pkg.binary_sensor")
    yield sensor, binary
    for name in ("o2pkg.sensor", "o2pkg.binary_sensor"):
        sys.modules.pop(name, None)


def test_legacy_and_new_provider_entities_have_distinct_ids(entity_modules):
    sensor, binary = entity_modules
    legacy = types.SimpleNamespace(entry_id="old", data={"provider": "o2"})
    movistar = types.SimpleNamespace(
        entry_id="new", data={"provider": "movistar", "unique_entities": True}
    )
    coordinator = object()
    assert (
        sensor.O2CloudTotalBytes(coordinator, legacy)._attr_unique_id
        == "o2cloud_total_bytes"
    )
    assert (
        sensor.O2CloudTotalBytes(coordinator, movistar)._attr_unique_id
        == "new_o2cloud_total_bytes"
    )
    assert (
        binary.O2CloudSessionValid(coordinator, legacy)._attr_unique_id
        == "o2cloud_session_valid"
    )
    assert (
        binary.O2CloudSessionValid(coordinator, movistar)._attr_unique_id
        == "new_o2cloud_session_valid"
    )
    assert (
        sensor.O2CloudTotalBytes(coordinator, legacy).device_info["name"] == "O2 Cloud"
    )
    assert (
        sensor.O2CloudTotalBytes(coordinator, legacy).device_info["manufacturer"]
        == "O2 España"
    )
    assert (
        binary.O2CloudSessionValid(coordinator, movistar).device_info["name"]
        == "Movistar Cloud"
    )
