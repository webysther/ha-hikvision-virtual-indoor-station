# Hikvision Virtual Indoor Station

Make Home Assistant the indoor station of your Hikvision video door station. Its
button rings in Home Assistant, on your dashboards and phones: you answer, talk,
hang up or refuse the call, and open the door.

> **Status: in development.** Tested with a DS-KD8003-IME1(B), firmware V3.7.3.

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

Then point the door station at Home Assistant. In its web page, under the VoIP
(SIP) settings:

1. Enable the line, and set the server to the address of Home Assistant, port
   5060.
2. Give the line a number and a display name.
3. Map the call button (the room) to a SIP number: the door's screen shows it
   during calls.
4. Set the SIP audio to G.711 only.

The **SIP registration** sensor turns on once the door station registers. The
address, account and password can be changed later with **Reconfigure**.

## Removal

**Settings → Devices & services → Hikvision Virtual Indoor Station**: **Delete**
in the three dots of the door station removes it, with its device and entities.
Then point the VoIP line of the door station elsewhere (or disable it), and
uninstall the integration from the Marketplace.

## How the data is updated

- **Calls are pushed**, as they happen: the door station calls Home Assistant over
  SIP, and the call sensor, the doorbell event and the cards change at once.
- **Once a minute** the door station is asked who it is (one small request): its
  entities are unavailable while it does not answer.
- **The registration**: the door station registers every 10 minutes at most, and
  sends a keepalive every 20 seconds while it does.
- **The camera** streams on demand; its picture is taken when a dashboard asks.

## Known limitations

- **One SIP server, port 5060.** It cannot run next to another SIP server on the
  same port, such as the Voice over IP integration.
- **G.711 only.** The Opus and G.722.1 of the door stations are non-standard.
- **The talk time of the door station** ends the call (90 seconds by default):
  raise it in its web page.
- **Half duplex.** The door station's echo canceller lowers the visitor's voice
  while you talk: talk by turns.
- **Talking needs HTTPS** in the browser (the microphone).

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
| Open door (button) | One per door, numbered when there are several |
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

## License

The code is under the
[Apache License 2.0](https://github.com/webysther/ha-hikvision-virtual-indoor-station/blob/main/LICENSE).

Hikvision and Home Assistant are trademarks of their owners, named here only to
identify them, without implying their endorsement; this project is not affiliated
with Hikvision. The icon of the integration is original art.
