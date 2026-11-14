"""Exercise the configuration flow without importing Home Assistant."""

import importlib
import sys
import types
from urllib.parse import urlencode

import pytest
from o2pkg.oauth import REDIRECT_URI


@pytest.fixture
def flow_module(monkeypatch):
    class ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__()

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

        def _get_reauth_entry(self):
            return self.entry

        def async_update_reload_and_abort(self, entry, *, data_updates):
            return {"type": "abort", "entry": entry, "data_updates": data_updates}

    homeassistant = types.ModuleType("homeassistant")
    homeassistant.config_entries = types.SimpleNamespace(
        ConfigFlow=ConfigFlow, OptionsFlow=object, ConfigEntry=object
    )
    core = types.ModuleType("homeassistant.core")
    core.callback = lambda function: function
    helpers = types.ModuleType("homeassistant.helpers")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda hass: hass.session
    for name, module in {
        "homeassistant": homeassistant,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.aiohttp_client": aiohttp_client,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    sys.modules.pop("o2pkg.config_flow", None)
    module = importlib.import_module("o2pkg.config_flow")
    yield module
    sys.modules.pop("o2pkg.config_flow", None)


@pytest.mark.parametrize("reauth", [False, True])
async def test_browser_flow_and_reauth(flow_module, monkeypatch, reauth):
    tokens = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": "3600",
        "last_refresh_date": 1700000000000,
    }

    async def exchange(session, *, code, verifier):
        assert code == "code"
        assert verifier
        return tokens

    class Client:
        def __init__(self, **kwargs):
            self.oauth_tokens = kwargs["oauth_tokens"]
            self.validation_key = "session-key"
            self.cookies = {"JSESSIONID": "session-id"}

        async def test_connection(self):
            return True

    monkeypatch.setattr(flow_module, "exchange_tokens", exchange)
    monkeypatch.setattr(flow_module, "O2CloudClient", Client)
    flow = flow_module.O2CloudConfigFlow()
    flow.hass = types.SimpleNamespace(session=object())
    flow.entry = object()
    if reauth:
        form = await flow.async_step_reauth()
    else:
        form = await flow.async_step_user({"folder_name": "backups"})
    assert form["step_id"] == "authorize"
    invalid = await flow.async_step_authorize(
        {"callback_url": "https://evil.example/?code=code"}
    )
    assert invalid["errors"]["base"] == "invalid_callback"
    callback = REDIRECT_URI + "?" + urlencode({"code": "code", "state": flow._state})
    result = await flow.async_step_authorize({"callback_url": callback})
    data = result["data_updates"] if reauth else result["data"]
    assert data["oauth_tokens"] == tokens
    assert data["validation_key"] == "session-key"
    assert result["type"] == ("abort" if reauth else "create_entry")
    if not reauth:
        assert data["folder_name"] == "backups"


@pytest.mark.parametrize("failure", ["exchange", "missing_refresh", "sapi"])
async def test_authorization_failure_logs_stage_without_secrets(
    flow_module, monkeypatch, caplog, failure
):
    tokens = {
        "access_token": "secret-access",
        "refresh_token": "" if failure == "missing_refresh" else "secret-refresh",
        "expires_in": "3600",
        "last_refresh_date": 1700000000000,
    }

    async def exchange(session, *, code, verifier):
        if failure == "exchange":
            raise flow_module.OAuthError(403)
        return tokens

    class Client:
        def __init__(self, **kwargs):
            pass

        async def test_connection(self):
            return False

    monkeypatch.setattr(flow_module, "exchange_tokens", exchange)
    monkeypatch.setattr(flow_module, "O2CloudClient", Client)
    flow = flow_module.O2CloudConfigFlow()
    flow.hass = types.SimpleNamespace(session=object())
    await flow.async_step_user({"folder_name": "backups"})
    callback = (
        REDIRECT_URI + "?" + urlencode({"code": "secret-code", "state": flow._state})
    )
    result = await flow.async_step_authorize({"callback_url": callback})
    assert result["errors"]["base"] == "invalid_credentials"
    expected = {
        "exchange": "exchange failed (403)",
        "missing_refresh": "no refresh token",
        "sapi": "SAPI validation failed",
    }
    assert expected[failure] in caplog.text
    assert "secret-code" not in caplog.text
    assert "secret-access" not in caplog.text
    assert "secret-refresh" not in caplog.text
