"""Whether the door station answers, and whether it still calls Home Assistant."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock

from aiohikvision import NotADoorStation, Registration
from aiohikvision.isapi.wire.faults import BadCredentials, Unreachable
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hikvision_virtual_indoor_station import sip
from custom_components.hikvision_virtual_indoor_station.const import DOMAIN

from .conftest import DOOR_IP, IDENTITY, INFO, FakeCallServer

CALL = "sensor.door_station_call"
REGISTRATION = "binary_sensor.door_station_sip_registration"


async def tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: int
) -> None:
    """Move the clock, and let what it wakes up run."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_unavailable_while_the_door_does_not_answer(
    freezer: FrozenDateTimeFactory,
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    door: MagicMock,
) -> None:
    """The door station is asked once a minute; its entities follow its answer."""
    door.check.side_effect = Unreachable("timeout")
    await tick(hass, freezer, 61)
    assert hass.states.get(CALL).state == STATE_UNAVAILABLE
    assert hass.states.get("camera.door_station").state == STATE_UNAVAILABLE
    door.check.side_effect = None
    await tick(hass, freezer, 61)
    assert hass.states.get(CALL).state == "idle"


async def test_a_refused_account_later(
    freezer: FrozenDateTimeFactory,
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    door: MagicMock,
) -> None:
    """The password changed on the door station: sign in again."""
    door.check.side_effect = BadCredentials("no")
    await tick(hass, freezer, 61)
    assert any(loaded.async_get_active_flows(hass, {"reauth"}))


async def test_no_longer_a_door_station(
    hass: HomeAssistant, entry: MockConfigEntry, door: MagicMock
) -> None:
    """The address now reaches a camera."""
    door.read_info.side_effect = NotADoorStation("a camera")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_another_door_station_at_the_address(
    hass: HomeAssistant, entry: MockConfigEntry, door: MagicMock
) -> None:
    """The address now reaches another door station: reconfigure."""
    door.read_info.return_value = replace(
        INFO, identity=replace(IDENTITY, serial="ANOTHER")
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert DOOR_IP in (entry.reason or "")


async def test_keepalives_tell_the_door_still_calls(
    freezer: FrozenDateTimeFactory,
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    server: FakeCallServer,
) -> None:
    """After a restart, the keepalives say the door calls here, until they stop."""
    sip_server: sip.SipServer = hass.data[sip.DATA_SIP]
    sip_server._keepalive(("192.0.2.99", 5060))
    sip_server._keepalive((DOOR_IP, 5060))
    await hass.async_block_till_done()
    assert hass.states.get(REGISTRATION).state == "on"
    sip_server._keepalive((DOOR_IP, 5060))
    await tick(hass, freezer, 61)
    assert hass.states.get(REGISTRATION).state == "on"
    await tick(hass, freezer, 61)
    assert hass.states.get(REGISTRATION).state == "off"


async def test_a_door_that_does_not_call_home_assistant(
    freezer: FrozenDateTimeFactory,
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    server: FakeCallServer,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Unheard for longer than a registration: a repair issue, gone on registering."""
    station = loaded.runtime_data
    for _ in range(10):
        await tick(hass, freezer, 61)
    assert issue_registry.async_get_issue(DOMAIN, station.issue_id) is None
    await tick(hass, freezer, 61)
    issue = issue_registry.async_get_issue(DOMAIN, station.issue_id)
    assert issue is not None
    assert issue.translation_placeholders == {
        "name": "Door Station",
        "address": "192.0.2.20",
        "port": "5060",
    }
    sip_server: sip.SipServer = hass.data[sip.DATA_SIP]
    registration = Registration("100", DOOR_IP, 5060, "sip:100@door", 1e12, "HKVS/2.0")
    sip_server._registered(registration, True)
    assert issue_registry.async_get_issue(DOMAIN, station.issue_id) is None

    sip_server._registered(registration, False)
    for _ in range(12):
        await tick(hass, freezer, 61)
    assert issue_registry.async_get_issue(DOMAIN, station.issue_id) is not None
    assert await hass.config_entries.async_unload(loaded.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, station.issue_id) is None
