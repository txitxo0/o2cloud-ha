"""O2 Cloud integration initialization."""

import json
import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import O2CloudClient
from .const import (
    CONF_COOKIES,
    CONF_FOLDER_ID,
    CONF_FOLDER_NAME,
    CONF_USER_AGENT,
    CONF_VALIDATION_KEY,
    DOMAIN,
)
from .coordinator import O2CloudCoordinator

_LOGGER = logging.getLogger(__name__)

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

    client = O2CloudClient(
        validation_key=entry.data[CONF_VALIDATION_KEY],
        cookies=cookies,
        user_agent=entry.data[CONF_USER_AGENT],
        session=session,
    )

    # Create coordinator
    coordinator = O2CloudCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "folder_id": entry.data.get(CONF_FOLDER_ID, "root"),
        "folder_name": entry.data.get(CONF_FOLDER_NAME, "homeassistant"),
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listener to reload when options change
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload integration."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["client"].close()

    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Listen for changes in options."""
    await hass.config_entries.async_reload(entry.entry_id)
