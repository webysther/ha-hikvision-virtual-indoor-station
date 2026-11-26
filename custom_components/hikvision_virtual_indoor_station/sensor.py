"""The call of the door station: idle, ringing or answered."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndoorStationConfigEntry
from .const import CALL_STATES
from .entity import IndoorStationEntity
from .station import IndoorStation

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndoorStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the call sensor."""
    async_add_entities([CallSensor(entry.runtime_data)])


class CallSensor(IndoorStationEntity, SensorEntity):
    """Whether the door station is calling, and whether someone answered."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = CALL_STATES
    _attr_translation_key = "call"

    def __init__(self, station: IndoorStation) -> None:
        """Create the call sensor of a station."""
        super().__init__(station, "call")

    @property
    def native_value(self) -> str:
        """The state of the call."""
        return self.station.call_state
