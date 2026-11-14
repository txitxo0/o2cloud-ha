"""Tests for backup agent availability without Home Assistant."""

import importlib
import sys
import types

import pytest


@pytest.fixture
def backup_module(monkeypatch):
    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    backup = types.ModuleType("homeassistant.components.backup")
    core = types.ModuleType("homeassistant.core")
    backup.AgentBackup = type("AgentBackup", (), {})
    backup.BackupAgent = type("BackupAgent", (), {})
    backup.BackupAgentError = type("BackupAgentError", (Exception,), {})
    backup.BackupNotFound = type("BackupNotFound", (backup.BackupAgentError,), {})
    backup.OnProgressCallback = object
    core.HomeAssistant = object
    for name, module in {
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.backup": backup,
        "homeassistant.core": core,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    sys.modules.pop("o2pkg.backup", None)
    module = importlib.import_module("o2pkg.backup")
    yield module
    sys.modules.pop("o2pkg.backup", None)


async def test_cached_agent_handles_unloaded_and_reloaded_entry(backup_module):
    client = object()
    hass = types.SimpleNamespace(data={"o2cloud": {"entry": {"client": client}}})
    agent = backup_module.O2CloudBackupAgent(
        hass, "entry", hass.data["o2cloud"]["entry"]
    )
    assert agent._client is client
    del hass.data["o2cloud"]["entry"]
    with pytest.raises(
        backup_module.BackupAgentError, match="integration is not available"
    ):
        await agent.async_list_backups()
    replacement = object()
    hass.data["o2cloud"]["entry"] = {"client": replacement}
    assert agent._client is replacement
