"""The charts of the visits of a door station, drawn as SVG (pure: no I/O).

When the door rings, as a 24-hour clock, and the visits of each of the last days. As
the charts of ha-arpa-piemonte, they carry no words, only numbers, so they read the
same in every language; their colours are those of the keys of the card (answered
green, rejected red) and of a missed call (amber), and read on a light or a dark
background.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import date, timedelta, tzinfo
import math
from typing import Final

from .visits import Outcome, Visit

WIDTH: Final = 640
"""Width of a drawing, in SVG units; it scales to the card."""
HEIGHT: Final = 240
"""Height of a drawing, in SVG units."""
FONT_SIZE: Final = 11

COLORS: Final = {
    Outcome.ANSWERED: "#43a047",
    Outcome.MISSED: "#ffa600",
    Outcome.REJECTED: "#db4437",
}
"""The colours of the outcomes: the defaults of Home Assistant's success, warning and
error colours, which the card uses for its keys."""
ORDER: Final = (Outcome.ANSWERED, Outcome.MISSED, Outcome.REJECTED)
"""How the outcomes stack: from the centre of the clock, from the bottom of a bar."""

STYLE: Final = (
    "text{fill:#888}.grid{stroke:#888;stroke-opacity:.25;fill:none}"
    ".weekend{fill:#888;fill-opacity:.08}"
    "@media (prefers-color-scheme:light){text{fill:#555}}"
    "@media (prefers-color-scheme:dark){text{fill:#bbb}}"
)
"""Grey text, darker on a light background and lighter on a dark one when the viewer
says which (as ha-arpa-piemonte)."""

# The clock: midnight on top, the hours clockwise, as on a watch.
CLOCK_X: Final = 120
CLOCK_Y: Final = 120
CLOCK_HOLE: Final = 34
"""Radius of the hole in the middle, which holds the number of visits."""
CLOCK_RADIUS: Final = 100
"""Radius of the busiest hour."""
HOUR_GAP: Final = 1.5
"""Degrees between two hours."""
HOURS_BETWEEN_LABELS: Final = 3
TOTAL_FONT_SIZE: Final = 26

# The share of each outcome, on the right of the clock.
SHARE_LEFT: Final = 268
SHARE_WIDTH: Final = 344
SHARE_TOP: Final = 92
SHARE_HEIGHT: Final = 14
COUNT_FONT_SIZE: Final = 22

DAYS: Final = 28
"""The days of the chart of the days: 4 weeks, today the last."""
DAYS_BETWEEN_LABELS: Final = 7
"""A label each week, counted back from today."""
LEFT: Final = 36
"""Room on the left of the plot, for the counts."""
RIGHT: Final = 8
TOP: Final = 14
BOTTOM: Final = 24
"""Room under the plot, for the days of the month."""
BAR_GAP: Final = 0.25
"""The share of a day left empty between two bars."""
COUNT_TICKS: Final = 4
"""At most this many steps on the axis of the counts."""
SATURDAY: Final = 5
"""``date.weekday()`` of Saturday; Sunday follows."""


def hours_chart(visits: Iterable[Visit], zone: tzinfo) -> str:
    """Return when the door rings: a 24-hour clock of the visits, and their outcomes.

    Each hour is a slice whose area grows with its visits, stacked by outcome; the
    middle holds the number of visits, the right their share by outcome. The visits
    are those of the log (the last HISTORY_DAYS).
    """
    by_hour: Counter[tuple[int, Outcome]] = Counter()
    totals: Counter[Outcome] = Counter()
    for visit in visits:
        by_hour[visit.rang_at.astimezone(zone).hour, visit.outcome] += 1
        totals[visit.outcome] += 1
    busiest = max(
        (sum(by_hour[hour, o] for o in ORDER) for hour in range(24)), default=0
    )
    parts = [
        _open(),
        f'<circle class="grid" cx="{CLOCK_X}" cy="{CLOCK_Y}" r="{CLOCK_RADIUS}"/>',
        f'<circle class="grid" cx="{CLOCK_X}" cy="{CLOCK_Y}" r="{CLOCK_HOLE}"/>',
    ]
    for hour in range(24):
        if hour % HOURS_BETWEEN_LABELS == 0:
            x, y = _point(_angle(hour + 0.5), CLOCK_RADIUS + 12)
            parts.append(_text(x, y + FONT_SIZE / 3, str(hour), "middle"))
        reached = 0
        for outcome in ORDER:
            count = by_hour[hour, outcome]
            if not count:
                continue
            inner = _radius(reached, busiest)
            reached += count
            parts.append(
                _slice(hour, inner, _radius(reached, busiest), COLORS[outcome])
            )
    total = totals.total()
    parts.append(
        _text(
            CLOCK_X,
            CLOCK_Y + TOTAL_FONT_SIZE / 3,
            str(total),
            "middle",
            TOTAL_FONT_SIZE,
        )
    )
    parts.extend(_shares(totals))
    parts.append("</svg>")
    return "".join(parts)


def days_chart(visits: Iterable[Visit], today: date, zone: tzinfo) -> str:
    """Return the visits of each of the last DAYS days, today the last, by outcome.

    The weekends are shaded; under the bars, the day of the month once a week.
    """
    first = today - timedelta(days=DAYS - 1)
    by_day: Counter[tuple[date, Outcome]] = Counter()
    for visit in visits:
        day = visit.rang_at.astimezone(zone).date()
        if first <= day <= today:
            by_day[day, visit.outcome] += 1
    days = [first + timedelta(days=offset) for offset in range(DAYS)]
    busiest = max(sum(by_day[day, o] for o in ORDER) for day in days)
    ticks = count_ticks(busiest)
    top = ticks[-1]
    plot_width = WIDTH - LEFT - RIGHT
    plot_height = HEIGHT - TOP - BOTTOM
    step = plot_width / DAYS
    bottom = TOP + plot_height

    def y_of(count: float) -> float:
        return bottom - plot_height * count / top

    parts = [_open()]
    for index, day in enumerate(days):
        x = LEFT + index * step
        if day.weekday() >= SATURDAY:
            parts.append(
                f'<rect class="weekend" x="{x:.1f}" y="{TOP}" '
                f'width="{step:.1f}" height="{plot_height}"/>'
            )
    for tick in ticks:
        y = y_of(tick)
        parts.append(_line(LEFT, y, WIDTH - RIGHT, y))
        parts.append(_text(LEFT - 6, y + FONT_SIZE / 3, str(tick), "end"))
    for index, day in enumerate(days):
        x = LEFT + (index + BAR_GAP / 2) * step
        reached = 0
        for outcome in ORDER:
            count = by_day[day, outcome]
            if not count:
                continue
            low, high = y_of(reached), y_of(reached + count)
            reached += count
            parts.append(
                f'<rect x="{x:.1f}" y="{high:.1f}" width="{step * (1 - BAR_GAP):.1f}" '
                f'height="{low - high:.1f}" fill="{COLORS[outcome]}"/>'
            )
        if (DAYS - 1 - index) % DAYS_BETWEEN_LABELS == 0:
            parts.append(
                _text(x + step * (1 - BAR_GAP) / 2, HEIGHT - 8, str(day.day), "middle")
            )
    parts.append("</svg>")
    return "".join(parts)


def count_ticks(busiest: int) -> list[int]:
    """Return the counts the axis marks: 0 to at least the busiest, in round steps."""
    step = 1
    while math.ceil(busiest / step) > COUNT_TICKS:
        step = _next_step(step)
    top = max(math.ceil(busiest / step), 1) * step
    return list(range(0, top + 1, step))


def _next_step(step: int) -> int:
    """Return the round step after a step: 1, 2, 5, 10, 20, 50, ..."""
    magnitude = 1
    while magnitude * 10 <= step:
        magnitude *= 10
    return next(lead * magnitude for lead in (2, 5, 10) if lead * magnitude > step)


def _shares(totals: Counter[Outcome]) -> Sequence[str]:
    """Draw the share of each outcome: a bar split by outcome, each count under it."""
    total = totals.total()
    parts = [
        f'<rect class="grid" x="{SHARE_LEFT}" y="{SHARE_TOP}" width="{SHARE_WIDTH}" '
        f'height="{SHARE_HEIGHT}" rx="3"/>'
    ]
    x = float(SHARE_LEFT)
    column = SHARE_WIDTH / len(ORDER)
    for index, outcome in enumerate(ORDER):
        count = totals[outcome]
        if total and count:
            width = SHARE_WIDTH * count / total
            parts.append(
                f'<rect x="{x:.1f}" y="{SHARE_TOP}" width="{width:.1f}" '
                f'height="{SHARE_HEIGHT}" fill="{COLORS[outcome]}"/>'
            )
            x += width
        left = SHARE_LEFT + index * column
        mark_y = SHARE_TOP + SHARE_HEIGHT + 22
        parts.append(
            f'<circle cx="{left + 6}" cy="{mark_y}" r="5" fill="{COLORS[outcome]}"/>'
        )
        parts.append(
            _text(
                left + 18,
                mark_y + COUNT_FONT_SIZE / 3,
                str(count),
                size=COUNT_FONT_SIZE,
            )
        )
        if total:
            share = f"{round(100 * count / total)}%"
            parts.append(_text(left + 18, mark_y + 24, share))
    return parts


def _open() -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" font-family="sans-serif" '
        f'font-size="{FONT_SIZE}"><style>{STYLE}</style>'
    )


def _radius(count: float, busiest: int) -> float:
    """Return the radius that gives a slice an area that grows with its count."""
    share = count / busiest
    return math.sqrt(CLOCK_HOLE**2 + (CLOCK_RADIUS**2 - CLOCK_HOLE**2) * share)


def _angle(hour: float) -> float:
    """Return the angle of a moment of the day, in radians: midnight up, clockwise."""
    return math.radians(hour * 15 - 90)


def _point(angle: float, radius: float) -> tuple[float, float]:
    return CLOCK_X + radius * math.cos(angle), CLOCK_Y + radius * math.sin(angle)


def _slice(hour: int, inner: float, outer: float, color: str) -> str:
    """Draw a ring sector: the visits of an hour, between two radii."""
    gap = math.radians(HOUR_GAP / 2)
    start, end = _angle(hour) + gap, _angle(hour + 1) - gap
    x1, y1 = _point(start, outer)
    x2, y2 = _point(end, outer)
    x3, y3 = _point(end, inner)
    x4, y4 = _point(start, inner)
    return (
        f'<path d="M{x1:.1f},{y1:.1f}A{outer:.1f},{outer:.1f} 0 0 1 {x2:.1f},{y2:.1f}'
        f"L{x3:.1f},{y3:.1f}A{inner:.1f},{inner:.1f} 0 0 0 {x4:.1f},{y4:.1f}Z"
        f'" fill="{color}"/>'
    )


def _line(x1: float, y1: float, x2: float, y2: float) -> str:
    return (
        f'<line class="grid" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>'
    )


def _text(
    x: float, y: float, content: str, anchor: str = "start", size: int | None = None
) -> str:
    font = f' font-size="{size}"' if size else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{font}>{content}</text>'
    )
