"""Settings of the door station that are on or off: its voice prompt, its BLC."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndoorStationConfigEntry
from .setting import SettingEntity, settings_of

# The station writes one setting at a time; each write is read back
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndoorStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a switch for each on/off setting the door station offers."""
    station = entry.runtime_data
    async_add_entities(
        SettingSwitch(station, setting) for setting in settings_of(station, "switch")
    )


class SettingSwitch(SettingEntity, SwitchEntity):
    """An on/off setting of the door station."""

    @property
    def is_on(self) -> bool | None:
        """Whether it is on."""
        current = self.current
        return current.value.lower() == "true" if current is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn it on."""
        await self.async_change("true")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn it off."""
        await self.async_change("false")
