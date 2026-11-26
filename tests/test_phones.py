"""The phones: a notification rings them, its buttons act, and it is taken back."""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import MagicMock

from aiohikvision.isapi.wire.faults import Unreachable
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.hikvision_virtual_indoor_station.const import (
    CONF_DO_NOT_DISTURB,
    CONF_OPEN_DOOR,
    DOMAIN,
    MOBILE_APP,
    SUBENTRY_EXTENSION,
)
from custom_components.hikvision_virtual_indoor_station.phones import (
    ACTION_EVENT,
    CLEAR_NOTIFICATION,
    notify_service_of,
)
from custom_components.hikvision_virtual_indoor_station.repairs import (
    async_create_fix_flow,
)
from custom_components.hikvision_virtual_indoor_station.station import call_token

from .conftest import FakeCallServer

TOKEN = call_token("call-1")


def phone(
    hass: HomeAssistant, name: str, *, app_data: dict[str, str] | None = None
) -> str:
    """Add a phone with the Home Assistant app; return its device id."""
    app = MockConfigEntry(
        domain=MOBILE_APP,
        data={"device_name": name} if app_data is None else app_data,
    )
    app.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=app.entry_id, identifiers={(MOBILE_APP, name)}, name=name
    )
    return device.id


def extension(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    device_id: str,
    *,
    do_not_disturb: bool = False,
    open_door: bool = True,
) -> None:
    """Make a phone an extension of the door station."""
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {
                    CONF_DEVICE_ID: device_id,
                    CONF_DO_NOT_DISTURB: do_not_disturb,
                    CONF_OPEN_DOOR: open_door,
                }
            ),
            subentry_type=SUBENTRY_EXTENSION,
            title=device_id,
            unique_id=device_id,
        ),
    )


def press(hass: HomeAssistant, action: str) -> None:
    """Press a button of a notification on a phone."""
    hass.bus.async_fire(ACTION_EVENT, {"action": action, "tag": "any"})


async def test_a_ring_notifies_the_phones(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeCallServer
) -> None:
    """Each phone not disturbed is notified once, and the notification goes away."""
    pixel = async_mock_service(hass, "notify", "mobile_app_pixel")
    iphone = async_mock_service(hass, "notify", "mobile_app_iphone")
    extension(hass, loaded, phone(hass, "Pixel"))
    extension(hass, loaded, phone(hass, "iPhone"), do_not_disturb=True)
    # A phone without notifications, and one that left Home Assistant
    extension(hass, loaded, phone(hass, "Tablet"))
    extension(hass, loaded, "gone")

    call = server.ring()
    await hass.async_block_till_done()
    assert not iphone
    (ring,) = pixel
    assert ring.data["title"] == "Door Station"
    assert ring.data["message"] == "Ringing"
    data = ring.data["data"]
    # The call is named by a digest: a Call-ID can carry the door's address
    assert call.id != TOKEN
    assert len(TOKEN) == 16
    # The cards know it by that name too: the panel answers the call it names
    assert loaded.runtime_data.snapshot()["call"]["token"] == TOKEN
    assert data["tag"] == f"hikvision_virtual_indoor_station-{TOKEN}"
    assert data["image"] == "/api/camera_proxy/camera.door_station"
    assert data["entity_id"] == "camera.door_station"
    panel = f"/hikvision-indoor-station?entry={loaded.entry_id}&call={TOKEN}"
    assert data["url"] == data["clickAction"] == panel
    assert data["push"] == {"interruption-level": "time-sensitive"}
    assert (data["priority"], data["ttl"], data["importance"]) == ("high", 0, "high")
    assert data["actions"] == [
        {"action": "URI", "title": "Answer", "uri": f"{panel}&answer=1"},
        {
            "action": f"HIKVISION_VIS_OPEN_DOOR_1_{TOKEN}",
            "title": "Open door 1",
            "activationMode": "background",
            "authenticationRequired": True,
        },
        {
            "action": f"HIKVISION_VIS_REJECT_{TOKEN}",
            "title": "Reject",
            "activationMode": "background",
            "destructive": True,
        },
    ]
    # The same ringing call, told again, does not ring twice
    loaded.runtime_data.call_changed(call)
    await hass.async_block_till_done()
    assert len(pixel) == 1

    await server.answer(call.id)
    await hass.async_block_till_done()
    clear = pixel[-1]
    assert clear.data == {
        "message": CLEAR_NOTIFICATION,
        "data": {"tag": f"hikvision_virtual_indoor_station-{TOKEN}"},
    }
    # Taken back once: hanging up sends nothing more
    await server.hangup(call.id)
    await hass.async_block_till_done()
    assert len(pixel) == 2


async def test_what_a_phone_may_do(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeCallServer
) -> None:
    """A phone that may not open the door has no such button; no camera, no picture."""
    pixel = async_mock_service(hass, "notify", "mobile_app_pixel")
    extension(hass, loaded, phone(hass, "Pixel"), open_door=False)
    er.async_get(hass).async_remove("camera.door_station")
    server.ring()
    await hass.async_block_till_done()
    data = pixel[0].data["data"]
    assert "image" not in data
    assert [action["title"] for action in data["actions"]] == ["Answer", "Reject"]


