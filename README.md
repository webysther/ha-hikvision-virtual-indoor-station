<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/webysther/ha-hikvision-virtual-indoor-station/main/custom_components/hikvision_virtual_indoor_station/brand/dark_logo@2x.png">
    <img src="https://raw.githubusercontent.com/webysther/ha-hikvision-virtual-indoor-station/main/custom_components/hikvision_virtual_indoor_station/brand/icon@2x.png" alt="" width="256">
  </picture>
</p>

<h1 align="center">Hikvision Virtual Indoor Station</h1>

<p align="center">Home Assistant as the indoor station of your Hikvision video door station: answer, talk and open the door from dashboards and phones</p>

<p align="center">
  <a href="https://github.com/webysther/ha-hikvision-virtual-indoor-station/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/webysther/ha-hikvision-virtual-indoor-station?include_prereleases&label=release&color=41BDF5"></a>
  <a href="https://www.home-assistant.io/integrations/marketplace/"><img alt="Marketplace custom repository" src="https://img.shields.io/badge/Marketplace-custom-41BDF5?logo=homeassistant&logoColor=white"></a>
  <a href="https://github.com/webysther/ha-hikvision-virtual-indoor-station/actions/workflows/tests.yaml"><img alt="Tests" src="https://github.com/webysther/ha-hikvision-virtual-indoor-station/actions/workflows/tests.yaml/badge.svg"></a>
  <a href="https://github.com/webysther/ha-hikvision-virtual-indoor-station/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/webysther/ha-hikvision-virtual-indoor-station?color=41BDF5"></a>
</p>

<p align="center"><b>English</b> · <a href="https://github.com/webysther/ha-hikvision-virtual-indoor-station/blob/main/README.it.md">Italiano</a> · <a href="https://github.com/webysther/ha-hikvision-virtual-indoor-station/blob/main/README.pt-BR.md">Português (Brasil)</a></p>

Make Home Assistant the indoor station of your Hikvision video door station. Its
button rings in Home Assistant, on your dashboards and phones: you answer, talk,
hang up or refuse the call, and open the door.

> **Status: in development.** Tested with a DS-KD8003-IME1(B), firmware V3.7.3.

## Why this integration

- **All in one.** The SIP server the door station calls, the card and a dashboard
  laid out like the screen of an indoor station come with the integration: no
  add-on, SIP server, MQTT broker or cloud account to set up next to it.
- **Hybrid, the best of each protocol.** SIP carries the call, as the door
  station expects from an indoor station; RTP carries your voice to the door, in
  the packets it plays best; RTSP brings its picture and sound; ISAPI opens the
  doors and talks through its speaker outside a call.
