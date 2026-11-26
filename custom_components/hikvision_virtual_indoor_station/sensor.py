"""The call of the door station, what its outputs and inputs do, and its load."""

from __future__ import annotations

from typing import Final

from aiohikvision import DoorStationInfo, Input, InputUse, Output, OutputUse
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndoorStationConfigEntry
from .const import CALL_STATES
from .entity import IndoorStationEntity
from .station import IndoorStation

PARALLEL_UPDATES = 0

# The states of an output sensor: what an output can drive.
OUTPUT_USES: Final = [use.value for use in OutputUse]
# The states of an input sensor: what an input can read.
INPUT_USES: Final = [use.value for use in InputUse]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndoorStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the call sensor, and the sensors of the outputs, inputs and load.

    An output or input has a sensor when its use can change; the load, where the door
    station says it.
    """
    station = entry.runtime_data
    assert station.health is not None  # created before the platforms
    load = station.health.data.load
    entities: list[SensorEntity] = [
        CallSensor(station),
        *(
            OutputSensor(station, output.number)
            for output in changeable_outputs(station.info)
        ),
        *(
            InputSensor(station, item.number)
            for item in changeable_inputs(station.info)
        ),
    ]
    if load.cpu_percent is not None:
        entities.append(CpuSensor(station))
    if load.video_sessions is not None:
        entities.append(VideoSessionsSensor(station))
    async_add_entities(entities)


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


def changeable_inputs(info: DoorStationInfo) -> list[Input]:
    """Return the inputs whose use can change, or all when the door station is silent.

    An input set to read nothing on one door station reads a door contact or an exit
    button on another.
    """
    return [item for item in info.inputs if len(item.options) != 1]


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


class InputSensor(IndoorStationEntity, SensorEntity):
    """What an input reads: a door contact, an exit button, or nothing."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = INPUT_USES
    _attr_translation_key = "input"

    def __init__(self, station: IndoorStation, number: int) -> None:
        """Create the sensor of one input."""
        super().__init__(station, f"input_{number}")
        self.number = number
        self._attr_translation_placeholders = {"input": str(number)}

    @property
    def native_value(self) -> str | None:
        """What the input reads, as last read."""
        found = next(
            (item for item in self.station.info.inputs if item.number == self.number),
            None,
        )
        return found.use.value if found is not None else None


class CpuSensor(IndoorStationEntity, SensorEntity):
    """How busy the processor of the door station is."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "cpu_usage"

    def __init__(self, station: IndoorStation) -> None:
        """Create the CPU sensor of a station."""
        super().__init__(station, "cpu_usage")

    @property
    def native_value(self) -> int | None:
        """The CPU usage, as last read."""
        return self.coordinator.data.load.cpu_percent


class VideoSessionsSensor(IndoorStationEntity, SensorEntity):
    """How many clients stream the door station's video (each one costs it CPU)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "video_sessions"

    def __init__(self, station: IndoorStation) -> None:
        """Create the video sessions sensor of a station."""
        super().__init__(station, "video_sessions")

    @property
    def native_value(self) -> int | None:
        """The number of video sessions, as last read."""
        return self.coordinator.data.load.video_sessions
