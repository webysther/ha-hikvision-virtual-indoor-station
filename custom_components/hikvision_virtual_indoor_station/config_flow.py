"""Add a door station by its address and an account; sign in again when refused."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohikvision import DoorStation, DoorStationInfo, HikvisionError, NotADoorStation
from aiohikvision.isapi.wire.faults import (
    BadCredentials,
    LockedOut,
    NotIsapi,
    Unreachable,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import DeviceSelector, DeviceSelectorConfig
import probatio

from .const import (
    CONF_DO_NOT_DISTURB,
    CONF_OPEN_DOOR,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    MOBILE_APP,
    SUBENTRY_EXTENSION,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)
# What each refusal of the device shows, the most specific first
ERRORS: tuple[tuple[type[HikvisionError], str], ...] = (
    (BadCredentials, "invalid_auth"),
    (LockedOut, "locked_out"),
    (NotADoorStation, "not_door_station"),
    (NotIsapi, "not_isapi"),
    (Unreachable, "cannot_connect"),
)
REAUTH_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)

# What an extension may do: changed at any time (reconfigure)
EXTENSION_SETTINGS = {
    probatio.Required(CONF_DO_NOT_DISTURB, default=False): bool,
    probatio.Required(CONF_OPEN_DOOR, default=True): bool,
}
EXTENSION_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE_ID): DeviceSelector(
            DeviceSelectorConfig(integration=MOBILE_APP)
        ),
        **EXTENSION_SETTINGS,
    }
)
EXTENSION_SETTINGS_SCHEMA = probatio.Schema(EXTENSION_SETTINGS)


class IndoorStationConfigFlow(ConfigFlow, domain=DOMAIN):
    """The config flow of a door station."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentries of a door station: the phones that ring with it."""
        return {SUBENTRY_EXTENSION: ExtensionSubentryFlow}

    async def _read(
        self, data: Mapping[str, Any]
    ) -> tuple[DoorStationInfo | None, str | None]:
        """Read what the door station is, or the error to show."""
        door = DoorStation(
            async_get_clientsession(self.hass),
            data[CONF_HOST],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            port=data.get(CONF_PORT, DEFAULT_PORT),
        )
        try:
            return await door.read_info(), None
        except HikvisionError as err:
            for fault, error in ERRORS:
                if isinstance(err, fault):
                    return None, error
            _LOGGER.exception("Unexpected answer of %s", data[CONF_HOST])
            return None, "unknown"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the door station's address and account."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**user_input, CONF_HOST: user_input[CONF_HOST].strip()}
            info, error = await self._read(data)
            if info is not None:
                await self.async_set_unique_id(info.identity.stable_id)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: data[CONF_HOST]}
                )
                return self.async_create_entry(
                    title=info.identity.name,
                    data={**data, CONF_PORT: DEFAULT_PORT},
                )
            errors["base"] = error or "unknown"
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start over when the door station refuses the stored account."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the account again."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            info, error = await self._read(data)
            if info is not None:
                await self.async_set_unique_id(info.identity.stable_id)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
            errors["base"] = error or "unknown"
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA, {CONF_USERNAME: entry.data[CONF_USERNAME]}
            ),
            description_placeholders={"host": entry.data[CONF_HOST]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address or the account of the door station."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            changes = {**user_input, CONF_HOST: user_input[CONF_HOST].strip()}
            info, error = await self._read({**entry.data, **changes})
            if info is not None:
                await self.async_set_unique_id(info.identity.stable_id)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates=changes)
            errors["base"] = error or "unknown"
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, user_input or dict(entry.data)
            ),
            errors=errors,
        )


class ExtensionSubentryFlow(ConfigSubentryFlow):
    """A phone with the Home Assistant app as an extension of the door station.

    Adding or changing an extension does not reload the door station: a call in
    progress goes on, and the next ring reads the extensions as they are.
    """

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose a phone, and what it may do."""
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            taken = (sub.unique_id for sub in self._get_entry().subentries.values())
            if device_id in taken:
                return self.async_abort(reason="already_configured")
            device = dr.async_get(self.hass).async_get(device_id)
            name = (device.name_by_user or device.name) if device else None
            return self.async_create_entry(
                title=name or device_id, data=user_input, unique_id=device_id
            )
        return self.async_show_form(step_id="user", data_schema=EXTENSION_SCHEMA)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change what the phone may do; another phone is another extension."""
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(), subentry, data_updates=user_input
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                EXTENSION_SETTINGS_SCHEMA, dict(subentry.data)
            ),
        )
