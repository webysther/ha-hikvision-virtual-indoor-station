"""Fixtures: the door station mocked at the boundary of aiohikvision, as HA tests do.

The library's own tests run it against doubles of the measured devices; here the
DoorStation (ISAPI) is a mock, and the CallServer (SIP) a double whose calls the tests
ring, answer and end.
"""

from __future__ import annotations

from collections.abc import Generator
import time
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

from aiohikvision import (
    CallError,
    CallState,
    DoorCall,
    DoorStationHealth,
    DoorStationInfo,
    EndReason,
    TalkbackStats,
)
from aiohikvision.isapi.model.features.inputs import Input, InputUse
from aiohikvision.isapi.model.features.outputs import Output, OutputUse
from aiohikvision.isapi.model.features.talk import TalkChannel
from aiohikvision.isapi.model.inventory import Identity
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hikvision_virtual_indoor_station.const import DOMAIN

# Documentation addresses (RFC 5737): no real network is described here
DOOR_IP = "192.0.2.10"
HA_IP = "192.0.2.20"
PACKAGE = "custom_components.hikvision_virtual_indoor_station"

IDENTITY = Identity(
    serial="DS-KD8003-IME1(B)0120250101ENFX0000001",
    model="DS-KD8003-IME1(B)",
    name="Door Station",
    firmware="V3.7.3",
    firmware_build="build 260915",
    mac="00:00:5e:00:53:01",
    device_type="VIS",
    hardware="1-1-0",
)
INFO = DoorStationInfo(
    identity=IDENTITY,
    doors=(1, 2),
    call_status=True,
    talk=TalkChannel("1", "G.711ulaw"),
    outputs=(
        Output(1, "COM1", OutputUse.ELECTRIC_LOCK),
        Output(2, "COM2", OutputUse.ELECTRIC_LOCK),
    ),
    # As a DS-KD8003 (V3.7.3) answers: inputs 2 and 4 can change, 1 and 3 cannot
    inputs=(
        Input(1, "AI1", InputUse.DOOR_CONTACT, (InputUse.DOOR_CONTACT,)),
        Input(2, "AI2", InputUse.DISABLED, (InputUse.DISABLED, InputUse.DOOR_CONTACT)),
        Input(3, "AI3", InputUse.EXIT_BUTTON, (InputUse.EXIT_BUTTON,)),
        Input(4, "AI4", InputUse.DISABLED, (InputUse.DISABLED, InputUse.EXIT_BUTTON)),
    ),
)
UNIQUE_ID = IDENTITY.stable_id
ENTRY_DATA = {
    CONF_HOST: DOOR_IP,
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "s3cret-pass",
    CONF_PORT: 80,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components."""


class FakeTalkback:
    """The microphone of an answered call: it keeps what it is given."""

    codec = "G.711ulaw"
    payload_type = 0

    def __init__(self) -> None:
        """Start empty."""
        self.frames: list[bytes] = []
        self.stats = TalkbackStats()

    def push(self, frame: bytes) -> None:
        """Keep a frame."""
        self.frames.append(frame)
        self.stats.packets += 1


class FakeCallServer:
    """aiohikvision's CallServer at its boundary: the tests ring and end the calls."""

    instances: ClassVar[list[FakeCallServer]] = []
    fail_start: ClassVar[OSError | None] = None

    def __init__(self, transport: Any, *, on_change: Any, **kwargs: Any) -> None:
        """Keep what the integration gives it."""
        self.transport = transport
        self.options = kwargs
        self.advertise: str = kwargs["advertise"]
        self._on_change = on_change
        self.calls: dict[str, DoorCall] = {}
        self.rejected: list[tuple[str, int]] = []
        self.started = False
        self.stopped = False
        FakeCallServer.instances.append(self)

    async def start(self) -> None:
        """Listen, or fail as a taken port does."""
        if FakeCallServer.fail_start is not None:
            raise FakeCallServer.fail_start
        self.started = True

    async def stop(self) -> None:
        """End every call."""
        self.stopped = True
        for call in list(self.calls.values()):
            if call.state is not CallState.ENDED:
                self.end(call, EndReason.STOPPED)

    def current(self, door: str) -> DoorCall | None:
        """Return the call of a door that has not ended."""
        return next(
            (
                c
                for c in self.calls.values()
                if c.door == door and c.state is not CallState.ENDED
            ),
            None,
        )

    def ring(self, door: str = DOOR_IP, call_id: str = "call-1") -> DoorCall:
        """Have the door station call."""
        call = DoorCall(id=call_id, door=door, callee="REDACTED", caller="Door Station")
        self.calls[call_id] = call
        self._on_change(call)
        return call

    def _live(self, call_id: str, state: CallState) -> DoorCall:
        call = self.calls.get(call_id)
        if call is None or call.state is not state:
            raise CallError(f"Call {call_id} is not {state.value}")
        return call

    async def answer(self, call_id: str) -> DoorCall:
        """Answer: the microphone is ready."""
        call = self._live(call_id, CallState.RINGING)
        call.talkback = FakeTalkback()  # type: ignore[assignment]  # a double of Talkback
        call.state = CallState.ANSWERED
        call.answered_at = time.monotonic()
        self._on_change(call)
        return call

    async def reject(self, call_id: str, code: int = 486) -> DoorCall:
        """Refuse a ringing call."""
        call = self._live(call_id, CallState.RINGING)
        self.rejected.append((call_id, code))
        self.end(call, EndReason.REJECTED)
        return call

    async def hangup(self, call_id: str) -> DoorCall:
        """Hang up an answered call."""
        call = self._live(call_id, CallState.ANSWERED)
        self.end(call, EndReason.HUNG_UP)
        return call

    def end(self, call: DoorCall, reason: EndReason) -> None:
        """End the call (the door hung up, the visitor left...)."""
        call.state = CallState.ENDED
        call.end_reason = reason
        call.ended_at = time.monotonic()
        call.talkback = None
        self._on_change(call)


@pytest.fixture(autouse=True)
def call_server() -> Generator[type[FakeCallServer]]:
    """Replace the SIP side, without sockets."""
    FakeCallServer.instances = []
    FakeCallServer.fail_start = None
    with (
        patch(f"{PACKAGE}.sip.CallServer", FakeCallServer),
        patch(f"{PACKAGE}.sip.async_get_source_ip", AsyncMock(return_value=HA_IP)),
    ):
        yield FakeCallServer


@pytest.fixture
def door() -> Generator[MagicMock]:
    """Mock the DoorStation of aiohikvision."""
    with (
        patch(f"{PACKAGE}.DoorStation", autospec=True) as door_class,
        patch(f"{PACKAGE}.config_flow.DoorStation", new=door_class),
    ):
        station = door_class.return_value
        station.read_info.return_value = INFO
        station.info = INFO
        station.read_outputs.return_value = INFO.outputs
        station.read_inputs.return_value = INFO.inputs
        # The DS-KD8003 of the capture: five video clients, the CPU at 88%
        station.read_health.return_value = DoorStationHealth(88, 5)
        station.read_settings.return_value = ()
        station.read_setting_values.return_value = {}
        station.rtsp_url.return_value = (
            f"rtsp://admin:s3cret-pass@{DOOR_IP}:554/Streaming/Channels/101"
        )
        station.snapshot.return_value = b"\xff\xd8jpeg\xff\xd9"
        yield station


@pytest.fixture
def entry() -> MockConfigEntry:
    """Return the entry of the door station."""
    return MockConfigEntry(
        domain=DOMAIN, title="Door Station", unique_id=UNIQUE_ID, data=ENTRY_DATA
    )


@pytest.fixture
async def loaded(
    hass: HomeAssistant, entry: MockConfigEntry, door: MagicMock
) -> MockConfigEntry:
    """Set the entry up."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def server(
    loaded: MockConfigEntry, call_server: type[FakeCallServer]
) -> FakeCallServer:
    """Return the call server of the loaded entry."""
    return call_server.instances[-1]
