"""A call through the entities: the doorbell, the call sensor and the buttons."""

from __future__ import annotations

from unittest.mock import MagicMock

from aiohikvision import CallError, EndReason
from aiohikvision.isapi.wire.faults import DeviceRejected
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import FakeCallServer

CALL = "sensor.door_station_call"
DOORBELL = "event.door_station_doorbell"


async def press(hass: HomeAssistant, button: str) -> None:
    """Press a button of the door station."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: f"button.door_station_{button}"},
        blocking=True,
    )


def last_event(hass: HomeAssistant) -> tuple[str, dict[str, object]]:
    """Return the type and attributes of the doorbell's last event."""
    state = hass.states.get(DOORBELL)
    assert state is not None
    return state.attributes["event_type"], dict(state.attributes)


async def test_ring_answer_hang_up(hass: HomeAssistant, server: FakeCallServer) -> None:
    """The doorbell rings, the call is answered from a button, then hung up."""
    call = server.ring()
    await hass.async_block_till_done()
    assert hass.states.get(CALL).state == "ringing"
    event, attributes = last_event(hass)
    assert event == "ring"
    assert attributes["call_id"] == call.id
    assert attributes["callee"] == "REDACTED"

    await press(hass, "answer")
    assert hass.states.get(CALL).state == "answered"
    assert last_event(hass)[0] == "answered"

    await press(hass, "hang_up")
    assert hass.states.get(CALL).state == "idle"
    event, attributes = last_event(hass)
    assert event == "ended"
    assert attributes["end_reason"] == "hung_up"


async def test_reject(hass: HomeAssistant, server: FakeCallServer) -> None:
    """Refusing a ringing call: the door shows busy."""
    call = server.ring()
    await press(hass, "reject")
    assert server.rejected == [(call.id, 486)]
    assert last_event(hass)[0] == "rejected"
    assert hass.states.get(CALL).state == "idle"


@pytest.mark.parametrize(
    "reason", [EndReason.CANCELLED, EndReason.LOST, EndReason.DOOR_HUNG_UP]
)
async def test_missed(
    hass: HomeAssistant, server: FakeCallServer, reason: EndReason
) -> None:
    """A call that ends before anyone answers is missed."""
    call = server.ring()
    server.end(call, reason)
    await hass.async_block_till_done()
    assert last_event(hass)[0] == "missed"


async def test_the_door_hangs_up(hass: HomeAssistant, server: FakeCallServer) -> None:
    """An answered call the door ends (its talk time ran out) has ended."""
    call = server.ring()
    await server.answer(call.id)
    server.end(call, EndReason.DOOR_HUNG_UP)
    await hass.async_block_till_done()
    assert last_event(hass)[0] == "ended"


async def test_buttons_without_the_call_they_need(
    hass: HomeAssistant, server: FakeCallServer
) -> None:
    """Answer and refuse need a ringing call, hang up an answered one."""
    for button, key in (
        ("answer", "no_ringing_call"),
        ("reject", "no_ringing_call"),
        ("hang_up", "no_answered_call"),
    ):
        with pytest.raises(ServiceValidationError) as caught:
            await press(hass, button)
        assert caught.value.translation_key == key
    call = server.ring()
    with pytest.raises(ServiceValidationError) as caught:
        await press(hass, "hang_up")
    assert caught.value.translation_key == "no_answered_call"
    await server.answer(call.id)
    with pytest.raises(ServiceValidationError):
        await press(hass, "answer")


async def test_an_answer_the_server_refuses(
    hass: HomeAssistant, server: FakeCallServer, loaded: MockConfigEntry
) -> None:
    """The door offers no G.711, or the call ended meanwhile: say why."""
    server.ring()

    async def refuse(call_id: str) -> None:
        raise CallError("The door station offers no G.711")

    server.answer = refuse  # type: ignore[method-assign]  # the server refuses
    with pytest.raises(HomeAssistantError) as caught:
        await press(hass, "answer")
    assert caught.value.translation_key == "answer_failed"


async def test_opening_the_doors(
    hass: HomeAssistant, loaded: MockConfigEntry, door: MagicMock
) -> None:
    """Each door has its button; a refusal is told."""
    await press(hass, "open_door_2")
    door.open_door.assert_awaited_once_with(2)
    door.open_door.side_effect = DeviceRejected("HTTP 403", 403)
    with pytest.raises(HomeAssistantError) as caught:
        await press(hass, "open_door_1")
    assert caught.value.translation_key == "open_door_failed"
    assert caught.value.translation_placeholders == {"door": "1", "error": "HTTP 403"}
