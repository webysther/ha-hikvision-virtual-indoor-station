"""Diagnostics of a door station: what it is, its registration, its call and its phones.

Masked: no addresses, names, account, nor the SIP Call-ID (it can carry the door's
address; the call's token stands for it). The phones say what they may do, not who
they are. The report of the device (aiohikvision's, read with GET only and anonymized)
holds what it answers and what the library is missing: attached to an issue, it is what
a fix needs.
"""

from __future__ import annotations

from dataclasses import asdict
import time
from typing import Any

from aiohikvision import HikvisionError
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import IndoorStationConfigEntry
from .phones import extensions_of, notify_service_of
from .version import __version__
from .visits import Outcome

TO_REDACT = {CONF_HOST, CONF_PASSWORD, CONF_USERNAME, "caller", "callee", "id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IndoorStationConfigEntry
) -> dict[str, Any]:
    """Return the diagnostics of an entry, without addresses, names or the account."""
    station = entry.runtime_data
    # They are created before the entry is loaded
    assert station.health is not None
    assert station.settings is not None
    info = station.info
    identity = info.identity
    registration = station.registration
    call = station.call
    talkback = call.talkback if call is not None else None
    assert station.device is not None
    try:
        report = (await station.device.report()).as_dict()
    except HikvisionError as err:
        report = {"error": type(err).__name__}
    return {
        "version": __version__,
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "device": {
            "model": identity.model,
            "firmware": str(identity.firmware),
            "hardware": identity.hardware,
            "device_type": identity.device_type,
        },
        "doors": list(info.doors),
        "call_status": info.call_status,
        "speaker": info.talk.codec if info.talk is not None else None,
        "rtsp_port": await station.streaming.rtsp_port() if station.streaming else None,
        "streams": [
            {
                "id": stream.id.isapi,
                "video": asdict(stream.video) if stream.video else None,
                "audio": stream.audio,
            }
            for stream in station.streams
        ],
        "sip": {
            "registered": registration is not None,
            "user_agent": registration.user_agent if registration else None,
            "expires_in": round(registration.expires_at - time.monotonic())
            if registration
            else None,
        },
        "call": async_redact_data(station.snapshot()["call"] or {}, TO_REDACT),
        "talkback": asdict(talkback.stats) if talkback is not None else None,
        "phones": [
            {
                "do_not_disturb": extension.do_not_disturb,
                "open_door": extension.open_door,
                "notify_service": notify_service_of(hass, extension.device_id)
                is not None,
            }
            for extension in extensions_of(entry)
        ],
        "load": asdict(station.health.data.load),
        "inputs": [item.use.value for item in info.inputs],
        # The values of its settings (levels and choices, nothing that names anyone)
        "settings": {
            f"{key}/{channel}": value.value
            for (key, channel), value in station.settings.data.values.items()
        },
        # How many visits, never when: their times tell the habits of a household
        "visits": {
            "kept": len(station.visits.recent()),
            "total": {
                outcome.value: station.visits.total(outcome) for outcome in Outcome
            },
        },
        "report": report,
    }