async def test_a_failed_notification(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    server: FakeCallServer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A notification that fails is logged; the call goes on."""
    async_mock_service(
        hass, "notify", "mobile_app_pixel", raise_exception=HomeAssistantError("down")
    )
    extension(hass, loaded, phone(hass, "Pixel"))
    server.ring()
    await hass.async_block_till_done()
    assert "notification (mobile_app_pixel) failed: down" in caplog.text
    assert hass.states.get("sensor.door_station_call").state == "ringing"


async def test_the_buttons_of_a_ring(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    server: FakeCallServer,
    door: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Open the door and refuse the call, only while the call lasts."""
    call = server.ring()
    await hass.async_block_till_done()
    # Not a button of this integration, of another call, or of an unknown door
    press(hass, "SNOOZE")
    hass.bus.async_fire(ACTION_EVENT, {})
    press(hass, f"HIKVISION_VIS_OPEN_DOOR_1_{call_token('other')}")
    press(hass, f"HIKVISION_VIS_OPEN_DOOR_x_{TOKEN}")
    press(hass, f"HIKVISION_VIS_SNOOZE_{TOKEN}")
    await hass.async_block_till_done()
    door.open_door.assert_not_called()

    press(hass, f"HIKVISION_VIS_OPEN_DOOR_1_{TOKEN}")
    await hass.async_block_till_done()
    door.open_door.assert_awaited_once_with(1)
    door.open_door.side_effect = Unreachable("busy")
    press(hass, f"HIKVISION_VIS_OPEN_DOOR_1_{TOKEN}")
    await hass.async_block_till_done()
    assert "The notification's button failed" in caplog.text

    press(hass, f"HIKVISION_VIS_REJECT_{TOKEN}")
    await hass.async_block_till_done()
    assert server.rejected == [(call.id, 486)]
    # The call is over: its buttons are spent
    door.open_door.reset_mock()
    press(hass, f"HIKVISION_VIS_OPEN_DOOR_1_{TOKEN}")
    await hass.async_block_till_done()
    door.open_door.assert_not_called()


async def test_no_call_no_buttons(
    hass: HomeAssistant, loaded: MockConfigEntry, door: MagicMock
) -> None:
    """A button pressed before any call does nothing."""
    press(hass, f"HIKVISION_VIS_OPEN_DOOR_1_{TOKEN}")
    await hass.async_block_till_done()
    door.open_door.assert_not_called()


async def test_the_notify_service_of_a_phone(hass: HomeAssistant) -> None:
    """Named as mobile_app names it, and only when it exists."""
    async_mock_service(hass, "notify", "mobile_app_pixel_9")
    assert notify_service_of(hass, phone(hass, "Pixel 9")) == "mobile_app_pixel_9"
    assert notify_service_of(hass, phone(hass, "Tablet")) is None
    assert notify_service_of(hass, phone(hass, "Old", app_data={})) is None
    assert notify_service_of(hass, "gone") is None
    # A device of another integration as well
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("other", "x")}
    )
    assert notify_service_of(hass, device.id) is None


def test_calls_are_named_alike() -> None:
    """The same call has the same name; another call another one."""
    assert call_token("call-1") == TOKEN
    assert call_token("call-2") != TOKEN


async def test_a_phone_that_left_home_assistant(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    """A repair issue says so, and its fix removes the phone from the door station."""
    issues = ir.async_get(hass)
    pixel = phone(hass, "Pixel")
    extension(hass, loaded, pixel)
    await hass.async_block_till_done()
    (subentry_id,) = loaded.subentries
    issue_id = f"phone_gone_{subentry_id}"
    assert issues.async_get_issue(DOMAIN, issue_id) is None

    dr.async_get(hass).async_remove_device(pixel)
    await hass.async_block_till_done()
    issue = issues.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_key == "phone_gone"
    assert issue.translation_placeholders == {"phone": pixel, "name": "Door Station"}

    flow = await async_create_fix_flow(hass, issue_id, issue.data)
    flow.hass = hass
    flow.handler = DOMAIN
    flow.issue_id = issue_id
    result = await flow.async_step_init()
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == issue.translation_placeholders
    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert not loaded.subentries
    # The phone is gone from the door station, and its issue with it
    assert issues.async_get_issue(DOMAIN, issue_id) is None
    # Confirmed twice (another window): nothing more to remove
    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    result = await flow.async_step_confirm()
    assert result["description_placeholders"] is None
    # An issue without its data names no phone: nothing is removed
    flow = await async_create_fix_flow(hass, issue_id, None)
    flow.hass = hass
    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_the_issues_go_with_the_door_station(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    """A phone that left has an issue while its door station is loaded."""
    extension(hass, loaded, "gone")
    await hass.async_block_till_done()
    (subentry_id,) = loaded.subentries
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, f"phone_gone_{subentry_id}") is not None
    assert await hass.config_entries.async_unload(loaded.entry_id)
    assert issues.async_get_issue(DOMAIN, f"phone_gone_{subentry_id}") is None
