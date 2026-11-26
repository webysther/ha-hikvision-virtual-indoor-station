"""Whether the door station's VoIP line is registered here (so that it can call)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndoorStationConfigEntry
from .entity import IndoorStationEntity
from .station import IndoorStation

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndoorStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the registration sensor."""
    async_add_entities([RegisteredSensor(entry.runtime_data)])


class RegisteredSensor(IndoorStationEntity, BinarySensorEntity):
    """On while the door's VoIP line is registered; off, its button calls nobody."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "sip_registered"

    def __init__(self, station: IndoorStation) -> None:
        """Create the registration sensor of a station."""
        super().__init__(station, "sip_registered")

    @property
    def is_on(self) -> bool:
        """Whether the door is registered."""
        return self.station.registered
