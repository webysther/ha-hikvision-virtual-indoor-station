"""The charts of the visits of a door station, as images (as ha-arpa-piemonte).

A chart is drawn when it is asked for, from the visits kept (a few kilobytes of SVG,
no request to the door). A dashboard asks again when its state changes, at each visit,
and when its access token is renewed (every 5 minutes): its days move on soon after
midnight without a timer of its own. Its state is when the last visit came.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import Final

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import IndoorStationConfigEntry
from .charts import days_chart, hours_chart
from .entity import IndoorStationEntity
from .station import IndoorStation
from .visits import Visit

# The charts are drawn from the visits kept in Home Assistant: nothing to ask the door
PARALLEL_UPDATES = 0

SVG: Final = "image/svg+xml"
"""The type of the charts: Home Assistant serves any image/ type."""


@dataclass(frozen=True, kw_only=True)
class ChartDescription(ImageEntityDescription):
    """A chart of the visits."""

    draw_fn: Callable[[tuple[Visit, ...], datetime, tzinfo], str]
    """Draw the chart of the visits, at a moment, in a time zone."""


CHARTS: Final = (
    ChartDescription(
        key="visits_by_hour",
        translation_key="visits_by_hour",
        draw_fn=lambda visits, _now, zone: hours_chart(visits, zone),
    ),
    ChartDescription(
        key="visits_by_day",
        translation_key="visits_by_day",
        draw_fn=lambda visits, now, zone: days_chart(visits, now.date(), zone),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndoorStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the charts of the visits of the door station."""
    station = entry.runtime_data
    async_add_entities(ChartImage(hass, station, description) for description in CHARTS)


class ChartImage(IndoorStationEntity, ImageEntity):
    """A chart of the visits of the door station, as SVG."""

    entity_description: ChartDescription
    _attr_content_type = SVG

    def __init__(
        self,
        hass: HomeAssistant,
        station: IndoorStation,
        description: ChartDescription,
    ) -> None:
        """Create a chart and draw it with the visits kept."""
        IndoorStationEntity.__init__(self, station, description.key)
        ImageEntity.__init__(self, hass)
        self.entity_description = description
        recent = station.visits.recent()
        self._attr_image_last_updated = recent[-1].rang_at if recent else None

    async def async_added_to_hass(self) -> None:
        """Change with each visit: a dashboard then asks for the chart again."""
        await super().async_added_to_hass()
        self.async_on_remove(self.station.visits.async_add_listener(self._visited))

    @callback
    def _visited(self) -> None:
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        """Draw the chart now, in the time zone of Home Assistant."""
        now = dt_util.now()
        zone = dt_util.get_default_time_zone()
        return self.entity_description.draw_fn(
            self.station.visits.recent(), now, zone
        ).encode()
