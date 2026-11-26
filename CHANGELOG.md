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
  snapshots. A snapshot takes the shape of the live video: a door station takes
  its pictures at a size of its own (11:9 on a DS-KD8003, which streams 16:9),
  which squeezed the picture in every card.
- Websocket commands for the cards: the state of the door, the call by its id,
  opening a door, and talking (with the call during an answered call, through
  the door's speaker otherwise).
- The door station is asked who it is once a minute: its entities are unavailable
  while it does not answer.
- The SIP registration counts the door's keepalives too, so it is right after a
  restart of Home Assistant; a repair issue says how to point a door station that
  does not call Home Assistant.
- Icons for every entity and state, and original brand art.
- Diagnostics without addresses, names, account or SIP Call-ID; they tell what
  each phone may do, not who it is.
- The indoor station card (`custom:hikvision-indoor-station-card`), in the card
  picker: a standard card of the theme, laid out like an indoor station. The
  door's camera is on top, with the name and the state of the call (**Live**
  while monitoring); its picture keeps the shape of the live video. The keys
  under it are always in the same places and lit when they can be pressed:
  Answer (green), Hang up (red, refusing a call that rings), Monitor, Push to
  talk and the ringer. The camera plays live while the door rings, during a call
  or while monitoring, and shows its picture otherwise; the door's sound plays
  once answered or monitored. A key for each door and the shortcuts sit under
  them. A warning shows when the door station is not registered.
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
- Phones with the Home Assistant app are added to a door station as its
  extensions (**Add phone** on its entry), each with its own do not disturb and
  whether it may open the door. Adding or changing one does not interrupt a
  call.
- The phones ring with the door station: a notification with the door's
  picture, delivered at once (time-sensitive on iOS, high priority on Android),
  with **Answer**, **Open door** (on an unlocked iPhone) and **Reject**. Answer
  opens the indoor station panel, which answers that call on the phone. The
  buttons work only while their call lasts, and the
  notification goes away when the call is answered elsewhere, missed or over.
  The notifications name the call by a digest, never by its SIP Call-ID. A
  phone that leaves Home Assistant has a repair issue, whose fix removes it
  from the door station.
- The indoor station panel: a door station's card on a page of its own, out of
  the sidebar, opened by the notifications.
- The indoor station dashboard (`custom:hikvision-indoor-station`, in **Add
  dashboard**): a view for each door station, named after it, with its card and
  its activity.
- The README shows how to set the door station up, with pictures of its web page
  (VoIP line, number and call priority).
- The README in Italian and Brazilian Portuguese, with a section on the
  dashboard and the card.

- A door opens only when its output drives a lock: the door stations list every
  door they can open remotely, even one whose relay rings a doorbell or drives
  nothing (Access Control → I/O Settings). Its button is unavailable, the card's
  key is off, and an **Output** diagnostic sensor tells what each changeable
  output drives (electric lock, doorbell, disabled). The outputs are read once a
  minute, as the door station's web page can change them.

### Changed since 2026.11.0b1

- Requires aiohikvision 0.1.2: door stations reached over HTTPS keep the TLS
  settings of Home Assistant's session, and what the outputs drive is read.
- The door station is asked what its outputs drive once a minute, in place of who
  it is: still one small request.
- The integration is in the **Doorbells and intercoms** category.
- The code is now under the MIT license.
- **Visit** on the device page opens the web page of the door station over
  HTTPS.

[Unreleased]: https://github.com/webysther/ha-hikvision-virtual-indoor-station/commits/main
