"""Buttons of the door station: open each door; answer, hang up or refuse its call."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndoorStationConfigEntry
from .entity import IndoorStationEntity
from .station import IndoorStation

# The station orders its commands itself (one call, one door relay at a time)
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CallButtonDescription(ButtonEntityDescription):
    """A button that acts on the current call."""

    press: Callable[[IndoorStation], Awaitable[object]]


CALL_BUTTONS = (
    CallButtonDescription(
        key="answer", translation_key="answer", press=lambda s: s.async_answer()
    ),
    CallButtonDescription(
        key="hang_up", translation_key="hang_up", press=lambda s: s.async_hangup()
    ),
    CallButtonDescription(
        key="reject", translation_key="reject", press=lambda s: s.async_reject()
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndoorStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a button per door, and the call buttons."""
    station = entry.runtime_data
    doors = station.info.doors or (1,)
    entities: list[ButtonEntity] = [
        OpenDoorButton(station, door, numbered=len(doors) > 1) for door in doors
    ]
    entities.extend(CallButton(station, description) for description in CALL_BUTTONS)
    async_add_entities(entities)


class OpenDoorButton(IndoorStationEntity, ButtonEntity):
    """Open a door through its lock relay."""

    def __init__(self, station: IndoorStation, door: int, *, numbered: bool) -> None:
        """Create the button of one door; with several doors, each is numbered."""
        super().__init__(station, f"open_door_{door}")
        self.door = door
        if numbered:
            self._attr_translation_key = "open_door_numbered"
            self._attr_translation_placeholders = {"door": str(door)}
        else:
            self._attr_translation_key = "open_door"

    @property
    def available(self) -> bool:
        """Unavailable while its output drives no lock (a doorbell, or nothing)."""
        return super().available and self.door in self.station.info.locks

    async def async_press(self) -> None:
        """Open the door."""
        await self.station.async_open_door(self.door)


class CallButton(IndoorStationEntity, ButtonEntity):
    """Answer, hang up or refuse the current call."""

    entity_description: CallButtonDescription

    def __init__(
        self, station: IndoorStation, description: CallButtonDescription
    ) -> None:
        """Create a call button of a station."""
        super().__init__(station, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Act on the call."""
        await self.entity_description.press(self.station)
