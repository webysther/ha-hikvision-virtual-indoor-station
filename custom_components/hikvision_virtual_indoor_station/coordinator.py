"""What is read from the door station over ISAPI, on two clocks.

The calls are pushed over SIP; the rest is polled:

- HealthCoordinator, once a minute (HEALTH_INTERVAL): what its outputs drive (its web
  page can change it at any time: a door may gain or lose its lock) and how loaded it is
  (its CPU, how many clients stream its video). Its entities are unavailable while the
  door station does not answer, and the station checks whether its door still calls.
- SettingsCoordinator, every few minutes (SETTINGS_INTERVAL): the values of its settings
  (image, volumes, how long each door stays open, its voice prompt) and what its inputs
  read. They change only when someone changes them, here or on its web page.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING

from aiohikvision import (
    DoorStation,
    DoorStationHealth,
    HikvisionError,
    ImageValue,
    Input,
    Output,
    Setting,
)
from aiohikvision.isapi.wire.faults import BadCredentials, LockedOut
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, HEALTH_INTERVAL, SETTINGS_INTERVAL

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
# Home Assistant logs every fetch of a coordinator at debug ("Finished fetching..."),
# once a minute here: the debug log of the integration keeps the failures and the
# recoveries (warning, error, info) without that line
_POLLING = logging.getLogger(f"{__name__}.polling")
_POLLING.setLevel(logging.INFO)


@dataclass(frozen=True, slots=True)
class Health:
    """What the door station's outputs drive, and how loaded it is."""

    outputs: tuple[Output, ...]
    load: DoorStationHealth = field(default_factory=DoorStationHealth)


@dataclass(frozen=True, slots=True)
class Settings:
    """The values of the door station's settings, by ``Setting.ref``, and its inputs."""

    values: dict[tuple[str, str], ImageValue]
    inputs: tuple[Input, ...] = ()


@contextmanager
def reading() -> Iterator[None]:
    """Translate the faults of a read: a refused account asks to sign in again."""
    try:
        yield
    except (BadCredentials, LockedOut) as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except HikvisionError as err:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err


class HealthCoordinator(DataUpdateCoordinator[Health]):
    """Ask the door station what its outputs drive and how loaded it is."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, door: DoorStation
    ) -> None:
        """Check one door station."""
        super().__init__(
            hass,
            _POLLING,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=HEALTH_INTERVAL,
        )
        self.door = door

    async def _async_update_data(self) -> Health:
        """Ask the door station."""
        with reading():
            return Health(await self.door.read_outputs(), await self.door.read_health())


class SettingsCoordinator(DataUpdateCoordinator[Settings]):
    """Read the values of the door station's settings, and its inputs."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        door: DoorStation,
        settings: tuple[Setting, ...],
    ) -> None:
        """Follow the settings the door station offers (fixed while it runs)."""
        super().__init__(
            hass,
            _POLLING,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title} settings",
            update_interval=SETTINGS_INTERVAL,
        )
        self.door = door
        self.settings = settings

    async def _async_update_data(self) -> Settings:
        """Read the settings and the inputs again."""
        with reading():
            return Settings(
                await self.door.read_setting_values(self.settings),
                await self.door.read_inputs(),
            )
