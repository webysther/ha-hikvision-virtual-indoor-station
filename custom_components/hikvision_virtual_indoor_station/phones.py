"""The phones of a door station: a notification rings them when the door rings.

Each phone is an extension of the door station (a subentry). Its notification shows
the door, and its buttons answer (in the indoor station panel, where the call's sound
plays), open the door or refuse the call. When the call is answered elsewhere, missed
or over, the notification is taken back.

The notification goes through the notify service of the Home Assistant app on the
phone. mobile_app has no public way to that service: it names it after the phone's
name in its entry, which is followed here, in one place, and checked against the
services that exist. A phone without one is skipped.

A phone that leaves Home Assistant (its app removed or signed out) can no longer ring:
a repair issue says so, and its fix removes the phone from the door station.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohikvision import CallState, DoorCall
from homeassistant.const import CONF_DEVICE_ID, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import slugify

from .const import (
    CONF_DO_NOT_DISTURB,
    CONF_OPEN_DOOR,
    DOMAIN,
    MOBILE_APP,
    PANEL_PATH,
    SUBENTRY_EXTENSION,
)
from .station import call_token

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry

    from .station import IndoorStation

_LOGGER = logging.getLogger(__name__)

NOTIFY: Final = "notify"
# Where the Home Assistant app keeps the name of its phone in its entry; mobile_app
# names the phone's notify service after it (mobile_app.const.ATTR_DEVICE_NAME).
APP_DEVICE_NAME: Final = "device_name"
# The event the Home Assistant app fires when a button of a notification is pressed.
ACTION_EVENT: Final = "mobile_app_notification_action"
# The message that takes a notification back from the phone, by its tag.
CLEAR_NOTIFICATION: Final = "clear_notification"
# The buttons of a ring: this integration's prefix, then what the button does (the door
# it opens), then the call it belongs to.
ACTION_PREFIX: Final = "HIKVISION_VIS"
ACTION_OPEN_DOOR: Final = "OPEN_DOOR"
ACTION_REJECT: Final = "REJECT"
# The action the app opens as an address instead of firing an event.
ACTION_URI: Final = "URI"
# The repair issue of a phone that left Home Assistant (one per phone).
ISSUE_PHONE_GONE: Final = "phone_gone"
# The Android channel of the rings: their own, so that their sound and importance can be
# set apart from the other notifications of Home Assistant.
ANDROID_CHANNEL: Final = "Door station"


@dataclass(frozen=True, slots=True)
class Extension:
    """A phone of a door station, as its subentry says."""

    device_id: str
    do_not_disturb: bool
    open_door: bool


def extensions_of(entry: ConfigEntry) -> list[Extension]:
    """Return the phones of a door station."""
    return [
        Extension(
            device_id=subentry.data[CONF_DEVICE_ID],
            do_not_disturb=subentry.data.get(CONF_DO_NOT_DISTURB, False),
            open_door=subentry.data.get(CONF_OPEN_DOOR, True),
        )
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_EXTENSION
    ]


@callback
def notify_service_of(hass: HomeAssistant, device_id: str) -> str | None:
    """Return the notify service of a phone (mobile_app_<its name>), or None."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None
    for entry_id in device.config_entries:
        app = hass.config_entries.async_get_entry(entry_id)
        if app is None or app.domain != MOBILE_APP or APP_DEVICE_NAME not in app.data:
            continue
        service = slugify(f"{MOBILE_APP}_{app.data[APP_DEVICE_NAME]}")
        if hass.services.has_service(NOTIFY, service):
            return service
    return None


def issue_id(subentry_id: str) -> str:
    """Return the repair issue of a phone that left Home Assistant."""
    return f"{ISSUE_PHONE_GONE}_{subentry_id}"


def panel_uri(entry_id: str, token: str, *, answer: bool = False) -> str:
    """Return the address of the indoor station panel for a call of a door station."""
    uri = f"/{PANEL_PATH}?entry={entry_id}&call={token}"
    return f"{uri}&answer=1" if answer else uri


