"""Config flow para integración O2 Cloud Backup."""

import json
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import O2CloudAuthError, O2CloudClient
from .const import (
    CONF_COOKIES,
    CONF_FOLDER_ID,
    CONF_FOLDER_NAME,
    CONF_INCLUDE_SOFT_DELETED,
    CONF_REFRESH_INTERVAL,
    CONF_USER_AGENT,
    CONF_VALIDATION_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONF_CREDENTIALS_JSON = "credentials_json"


def _merge_credentials_json(user_input: Dict[str, Any]) -> Dict[str, Any]:
    """Permitir pegar el contenido de o2_credentials.json en un solo campo.

    Si el usuario pega el JSON generado por extract_o2_credentials.py, se
    autocompletan validation_key, cookies y user_agent.
    """
    raw = (user_input.get(CONF_CREDENTIALS_JSON) or "").strip()
    if not raw:
        return user_input

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return user_input

    if not isinstance(data, dict):
        return user_input

    merged = dict(user_input)

    validation_key = (
        data.get("validation_key")
        or data.get("validationKey")
        or (data.get("cookies") or {}).get("validationKey")
    )
    if validation_key and not merged.get(CONF_VALIDATION_KEY):
        merged[CONF_VALIDATION_KEY] = validation_key

    if data.get("user_agent") and not merged.get(CONF_USER_AGENT):
        merged[CONF_USER_AGENT] = data["user_agent"]

    cookies = data.get("cookies")
    if cookies and not merged.get(CONF_COOKIES):
        merged[CONF_COOKIES] = json.dumps(cookies) if isinstance(cookies, dict) else cookies

    return merged


def _parse_cookies_input(raw: Any) -> dict[str, str]:
    """Parsear cookies desde JSON o string header Cookie."""
    if not raw:
        return {}

    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}

    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return {}

        # Intento 1: JSON
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError:
            pass

        # Intento 2: Header Cookie estándar
        cookies: dict[str, str] = {}
        for part in raw.split(";"):
            item = part.strip()
            if not item or "=" not in item:
                continue
            name, value = item.split("=", 1)
            cookies[name.strip()] = value.strip()
        return cookies

    return {}


class O2CloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow para O2 Cloud Backup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Manejo del paso de configuración del usuario."""
        errors = {}

        if user_input is not None:
            user_input = _merge_credentials_json(user_input)

            # Validar campos obligatorios (tras fusionar JSON pegado)
            if not user_input.get(CONF_VALIDATION_KEY) or not user_input.get(CONF_USER_AGENT):
                errors["base"] = "missing_fields"

        if user_input is not None and not errors:
            # Validar credenciales
            try:
                session = async_get_clientsession(self.hass)
                
                cookies = _parse_cookies_input(user_input.get(CONF_COOKIES, ""))
                
                client = O2CloudClient(
                    validation_key=user_input[CONF_VALIDATION_KEY],
                    cookies=cookies,
                    user_agent=user_input[CONF_USER_AGENT],
                    session=session,
                )

                # Probar conexión
                is_valid = await client.test_connection()
                if not is_valid:
                    errors["base"] = "invalid_credentials"
                else:
                    # Crear entry
                    return self.async_create_entry(
                        title="O2 Cloud Backup",
                        data={
                            CONF_VALIDATION_KEY: user_input[CONF_VALIDATION_KEY],
                            CONF_COOKIES: user_input.get(CONF_COOKIES, ""),
                            CONF_USER_AGENT: user_input[CONF_USER_AGENT],
                            CONF_FOLDER_NAME: user_input.get(CONF_FOLDER_NAME, "backups"),
                            CONF_FOLDER_ID: user_input.get(CONF_FOLDER_ID, "root"),
                        },
                        options={
                            CONF_REFRESH_INTERVAL: user_input.get(
                                CONF_REFRESH_INTERVAL, 30
                            ),
                            CONF_INCLUDE_SOFT_DELETED: user_input.get(
                                CONF_INCLUDE_SOFT_DELETED, False
                            ),
                        },
                    )

            except O2CloudAuthError:
                errors["base"] = "invalid_credentials"
            except Exception as err:
                _LOGGER.error("Unexpected error: %s", err)
                errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Optional(CONF_CREDENTIALS_JSON, default=""): str,
                vol.Optional(CONF_VALIDATION_KEY, default=""): str,
                vol.Optional(CONF_COOKIES, default=""): str,
                vol.Optional(CONF_USER_AGENT, default=""): str,
                vol.Optional(CONF_FOLDER_NAME, default="backups"): str,
                vol.Optional(CONF_FOLDER_ID, default="root"): str,
                vol.Optional(CONF_REFRESH_INTERVAL, default=30): int,
                vol.Optional(CONF_INCLUDE_SOFT_DELETED, default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "login_url": "https://cloud.o2online.es",
                "instructions": "Abre sesión en O2 Cloud, inspecciona red (F12 > Network), "
                "busca una request y extrae: validationkey, cookies y User-Agent",
            },
        )

    async def async_step_reauth(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Manejo de reautenticación."""
        config_entry = self._get_reauth_entry()
        errors: Dict[str, str] = {}

        if user_input is not None:
            user_input = _merge_credentials_json(user_input)
            if not user_input.get(CONF_VALIDATION_KEY) or not user_input.get(CONF_USER_AGENT):
                errors["base"] = "missing_fields"
            else:
                try:
                    session = async_get_clientsession(self.hass)
                    cookies = _parse_cookies_input(user_input.get(CONF_COOKIES, ""))
                    client = O2CloudClient(
                        validation_key=user_input[CONF_VALIDATION_KEY],
                        cookies=cookies,
                        user_agent=user_input[CONF_USER_AGENT],
                        session=session,
                    )

                    if await client.test_connection():
                        self.hass.config_entries.async_update_entry(
                            config_entry,
                            data={
                                **config_entry.data,
                                CONF_VALIDATION_KEY: user_input[CONF_VALIDATION_KEY],
                                CONF_COOKIES: user_input.get(CONF_COOKIES, ""),
                                CONF_USER_AGENT: user_input[CONF_USER_AGENT],
                            },
                        )
                        await self.hass.config_entries.async_reload(config_entry.entry_id)
                        return self.async_abort(reason="reauth_successful")

                    errors["base"] = "invalid_credentials"
                except Exception as err:
                    _LOGGER.error("Reauth failed: %s", err)
                    errors["base"] = "invalid_credentials"

        schema = vol.Schema(
            {
                vol.Optional(CONF_CREDENTIALS_JSON, default=""): str,
                vol.Optional(CONF_VALIDATION_KEY, default=""): str,
                vol.Optional(CONF_COOKIES, default=""): str,
                vol.Optional(CONF_USER_AGENT, default=""): str,
            }
        )

        return self.async_show_form(
            step_id="reauth",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Retornar options flow."""
        return O2CloudOptionsFlow(config_entry)


class O2CloudOptionsFlow(config_entries.OptionsFlow):
    """Options flow para O2 Cloud Backup."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Inicializar options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Manejo del paso inicial."""
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
                    default=self.config_entry.options.get(CONF_INCLUDE_SOFT_DELETED, False),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
