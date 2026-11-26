"""Hikvision Virtual Indoor Station: Home Assistant as a door station's indoor station.

Each entry is a door station. Its calls come over SIP, to a server shared by all entries
(sip.py); everything else (identity, doors, picture, speaker) is ISAPI, through
aiohikvision's DoorStation. The entities and the cards read and command an IndoorStation
(station.py).
"""

from __future__ import annotations

import asyncio
import socket

from aiohikvision import DoorStation, NotADoorStation
from aiohikvision.isapi.wire.faults import BadCredentials, BridgeFault, LockedOut
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from . import sip, websocket
from .const import DEFAULT_PORT, DOMAIN
from .coordinator import HealthCoordinator
from .station import IndoorStation

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.EVENT,
    Platform.SENSOR,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type IndoorStationConfigEntry = ConfigEntry[IndoorStation]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the commands of the cards."""
    websocket.async_register_commands(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: IndoorStationConfigEntry
) -> bool:
    """Reach the door station, then hear its calls."""
    host: str = entry.data[CONF_HOST]
    door = DoorStation(
        async_get_clientsession(hass),
        host,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        trusted=True,
    )
    try:
        info = await door.read_info()
    except (BadCredentials, LockedOut) as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except NotADoorStation as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="not_door_station"
        ) from err
    except BridgeFault as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    if entry.unique_id is not None and info.identity.stable_id != entry.unique_id:
        # The address now reaches another door station: reconfigure the entry
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="wrong_device",
            translation_placeholders={"host": host},
        )

    station = IndoorStation(hass, entry, door, info, await _address(host))
    station.health = HealthCoordinator(hass, entry, door)
    # The door station just answered: no second request before the first interval
    station.health.async_set_updated_data(None)
    entry.async_on_unload(
        station.health.async_add_listener(station.async_check_presence)
    )
    try:
        station.sip = await sip.async_acquire(hass, station)
    except OSError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="sip_port_in_use",
            translation_placeholders={"port": str(sip.PORT), "error": str(err)},
        ) from err
    entry.runtime_data = station
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: IndoorStationConfigEntry
) -> bool:
    """Stop hearing the door station; its call ends, and its talk."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        station = entry.runtime_data
        await sip.async_release(hass, station)
        await station.async_close()
    return unloaded


async def _address(host: str) -> str:
    """Find the IP address the door station calls from (SIP packets carry no name)."""
    try:
        found = await asyncio.get_running_loop().getaddrinfo(
            host, None, type=socket.SOCK_DGRAM
        )
    except OSError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err
    return str(found[0][4][0])
