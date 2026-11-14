"""O2 Cloud integration initialization."""

import json
import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import O2CloudClient
from .const import (
    CONF_COOKIES,
    CONF_DEVICE_ID,
    CONF_FOLDER_ID,
    CONF_FOLDER_NAME,
    CONF_OAUTH_TOKENS,
    CONF_PROVIDER,
    CONF_USER_AGENT,
    CONF_VALIDATION_KEY,
    DEFAULT_PROVIDER,
    DOMAIN,
)
from .coordinator import O2CloudCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: Final = ["sensor", "binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration (called when HA starts)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create client.
    # Use the shared HA client session (NOT async_create_clientsession):
    # sessions created per-entry are auto-closed on reload/reauth, which left
    # the client (and the backup agent) holding a closed session
    # ("RuntimeError: Session is closed"). Cookies are passed per-request, so
    # the shared session is safe here.
    session = async_get_clientsession(hass)

    # Parse cookies from JSON
    cookies_str = entry.data.get(CONF_COOKIES, "{}")
    try:
        cookies = (
            json.loads(cookies_str) if isinstance(cookies_str, str) else cookies_str
        )
    except json.JSONDecodeError:
        cookies = {}

    def update_tokens(tokens):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_OAUTH_TOKENS: tokens}
        )

    client = O2CloudClient(
        validation_key=entry.data.get(CONF_VALIDATION_KEY, ""),
        cookies=cookies,
        user_agent=entry.data[CONF_USER_AGENT],
        session=session,
        oauth_tokens=entry.data.get(CONF_OAUTH_TOKENS),
        token_update=update_tokens,
        device_id=entry.data.get(CONF_DEVICE_ID, ""),
        provider=entry.data.get(CONF_PROVIDER, DEFAULT_PROVIDER),
    )

    # Create coordinator
    coordinator = O2CloudCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "folder_id": entry.data.get(CONF_FOLDER_ID, "root"),
        "folder_name": entry.data.get(CONF_FOLDER_NAME, "homeassistant"),
        CONF_PROVIDER: entry.data.get(CONF_PROVIDER, DEFAULT_PROVIDER),
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    options = dict(entry.options)

    async def options_updated(hass, updated_entry):
        nonlocal options
        if options != updated_entry.options:
            options = dict(updated_entry.options)
            await hass.config_entries.async_reload(updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload integration."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["client"].close()

    return unload_ok
