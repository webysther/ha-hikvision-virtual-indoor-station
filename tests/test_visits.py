"""The visits: counted, kept across restarts, and drawn as charts."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

from aiohikvision import EndReason
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.image import async_get_image
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.hikvision_virtual_indoor_station.charts import COLORS
from custom_components.hikvision_virtual_indoor_station.visits import (
    HISTORY_DAYS,
    SAVE_DELAY,
    STORAGE_VERSION,
    Outcome,
    storage_key,
)

from .conftest import FakeCallServer

VISITS = "sensor.door_station_visits"
MISSED = "sensor.door_station_missed_visits"
BY_HOUR = "image.door_station_visits_by_hour"
BY_DAY = "image.door_station_visits_by_day"


async def chart(hass_client: ClientSessionGenerator, entity_id: str) -> str:
    """Return the SVG of a chart, as a dashboard gets it."""
    client = await hass_client()
    response = await client.get(f"/api/image_proxy/{entity_id}")
    assert response.status == 200
    assert response.content_type == "image/svg+xml"
    return await response.text()


async def drawn(hass: HomeAssistant, entity_id: str) -> str:
    """Return the SVG of a chart from its entity (the clock may move: no session)."""
    image = await async_get_image(hass, entity_id)
    assert image.content_type == "image/svg+xml"
    return image.content.decode()


async def visit(
    hass: HomeAssistant, server: FakeCallServer, call_id: str, outcome: Outcome
) -> None:
    """Have the door ring, and its call end in an outcome."""
    call = server.ring(call_id=call_id)
    if outcome is Outcome.ANSWERED:
        await server.answer(call_id)
        await server.hangup(call_id)
    elif outcome is Outcome.REJECTED:
        await server.reject(call_id)
    else:
        server.end(call, EndReason.CANCELLED)
    await hass.async_block_till_done()


async def saved(hass: HomeAssistant) -> None:
    """Let the visits be written: a while after a visit.

    The clock is not frozen here: a call keeps the monotonic clock it started with,
    which freezegun would move apart from the one of the station.
    """
    later = dt_util.utcnow() + timedelta(seconds=SAVE_DELAY + 1)
    async_fire_time_changed(hass, later)
    await hass.async_block_till_done()


def stored(hass_storage: dict[str, Any], entry: MockConfigEntry) -> dict[str, Any]:
    """Return what the storage of the visits of an entry holds."""
    data: dict[str, Any] = hass_storage[storage_key(entry.entry_id)]["data"]
    return data


async def test_each_visit_is_counted_and_drawn(
    hass: HomeAssistant,
    server: FakeCallServer,
    hass_client: ClientSessionGenerator,
) -> None:
    """A visit counts once its call is over, as answered, rejected or missed."""
    assert hass.states.get(VISITS).state == "0"
    assert "<path" not in await chart(hass_client, BY_HOUR)

    await visit(hass, server, "call-1", Outcome.ANSWERED)
    await visit(hass, server, "call-2", Outcome.REJECTED)
    await visit(hass, server, "call-3", Outcome.MISSED)
    # A call told again once over is the same visit
    server.end(server.calls["call-3"], EndReason.CANCELLED)
    await hass.async_block_till_done()

    assert hass.states.get(VISITS).state == "3"
    assert hass.states.get(MISSED).state == "1"
    hours = await chart(hass_client, BY_HOUR)
    days = await chart(hass_client, BY_DAY)
    assert '<path d="' in hours
    for color in COLORS.values():
        assert color in hours
        assert color in days
    assert ">3</text>" in hours  # the number of visits, in the middle of the clock


async def test_the_visits_are_kept_across_restarts(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    entry: MockConfigEntry,
    door: MagicMock,
    call_server: type[FakeCallServer],
) -> None:
    """The visits of the last weeks and the totals are read back; a new one is kept."""
    now = dt_util.utcnow()
    old = now - timedelta(days=HISTORY_DAYS + 1)
    hass_storage[storage_key(entry.entry_id)] = {
        "version": STORAGE_VERSION,
        "minor_version": 1,
        "key": storage_key(entry.entry_id),
        "data": {
            "visits": [
                {"at": (now - timedelta(days=1)).isoformat(), "outcome": "missed"},
                {"at": old.isoformat(), "outcome": "answered"},
                # Written by a later version: left out
                {"at": "yesterday", "outcome": "answered"},
                {"at": now.isoformat(), "outcome": "visited"},
            ],
            "totals": {"answered": 9, "missed": 5, "visited": 2},
        },
    }
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(VISITS).state == "14"
    assert hass.states.get(MISSED).state == "5"
    assert len(entry.runtime_data.visits.recent()) == 1

    await visit(hass, call_server.instances[-1], "call-1", Outcome.ANSWERED)
    await saved(hass)
    kept = stored(hass_storage, entry)
    assert [item["outcome"] for item in kept["visits"]] == ["missed", "answered"]
    assert kept["totals"] == {"answered": 10, "missed": 5}


async def test_the_charts_move_on_at_midnight(
    freezer: FrozenDateTimeFactory,
    hass: HomeAssistant,
    entry: MockConfigEntry,
    door: MagicMock,
) -> None:
    """A chart is drawn when it is asked for: its days move on at midnight."""
    zone = dt_util.get_default_time_zone()
    freezer.move_to(datetime(2026, 11, 27, 23, 59, 50, tzinfo=zone))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert ">27</text>" in await drawn(hass, BY_DAY)

    freezer.move_to(datetime(2026, 11, 28, 0, 0, 10, tzinfo=zone))
    days = await drawn(hass, BY_DAY)
    assert ">28</text>" in days
    assert ">27</text>" not in days


async def test_a_removed_door_station_forgets_its_visits(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    loaded: MockConfigEntry,
    server: FakeCallServer,
) -> None:
    """Removing the door station removes its visits."""
    await visit(hass, server, "call-1", Outcome.MISSED)
    await saved(hass)
    assert storage_key(loaded.entry_id) in hass_storage

    await hass.config_entries.async_remove(loaded.entry_id)
    await hass.async_block_till_done()
    assert storage_key(loaded.entry_id) not in hass_storage
