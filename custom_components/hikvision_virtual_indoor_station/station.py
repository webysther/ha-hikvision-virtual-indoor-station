"""A door station and its calls, as the entities, services and cards of an entry see it.

The call itself lives in the SIP server (aiohikvision's ``CallServer``); the station
keeps the latest call of its door, tells the entities and the cards when it changes, and
carries out the commands: answer, hang up, reject (each naming the call, so a late click
never touches the next call), and open a door.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import time
from typing import TYPE_CHECKING, Final, overload

from aiohikvision import (
    CallError,
    CallState,
    DoorCall,
    DoorStation,
    DoorStationInfo,
    ImageValue,
    Setting,
)
from aiohikvision.isapi.wire.faults import BridgeFault
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.util import dt as dt_util

from .const import (
    CALL_ANSWERED,
    CALL_IDLE,
    CALL_RINGING,
    DOMAIN,
    SIP_KEEPALIVE_TIMEOUT,
    SIP_UNHEARD_GRACE,
)
from .visits import VisitLog

if TYPE_CHECKING:
    from aiohikvision import Registration
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import HealthCoordinator, SettingsCoordinator
    from .sip import SipServer


# A call is named outside Home Assistant by a digest of its SIP Call-ID: the phones'
# notifications cross Apple's and Google's push services, and a Call-ID can carry the
# door's address. 16 hex digits (64 bits) cannot be guessed while a call lasts.
TOKEN_LENGTH: Final = 16


def call_token(call_id: str) -> str:
    """Return the name of a call outside Home Assistant."""
    return hashlib.sha256(call_id.encode()).hexdigest()[:TOKEN_LENGTH]


@overload
def wall_clock(monotonic: float) -> datetime: ...
@overload
def wall_clock(monotonic: None) -> None: ...
@overload
def wall_clock(monotonic: float | None) -> datetime | None: ...
def wall_clock(monotonic: float | None) -> datetime | None:
    """When a moment of the monotonic clock was, in UTC."""
    if monotonic is None:
        return None
    return dt_util.utcnow() - timedelta(seconds=time.monotonic() - monotonic)


class IndoorStation:
    """The indoor station of one door station."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        door: DoorStation,
        info: DoorStationInfo,
        door_ip: str,
    ) -> None:
        """Build it; the SIP server is attached once it hears the door."""
        self.hass = hass
        self.entry = entry
        self.door = door
        self.info = info
        self.door_ip = door_ip
        self.sip: SipServer | None = None
        self.call: DoorCall | None = None
        self.registration: Registration | None = None
        self.health: HealthCoordinator | None = None
        self.settings: SettingsCoordinator | None = None
        self.visits = VisitLog(hass, entry.entry_id)
        # When the door's last keepalive arrived, and since when it is unheard
        self.last_heard: float | None = None
        self._unheard_since = time.monotonic()
        self._was_registered = False
        self._listeners: list[Callable[[], None]] = []
        self._call_listeners: list[Callable[[DoorCall], None]] = []

    @property
    def unique_id(self) -> str:
        """The serial of the door station, as identifiers take it."""
        return self.info.identity.stable_id

    @property
    def device_info(self) -> DeviceInfo:
        """The door station as a device."""
        identity = self.info.identity
        host = self.entry.data[CONF_HOST]
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            connections={(CONNECTION_NETWORK_MAC, identity.mac)}
            if identity.mac
            else set(),
            manufacturer="Hikvision",
            model=identity.model,
            name=identity.name,
            serial_number=identity.serial or None,
            sw_version=" ".join(
                part for part in (identity.firmware, identity.firmware_build) if part
            ),
            hw_version=identity.hardware,
            # Its web page over HTTPS, on the standard port whatever port ISAPI is
            # reached on: the account is typed into it
            configuration_url=f"https://{host}",
        )

    # ------------------------------------------------------------ state

    @property
    def call_state(self) -> str:
        """idle, ringing or answered."""
        if self.call is None or self.call.state is CallState.ENDED:
            return CALL_IDLE
        return CALL_ANSWERED if self.call.state is CallState.ANSWERED else CALL_RINGING

    @property
    def registered(self) -> bool:
        """Whether the door's VoIP line is registered here, or keeps alive with us.

        After a restart of Home Assistant the door only registers again when its
        registration runs out, but it keeps sending its keepalives: it still calls here.
        """
        if self.registration is not None:
            return True
        return (
            self.last_heard is not None
            and time.monotonic() - self.last_heard < SIP_KEEPALIVE_TIMEOUT
        )

    @property
    def issue_id(self) -> str:
        """The repair issue of a door that does not call Home Assistant."""
        return f"door_unheard_{self.entry.entry_id}"

    @property
    def talk_codec(self) -> str | None:
        """The G.711 variant of the microphone during the answered call."""
        call = self.call
        if (
            call is None
            or call.state is not CallState.ANSWERED
            or call.talkback is None
        ):
            return None
        return call.talkback.codec

    def snapshot(self) -> dict[str, object]:
        """Return the state the cards are given."""
        call = self.call
        return {
            "registered": self.registered,
            "doors": list(self.info.doors),
            "locks": list(self.info.locks),
            "speaker": self.info.talk is not None,
            "call": None
            if call is None
            else {
                "id": call.id,
                # How the phones' notifications name it (the panel answers by it)
                "token": call_token(call.id),
                "state": call.state.value,
                "caller": call.caller,
                "callee": call.callee,
                "end_reason": call.end_reason.value if call.end_reason else None,
                "started_at": _iso(wall_clock(call.started_at)),
                "answered_at": _iso(wall_clock(call.answered_at)),
                "ended_at": _iso(wall_clock(call.ended_at)),
            },
        }

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Be told of every change; returns the way to stop."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def async_add_call_listener(
        self, listener: Callable[[DoorCall], None]
    ) -> Callable[[], None]:
        """Be told of each change of a call; returns the way to stop."""
        self._call_listeners.append(listener)
        return lambda: self._call_listeners.remove(listener)

    @callback
    def call_changed(self, call: DoorCall) -> None:
        """Take a change of a call of this door: it rang, was answered or ended."""
        self.call = call
        self.visits.record(call, wall_clock(call.started_at))
        for listener in list(self._call_listeners):
            listener(call)
        self._notify()

    @callback
    def outputs_changed(self) -> None:
        """Take the outputs, read again: a door may have gained or lost its lock."""
        health = self.health.data if self.health is not None else None
        if health is None or health.outputs == self.info.outputs:
            return
        self.info = replace(self.info, outputs=health.outputs)
        self._notify()

    @callback
    def inputs_changed(self) -> None:
        """Take the inputs, read again: its web page can change what each one reads."""
        settings = self.settings.data if self.settings is not None else None
        if settings is None or settings.inputs == self.info.inputs:
            return
        self.info = replace(self.info, inputs=settings.inputs)
        self._notify()

    @callback
    def registration_changed(self, registration: Registration | None) -> None:
        """Take a change of the registration of the door's VoIP line."""
        self.registration = registration
        self.async_check_presence()

    @callback
    def heard(self) -> None:
        """Take a keepalive of the door: it still calls here."""
        self.last_heard = time.monotonic()
        if not self._was_registered:
            self.async_check_presence()

    @callback
    def async_check_presence(self) -> None:
        """Tell the entities when the door starts or stops calling here.

        A door unheard for longer than a registration lasts has a repair issue: its
        VoIP line does not point at Home Assistant.
        """
        registered = self.registered
        if registered:
            self._unheard_since = time.monotonic()
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
        elif time.monotonic() - self._unheard_since > SIP_UNHEARD_GRACE.total_seconds():
            address, port = ("", 0) if self.sip is None else self.sip.contact
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self.issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="door_unheard",
                translation_placeholders={
                    "name": self.entry.title,
                    "address": address,
                    "port": str(port),
                },
                learn_more_url="https://github.com/webysther/ha-hikvision-virtual-indoor-station#troubleshooting",
            )
        if registered != self._was_registered:
            self._was_registered = registered
            self._notify()

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # ------------------------------------------------------------ commands

    def _live_call(
        self, call_id: str | None, state: CallState, missing: str
    ) -> DoorCall:
        call = self.call
        if call is None or (call_id is None and call.state is not state):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key=missing
            )
        if (call_id is not None and call.id != call_id) or call.state is not state:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="call_gone"
            )
        return call

    def _server(self) -> SipServer:
        if self.sip is None:  # pragma: no cover (attached before the entities exist)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="no_sip"
            )
        return self.sip

    async def async_answer(self, call_id: str | None = None) -> DoorCall:
        """Answer the ringing call; the first who answers takes it."""
        call = self._live_call(call_id, CallState.RINGING, "no_ringing_call")
        try:
            return await self._server().calls.answer(call.id)
        except CallError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="answer_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def async_reject(self, call_id: str | None = None) -> DoorCall:
        """Refuse the ringing call: the door shows "busy"."""
        call = self._live_call(call_id, CallState.RINGING, "no_ringing_call")
        try:
            return await self._server().calls.reject(call.id)
        except CallError as err:  # pragma: no cover (it ended within the same tick)
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="call_gone"
            ) from err

    async def async_hangup(self, call_id: str | None = None) -> DoorCall:
        """End the answered call."""
        call = self._live_call(call_id, CallState.ANSWERED, "no_answered_call")
        try:
            return await self._server().calls.hangup(call.id)
        except CallError as err:  # pragma: no cover (it ended within the same tick)
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="call_gone"
            ) from err

    async def async_open_door(self, door: int = 1) -> None:
        """Open a door through its lock relay; refuse one whose output has no lock."""
        output = self.info.output_of(door)
        if door not in self.info.locks and output is not None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_a_lock",
                translation_placeholders={"door": str(door), "use": output.use.value},
            )
        try:
            await self.door.open_door(door)
        except BridgeFault as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="open_door_failed",
                translation_placeholders={"door": str(door), "error": str(err)},
            ) from err

    async def async_set_setting(self, setting: Setting, value: str) -> None:
        """Change a setting of the door station (it is read back); show it at once."""
        assert self.settings is not None  # created before the platforms
        current = self.settings.data.values.get(setting.ref)
        field = current.field if current is not None else setting.spec.fields[0]
        try:
            await self.door.write_setting(setting, field, value)
        except BridgeFault as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="setting_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        values = {**self.settings.data.values, setting.ref: ImageValue(field, value)}
        self.settings.async_set_updated_data(replace(self.settings.data, values=values))

    async def async_close(self) -> None:
        """End the talk through the speaker and drop the repair issue."""
        ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
        await self.door.close()


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment is not None else None
