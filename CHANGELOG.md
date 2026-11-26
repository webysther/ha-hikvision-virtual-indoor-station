# Changelog

All notable changes to Hikvision Virtual Indoor Station are documented here. The
format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions
are `YEAR.MONTH.PATCH`.

## [Unreleased]

The first version: Home Assistant answers the calls of a Hikvision video door
station.

### Added

- A door station is added by its address and an account; a refused account asks
  to sign in again, and the address or account can be changed (Reconfigure).
- A SIP server for the door stations, shared by every entry: their VoIP line
  registers with Home Assistant and calls it.
- The doorbell event (`ring`, `answered`, `rejected`, `missed`, `ended`, with the
  call's id), the call sensor and the SIP registration sensor.
- Buttons to open each door, and to answer, hang up or refuse the call.
- The camera of the door station: its RTSP stream, with the visitor's voice, and
  snapshots.
- Websocket commands for the cards: the state of the door, the call by its id,
  opening a door, and talking (with the call during an answered call, through
  the door's speaker otherwise).
- The door station is asked who it is once a minute: its entities are unavailable
  while it does not answer.
- The SIP registration counts the door's keepalives too, so it is right after a
  restart of Home Assistant; a repair issue says how to point a door station that
  does not call Home Assistant.
- Icons for every entity and state, and original brand art.
- Diagnostics without addresses, names or account.

[Unreleased]: https://github.com/webysther/ha-hikvision-virtual-indoor-station/commits/main
