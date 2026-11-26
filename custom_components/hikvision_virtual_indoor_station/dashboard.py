"""The indoor station card and dashboard, offered by the frontend of Home Assistant.

The card (frontend/hikvision-indoor-station-card.js) is the screen of an indoor
station: the door's camera, the call (answer, refuse, hang up), the doors and
push-to-talk. The dashboard is a strategy
(frontend/hikvision-indoor-station-dashboard.js): a script the frontend runs to
build a view for each door station, with that card and native cards. The
integration serves both and has the frontend load them, so the dashboard can be
added and the card is in the card picker as soon as the integration is installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import FRONTEND_MODULES, FRONTEND_URL

FRONTEND_DIRECTORY: Final = Path(__file__).parent / "frontend"
"""The modules of the frontend: JavaScript without dependencies or build."""


async def async_offer_the_frontend(hass: HomeAssistant) -> None:
    """Serve the card and the dashboard strategy, and have the frontend load them.

    Only when the frontend runs: without it there is nothing to offer.
    """
    if "frontend" not in hass.config.components:
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL, str(FRONTEND_DIRECTORY))]
    )
    for module in FRONTEND_MODULES:
        frontend.add_extra_js_url(hass, f"{FRONTEND_URL}/{module}")
