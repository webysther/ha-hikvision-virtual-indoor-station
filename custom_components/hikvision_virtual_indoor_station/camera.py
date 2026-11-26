"""The camera of the door station: its RTSP stream (with sound) and snapshots."""

from __future__ import annotations

import io
from typing import Final

from aiohikvision.isapi.wire.faults import BridgeFault
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from PIL import Image  # Pillow comes with Home Assistant (its own requirement)

from . import IndoorStationConfigEntry
from .entity import IndoorStationEntity
from .station import IndoorStation

PARALLEL_UPDATES = 0

# How much the shape of a picture may differ from the shape of its stream and be left as
# it is: sizes are rounded (1920x1080 and 1280x720 are both 16:9, 1366x768 nearly).
SHAPE_TOLERANCE: Final = 0.02
# The JPEG quality of a reshaped picture: well above Pillow's default (75), so redrawing
# it adds no visible loss to what the door station already compressed.
JPEG_QUALITY: Final = 90


def shaped_like_stream(picture: bytes, width: int, height: int) -> bytes:
    """Return a picture in the shape of its stream, width by height.

    A door station takes its pictures at a size of its own, not always in the shape of
    its stream: a DS-KD8003 takes them 11:9 of a 16:9 view, which squeezes the street.
    The picture keeps its height and takes the width of the live video's shape, so both
    show the door alike. A picture that cannot be read is left as it is.
    """
    shape = width / height
    try:
        with Image.open(io.BytesIO(picture)) as image:
            if abs(image.width / image.height / shape - 1) <= SHAPE_TOLERANCE:
                return picture
            reshaped = image.convert("RGB").resize(
                (round(image.height * shape), image.height), Image.Resampling.LANCZOS
            )
    except OSError:  # not a picture, or a truncated one
        return picture
    output = io.BytesIO()
    reshaped.save(output, format="JPEG", quality=JPEG_QUALITY)
    return output.getvalue()


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
        """Take a snapshot from the door station, in the shape of its stream."""
        try:
            picture = await self.station.door.snapshot()
        except BridgeFault:
            return None
        stream = self.station.info.stream
        if stream is None or not stream.width or not stream.height:
            return picture
        return await self.hass.async_add_executor_job(
            shaped_like_stream, picture, stream.width, stream.height
        )
