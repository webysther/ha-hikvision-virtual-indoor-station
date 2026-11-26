"""The charts of the visits, drawn alone (pure)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
import xml.etree.ElementTree as ET

import pytest

from custom_components.hikvision_virtual_indoor_station.charts import (
    COLORS,
    DAYS,
    count_ticks,
    days_chart,
    hours_chart,
)
from custom_components.hikvision_virtual_indoor_station.visits import Outcome, Visit

SVG = "{http://www.w3.org/2000/svg}"
# A zone one hour ahead of UTC, as Rome in winter
ROME = timezone(timedelta(hours=1))
TODAY = date(2026, 11, 27)  # a Friday


def at(day: date, hour: int, outcome: Outcome = Outcome.ANSWERED) -> Visit:
    """Return a visit at an hour of a day in Rome."""
    moment = datetime(day.year, day.month, day.day, hour, 30, tzinfo=ROME)
    return Visit(moment.astimezone(UTC), outcome)


def texts(svg: str) -> list[str]:
    """Return the texts of a chart, in order."""
    return [node.text or "" for node in ET.fromstring(svg).iter(f"{SVG}text")]


def fills(svg: str, tag: str) -> list[str]:
    """Return the fill of each element of a kind, in order."""
    return [node.get("fill", "") for node in ET.fromstring(svg).iter(f"{SVG}{tag}")]


@pytest.mark.parametrize(
    ("busiest", "ticks"),
    [
        (0, [0, 1]),
        (3, [0, 1, 2, 3]),
        (5, [0, 2, 4, 6]),
        (9, [0, 5, 10]),
        (30, [0, 10, 20, 30]),
        (250, [0, 100, 200, 300]),
    ],
)
def test_the_counts_of_the_axis(busiest: int, ticks: list[int]) -> None:
    """The axis counts in round steps, from 0 to at least the busiest."""
    assert count_ticks(busiest) == ticks


def test_a_clock_without_visits() -> None:
    """No visit: the clock is empty, its middle says 0."""
    svg = hours_chart([], ROME)
    assert not fills(svg, "path")
    assert "0" in texts(svg)  # the number of visits
    assert "%" not in svg


def test_the_clock_of_the_visits() -> None:
    """Each hour a slice, stacked by outcome; the hours of Rome, not of UTC."""
    visits = [
        at(TODAY, 0),  # 23:30 UTC the day before: midnight in Rome
        at(TODAY, 9),
        at(TODAY, 9, Outcome.MISSED),
        at(TODAY - timedelta(days=1), 9, Outcome.REJECTED),
    ]
    svg = hours_chart(visits, ROME)
    assert fills(svg, "path") == [
        COLORS[Outcome.ANSWERED],  # midnight
        COLORS[Outcome.ANSWERED],  # 9, from the middle out
        COLORS[Outcome.MISSED],
        COLORS[Outcome.REJECTED],
    ]
    labels = texts(svg)
    assert labels[:8] == ["0", "3", "6", "9", "12", "15", "18", "21"]
    assert "4" in labels  # the number of visits
    assert labels[-6:] == ["2", "50%", "1", "25%", "1", "25%"]


def test_the_days_of_the_visits() -> None:
    """The last 28 days, today the last; the weekends shaded, a label each week."""
    visits = [
        at(TODAY, 10),
        at(TODAY, 11, Outcome.MISSED),
        at(TODAY - timedelta(days=3), 10, Outcome.REJECTED),
        at(TODAY - timedelta(days=DAYS), 10),  # a day before the chart
    ]
    svg = days_chart(visits, TODAY, ROME)
    root = ET.fromstring(svg)
    rects = list(root.iter(f"{SVG}rect"))
    assert sum(rect.get("class") == "weekend" for rect in rects) == 8
    assert [rect.get("fill") for rect in rects if rect.get("fill")] == [
        COLORS[Outcome.REJECTED],
        COLORS[Outcome.ANSWERED],
        COLORS[Outcome.MISSED],
    ]
    days = [text for text in texts(svg) if text not in {"0", "1", "2"}]
    assert days == ["6", "13", "20", "27"]
