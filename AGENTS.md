# AGENTS.md: Hikvision Virtual Indoor Station

Guidance for AI coding agents and contributors working on this repository.
`CLAUDE.md` imports this file.

Hikvision Virtual Indoor Station is a Home Assistant custom integration (domain
`hikvision_virtual_indoor_station`) that makes Home Assistant the indoor station
of a Hikvision video door station: its button rings in Home Assistant, the call
is answered, talked through (push-to-talk) and hung up from dashboards and
phones, and its doors open. Each door station is a config entry.

Everything that talks to the devices lives in
[aiohikvision](https://github.com/webysther/aio-hikvision), maintained alongside
this repository: the SIP side of the calls (`aiohikvision.sip`, `.rtp`) and the
ISAPI side of the door station (`aiohikvision.DoorStation`). This repository
holds the Home Assistant side only. It can be installed next to Hikvision Bridge
(`hikvision_bridge`): every name differs.

## Ground rules

- **Do not commit, amend, push, tag, release or move branches.** Leave every
  change uncommitted in the working tree; the maintainer reviews and commits it.
  Read-only git commands are fine.
- Ask before anything that leaves the machine: releases, PRs, issues, comments.
- Reply in the language the person writes in. Code, comments, docstrings, docs
  and the changelog are in English.
- **No real addresses or identifying data, anywhere.** In prose, masks
  (`<door-ip>`, `<ha-ip>`); in data a parser reads, only loopback or the
  documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24, MAC
  00:00:5e:00:53:xx); names and identifiers of real devices as `REDACTED`.
  Recordings and videos never go in a repository folder.
- Protocol fixes belong in aiohikvision. Here, only Home Assistant code.
- Check instead of guessing: for Home Assistant behaviour, read its source in
  the test environment (`.venv/lib/python3.14/site-packages/homeassistant`).

## How a call works

The design is hybrid (aiohikvision's `docs/ADR-0001-hybrid-call.md`):

- **SIP carries the call.** The door's VoIP line registers with Home Assistant
  and calls it; the call rings (180), is answered (200), refused (486) or hung
  up (BYE) on command, and every command names its call by its id.
- **SIP carries the microphone during a call**, in 40 ms G.711 packets
  (`a=sendonly`, `m=video 0`): the door slows its own audio when it receives
  20 ms ones.
- **The door's picture and sound come over RTSP** (the camera entity, played
  with WebRTC). Outside a call, the microphone goes through the door's speaker
  (ISAPI two-way audio).

## Layout

```text
custom_components/hikvision_virtual_indoor_station/
  __init__.py      setup and unload of a door station
  sip.py           the SIP server shared by all entries (one UDP port, 5060):
                   starts with the first entry, stops with the last, hears
                   only the doors of the entries
  station.py       IndoorStation: the latest call of a door, its registration,
                   the listeners, and the commands (answer, hang up, reject,
                   open a door), each naming its call
  config_flow.py   address and account; reauthentication; reconfiguration
  coordinator.py   HealthCoordinator: asks the door station who it is once a
                   minute; the entities are unavailable while it does not
                   answer, and the station checks whether the door still calls
                   (the repair issue door_unheard)
  entity.py        the device of the door station; event.py (the doorbell:
                   ring, answered, rejected, missed, ended), sensor.py (the
                   call), binary_sensor.py (SIP registration), button.py (open
                   each door; answer, hang up, reject), camera.py (RTSP)
  websocket.py     the commands of the cards: subscribe, call, open_door, talk
                   (binary frames routed to the call or to the speaker)
  diagnostics.py   masked: no addresses, names or account
  dashboard.py     serves frontend/ and has the frontend load it
  frontend/        JavaScript without build (// @ts-check + JSDoc):
                   hikvision-indoor-station-card.js (the card, laid out like
                   a wall monitor), hikvision-indoor-station-dashboard.js (the
                   dashboard strategy, a view per door station, and the
                   helpers the card shares)
  strings.json, translations/ (en, it, pt-BR), icons.json, quality_scale.yaml,
  manifest.json, version.py, brand/ (original art, not Hikvision's)
tests/             pytest-homeassistant-custom-component; aiohikvision mocked
                   at its boundary (DoorStation, CallServer)
tests/frontend/    node --test of the card and the strategy (fixtures.mjs: door
                   stations as the frontend has them)
release.sh         releases, run by the maintainer
```

