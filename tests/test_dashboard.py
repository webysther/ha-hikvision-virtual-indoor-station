"""Tests of the indoor station card and dashboard, served to the frontend."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import MagicMock, call, patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.hikvision_virtual_indoor_station.const import (
    FRONTEND_URL,
    VERSION,
)

ADD_EXTRA_JS_URL = (
    "custom_components.hikvision_virtual_indoor_station.dashboard."
    "frontend.add_extra_js_url"
)
REGISTER_PANEL = (
    "custom_components.hikvision_virtual_indoor_station.dashboard."
    "panel_custom.async_register_panel"
)
DASHBOARD = "hikvision-indoor-station-dashboard.js"
CARD = "hikvision-indoor-station-card.js"


async def _set_up(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_dashboard_is_offered_with_the_frontend(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    door: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that the strategy and the card are served, and loaded by the frontend."""
    assert await async_setup_component(hass, "http", {})
    # The frontend itself needs its package, absent from the tests
    hass.config.components.add("frontend")

    with (
        patch(ADD_EXTRA_JS_URL) as add_extra_js_url,
        patch(REGISTER_PANEL) as register_panel,
    ):
        await _set_up(hass, entry)

    # The panel the phones' notifications open, out of the sidebar
    register_panel.assert_awaited_once_with(
        hass,
        frontend_url_path="hikvision-indoor-station",
        webcomponent_name="hikvision-indoor-station-panel",
        module_url=f"{FRONTEND_URL}/{CARD}",
    )
    # The version in the path makes the browsers load them again after an update
    assert f"/hikvision_virtual_indoor_station/frontend/{VERSION}" == FRONTEND_URL
    assert add_extra_js_url.call_args_list == [
        call(hass, f"{FRONTEND_URL}/{DASHBOARD}"),
        call(hass, f"{FRONTEND_URL}/{CARD}"),
    ]
    client = await hass_client()
    response = await client.get(f"{FRONTEND_URL}/{DASHBOARD}")
    assert response.status == HTTPStatus.OK
    # Listed in the Add dashboard dialog
    assert "window).customStrategies" in await response.text()
    response = await client.get(f"{FRONTEND_URL}/{CARD}")
    assert response.status == HTTPStatus.OK
    # Listed in the card picker, importing the strategy with the same version
    text = await response.text()
    assert "window).customCards" in text
    assert f'from "./{DASHBOARD}"' in text


async def test_no_dashboard_without_the_frontend(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    door: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that nothing is served when the frontend does not run."""
    assert await async_setup_component(hass, "http", {})

    with (
        patch(ADD_EXTRA_JS_URL) as add_extra_js_url,
        patch(REGISTER_PANEL) as register_panel,
    ):
        await _set_up(hass, entry)

    add_extra_js_url.assert_not_called()
    register_panel.assert_not_called()
    client = await hass_client()
    response = await client.get(f"{FRONTEND_URL}/{DASHBOARD}")
    assert response.status == HTTPStatus.NOT_FOUND
