"""What the outputs of the door station drive: a door without a lock does not open."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock

from aiohikvision import Output, OutputUse
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.hikvision_virtual_indoor_station.const import DOMAIN
from custom_components.hikvision_virtual_indoor_station.sensor import (
    changeable_outputs,
)

from .conftest import INFO

LOCK = OutputUse.ELECTRIC_LOCK
# As a DS-KD8003 can be set: COM2 rings a mechanical doorbell
DOORBELL = (Output(1, "COM1", LOCK), Output(2, "COM2", OutputUse.DOORBELL))
DOOR_2 = "button.door_station_open_door_2"
OUTPUT_2 = "sensor.door_station_output_2"


@pytest.fixture
def doorbell(door: MagicMock) -> MagicMock:
    """Mock a door station whose second output rings a doorbell."""
    door.read_info.return_value = replace(INFO, outputs=DOORBELL)
    door.read_outputs.return_value = DOORBELL
    return door


async def _set_up(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_a_door_without_a_lock(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entry: MockConfigEntry,
    doorbell: MagicMock,
) -> None:
    """Its button is unavailable, its output says why, and the card's key is refused."""
    await _set_up(hass, entry)
    assert hass.states.get(DOOR_2).state == STATE_UNAVAILABLE
    assert hass.states.get("button.door_station_open_door_1").state != (
        STATE_UNAVAILABLE
    )
    assert hass.states.get(OUTPUT_2).state == "doorbell"
    # The first output always drives the lock of door 1: nothing to tell
    assert hass.states.get("sensor.door_station_output_1") is None

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/subscribe", "entry_id": entry.entry_id}
    )
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["event"]["locks"] == [1]
    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/open_door", "entry_id": entry.entry_id, "door": 2}
    )
    reply = await client.receive_json()
    assert not reply["success"]
    assert reply["error"]["translation_key"] == "not_a_lock"
    doorbell.open_door.assert_not_awaited()


async def test_a_door_that_gains_its_lock(
    freezer: FrozenDateTimeFactory,
    hass: HomeAssistant,
    entry: MockConfigEntry,
    doorbell: MagicMock,
) -> None:
    """The outputs are read once a minute: its web page can change them."""
    await _set_up(hass, entry)
    doorbell.read_outputs.return_value = INFO.outputs
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(DOOR_2).state != STATE_UNAVAILABLE
    assert hass.states.get(OUTPUT_2).state == "electric_lock"


def test_the_outputs_worth_a_sensor() -> None:
    """Those whose use can change: told by the door station, or all its doors but 1."""
    offered = (
        Output(1, "COM1", LOCK, (LOCK,)),
        Output(2, "COM2", LOCK, (OutputUse.DISABLED, LOCK, OutputUse.DOORBELL)),
        Output(3, "COM3", LOCK, (LOCK, OutputUse.DOORBELL)),
    )
    told = replace(INFO, doors=(1, 2), outputs=offered)
    assert [output.number for output in changeable_outputs(told)] == [2, 3]
    untold = replace(INFO, doors=(1, 2), outputs=(*DOORBELL, Output(3, "COM3", LOCK)))
    assert [output.number for output in changeable_outputs(untold)] == [2]
