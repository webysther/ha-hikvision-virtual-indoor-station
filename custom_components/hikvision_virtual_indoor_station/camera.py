"""The cameras of the door station: one per stream (with sound), and snapshots."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Final

from aiohikvision import HikvisionError, Stream, StreamId, StreamKind
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from PIL import Image  # Pillow comes with Home Assistant (its own requirement)

from . import IndoorStationConfigEntry
from .entity import IndoorStationEntity

if TYPE_CHECKING:
    from aiohikvision import Streaming

    from .station import IndoorStation

PARALLEL_UPDATES = 0

MAIN: Final = StreamId(1, 1)
"""The main stream of the door station: the camera it had before it had more."""

# The entities of the other streams, by their place in the channel
TRANSLATION_KEYS: Final = {
    StreamKind.SUB: "sub_stream",
    StreamKind.THIRD: "third_stream",
}

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
    """Add a camera for each stream of the door station."""
    station = entry.runtime_data
    if station.streaming is None:
        return
    # A door station that does not list its streams still has its main stream
    streams = station.streams or (Stream(MAIN),)
    async_add_entities(
        StreamCamera(station, station.streaming, stream) for stream in streams
    )


class StreamCamera(IndoorStationEntity, Camera):
    """A stream of the door: what the visitor shows and says.

    The main stream is the camera of the device (named as the door station); the others,
    lighter to play, start disabled: a door station serves few video sessions at once.
    """

    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self, station: IndoorStation, streaming: Streaming, door_stream: Stream
    ) -> None:
        """Create the camera of a stream."""
        main = door_stream.id == MAIN
        IndoorStationEntity.__init__(
            self, station, "camera" if main else f"camera_{door_stream.id.isapi}"
        )
        Camera.__init__(self)
        self.streaming = streaming
        self.door_stream = door_stream
        if main:
            self._attr_name = None
        else:
            self._attr_translation_key = TRANSLATION_KEYS.get(
                door_stream.kind, "stream"
            )
            self._attr_translation_placeholders = {"stream": door_stream.id.isapi}
            self._attr_entity_registry_enabled_default = False

    async def stream_source(self) -> str:
        """Return the RTSP address of the stream (played with WebRTC)."""
        return await self.streaming.rtsp_url(self.door_stream.id)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Take a snapshot of the stream, in the shape of the stream."""
        try:
            picture = await self.streaming.snapshot(self.door_stream.id)
        except HikvisionError:
            return None
        video = self.door_stream.video
        if video is None or not video.width or not video.height:
            return picture
        return await self.hass.async_add_executor_job(
            shaped_like_stream, picture, video.width, video.height
        )
