"""The commands of the cards: the state, the call by its id, the doors, and talking."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from aiohikvision import CallState, EndReason, TalkEnd, TalkError
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.hikvision_virtual_indoor_station.const import DOMAIN

from .conftest import FakeCallServer, FakeTalkback

FRAME = bytes(range(160))


class FakeSession:
    """An open talk through the door's speaker."""

    codec = "G.711ulaw"

    def __init__(self, on_end: Any) -> None:
        """Remember how to tell the end."""
        self.on_end = on_end
        self.sent: list[bytes] = []
        self.closed: list[TalkEnd] = []

    def send(self, frame: bytes) -> None:
        """Keep a frame."""
        self.sent.append(frame)

    async def close(self, reason: TalkEnd) -> None:
        """End, telling why."""
        self.closed.append(reason)
        self.on_end(reason)


def speaker(door: MagicMock) -> list[FakeSession]:
    """Have the door open fake talks; the list gets each one."""
    sessions: list[FakeSession] = []

    async def talk(on_end: Any) -> FakeSession:
        sessions.append(FakeSession(on_end))
        return sessions[-1]

    door.talk.side_effect = talk
    return sessions


async def test_the_state_and_its_changes(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded: MockConfigEntry,
    server: FakeCallServer,
) -> None:
    """The card gets the state at once, then at each change."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/subscribe", "entry_id": loaded.entry_id}
    )
    assert (await client.receive_json())["success"]
    first = (await client.receive_json())["event"]
    assert first == {
        "registered": False,
        "doors": [1, 2],
        "speaker": True,
        "call": None,
    }
    server.ring()
    ringing = (await client.receive_json())["event"]["call"]
    assert ringing["id"] == "call-1"
    assert ringing["state"] == "ringing"
    assert ringing["started_at"] is not None
    assert ringing["answered_at"] is None


async def test_unknown_entries(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, loaded: MockConfigEntry
) -> None:
    """Every command needs a loaded door station."""
    client = await hass_ws_client(hass)
    for command in (
        {"type": f"{DOMAIN}/subscribe"},
        {"type": f"{DOMAIN}/call", "call_id": "x", "action": "answer"},
        {"type": f"{DOMAIN}/open_door"},
        {"type": f"{DOMAIN}/talk"},
    ):
        await client.send_json_auto_id({**command, "entry_id": "nope"})
        reply = await client.receive_json()
        assert reply["error"]["code"] == "not_found"


async def test_the_call_by_its_id(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded: MockConfigEntry,
    server: FakeCallServer,
) -> None:
    """The first answer takes the call; a late or wrong id finds it gone."""
    call = server.ring()
    client = await hass_ws_client(hass)
    base = {"type": f"{DOMAIN}/call", "entry_id": loaded.entry_id}
    await client.send_json_auto_id({**base, "call_id": "old", "action": "answer"})
    reply = await client.receive_json()
    assert reply["error"]["translation_key"] == "call_gone"

    await client.send_json_auto_id({**base, "call_id": call.id, "action": "answer"})
    reply = await client.receive_json()
    assert reply["success"]
    assert reply["result"]["state"] == "answered"

    await client.send_json_auto_id({**base, "call_id": call.id, "action": "answer"})
    reply = await client.receive_json()
    assert reply["error"]["translation_key"] == "call_gone"

    await client.send_json_auto_id({**base, "call_id": call.id, "action": "hangup"})
    assert (await client.receive_json())["result"]["state"] == "ended"


async def test_refusing_by_id(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded: MockConfigEntry,
    server: FakeCallServer,
) -> None:
    """A card refuses the ringing call."""
    call = server.ring()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/call",
            "entry_id": loaded.entry_id,
            "call_id": call.id,
            "action": "reject",
        }
    )
    assert (await client.receive_json())["result"]["end_reason"] == "rejected"


async def test_opening_a_door(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded: MockConfigEntry,
    door: MagicMock,
) -> None:
    """The card's key."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/open_door", "entry_id": loaded.entry_id, "door": 2}
    )
    assert (await client.receive_json())["success"]
    door.open_door.assert_awaited_once_with(2)


