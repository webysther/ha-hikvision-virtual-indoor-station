"""Diagnostics of a door station: what it is, its registration, its call and its phones.

Masked: no addresses, names, account, nor the SIP Call-ID (it can carry the door's
address; the call's token stands for it). The phones say what they may do, not who
they are.
"""

from __future__ import annotations

from dataclasses import asdict
import time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import IndoorStationConfigEntry
from .phones import extensions_of, notify_service_of
from .version import __version__

TO_REDACT = {CONF_HOST, CONF_PASSWORD, CONF_USERNAME, "caller", "callee", "id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IndoorStationConfigEntry
) -> dict[str, Any]:
    """Return the diagnostics of an entry, without addresses, names or the account."""
    station = entry.runtime_data
    info = station.info
    identity = info.identity
    registration = station.registration
    call = station.call
    talkback = call.talkback if call is not None else None
    return {
        "version": __version__,
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "device": {
            "model": identity.model,
            "firmware": identity.firmware,
            "firmware_build": identity.firmware_build,
            "hardware": identity.hardware,
            "device_type": identity.device_type,
        },
        "doors": list(info.doors),
        "call_status": info.call_status,
        "speaker": info.talk.codec if info.talk is not None else None,
        "rtsp_port": info.rtsp_port,
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
    }
