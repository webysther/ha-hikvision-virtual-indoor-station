"""The SIP server of the door stations: one UDP port, shared by the entries.

The VoIP line of each door station registers here and calls here. The server starts with
the first entry and stops with the last one; it hears only the door stations of the
entries, and hands each call and registration to the station of its address.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from aiohikvision import (
    CallError,
    CallServer,
    CallState,
    DoorCall,
    DoorRegistrar,
    DoorTransport,
    Registration,
)
from homeassistant.components.network import async_get_source_ip
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, SIP_MAX_EXPIRES, SIP_PORT, SIP_PRUNE_SECONDS

if TYPE_CHECKING:
    from .station import IndoorStation

_LOGGER = logging.getLogger(__name__)

DATA_SIP: HassKey[SipServer] = HassKey(f"{DOMAIN}_sip")
DATA_SIP_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_sip_lock")
# Where the server listens (read at start, so that the tests can listen on loopback).
BIND_HOST = "0.0.0.0"
PORT = SIP_PORT


class SipServer:
    """The registrar and the call server of the door stations."""

    def __init__(
        self, hass: HomeAssistant, advertise: str, host: str, port: int
    ) -> None:
        """Build the server; ``advertise`` is our address as the doors reach it."""
        self.hass = hass
        self.transport = DoorTransport(
            local_addr=(host, port), allowed_hosts=set(), on_keepalive=self._keepalive
        )
        self.registrar = DoorRegistrar(
            max_expires=SIP_MAX_EXPIRES, on_change=self._registered
        )
        self.calls = CallServer(
            self.transport,
            advertise=advertise,
            rtp_host=host,
            on_change=self._changed,
            registrar=self.registrar,
        )
        self._stations: dict[str, IndoorStation] = {}
        self._cancel_prune: Callable[[], None] | None = None
        self._cancel_stop: Callable[[], None] | None = None

    @property
    def contact(self) -> tuple[str, int]:
        """Where the door stations must send: our address as they reach it, and port."""
        return self.calls.advertise, self.address[1]

    @property
    def address(self) -> tuple[str, int]:
        """Where the server listens, once started."""
        udp = self.transport._udp_transport
        if udp is None:
            return self.transport.local_addr
        host, port = udp.get_extra_info("sockname")[:2]
        return str(host), int(port)

    async def start(self) -> None:
        """Listen; OSError if the port is taken (by another SIP server)."""
        await self.calls.start()
        self._cancel_prune = async_track_time_interval(
            self.hass, self._prune, timedelta(seconds=SIP_PRUNE_SECONDS)
        )
        self._cancel_stop = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._on_stop
        )
        _LOGGER.debug("SIP server listening on %s:%d", *self.address)

    async def stop(self) -> None:
        """Hang up the answered calls, refuse the ringing ones, and stop listening."""
        if self._cancel_prune is not None:
            self._cancel_prune()
            self._cancel_prune = None
        if self._cancel_stop is not None:
            self._cancel_stop()
            self._cancel_stop = None
        await self.calls.stop()

    async def _on_stop(self, _event: Event) -> None:
        self._cancel_stop = None  # a listener of one event is gone once it ran
        await self.stop()

    def add(self, station: IndoorStation) -> None:
        """Hear a door station, and tell its station what is already known of it."""
        self._stations[station.door_ip] = station
        self.transport.allowed_hosts.add(station.door_ip)
        if registration := self.registrar.registration(station.door_ip):
            station.registration_changed(registration)
        if call := self.calls.current(station.door_ip):
            station.call_changed(call)

    async def remove(self, station: IndoorStation) -> bool:
        """Stop hearing a door station, ending its call; True while others remain."""
        if self._stations.get(station.door_ip) is station:
            del self._stations[station.door_ip]
            self.transport.allowed_hosts.discard(station.door_ip)
            if call := self.calls.current(station.door_ip):
                try:
                    if call.state is CallState.ANSWERED:
                        await self.calls.hangup(call.id)
                    else:
                        await self.calls.reject(call.id, 480)
                except CallError:
                    pass  # it ended meanwhile
        return bool(self._stations)

    @callback
    def _keepalive(self, address: tuple[str, int]) -> None:
        if station := self._stations.get(address[0]):
            station.heard()

    @callback
    def _changed(self, call: DoorCall) -> None:
        if station := self._stations.get(call.door):
            station.call_changed(call)

    @callback
    def _registered(self, registration: Registration, registered: bool) -> None:
        if station := self._stations.get(registration.host):
            station.registration_changed(registration if registered else None)

    @callback
    def _prune(self, _now: datetime) -> None:
        self.registrar.prune()


async def async_acquire(hass: HomeAssistant, station: IndoorStation) -> SipServer:
    """Start the SIP server for the first door station, and hear the station."""
    async with hass.data.setdefault(DATA_SIP_LOCK, asyncio.Lock()):
        server = hass.data.get(DATA_SIP)
        if server is None:
            advertise = await async_get_source_ip(hass, target_ip=station.door_ip)
            server = SipServer(hass, advertise, BIND_HOST, PORT)
            await server.start()
            hass.data[DATA_SIP] = server
        server.add(station)
        return server


async def async_release(hass: HomeAssistant, station: IndoorStation) -> None:
    """Stop hearing a door station; the server stops with the last one."""
    async with hass.data.setdefault(DATA_SIP_LOCK, asyncio.Lock()):
        server = hass.data.get(DATA_SIP)
        if server is not None and not await server.remove(station):
            del hass.data[DATA_SIP]
            await server.stop()