## Checks

Python 3.14, as required by the pinned `pytest-homeassistant-custom-component`
(which also pins the Home Assistant version of the tests):

```bash
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
ruff format custom_components tests && ruff check custom_components tests
mypy                                   # strict, configured in pyproject.toml
pytest --cov --cov-report=term-missing
node --test "tests/frontend/*.test.mjs" # the card and the dashboard
npx prettier --check .                 # the YAML and the JavaScript
```

CI runs them (`tests.yaml`), with hassfest and the checks of the Marketplace
(`validate.yaml`). Keep the coverage of
the integration at 100% (the gate is 95%).

## Compatibility

Users' automations and dashboards depend on what the integration exposes.

- Never change unique IDs: entries are the serial of the door station
  (`Identity.stable_id`), as its device; entities are `<serial>_<key>`, with the
  keys `call`, `doorbell`, `sip_registered`, `camera`, `answer`, `hang_up`,
  `reject` and `open_door_<number>`.
- Never rename the custom elements (`custom:hikvision-indoor-station-card`, the strategy
  `custom:hikvision-indoor-station`) nor the keys of the card's configuration
  (`device_id`): they are in users' dashboards.
- Never rename the states of the call sensor (`CALL_STATES`), the event types of the
  doorbell (`EVENT_TYPES`), nor the fields of the websocket commands and of the
  doorbell's events (`call_id`, `caller`, `callee`, `end_reason`).
- Changing the shape of entry data needs a migration and a new `MINOR_VERSION`.
- Supported Home Assistant: from the `homeassistant` version in `hacs.json`
  (2026.10.0: `probatio`, `async_get_device_by_identifier`) to the latest.

## Home Assistant conventions

- `strings.json` is the source of the texts and `translations/en.json` is identical
  to it; every key exists in each language (`tests/test_texts.py`).
- Data is an entity, not an attribute: only the doorbell's events carry data.
- Every entity has an icon in `icons.json`, and the states and event types have
  theirs.
- `quality_scale.yaml` states each rule of the integration quality scale (Platinum).
  Keep it true when a change affects a rule.
- The README is the page users install from, through the Marketplace, and holds the
  sections the quality scale asks for: keep them current.
- `brand/` holds original art (`icon.png` 256 px, `icon@2x.png` 512 px,
  transparent, `dark_icon*`, `logo*`), checked by `tests/test_brand.py`. Hikvision's
  logo is its trademark: never use it.
- Errors a person sees are translated (`exceptions`, `issues`).

## Tests

- Never reach the network nor a device: `DoorStation` is mocked (`door` fixture) and
  `CallServer` replaced by `FakeCallServer` (tests/conftest.py), whose calls the
  tests ring, answer and end. The library tests the protocol against its own doubles.
- Never depend on the clock: move it with `freezer` (asked for first, before the
  entry is set up) and `async_fire_time_changed`.
- The websocket handles messages in order: send a `ping` and wait for its `pong`
  before checking what binary frames did.

## The library

aiohikvision is pinned exactly in `manifest.json` (`requirements`) and in
`requirements_test.txt`. Bump both together, and only once the release is on PyPI.

## Code style

- Readable, descriptive code over clever code: descriptive names, small focused
  helpers, docstrings that say what and why.
- No magic numbers: a `Final` constant whose comment says where its value comes from
  (see `SIP_KEEPALIVE_TIMEOUT`).
- mypy strict. A `# type: ignore[code]` needs a comment saying why.
- Comments explain why, not what.

## Versioning and releases

- Versions are `YEAR.MONTH.PATCH` (betas `bN`); the version is in the tag only:
  `manifest.json` (`0.0.0`) and `version.py` (`develop`) are written by the
  release workflow, which also attaches `hikvision_virtual_indoor_station.zip`.
- Describe the changes under `## [Unreleased]` in `CHANGELOG.md`, written for the
  users of the integration.
- The maintainer commits and runs `./release.sh VERSION [--dry-run]`: it dates the
  section, checks that Tests and Validate passed on the commit, and publishes
  the GitHub release.
