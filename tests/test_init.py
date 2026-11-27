"""Setting up and unloading a door station, and the SIP server they share."""

from __future__ import annotations

from datetime import timedelta
import io
import logging
from types import MappingProxyType
from unittest.mock import MagicMock, patch

from aiohikvision import CallError, DoorStationInfo, Firmware, Registration, StreamId
from aiohikvision.isapi.wire.faults import BadCredentials, Unreachable
from homeassistant.components.camera import async_get_image, async_get_stream_source
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from PIL import Image
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hikvision_virtual_indoor_station import sip
from custom_components.hikvision_virtual_indoor_station.const import DOMAIN
from custom_components.hikvision_virtual_indoor_station.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import (
    DOOR_IP,
    ENTRY_DATA,
    HA_IP,
    IDENTITY,
    INFO,
    UNIQUE_ID,
    FakeCallServer,
)


async def test_the_door_station_and_its_entities(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeCallServer
) -> None:
    """One device, its entities, and the SIP server listening for it."""
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, UNIQUE_ID), loaded.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Hikvision"
    assert device.model == "DS-KD8003-IME1(B)"
    assert device.sw_version == "V3.7.3 build 260915"
    assert device.configuration_url == f"https://{DOOR_IP}"
    assert hass.states.get("sensor.door_station_call").state == "idle"
    assert hass.states.get("binary_sensor.door_station_sip_registration").state == "off"
    assert hass.states.get("event.door_station_doorbell").state == "unknown"
    for button in ("open_door_1", "open_door_2", "answer", "hang_up", "reject"):
        assert hass.states.get(f"button.door_station_{button}") is not None
    assert server.started
    assert server.options["advertise"] == HA_IP
    assert server.transport.allowed_hosts == {DOOR_IP}


