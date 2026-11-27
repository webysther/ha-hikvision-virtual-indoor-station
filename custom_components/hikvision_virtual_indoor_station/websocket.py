"""The commands of the cards: the state of the door, the call, the doors, and talking.

Talking goes where the door station plays it: during an answered call, with the call
(SIP, in 40 ms packets); otherwise through its speaker (ISAPI two-way audio). The
browser sends 20 ms G.711 frames either way, in the variant the "started" event names.

Listening to an answered call gets the door's sound as it sends it over SIP: 40 ms of
G.711 an event, which browsers whose camera player has no G.711 (Home Assistant's HLS)
cannot play from the camera.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any

from aiohikvision import CallState, DoorCall, TalkEnd, TalkError
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
import probatio

from .const import DOMAIN
from .station import IndoorStation

ACTIONS = ("answer", "hangup", "reject")


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Register the commands."""
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_call)
    websocket_api.async_register_command(hass, ws_open_door)
    websocket_api.async_register_command(hass, ws_talk)
    websocket_api.async_register_command(hass, ws_listen)


def _station(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> IndoorStation | None:
    """Return the station of a loaded entry, or None after telling the client."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if (
        entry is None
        or entry.domain != DOMAIN
        or entry.state is not ConfigEntryState.LOADED
    ):
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "No such door station"
        )
        return None
    station: IndoorStation = entry.runtime_data
    return station


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/subscribe",
        probatio.Required("entry_id"): str,
    }
)
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send the state of the door station now, and at each change."""
    station = _station(hass, connection, msg)
    if station is None:
        return

    @callback
    def send() -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], station.snapshot())
        )

    connection.subscriptions[msg["id"]] = station.async_add_listener(send)
    connection.send_result(msg["id"])
    send()


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/listen",
        probatio.Required("entry_id"): str,
        probatio.Required("call_id"): str,
    }
)
@callback
def ws_listen(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send the door's sound of a call as it comes, once the call is answered.

    Each event is 40 ms of G.711 (``audio``, base64) in the variant of the call
    (``codec``). Nothing comes for another call, nor once the call is over.
    """
    station = _station(hass, connection, msg)
    if station is None:
        return

    @callback
    def heard(call: DoorCall, payload: bytes) -> None:
        if call.id != msg["call_id"] or call.talkback is None:
            return
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "audio": base64.b64encode(payload).decode(),
                    "codec": call.talkback.codec,
                },
            )
        )

    connection.subscriptions[msg["id"]] = station.async_add_audio_listener(heard)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/call",
        probatio.Required("entry_id"): str,
        probatio.Required("call_id"): str,
        probatio.Required("action"): probatio.In(ACTIONS),
    }
)
@websocket_api.async_response
async def ws_call(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Answer, hang up or refuse a call by its id (a late click finds it gone)."""
    station = _station(hass, connection, msg)
    if station is None:
        return
    command = {
        "answer": station.async_answer,
        "hangup": station.async_hangup,
        "reject": station.async_reject,
    }[msg["action"]]
    await command(msg["call_id"])
    connection.send_result(msg["id"], station.snapshot()["call"])


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/open_door",
        probatio.Required("entry_id"): str,
        probatio.Optional("door", default=1): probatio.All(int, probatio.Range(min=1)),
    }
)
@websocket_api.async_response
async def ws_open_door(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Open a door."""
    station = _station(hass, connection, msg)
    if station is None:
        return
    await station.async_open_door(msg["door"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {probatio.Required("type"): f"{DOMAIN}/talk", probatio.Required("entry_id"): str}
)
@websocket_api.async_response
async def ws_talk(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Talk to the door for as long as the subscription lasts.

    Once the door is ready, a "started" event says which binary handler takes the
    microphone, in which G.711 variant, and where it goes ("call" or "speaker").
    Unsubscribing, or the browser leaving, ends the talk; the door ending it, the call
    ending, or a call answered while talking through the speaker is told as an "ended"
    event.
    """
    station = _station(hass, connection, msg)
    if station is None:
        return
    talk = _Talk(hass, connection, msg["id"])
    call = station.call
    codec = station.talk_codec
    if call is not None and call.state is CallState.ANSWERED and codec is not None:
        _talk_with_call(talk, station, call, codec)
    else:
        await _talk_through_speaker(talk, station)


class _Talk:
    """One talk of a card: where its frames go, and how it ends."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg_id: int,
    ) -> None:
        self.hass = hass
        self.connection = connection
        self.msg_id = msg_id
        self.cleanup: list[Callable[[], None]] = []
        self.stopping = False
        self.ended = False

    @callback
    def started(
        self,
        receive: Callable[[bytes], None],
        stop: Callable[[], None],
        codec: str,
        target: str,
    ) -> None:
        """Take the microphone, and tell the card where it goes."""

        @callback
        def binary(
            _hass: HomeAssistant,
            _connection: websocket_api.ActiveConnection,
            data: bytes,
        ) -> None:
            receive(data)

        handler_id, unregister = self.connection.async_register_binary_handler(binary)
        self.cleanup.append(unregister)
        self.connection.subscriptions[self.msg_id] = stop
        self.connection.send_result(self.msg_id)
        self.connection.send_message(
            websocket_api.event_message(
                self.msg_id,
                {
                    "type": "started",
                    "handler_id": handler_id,
                    "codec": codec,
                    "target": target,
                },
            )
        )

    @callback
    def finish(self, reason: str) -> None:
        """End once; the card hears why, unless it stopped the talk itself."""
        if self.ended:
            return
        self.ended = True
        for undo in self.cleanup:
            undo()
        if not self.stopping:
            # The talk ended on its own; an unsubscription removes itself
            self.connection.subscriptions.pop(self.msg_id, None)
            self.connection.send_message(
                websocket_api.event_message(
                    self.msg_id, {"type": "ended", "reason": reason}
                )
            )


def _talk_with_call(
    talk: _Talk, station: IndoorStation, call: DoorCall, codec: str
) -> None:
    """Send the microphone with the answered call (SIP)."""

    @callback
    def call_changed(changed: DoorCall) -> None:
        if changed is call and changed.state is CallState.ENDED:
            talk.finish("call_ended")

    @callback
    def stop() -> None:
        talk.stopping = True
        talk.finish("stopped")

    talk.cleanup.append(station.async_add_call_listener(call_changed))
    talk.started(call.push, stop, codec, "call")


async def _talk_through_speaker(talk: _Talk, station: IndoorStation) -> None:
    """Send the microphone through the door's speaker (ISAPI two-way audio)."""
    try:
        session = await station.door.talk(lambda reason: talk.finish(reason.value))
    except TalkError as err:
        talk.connection.send_error(talk.msg_id, err.reason, err.reason)
        return

    @callback
    def answered_meanwhile(changed: DoorCall) -> None:
        # The speaker is mute during a call: the card talks with the call instead
        if changed.state is CallState.ANSWERED:
            talk.finish("call_answered")
            talk.hass.async_create_task(session.close(TalkEnd.STOPPED))

    @callback
    def stop() -> None:
        talk.stopping = True
        talk.hass.async_create_task(session.close(TalkEnd.STOPPED))

    talk.cleanup.append(station.async_add_call_listener(answered_meanwhile))
    talk.started(session.send, stop, session.codec, "speaker")
