"""The camera of the door station: its RTSP stream (with sound) and snapshots."""

from __future__ import annotations

from aiohikvision.isapi.wire.faults import BridgeFault
from homeassistant.components.camera import Camera, CameraEntityFeature
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
    """Add the camera."""
    async_add_entities([DoorCamera(entry.runtime_data)])


class DoorCamera(IndoorStationEntity, Camera):
    """The picture and sound of the door: what the visitor shows and says."""

    _attr_name = None
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, station: IndoorStation) -> None:
        """Create the camera of a station."""
        IndoorStationEntity.__init__(self, station, "camera")
        Camera.__init__(self)

    async def stream_source(self) -> str:
        """Return the RTSP address of the main stream (played with WebRTC)."""
        return self.station.door.rtsp_url()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Take a snapshot from the door station."""
        try:
            return await self.station.door.snapshot()
        except BridgeFault:
            return None