async def test_the_cameras_of_the_streams(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    streaming: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A camera per stream: the main one is the door station's, the others start off."""
    source = await async_get_stream_source(hass, "camera.door_station")
    assert source == f"rtsp://admin:s3cret-pass@{DOOR_IP}:554/Streaming/Channels/101"
    image = await async_get_image(hass, "camera.door_station")
    assert image.content == b"\xff\xd8jpeg\xff\xd9"
    streaming.snapshot.side_effect = Unreachable("busy")
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, "camera.door_station")
    sub = entity_registry.async_get("camera.door_station_sub_stream")
    assert sub is not None
    assert sub.unique_id == f"{UNIQUE_ID}_camera_102"
    assert sub.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_a_sub_stream_turned_on(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    door: MagicMock,
    streaming: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """The sub stream, once turned on, plays its own RTSP stream and pictures."""
    entity_registry.async_get_or_create(
        "camera",
        DOMAIN,
        f"{UNIQUE_ID}_camera_102",
        suggested_object_id="door_station_sub_stream",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    source = await async_get_stream_source(hass, "camera.door_station_sub_stream")
    assert source == f"rtsp://admin:s3cret-pass@{DOOR_IP}:554/Streaming/Channels/102"
    streaming.snapshot.return_value = jpeg(704, 576)
    image = await async_get_image(hass, "camera.door_station_sub_stream")
    assert streaming.snapshot.call_args.args == (StreamId(1, 2),)
    with Image.open(io.BytesIO(image.content)) as picture:
        assert picture.size == (1024, 576)


async def test_a_door_station_that_does_not_list_its_streams(
    hass: HomeAssistant, entry: MockConfigEntry, door: MagicMock, streaming: MagicMock
) -> None:
    """Without a list of streams, the camera of its main stream is still there."""
    streaming.streams.return_value = ()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("camera.door_station") is not None
    image = await async_get_image(hass, "camera.door_station")
    assert image.content == b"\xff\xd8jpeg\xff\xd9"


async def test_a_door_station_without_video(
    hass: HomeAssistant, entry: MockConfigEntry, door: MagicMock
) -> None:
    """A door station whose capabilities show no video has no camera."""
    with patch(
        "custom_components.hikvision_virtual_indoor_station.Device.from_link",
        return_value=MagicMock(streaming=None),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get("camera.door_station") is None
    assert hass.states.get("sensor.door_station_call") is not None


def jpeg(width: int, height: int) -> bytes:
    """Return a JPEG picture of a size."""
    output = io.BytesIO()
    Image.new("RGB", (width, height), "gray").save(output, format="JPEG")
    return output.getvalue()


async def test_the_picture_takes_the_shape_of_the_stream(
    hass: HomeAssistant, loaded: MockConfigEntry, streaming: MagicMock
) -> None:
    """A DS-KD8003 takes its pictures 11:9 while it streams 16:9: they are widened."""
    streaming.snapshot.return_value = jpeg(704, 576)
    image = await async_get_image(hass, "camera.door_station")
    with Image.open(io.BytesIO(image.content)) as picture:
        assert picture.size == (1024, 576)
    # A picture in the shape of the stream, or one that cannot be read, is left as it is
    streaming.snapshot.return_value = sixteen_by_nine = jpeg(1920, 1080)
    image = await async_get_image(hass, "camera.door_station")
    assert image.content == sixteen_by_nine
    streaming.snapshot.return_value = b"\xff\xd8jpeg\xff\xd9"
    image = await async_get_image(hass, "camera.door_station")
    assert image.content == b"\xff\xd8jpeg\xff\xd9"


async def test_a_refused_account_asks_to_sign_in_again(
    hass: HomeAssistant, entry: MockConfigEntry, door: MagicMock
) -> None:
    """The stored password no longer works."""
    door.read_info.side_effect = BadCredentials("no")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(entry.async_get_active_flows(hass, {"reauth"}))


async def test_an_unreachable_door_station_is_retried(
    hass: HomeAssistant, entry: MockConfigEntry, door: MagicMock
) -> None:
    """The door station does not answer: try again later."""
    door.read_info.side_effect = Unreachable("timeout")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_an_unknown_host_is_retried(hass: HomeAssistant, door: MagicMock) -> None:
    """A name that does not resolve: try again later."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={**ENTRY_DATA, CONF_HOST: "door.invalid"},
    )
    entry.add_to_hass(hass)
    with patch("socket.getaddrinfo", side_effect=OSError("no such name")):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_the_sip_port_in_use(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    door: MagicMock,
    call_server: type[FakeCallServer],
) -> None:
    """Another SIP server holds the port: try again later, saying so."""
    call_server.fail_start = OSError(98, "Address already in use")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert "SIP port 5060" in (entry.reason or "")
    assert sip.DATA_SIP not in hass.data


async def test_two_door_stations_share_the_sip_server(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    door: MagicMock,
    server: FakeCallServer,
    call_server: type[FakeCallServer],
) -> None:
    """One server hears both; it stops with the last one."""
    other_identity = DoorStationInfo(
        identity=type(IDENTITY)(
            serial="S2", model="M", name="Back Door", firmware=Firmware.parse("F")
        ),
        doors=(1,),
        call_status=False,
        talk=None,
    )
    door.read_info.return_value = other_identity
    second = MockConfigEntry(
        domain=DOMAIN, unique_id="s2", data={**ENTRY_DATA, CONF_HOST: "192.0.2.11"}
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    assert len(call_server.instances) == 1
    assert server.transport.allowed_hosts == {DOOR_IP, "192.0.2.11"}
    assert hass.states.get("button.back_door_open_door") is not None

    assert await hass.config_entries.async_unload(loaded.entry_id)
    assert not server.stopped
    assert server.transport.allowed_hosts == {"192.0.2.11"}
    assert await hass.config_entries.async_unload(second.entry_id)
    assert server.stopped
    assert sip.DATA_SIP not in hass.data
    door.close.assert_awaited()


async def test_unloading_during_calls(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeCallServer
) -> None:
    """A ringing call is refused (480) and an answered one hung up as the entry goes."""
    call = server.ring()
    assert await hass.config_entries.async_unload(loaded.entry_id)
    assert server.rejected == [(call.id, 480)]

    await hass.config_entries.async_setup(loaded.entry_id)
    await hass.async_block_till_done()
    new_server = FakeCallServer.instances[-1]
    answered = new_server.ring(call_id="call-2")
    await new_server.answer(answered.id)
    assert await hass.config_entries.async_unload(loaded.entry_id)
    assert answered.end_reason is not None


async def test_a_reload_knows_the_registration_and_the_call(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    door: MagicMock,
    server: FakeCallServer,
) -> None:
    """A second entry of the same server is told what the server already knows."""
    sip_server: sip.SipServer = hass.data[sip.DATA_SIP]
    registration = Registration("100", DOOR_IP, 5060, "sip:100@door", 1e12, "HKVS/2.0")
    sip_server.registrar._registrations[(DOOR_IP, "100")] = registration
    server.ring()
    station = loaded.runtime_data
    sip_server.add(station)
    assert station.registered
    assert station.call_state == "ringing"


async def test_registration_and_pruning(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeCallServer
) -> None:
    """The door's line registers; when it runs out, the sensor turns off."""
    sip_server: sip.SipServer = hass.data[sip.DATA_SIP]
    registration = Registration("100", DOOR_IP, 5060, "sip:100@door", 0, "HKVS/2.0")
    sip_server._registered(registration, True)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.door_station_sip_registration").state == "on"
    sip_server._registered(registration, False)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.door_station_sip_registration").state == "off"
    # Another door's registration is not this one's
    sip_server._registered(Registration("1", "192.0.2.99", 1, "x", 0, None), True)
    with patch.object(sip_server.registrar, "prune") as prune:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()
    prune.assert_called()


async def test_home_assistant_stopping(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeCallServer
) -> None:
    """The calls end with Home Assistant."""
    call = server.ring()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert server.stopped
    assert call.state.value == "ended"


async def test_diagnostics(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeCallServer
) -> None:
    """What the door is and how its call goes, without addresses, names or account."""
    call = server.ring()
    await server.answer(call.id)
    sip_server: sip.SipServer = hass.data[sip.DATA_SIP]
    sip_server._registered(
        Registration("100", DOOR_IP, 5060, "sip:100@door", 1e12, "HKVS/2.0"), True
    )
    hass.config_entries.async_add_subentry(
        loaded,
        ConfigSubentry(
            data=MappingProxyType(
                {CONF_DEVICE_ID: "gone", "do_not_disturb": True, "open_door": False}
            ),
            subentry_type="extension",
            title="Pixel",
            unique_id="gone",
        ),
    )
    data = await async_get_config_entry_diagnostics(hass, loaded)
    assert data["version"] == "develop"  # the release workflow writes the tag
    assert data["entry"]["host"] == "**REDACTED**"
    assert data["entry"]["password"] == "**REDACTED**"
    assert data["device"]["model"] == "DS-KD8003-IME1(B)"
    assert data["doors"] == [1, 2]
    assert data["speaker"] == "G.711ulaw"
    assert data["sip"]["registered"]
    assert data["sip"]["user_agent"] == "HKVS/2.0"
    assert data["call"]["state"] == "answered"
    assert data["call"]["caller"] == "**REDACTED**"
    assert data["talkback"] == {"packets": 0, "bursts": 0, "frames_dropped": 0}
    # The SIP Call-ID can carry the door's address: the token stands for it
    assert data["call"]["id"] == "**REDACTED**"
    assert data["call"]["token"]
    # The phones say what they may do, not who they are
    assert data["phones"] == [
        {"do_not_disturb": True, "open_door": False, "notify_service": False}
    ]
    # How loaded it is, what its inputs read, and its settings
    assert data["load"] == {"cpu_percent": 88, "video_sessions": 5}
    assert data["inputs"] == ["door_contact", "disabled", "exit_button", "disabled"]
    assert data["settings"] == {}
    # How many visits, never when
    assert data["visits"] == {
        "kept": 0,
        "total": {"answered": 0, "rejected": 0, "missed": 0},
    }
    # The device's report (aiohikvision's, anonymized), and the streams
    assert data["report"] == {"library": "0.2.0"}
    assert [stream["id"] for stream in data["streams"]] == ["101", "102"]
    assert data["streams"][0]["video"]["width"] == 1920
    assert data["rtsp_port"] == 554
    assert "Pixel" not in str(data)
    assert DOOR_IP not in str(data)
    assert INFO.identity.serial not in str(data)


async def test_diagnostics_of_a_device_that_does_not_answer(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    """The report of a door station that does not answer says why."""
    device = loaded.runtime_data.device
    device.report.side_effect = Unreachable("timeout")
    data = await async_get_config_entry_diagnostics(hass, loaded)
    assert data["report"] == {"error": "Unreachable"}


async def test_what_the_debug_log_says_of_the_setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    door: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One record says what was set up: doors, inputs, outputs, speaker, cameras."""
    caplog.set_level(
        logging.DEBUG, logger="custom_components.hikvision_virtual_indoor_station"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    summary = entry.runtime_data.summary()
    assert summary == [
        f"Set up DS-KD8003-IME1(B) V3.7.3 build 260915 at {DOOR_IP}",
        "Doors [1, 2], opening [1, 2]; outputs: COM1 electric_lock, "
        "COM2 electric_lock; inputs: AI1 door_contact, AI2 disabled, "
        "AI3 exit_button, AI4 disabled",
        "Speaker: G.711ulaw; call status: read; settings offered: 0",
        "Cameras: 101 (main), 102 (off at first)",
        f"SIP server at {HA_IP}:5060, hearing {DOOR_IP}; phones: 0",
    ]
    assert "\n  ".join(summary) in caplog.text
    # The fetches of the coordinators are not logged, only their failures
    assert "Finished fetching" not in caplog.text


async def test_where_the_sip_server_listens(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    """The address of the socket once it listens; the asked one before."""
    sip_server: sip.SipServer = hass.data[sip.DATA_SIP]
    assert sip_server.address == ("0.0.0.0", 5060)
    socket = MagicMock()
    socket.get_extra_info.return_value = ("0.0.0.0", 5061, 0, 0)
    sip_server.transport._udp_transport = socket
    assert sip_server.address == ("0.0.0.0", 5061)
    assert sip_server.contact == (HA_IP, 5061)
    sip_server.transport._udp_transport = None
    # A station the server does not hear is not removed; the door of the entry stays
    assert await sip_server.remove(MagicMock(door_ip="192.0.2.99"))
    assert sip_server.transport.allowed_hosts == {DOOR_IP}


async def test_a_call_that_ends_while_the_entry_goes(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeCallServer
) -> None:
    """The visitor left as the entry unloads: nothing to refuse."""
    server.ring()

    async def gone(call_id: str, code: int = 486) -> None:
        raise CallError(f"Call {call_id} is not ringing")

    server.reject = gone  # type: ignore[method-assign]  # the call is gone
    assert await hass.config_entries.async_unload(loaded.entry_id)


async def test_platforms_that_do_not_unload(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeCallServer
) -> None:
    """The SIP server keeps hearing the door while its entities stay."""
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(loaded.entry_id)
    assert not server.stopped