class Phones:
    """The phones of one door station: they ring with it, and their buttons act."""

    def __init__(self, hass: HomeAssistant, station: IndoorStation) -> None:
        """Ring the phones of a station."""
        self.hass = hass
        self.station = station
        # The phones (their notify services) a ringing call rang, to take it back
        self._rung: dict[str, list[str]] = {}
        self._texts: dict[str, str] = {}
        # The phones (their subentries) that left Home Assistant: each has an issue
        self._gone: set[str] = set()

    async def async_start(self) -> Callable[[], None]:
        """Hear the calls and the buttons of the notifications; return how to stop."""
        self._texts = await async_get_translations(
            self.hass, self.hass.config.language, "entity", {DOMAIN}
        )
        stops = [
            self.station.async_add_call_listener(self._call_changed),
            self.hass.bus.async_listen(ACTION_EVENT, self._action),
            # A phone removed from Home Assistant
            self.hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED, self._devices_changed
            ),
            # A phone added, changed or removed (subentries do not reload the entry)
            self.station.entry.add_update_listener(self._async_entry_updated),
        ]
        self.async_check_phones()

        @callback
        def stop() -> None:
            for stop_one in stops:
                stop_one()
            for subentry_id in self._gone:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id(subentry_id))

        return stop

    def _text(self, key: str, default: str, **values: object) -> str:
        """Return a text of the integration's entities, in the server's language."""
        text = self._texts.get(f"component.{DOMAIN}.entity.{key}") or default
        return text.format(**values) if values else text

    # ------------------------------------------------------------ the phones

    @callback
    def async_check_phones(self) -> None:
        """Have a repair issue for each phone that left Home Assistant, only those."""
        entry = self.station.entry
        devices = dr.async_get(self.hass)
        gone: dict[str, ConfigSubentry] = {
            subentry.subentry_id: subentry
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_EXTENSION
            and devices.async_get(subentry.data[CONF_DEVICE_ID]) is None
        }
        for subentry_id in self._gone - gone.keys():
            ir.async_delete_issue(self.hass, DOMAIN, issue_id(subentry_id))
        for subentry_id, subentry in gone.items():
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id(subentry_id),
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_PHONE_GONE,
                translation_placeholders={"phone": subentry.title, "name": entry.title},
                data={"entry_id": entry.entry_id, "subentry_id": subentry_id},
            )
        self._gone = set(gone)

    @callback
    def _devices_changed(self, event: Event[dr.EventDeviceRegistryUpdatedData]) -> None:
        self.async_check_phones()

    async def _async_entry_updated(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        self.async_check_phones()

    # ------------------------------------------------------------ the calls

    @callback
    def _call_changed(self, call: DoorCall) -> None:
        if call.state is CallState.RINGING:
            if call.id not in self._rung:
                self._ring(call)
        elif services := self._rung.pop(call.id, None):
            # Answered here or on another phone, refused, missed or over
            tag = self._tag(call_token(call.id))
            for service in services:
                self._send(
                    service, {"message": CLEAR_NOTIFICATION, "data": {"tag": tag}}
                )

    def _ring(self, call: DoorCall) -> None:
        token = call_token(call.id)
        services: list[str] = []
        for extension in extensions_of(self.station.entry):
            if extension.do_not_disturb:
                continue
            service = notify_service_of(self.hass, extension.device_id)
            if service is None:
                _LOGGER.debug("Phone %s has no notify service", extension.device_id)
                continue
            services.append(service)
            self._send(service, self._ring_message(token, extension))
        self._rung[call.id] = services

    def _tag(self, token: str) -> str:
        """Return the tag of a call's notifications: one per call, taken back by it."""
        return f"{DOMAIN}-{token}"

    def _ring_message(self, token: str, extension: Extension) -> dict[str, Any]:
        """Return the notification of a ring for a phone."""
        entry_id = self.station.entry.entry_id
        opening = panel_uri(entry_id, token)
        data: dict[str, Any] = {
            "tag": self._tag(token),
            "url": opening,  # iOS: a tap opens the door station's panel
            "clickAction": opening,  # Android: the same
            "push": {"interruption-level": "time-sensitive"},  # iOS: past focus modes
            "priority": "high",  # Android: delivered at once,
            "ttl": 0,  # even to a phone asleep
            "channel": ANDROID_CHANNEL,
            "importance": "high",
            "actions": self._actions(token, extension),
        }
        if camera := self._camera():
            data["image"] = f"/api/camera_proxy/{camera}"
            data["entity_id"] = camera  # iOS: the live camera, once opened
        return {
            "title": self.station.entry.title,
            "message": self._text(
                "event.doorbell.state_attributes.event_type.state.ring", "Ringing"
            ),
            "data": data,
        }

    def _actions(self, token: str, extension: Extension) -> list[dict[str, Any]]:
        """Return the buttons of a ring: answer, open the door, refuse (Android: 3)."""
        actions: list[dict[str, Any]] = [
            {
                "action": ACTION_URI,
                "title": self._text("button.answer.name", "Answer"),
                "uri": panel_uri(self.station.entry.entry_id, token, answer=True),
            }
        ]
        locks = self.station.info.locks
        if extension.open_door and locks:
            door = locks[0]
            name = (
                self._text(
                    "button.open_door_numbered.name", "Open door {door}", door=door
                )
                if len(self.station.info.doors) > 1
                else self._text("button.open_door.name", "Open door")
            )
            actions.append(
                {
                    "action": f"{ACTION_PREFIX}_{ACTION_OPEN_DOOR}_{door}_{token}",
                    "title": name,
                    "activationMode": "background",
                    "authenticationRequired": True,  # iOS: unlocked phones only
                }
            )
        actions.append(
            {
                "action": f"{ACTION_PREFIX}_{ACTION_REJECT}_{token}",
                "title": self._text("button.reject.name", "Reject"),
                "activationMode": "background",
                "destructive": True,
            }
        )
        return actions

    def _camera(self) -> str | None:
        """Return the camera of the door station, if it is in the entity registry."""
        return er.async_get(self.hass).async_get_entity_id(
            Platform.CAMERA, DOMAIN, f"{self.station.unique_id}_camera"
        )

    def _send(self, service: str, message: dict[str, Any]) -> None:
        """Send a notification, without holding the call up."""
        self.station.entry.async_create_task(
            self.hass, self._async_send(service, message), f"{DOMAIN} {service}"
        )

    async def _async_send(self, service: str, message: dict[str, Any]) -> None:
        try:
            await self.hass.services.async_call(NOTIFY, service, message, blocking=True)
        except HomeAssistantError as err:
            _LOGGER.warning("The phone's notification (%s) failed: %s", service, err)

    # ------------------------------------------------------------ the buttons

    @callback
    def _action(self, event: Event) -> None:
        """Do what a button of a ring asks, if it belongs to this door's call."""
        action = event.data.get("action")
        prefix = f"{ACTION_PREFIX}_"
        if not isinstance(action, str) or not action.startswith(prefix):
            return
        what, _, token = action.removeprefix(prefix).rpartition("_")
        call = self.station.call
        # Another door station's call, or a call that is over: its buttons are spent
        if (
            call is None
            or call.state is CallState.ENDED
            or call_token(call.id) != token
        ):
            return
        if what == ACTION_REJECT:
            self.station.entry.async_create_task(
                self.hass, self._async_do(self.station.async_reject(call.id))
            )
        elif what.startswith(f"{ACTION_OPEN_DOOR}_"):
            door = what.removeprefix(f"{ACTION_OPEN_DOOR}_")
            if door.isdigit():
                self.station.entry.async_create_task(
                    self.hass, self._async_do(self.station.async_open_door(int(door)))
                )

    async def _async_do(self, command: Any) -> None:
        """Carry out a button's command; a refusal is logged, as no one waits for it."""
        try:
            await command
        except HomeAssistantError as err:
            _LOGGER.warning("The notification's button failed: %s", err)
