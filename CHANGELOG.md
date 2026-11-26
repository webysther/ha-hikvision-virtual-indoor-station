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
- The indoor station card (`custom:hikvision-indoor-station-card`), in the card
  picker: the door's camera, live while the door rings, during a call or while
  monitoring, and its picture otherwise; the state of the call; Answer and
  Reject while it rings, Hang up once answered, Monitor while idle (the door's
  sound plays once answered or monitored); a key for each door. A warning shows
  when the door station is not registered.
- Push-to-talk on the card: hold the button (or the space bar on it), or press
  it once to talk and once to stop (`talk_mode: toggle`). Your voice goes with
  an answered call, or through the door's speaker while idle; the door's sound
  is muted while you talk. The card says why a talk could not start (HTTPS, the
  microphone's permission) or why it ended.
- The browser rings while the door rings, with a button to mute it (remembered
  by each browser), and asks for a tap when the browser holds the sound. The
  time of an answered call is counted.
- Shortcuts on the card for other entities (a light, a scene, another door):
  buttons are pressed, scenes and scripts turned on, automations triggered, the
  rest toggled. The card has a visual editor: the door station, the way to talk
  and the shortcuts.
- The indoor station dashboard (`custom:hikvision-indoor-station`, in **Add
  dashboard**): a view for each door station, with its card and its activity.
- The README shows how to set the door station up, with pictures of its web page
  (VoIP line, number and call priority).
- The README in Italian and Brazilian Portuguese, with a section on the
  dashboard and the card.

### Changed since 2026.11.0b1

- Requires aiohikvision 0.1.1: door stations reached over HTTPS keep the TLS
  settings of Home Assistant's session.
- The integration is in the **Doorbells and intercoms** category.
- The code is now under the MIT license.

[Unreleased]: https://github.com/webysther/ha-hikvision-virtual-indoor-station/commits/main
