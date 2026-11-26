"""Settings of the door station that are a level: image, volumes, door open time."""

from __future__ import annotations

from aiohikvision import Setting
from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndoorStationConfigEntry
from .setting import SettingEntity, settings_of
from .station import IndoorStation

# The station writes one setting at a time; each write is read back
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndoorStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a number for each level the door station offers."""
    station = entry.runtime_data
    async_add_entities(
        SettingNumber(station, setting) for setting in settings_of(station, "number")
    )


class SettingNumber(SettingEntity, NumberEntity):
    """A level of the door station, within the range it says."""

    _attr_native_step = 1

    def __init__(self, station: IndoorStation, setting: Setting) -> None:
        """Create the number of one setting."""
        super().__init__(station, setting)
        # A level always has its range (aiohikvision offers no level without one)
        capability = setting.capability
        self._attr_native_min_value = capability.minimum or 0
        self._attr_native_max_value = capability.maximum or 0
        if setting.spec.seconds:
            # A time is typed: its range is wide (a door may stay open up to minutes)
            self._attr_device_class = NumberDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
            self._attr_mode = NumberMode.BOX
        else:
            self._attr_mode = NumberMode.SLIDER

    @property
    def native_value(self) -> float | None:
        """The level now; None when the door station says something else."""
        current = self.current
        try:
            return float(current.value) if current is not None else None
        except ValueError:
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Change the level."""
        await self.async_change(str(round(value)))