- **Platinum from day one.** It follows every rule of the top tier of the
  [integration quality scale](https://www.home-assistant.io/docs/quality_scale/):
  async, typed, fully tested, translated, with repairs, reauthentication and
  diagnostics. The protocol lives in its own library on PyPI,
  [aiohikvision](https://pypi.org/project/aiohikvision/).
- **Tested on real hardware.** Every behaviour it relies on was measured on a
  real door station (a DS-KD8003-IME1(B)), and calls are answered, refused and
  hung up on it.

## Features

- **The doorbell rings in Home Assistant.** The door station's VoIP line registers
  with Home Assistant and calls it: the visitor hears it ring, and the doorbell
  event fires.
- **Answer, hang up or refuse** from buttons, automations or the cards; every
  command names its call, so a late tap never touches the next visitor.
- **Talk to the visitor.** During a call your microphone goes to the door with the
  call; outside a call, through the door's speaker.
- **See and hear the visitor**: the camera of the door station, with its sound,
  played with WebRTC.
- **Open the doors** wired to the door station, one button each.
- **Your phones ring with the door**: a notification with the door's picture,
  through focus modes, with **Answer**, **Open door** and **Reject** on it.
- **Knows when the door cannot call**: a sensor of the SIP registration, and a
  repair issue that says how to point the door station at Home Assistant.

## Use cases

- A wall tablet or the phones of the household as the indoor station, with no
  Hikvision monitor and no cloud account.
- A notification with the visitor's picture when someone rings, and the door
  opened from it.
- Automations: a light at the door when it rings at night, the call refused while
  nobody is home, the gate opened for a known visitor.

## Installation

From the [Marketplace](https://www.home-assistant.io/integrations/marketplace/)
of Home Assistant:

[![Open your Home Assistant instance and open Hikvision Virtual Indoor Station in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=webysther&repository=ha-hikvision-virtual-indoor-station&category=integration)

1. Open the link above, or **Settings → Marketplace → Add from link**, and add
   `https://github.com/webysther/ha-hikvision-virtual-indoor-station`.
2. Open **Hikvision Virtual Indoor Station** and install it.

Home Assistant 2026.10 or newer.

## Configuration

**Settings → Devices & services → Add integration → Hikvision Virtual Indoor
Station**, then:

| Field | What to give |
| --- | --- |
| Host | The IP address or name of the door station on your network |
| Username | An account of its web page (its admin account works) |
| Password | The password of that account |

Then point the door station at Home Assistant, in its web page:

1. **System and Maintenance → System Configuration → Network → Device Access →
   VoIP**, line **VoIP1**:
   - turn on **Enable VoIP Gateway**;
   - **Server IP Address**: the address of Home Assistant; **Server Port**:
     5060;
   - **Register User Name** and **Number**: a number for the door station, such
     as `100` (Home Assistant does not check the **Registration Password**);
   - **Display User Name**: a name for the door station;
   - **Expiry Time** can stay at 60 minutes: Home Assistant shortens it to 10;
   - leave **Enable P2P** off.

   Once saved, **Registration Status** shows **Registered**.

   ![The VoIP line of the door station, registered with Home Assistant](https://raw.githubusercontent.com/webysther/ha-hikvision-virtual-indoor-station/main/docs/images/voip.png)

2. **Video Intercom → Call Parameters → Number Settings**: map the room of the
   call button (room 1) to the SIP line. The door's screen shows its name during
   calls.

   ![Room 1 mapped to the SIP line](https://raw.githubusercontent.com/webysther/ha-hikvision-virtual-indoor-station/main/docs/images/number-settings.png)

3. **Video Intercom → Call Parameters → Call Priority**: **Telephone Gateway**
   as **Priority1**, so the button calls Home Assistant. Its **Ring Duration**
   is how long a call rings before it is missed.

   ![Telephone Gateway as the first call priority](https://raw.githubusercontent.com/webysther/ha-hikvision-virtual-indoor-station/main/docs/images/call-priority.png)

4. Set the SIP audio to G.711 only.

The **SIP registration** sensor turns on once the door station registers. The
address, account and password can be changed later with **Reconfigure**.

## Dashboard and card

The integration brings its own card and dashboard: there is nothing else to
install.

- **The dashboard**: **Settings → Dashboards → Add dashboard → Hikvision Virtual
  Indoor Station**. It has a view for each door station, with its card and its
  activity (rings, calls, registration).
- **The card**: **Hikvision Virtual Indoor Station** in the card picker of any
  dashboard, with a visual editor. It is laid out like the screen of an indoor
  station:
  - the door's camera, live while the door rings, during a call or while you
    monitor, and its picture otherwise;
  - **Answer** and **Reject** while the door rings, **Hang up** once answered,
    **Monitor** while idle, and **Mute ringer** for this browser;
  - **Push to talk**: hold it (or the space bar on it). Your voice goes with the
    call, or through the door's speaker while idle, and the door's sound is
    muted while you talk;
  - a key for each door, and your shortcuts.

```yaml
type: custom:hikvision-indoor-station-card
# The door station (its device); the first one when left out
device_id: 0123456789abcdef0123456789abcdef
# hold (the default) or toggle: press once to talk, once to stop
talk_mode: hold
# Other entities: buttons are pressed, scenes and scripts turned on,
# automations triggered, the rest toggled
shortcuts:
  - light.porch
  - entity: scene.welcome
    name: Welcome
    icon: mdi:hand-wave
```

Browsers hold the sound of a page until it is tapped: the card asks for a tap
when the door rings before that. Talking needs Home Assistant opened over HTTPS.

## Phones

Each phone with the Home Assistant app can ring with a door station: **Settings →
Devices & services → Hikvision Virtual Indoor Station**, then **Add phone** on the
door station.

| Field | What it does |
| --- | --- |
| Phone | A device of the Home Assistant app (Mobile App) |
| Do not disturb | The phone is not notified when this door station rings |
| Can open the door | The notification has a button that opens the door |

The last two can be changed later (**Reconfigure** on the phone); adding or
changing a phone does not interrupt a call. When the door rings, each phone gets
a notification with the door's picture, delivered at once (time-sensitive on
iOS, high priority on Android), with:

- **Answer**: opens the indoor station panel, a page with the door station's
  card, which answers that call;
- **Open door**: opens the first door with a lock, in the background (an iPhone
  asks to be unlocked first);
- **Reject**: the door station shows busy.

The buttons work only while their call lasts, and the notification goes away
once the call is answered elsewhere, missed or over. A tap on the notification
opens the panel without answering. A phone that leaves Home Assistant has a
repair issue, whose fix removes it from the door station.

## Removal

**Settings → Devices & services → Hikvision Virtual Indoor Station**: **Delete**
in the three dots of the door station removes it, with its device and entities.
Then point the VoIP line of the door station elsewhere (or disable it), and
uninstall the integration from the Marketplace. A phone alone is removed with
**Delete** in the three dots of its line, under its door station.

## How the data is updated

- **Calls are pushed**, as they happen: the door station calls Home Assistant over
  SIP, and the call sensor, the doorbell event and the cards change at once.
- **Once a minute** the door station is asked what its outputs drive (one small
  request): its entities are unavailable while it does not answer, and a door
  whose output no longer drives a lock no longer opens.
- **The registration**: the door station registers every 10 minutes at most, and
  sends a keepalive every 20 seconds while it does.
- **The camera** streams on demand; its picture is taken when a dashboard asks.
- **The phones** are notified when the door rings, and the notification is taken
  back when the call is answered elsewhere, missed or over.

## Known limitations

- **One SIP server, port 5060.** It cannot run next to another SIP server on the
  same port, such as the Voice over IP integration.
- **G.711 only.** The Opus and G.722.1 of the door stations are non-standard.
- **The talk time of the door station** ends the call (90 seconds by default):
  raise it in its web page.
- **Half duplex.** The door station's echo canceller lowers the visitor's voice
  while you talk: talk by turns.
- **Talking needs HTTPS** in the browser (the microphone).
- **Three buttons on Android**: a notification opens the first door with a lock
  only.
- **The notifications need the phone online**: they go through the push service
  of the Home Assistant app, which limits how many a phone gets a day.

## Troubleshooting

- **The button does not ring.** Check the **SIP registration** sensor. Off: the
  VoIP line does not point at Home Assistant (see Configuration), or port 5060 is
  blocked between them. A repair issue says the address and port to set.
- **Setup is retried, saying port 5060 is taken.** Another SIP server listens there:
  stop it, or the Voice over IP integration.
- **The door station beeps three times and shows nothing.** No SIP server answered:
  Home Assistant was off or unreachable.
- **No sound to the door, or a choppy one.** Set the SIP audio of the door station
  to G.711 only.
- **The call ends by itself after 90 seconds.** That is the talk time of the door
  station.
- **The button of door 2 is unavailable.** Its output rings a doorbell or drives
  nothing (see its **Output** sensor): set it to Electric Lock in the web page of
  the door station (Access Control → I/O Settings).
- **A phone does not ring.** Allow the notifications of the Home Assistant app on
  it, and check that it is not in **Do not disturb** for this door station. Its
  app must be signed in: Home Assistant then has its notify action
  (`notify.mobile_app_<its name>`).
- **The video takes long to start.** Turn on **Preload camera stream** in the
  settings of the door station's camera: its stream is then always ready (it
  keeps one stream of the door station open).

Enable debug logs (**Settings → Devices & services → Hikvision Virtual Indoor
Station → Enable debug logging**) and download the diagnostics before opening an
issue: they leave out addresses, names and the account.

## Supported devices

Hikvision video door stations with standard SIP (a VoIP line), such as the
DS-KD8003 series with firmware V3.7.1 build250709 or newer. Tested: DS-KD8003-IME1(B)
with V3.7.3. Other door stations of the DS-KD and DS-KV series are expected to work;
please report yours.

## Entities

| Entity | What it does |
| --- | --- |
| Camera | The door's picture and sound (RTSP), and snapshots |
| Doorbell (event) | `ring`, `answered`, `rejected`, `missed`, `ended`, with the call's id |
| Call (sensor) | `idle`, `ringing`, `answered` |
| SIP registration (diagnostic) | On while the door station can call Home Assistant |
| Open door (button) | One per door, numbered when there are several; unavailable while its output drives no lock |
| Output (diagnostic) | What a changeable output drives: `electric_lock`, `doorbell`, `disabled` |
| Answer, Hang up, Reject (buttons) | Act on the current call |

## Automation examples

A notification when someone rings (each event changes the state of the doorbell,
even two rings in a row):

```yaml
triggers:
  - trigger: state
    entity_id: event.door_station_doorbell
    not_from: [unavailable, unknown]
conditions:
  - condition: template
    value_template: "{{ trigger.to_state.attributes.event_type == 'ring' }}"
actions:
  - action: notify.notify
    data:
      title: Someone is at the door
      message: "{{ now().strftime('%H:%M') }}"
```

Refuse the calls while nobody is home:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.door_station_call
    to: ringing
conditions:
  - condition: state
    entity_id: zone.home
    state: "0"
actions:
  - action: button.press
    target:
      entity_id: button.door_station_reject
```

## Contributing

See [AGENTS.md](https://github.com/webysther/ha-hikvision-virtual-indoor-station/blob/main/AGENTS.md):
how the integration is laid out, its checks and its conventions. The protocol lives
in [aiohikvision](https://github.com/webysther/aio-hikvision).

## Related projects

Other projects that bring Hikvision devices to Home Assistant. If you use one of
them for a door station, give this integration a try: it does the indoor station
in one integration, locally, with no add-on, MQTT broker or cloud account. For
cameras and recorders, try [Hikvision Bridge](https://github.com/yannik2480/hikvision_bridge),
which can be installed next to this integration.

Door stations and intercoms:

- [Hikvision Bridge](https://github.com/yannik2480/hikvision_bridge): cameras,
  recorders and door stations over local ISAPI (events, live streams,
  recordings, doors). The ISAPI code of
  [aiohikvision](https://github.com/webysther/aio-hikvision) comes from it.
- [Hikvision-Addons](https://github.com/pergolafabio/Hikvision-Addons): an add-on
  built on the Hikvision SDK that exposes the doorbell over MQTT, to answer,
  refuse and hang up calls and open the doors.
- [SIP Indoor Station](https://github.com/arturzx/sip-indoor-station): a SIP
  server and WebRTC audio bridge for SIP door stations, with its
  [integration](https://github.com/arturzx/sip-indoor-station-integration),
  [card](https://github.com/arturzx/sip-indoor-station-card) and
  [add-on](https://github.com/arturzx/hass-addons) in separate repositories.
- [Hikvision Doorbell Integration](https://github.com/acardace/hikvision-doorbell-integration):
  WebRTC two-way audio over ISAPI, with its
  [server](https://github.com/acardace/hikvision-doorbell-server).
- [Hikvision Intercom](https://github.com/schmidt-gabriel/hikvision-intercom-hass-integration):
  doorbell detection and doors over ISAPI.
- [Hikvision Intercom (2-wire)](https://github.com/TimLuist1/hikvision-intercom):
  2-wire intercoms through the Hikvision SDK.
- [Hik-Connect](https://github.com/tomasbedrich/home-assistant-hikconnect): smart
  doorbells through the Hik-Connect cloud.
- [Intercom HomeKit](https://github.com/DmytryS/intercom-homekit): an add-on
  that makes a door station an Apple HomeKit video doorbell.

Cameras and recorders:

- [Hikvision](https://www.home-assistant.io/integrations/hikvision/), the
  integration that ships with Home Assistant, built on
  [pyHik](https://github.com/mezz64/pyHik).
- [Hikvision NVR / IP cameras](https://github.com/maciej-or/hikvision_next)
  (`hikvision_next`).

## License

The code is under the
[MIT License](https://github.com/webysther/ha-hikvision-virtual-indoor-station/blob/main/LICENSE).

Hikvision and Home Assistant are trademarks of their owners, named here only to
identify them, without implying their endorsement; this project is not affiliated
with Hikvision. The icon of the integration is original art.
