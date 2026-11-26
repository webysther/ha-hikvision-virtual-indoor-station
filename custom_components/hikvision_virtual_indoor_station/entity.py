"""The base of the entities of a door station."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HealthCoordinator
from .station import IndoorStation


class IndoorStationEntity(CoordinatorEntity[HealthCoordinator]):
    """An entity of the door station's device.

    It is available while the door station answers (HealthCoordinator), and written
    again when its station changes (a call, the registration).
    """

    _attr_has_entity_name = True

    def __init__(self, station: IndoorStation, key: str) -> None:
        """Name the entity by its key, on the door station's device."""
        assert station.health is not None  # created before the platforms
        super().__init__(station.health)
        self.station = station
        self._attr_unique_id = f"{station.unique_id}_{key}"
        self._attr_device_info = station.device_info

    async def async_added_to_hass(self) -> None:
        """Follow the station."""
        await super().async_added_to_hass()
        self.async_on_remove(self.station.async_add_listener(self.async_write_ha_state))
