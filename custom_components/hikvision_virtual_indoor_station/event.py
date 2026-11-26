"""The doorbell: an event at each step of a call (rang, answered, refused, ended...)."""

from __future__ import annotations

from aiohikvision import CallState, DoorCall, EndReason
from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndoorStationConfigEntry
from .const import (
    EVENT_ANSWERED,
    EVENT_ENDED,
    EVENT_MISSED,
    EVENT_REJECTED,
    EVENT_RING,
    EVENT_TYPES,
)
from .entity import IndoorStationEntity
from .station import IndoorStation

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndoorStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the doorbell of the door station."""
    async_add_entities([DoorbellEvent(entry.runtime_data)])


def event_type(call: DoorCall) -> str:
    """Return what a change of a call tells."""
    if call.state is CallState.RINGING:
        return EVENT_RING
    if call.state is CallState.ANSWERED:
        return EVENT_ANSWERED
    if call.answered_at is not None:
        return EVENT_ENDED
    return EVENT_REJECTED if call.end_reason is EndReason.REJECTED else EVENT_MISSED


class DoorbellEvent(IndoorStationEntity, EventEntity):
    """The doorbell of the door station."""

    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = EVENT_TYPES
    _attr_translation_key = "doorbell"

    def __init__(self, station: IndoorStation) -> None:
        """Create the doorbell of a station."""
        super().__init__(station, "doorbell")

    async def async_added_to_hass(self) -> None:
        """Hear the calls; the state is written only when an event is triggered."""
        self.async_on_remove(self.station.async_add_call_listener(self._call_changed))

    @callback
    def _call_changed(self, call: DoorCall) -> None:
        self._trigger_event(
            event_type(call),
            {
                "call_id": call.id,
                "caller": call.caller,
                "callee": call.callee,
                "end_reason": call.end_reason.value if call.end_reason else None,
            },
        )
        self.async_write_ha_state()
