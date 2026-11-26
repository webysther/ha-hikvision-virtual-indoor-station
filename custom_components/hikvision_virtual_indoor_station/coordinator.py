"""Whether the door station answers: its entities are unavailable while it does not.

The calls are pushed over SIP; this only asks the door station what its outputs drive,
once a minute (HEALTH_INTERVAL): one small request, which tells whether it answers and
whether a door gained or lost its lock (its web page can change it at any time). It
also lets the station check whether its door still calls Home Assistant.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohikvision import DoorStation, Output
from aiohikvision.isapi.wire.faults import BadCredentials, BridgeFault, LockedOut
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, HEALTH_INTERVAL

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class HealthCoordinator(DataUpdateCoordinator[tuple[Output, ...]]):
    """Ask the door station what its outputs drive, once a minute."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, door: DoorStation
    ) -> None:
        """Check one door station."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=HEALTH_INTERVAL,
        )
        self.door = door

    async def _async_update_data(self) -> tuple[Output, ...]:
        """Ask the door station; a refused account asks to sign in again."""
        try:
            return await self.door.read_outputs()
        except (BadCredentials, LockedOut) as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except BridgeFault as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err
