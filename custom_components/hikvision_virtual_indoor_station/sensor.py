"""The call of the door station, and what its outputs drive."""

from __future__ import annotations

from typing import Final

from aiohikvision import DoorStationInfo, Output, OutputUse
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndoorStationConfigEntry
from .const import CALL_STATES
from .entity import IndoorStationEntity
from .station import IndoorStation

PARALLEL_UPDATES = 0

# The states of an output sensor: what an output can drive.
OUTPUT_USES: Final = [use.value for use in OutputUse]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndoorStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the call sensor, and one for each output whose use can change."""
    station = entry.runtime_data
    async_add_entities(
        [
            CallSensor(station),
            *(
                OutputSensor(station, output.number)
                for output in changeable_outputs(station.info)
            ),
        ]
    )


def changeable_outputs(info: DoorStationInfo) -> list[Output]:
    """Return the outputs whose use can change: those that offer several uses.

    When the door station does not say, those of its doors but the first: on a
    DS-KD8003 the first output always drives the lock of door 1.
    """
    return [
        output
        for output in info.outputs
        if len(output.options) > 1
        or (not output.options and output.number in info.doors and output.number > 1)
    ]


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


class OutputSensor(IndoorStationEntity, SensorEntity):
    """What an output drives: the lock of its door, a doorbell, or nothing.

    A door whose output drives no lock cannot be opened; its button is unavailable.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = OUTPUT_USES
    _attr_translation_key = "output"

    def __init__(self, station: IndoorStation, number: int) -> None:
        """Create the sensor of one output."""
        super().__init__(station, f"output_{number}")
        self.number = number
        self._attr_translation_placeholders = {"output": str(number)}

    @property
    def native_value(self) -> str | None:
        """What the output drives, as last read."""
        output = self.station.info.output_of(self.number)
        return output.use.value if output is not None else None
