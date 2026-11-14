"""Config flow for O2 Cloud Backup integration."""

import json
import logging
import secrets
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import O2CloudClient
from .const import (
    CLOUD_PROVIDERS,
    CONF_COOKIES,
    CONF_DEVICE_ID,
    CONF_FOLDER_ID,
    CONF_FOLDER_NAME,
    CONF_INCLUDE_SOFT_DELETED,
    CONF_OAUTH_TOKENS,
    CONF_PROVIDER,
    CONF_REFRESH_INTERVAL,
    CONF_UNIQUE_ENTITIES,
    CONF_USER_AGENT,
    CONF_VALIDATION_KEY,
    DEFAULT_PROVIDER,
    DOMAIN,
)
from .oauth import (
    SAPI_USER_AGENT,
    OAuthError,
    build_login_url,
    exchange_tokens,
    parse_callback,
)

_LOGGER = logging.getLogger(__name__)


class O2CloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for O2 Cloud Backup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the user configuration step."""
        if user_input is not None:
            self._folder_name = user_input.get(CONF_FOLDER_NAME, "homeassistant")
            self._provider = user_input.get(CONF_PROVIDER, DEFAULT_PROVIDER)
            return await self.async_step_authorize()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVIDER, default=DEFAULT_PROVIDER): vol.In(
                        {key: value["name"] for key, value in CLOUD_PROVIDERS.items()}
                    ),
                    vol.Optional(CONF_FOLDER_NAME, default="homeassistant"): str,
                }
            ),
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle reauthentication."""
        self._reauth_entry = self._get_reauth_entry()
        self._provider = self._reauth_entry.data.get(CONF_PROVIDER, DEFAULT_PROVIDER)
        return await self.async_step_authorize()

    async def async_step_authorize(self, user_input=None):
        """Authorize in the provider's browser and paste the callback URL."""
        errors = {}
        if not hasattr(self, "_auth_url"):
            self._auth_url, self._verifier, self._state = build_login_url(
                self._provider
            )
        if user_input is not None:
            try:
                code = parse_callback(
                    user_input["callback_url"], self._state, self._provider
                )
                session = async_get_clientsession(self.hass)
                tokens = await exchange_tokens(
                    session, code=code, verifier=self._verifier, provider=self._provider
                )
                if not tokens["refresh_token"]:
                    raise OAuthError("no refresh token")
                device_id = "fol-" + secrets.token_urlsafe(16)
                client = O2CloudClient(
                    validation_key="",
                    cookies={},
                    user_agent=SAPI_USER_AGENT,
                    session=session,
                    oauth_tokens=tokens,
                    device_id=device_id,
                    provider=self._provider,
                )
                if not await client.test_connection():
                    _LOGGER.warning(
                        "OAuth token exchange succeeded, but SAPI validation failed"
                    )
                    errors["base"] = "invalid_credentials"
                else:
                    data = {
                        CONF_PROVIDER: self._provider,
                        CONF_VALIDATION_KEY: client.validation_key,
                        CONF_COOKIES: json.dumps(client.cookies),
                        CONF_USER_AGENT: SAPI_USER_AGENT,
                        CONF_OAUTH_TOKENS: client.oauth_tokens,
                        CONF_DEVICE_ID: device_id,
                    }
                    entry = getattr(self, "_reauth_entry", None)
                    if entry:
                        return self.async_update_reload_and_abort(
                            entry, data_updates=data
                        )
                    data.update(
                        {
                            CONF_FOLDER_NAME: self._folder_name,
                            CONF_FOLDER_ID: "root",
                            CONF_UNIQUE_ENTITIES: True,
                        }
                    )
                    return self.async_create_entry(
                        title=f"{CLOUD_PROVIDERS[self._provider]['name']} Backup",
                        data=data,
                    )
            except ValueError:
                errors["base"] = "invalid_callback"
            except OAuthError as err:
                _LOGGER.warning("OAuth token exchange failed (%s)", err.args[0])
                errors["base"] = "invalid_credentials"
            except Exception:
                _LOGGER.exception("O2 Cloud authorization failed")
                errors["base"] = "cannot_connect"
            if errors.get("base") != "invalid_callback":
                self._auth_url, self._verifier, self._state = build_login_url(
                    self._provider
                )
        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema({vol.Required("callback_url"): str}),
            description_placeholders={
                "auth_url": self._auth_url,
                "provider": CLOUD_PROVIDERS[self._provider]["name"],
            },
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return options flow."""
        return O2CloudOptionsFlow(config_entry)


class O2CloudOptionsFlow(config_entries.OptionsFlow):
    """Options flow for O2 Cloud Backup."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_REFRESH_INTERVAL,
                    default=self.config_entry.options.get(CONF_REFRESH_INTERVAL, 30),
                ): vol.In([15, 30, 60, 120]),
                vol.Optional(
                    CONF_INCLUDE_SOFT_DELETED,
                    default=self.config_entry.options.get(
                        CONF_INCLUDE_SOFT_DELETED, False
                    ),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
