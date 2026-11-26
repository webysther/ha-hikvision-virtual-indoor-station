"""The visits of a door station: each ring, once its call is over, kept for the charts.

A visit is when the door rang and how its call ended (answered, rejected, missed): no
caller, no Call-ID. The visits of the last HISTORY_DAYS are kept in the storage of Home
Assistant, with a count of every visit ever, which the counters read: the recorder may
keep less, or leave the doorbell out.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final, TypedDict

from aiohikvision import CallState, DoorCall, EndReason
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

# The chart of the hours covers 8 weeks: enough rings to show a habit (deliveries in the
# morning, the school bus), recent enough to follow when it changes.
HISTORY_DAYS: Final = 8 * 7
STORAGE_VERSION: Final = 1
# Seconds before the visits are written: soon after a call, once for a few in a row.
SAVE_DELAY: Final = 10


class Outcome(StrEnum):
    """How the call of a visit ended."""

    ANSWERED = "answered"
    REJECTED = "rejected"
    MISSED = "missed"

    @classmethod
    def of(cls, call: DoorCall) -> Outcome:
        """Return how a call that is over ended, as the doorbell tells it."""
        if call.answered_at is not None:
            return cls.ANSWERED
        return cls.REJECTED if call.end_reason is EndReason.REJECTED else cls.MISSED


@dataclass(frozen=True, slots=True)
class Visit:
    """A ring at the door: when (UTC), and how its call ended."""

    rang_at: datetime
    outcome: Outcome


class StoredVisit(TypedDict):
    """A visit, as it is written."""

    at: str
    outcome: str


class StoredVisits(TypedDict):
    """What the storage of a door station holds."""

    visits: list[StoredVisit]
    totals: dict[str, int]


def storage_key(entry_id: str) -> str:
    """Return the name of the storage of the visits of an entry."""
    return f"{DOMAIN}.{entry_id}.visits"


def _visit(stored: StoredVisit) -> Visit | None:
    """Read a stored visit; None when it does not read (written by a later version)."""
    moment = dt_util.parse_datetime(stored.get("at", ""))
    try:
        outcome = Outcome(stored.get("outcome"))
    except ValueError:
        return None
    return Visit(moment, outcome) if moment is not None else None


class VisitLog:
    """The visits of a door station of the last HISTORY_DAYS, and how many came."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Create the log; async_load reads what was kept."""
        self._store: Store[StoredVisits] = Store(
            hass, STORAGE_VERSION, storage_key(entry_id), private=True
        )
        self._visits: list[Visit] = []
        self._totals: Counter[Outcome] = Counter()
        self._last_call: DoorCall | None = None
        self._listeners: list[Callable[[], None]] = []

    async def async_load(self) -> None:
        """Read the visits kept, dropping those older than HISTORY_DAYS."""
        stored = await self._store.async_load()
        if stored is None:
            return
        visits = (_visit(item) for item in stored.get("visits", []))
        self._visits = [visit for visit in visits if visit is not None]
        for name, count in stored.get("totals", {}).items():
            if name in Outcome:
                self._totals[Outcome(name)] = count
        self._prune()

    def recent(self) -> tuple[Visit, ...]:
        """Return the visits of the last HISTORY_DAYS, the oldest first."""
        return tuple(self._visits)

    def total(self, outcome: Outcome | None = None) -> int:
        """Return how many visits ever came, or ended in an outcome."""
        if outcome is None:
            return self._totals.total()
        return self._totals[outcome]

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call a listener when a visit is added; return what removes it."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def record(self, call: DoorCall, rang_at: datetime) -> None:
        """Add the visit of a call once it is over (once, however often it is told)."""
        if call.state is not CallState.ENDED or call is self._last_call:
            return
        self._last_call = call
        self.add(Visit(rang_at, Outcome.of(call)))

    @callback
    def add(self, visit: Visit) -> None:
        """Add a visit, keep it, and tell the listeners."""
        self._visits.append(visit)
        self._totals[visit.outcome] += 1
        self._prune()
        self._store.async_delay_save(self._stored, SAVE_DELAY)
        for listener in list(self._listeners):
            listener()

    async def async_remove(self) -> None:
        """Forget the visits: the door station is removed."""
        await self._store.async_remove()

    def _prune(self) -> None:
        oldest = dt_util.utcnow() - timedelta(days=HISTORY_DAYS)
        self._visits = sorted(
            (visit for visit in self._visits if visit.rang_at >= oldest),
            key=lambda visit: visit.rang_at,
        )

    def _stored(self) -> StoredVisits:
        return {
            "visits": [
                {"at": visit.rang_at.isoformat(), "outcome": visit.outcome.value}
                for visit in self._visits
            ],
            "totals": {outcome.value: count for outcome, count in self._totals.items()},
        }
