"""Constants of Hikvision Virtual Indoor Station."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from .version import __version__

DOMAIN: Final = "hikvision_virtual_indoor_station"

VERSION: Final = __version__
"""The version of the integration: "develop" in the repository, the tag in a release."""

FRONTEND_URL: Final = f"/{DOMAIN}/frontend/{VERSION}"
"""URL of the modules of the frontend, loaded by the frontend of every user.

The browsers keep the modules in their cache: the version in the path makes them load
the modules again when the integration is updated, and the card imports the dashboard
strategy by a relative path, which keeps the version.
"""

FRONTEND_MODULES: Final = (
    "hikvision-indoor-station-dashboard.js",
    "hikvision-indoor-station-card.js",
)
"""The modules of the frontend: the dashboard strategy and the card."""

# The SIP port of Home Assistant, where the VoIP line of each door station registers and
# calls. One for all door stations: the doors tell their calls apart by address.
SIP_PORT: Final = 5060
# Longest registration granted. The doors ask for 3600 s; a shorter one lets Home
# Assistant notice a door that went away within minutes (its keepalives keep NAT
# bindings, not the registration).
SIP_MAX_EXPIRES: Final = 600
# How often the registrations that ran out are forgotten.
SIP_PRUNE_SECONDS: Final = 30
# A registered door sends a keepalive (eXosip2's "jaK") every 20 s, measured on a
# DS-KD8003 (V3.7.3): three missed ones, and it is no longer heard. Its keepalives
# tell Home Assistant, right after a restart, that the door still calls it, before
# the door registers again.
SIP_KEEPALIVE_TIMEOUT: Final = 70
# How long a door may go unheard on SIP before a repair issue says its VoIP line does
# not point at Home Assistant: longer than a registration (SIP_MAX_EXPIRES), so that
# a door that only waits to register again is not reported.
SIP_UNHEARD_GRACE: Final = timedelta(seconds=SIP_MAX_EXPIRES + 60)

# How often the door station is asked who it is (one small ISAPI request): its
# entities are unavailable while it does not answer. The calls are pushed over SIP and
# are not polled.
HEALTH_INTERVAL: Final = timedelta(seconds=60)
# How often the values of its settings (image, volumes, doors, voice prompt) and its
# inputs are read again: they change only when someone changes them, and a DS-KD8003
# (V3.7.3) runs near its limit (88% of CPU measured with five video clients), so they
# are not asked for every minute. A change made here is seen at once.
SETTINGS_INTERVAL: Final = timedelta(minutes=5)

DEFAULT_USERNAME: Final = "admin"
DEFAULT_PORT: Final = 80

# What the doorbell event entity tells: a call rang, was answered, refused, missed,
# ended.
EVENT_RING: Final = "ring"
EVENT_ANSWERED: Final = "answered"
EVENT_REJECTED: Final = "rejected"
EVENT_MISSED: Final = "missed"
EVENT_ENDED: Final = "ended"
EVENT_TYPES: Final = [
    EVENT_RING,
    EVENT_ANSWERED,
    EVENT_REJECTED,
    EVENT_MISSED,
    EVENT_ENDED,
]

# The states of the call sensor (an ended call is idle again).
CALL_IDLE: Final = "idle"
CALL_RINGING: Final = "ringing"
CALL_ANSWERED: Final = "answered"
CALL_STATES: Final = [CALL_IDLE, CALL_RINGING, CALL_ANSWERED]

# A phone of the household as an extension of a door station (a subentry): it is
# notified when the door rings, and answers, refuses or opens the door from there.
SUBENTRY_EXTENSION: Final = "extension"
# The phone is not notified (its own do not disturb, for this door only).
CONF_DO_NOT_DISTURB: Final = "do_not_disturb"
# The phone's notification may open the door.
CONF_OPEN_DOOR: Final = "open_door"
# The integration of the Home Assistant app on phones, whose devices are extensions.
MOBILE_APP: Final = "mobile_app"
# The path of the indoor station panel: a door station's card on a page of its own,
# opened by the buttons of the phones' notifications (?entry=, call=, answer=1).
PANEL_PATH: Final = "hikvision-indoor-station"
