"""Services for O2 Cloud Backup integration."""

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.service import verify_domain_control

from .client import O2CloudAPIError, O2CloudClient
from .const import (
    ATTR_FILE_PATH,
    ATTR_REMOTE_NAME,
    DOMAIN,
    SERVICE_REFRESH_QUOTA,
    SERVICE_TEST_CONNECTION,
    SERVICE_UPLOAD_BACKUP,
)

_LOGGER = logging.getLogger(__name__)

UPLOAD_BACKUP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_FILE_PATH): str,
        vol.Optional(ATTR_REMOTE_NAME): str,
    }
)

REFRESH_QUOTA_SCHEMA = vol.Schema({})

TEST_CONNECTION_SCHEMA = vol.Schema({})


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    async def handle_upload_backup(call: ServiceCall) -> None:
        """Handle backup upload service."""
        file_path = call.data.get(ATTR_FILE_PATH)
        remote_name = call.data.get(ATTR_REMOTE_NAME)

        if not file_path:
            _LOGGER.error("No file path provided")
            return

        try:
            # Get the integration client
            # Note: this assumes there is only one configuration, adjust as needed
            entries = hass.config_entries.async_entries(DOMAIN)
            if not entries:
                _LOGGER.error("No O2 Cloud entry found")
                return

            entry = entries[0]
            data = hass.data[DOMAIN][entry.entry_id]
            client: O2CloudClient = data["client"]
            coordinator = data["coordinator"]

            # Upload file
            import os
            if not os.path.exists(file_path):
                _LOGGER.error("File not found: %s", file_path)
                return

            _LOGGER.info("Uploading backup: %s", file_path)

            folder_id = await client.resolve_folder_id(
                entry.data.get("folder_name")
                or entry.data.get("folder_id")
                or "homeassistant"
            )
            result = await client.upload_file(
                file_path=file_path,
                folder_id=folder_id,
                remote_name=remote_name,
            )

            _LOGGER.info("Backup uploaded successfully: %s", result)

            # Refresh quota
            await coordinator.async_refresh()

        except O2CloudAPIError as err:
            _LOGGER.error("Upload failed: %s", err)
        except Exception as err:
            _LOGGER.error("Unexpected error during upload: %s", err)

    async def handle_refresh_quota(call: ServiceCall) -> None:
        """Handle quota refresh service."""
        try:
            entries = hass.config_entries.async_entries(DOMAIN)
            if not entries:
                _LOGGER.error("No O2 Cloud entry found")
                return

            entry = entries[0]
            data = hass.data[DOMAIN][entry.entry_id]
            coordinator = data["coordinator"]

            await coordinator.async_refresh()
            _LOGGER.info("Quota refreshed")

        except Exception as err:
            _LOGGER.error("Error refreshing quota: %s", err)

    async def handle_test_connection(call: ServiceCall) -> None:
        """Handle connection test service."""
        try:
            entries = hass.config_entries.async_entries(DOMAIN)
            if not entries:
                _LOGGER.error("No O2 Cloud entry found")
                return

            entry = entries[0]
            data = hass.data[DOMAIN][entry.entry_id]
            client: O2CloudClient = data["client"]

            result = await client.test_connection()
            _LOGGER.info("Connection test result: %s", result)

        except Exception as err:
            _LOGGER.error("Connection test failed: %s", err)

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPLOAD_BACKUP,
        verify_domain_control(hass, DOMAIN)(handle_upload_backup),
        schema=UPLOAD_BACKUP_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_QUOTA,
        verify_domain_control(hass, DOMAIN)(handle_refresh_quota),
        schema=REFRESH_QUOTA_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TEST_CONNECTION,
        verify_domain_control(hass, DOMAIN)(handle_test_connection),
        schema=TEST_CONNECTION_SCHEMA,
    )