async def flush(client: Any) -> None:
    """Wait until the server handled what was sent (it handles messages in order)."""
    await client.send_json_auto_id({"type": "ping"})
    assert (await client.receive_json())["type"] == "pong"


async def start_talk(client: Any, entry_id: str) -> tuple[int, dict[str, Any]]:
    """Subscribe to a talk; return its id and its "started" event."""
    await client.send_json_auto_id({"type": f"{DOMAIN}/talk", "entry_id": entry_id})
    reply = await client.receive_json()
    assert reply["success"], reply
    started = await client.receive_json()
    assert started["event"]["type"] == "started"
    return reply["id"], started["event"]


async def test_talking_with_the_call(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded: MockConfigEntry,
    server: FakeCallServer,
    door: MagicMock,
) -> None:
    """During an answered call the microphone goes with the call (SIP)."""
    call = server.ring()
    await server.answer(call.id)
    talkback = call.talkback
    assert isinstance(talkback, FakeTalkback)
    client = await hass_ws_client(hass)
    _, started = await start_talk(client, loaded.entry_id)
    assert started["target"] == "call"
    assert started["codec"] == "G.711ulaw"
    await client.send_bytes(bytes([started["handler_id"]]) + FRAME)
    await client.send_bytes(bytes([started["handler_id"]]) + FRAME)
    await flush(client)
    assert talkback.frames == [FRAME, FRAME]
    door.talk.assert_not_called()

    server._on_change(call)
    server.end(call, EndReason.DOOR_HUNG_UP)
    ended = await client.receive_json()
    assert ended["event"] == {"type": "ended", "reason": "call_ended"}


async def test_stopping_a_talk_with_the_call(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded: MockConfigEntry,
    server: FakeCallServer,
) -> None:
    """Releasing push-to-talk ends the subscription; the call goes on."""
    call = server.ring()
    await server.answer(call.id)
    client = await hass_ws_client(hass)
    talk_id, _ = await start_talk(client, loaded.entry_id)
    await client.send_json_auto_id(
        {"type": "unsubscribe_events", "subscription": talk_id}
    )
    assert (await client.receive_json())["success"]
    assert call.state is CallState.ANSWERED


async def test_talking_through_the_speaker(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded: MockConfigEntry,
    door: MagicMock,
) -> None:
    """Outside a call the microphone goes through the speaker (ISAPI)."""
    sessions = speaker(door)
    client = await hass_ws_client(hass)
    talk_id, started = await start_talk(client, loaded.entry_id)
    assert started["target"] == "speaker"
    await client.send_bytes(bytes([started["handler_id"]]) + FRAME)
    await flush(client)
    assert sessions[0].sent == [FRAME]
    await client.send_json_auto_id(
        {"type": "unsubscribe_events", "subscription": talk_id}
    )
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    assert sessions[0].closed == [TalkEnd.STOPPED]


async def test_the_door_ends_the_speaker_talk(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded: MockConfigEntry,
    door: MagicMock,
) -> None:
    """The device closing the talk, or another talk taking over, is told."""
    sessions = speaker(door)
    client = await hass_ws_client(hass)
    await start_talk(client, loaded.entry_id)
    sessions[0].on_end(TalkEnd.REPLACED)
    ended = await client.receive_json()
    assert ended["event"] == {"type": "ended", "reason": "replaced"}


async def test_a_call_answered_while_talking_through_the_speaker(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded: MockConfigEntry,
    server: FakeCallServer,
    door: MagicMock,
) -> None:
    """The speaker is mute during a call: the talk ends so the card can talk with it."""
    sessions = speaker(door)
    client = await hass_ws_client(hass)
    await start_talk(client, loaded.entry_id)
    call = server.ring()
    await server.answer(call.id)
    ended = await client.receive_json()
    assert ended["event"] == {"type": "ended", "reason": "call_answered"}
    await hass.async_block_till_done()
    assert sessions[0].closed == [TalkEnd.STOPPED]


async def test_a_speaker_that_does_not_open(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded: MockConfigEntry,
    door: MagicMock,
) -> None:
    """The reason goes to the card."""
    door.talk.side_effect = TalkError("talk_failed")
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/talk", "entry_id": loaded.entry_id}
    )
    reply = await client.receive_json()
    assert reply["error"]["code"] == "talk_failed"
