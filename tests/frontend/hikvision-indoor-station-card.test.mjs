// Tests of the indoor station card: node --test tests/frontend
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  CARD,
  RING,
  Ringer,
  actionName,
  callMessage,
  callStateName,
  callStateOf,
  checkConfig,
  configFromEditor,
  doorName,
  doorsOf,
  editorData,
  editorSchema,
  elapsed,
  mainActions,
  openDoorMessage,
  screenOf,
  shortcutService,
  shortcutView,
  shortcutsOf,
  stubConfig,
  talkAllowed,
  talkMessage,
} from "../../custom_components/hikvision_virtual_indoor_station/frontend/hikvision-indoor-station-card.js";
import { TEXTS } from "../../custom_components/hikvision_virtual_indoor_station/frontend/hikvision-indoor-station-dashboard.js";
import { STATIONS, homeAssistant } from "./fixtures.mjs";

/** Return a snapshot of a door station, as `subscribe` gives it, with a call in a state. */
const snapshot = (state) => ({
  registered: true,
  doors: [1],
  speaker: true,
  call: state ? { id: "call-1", state, caller: "100", callee: "200", end_reason: null } : null,
});

describe("callStateOf", () => {
  it("follows the latest call, and an ended call leaves the station idle", () => {
    assert.equal(callStateOf(null), "idle");
    assert.equal(callStateOf(snapshot(null)), "idle");
    assert.equal(callStateOf(snapshot("ringing")), "ringing");
    assert.equal(callStateOf(snapshot("answered")), "answered");
    assert.equal(callStateOf(snapshot("ended")), "idle");
  });

  it("is named as the states of the call sensor", () => {
    const hass = homeAssistant(["front"], {
      "component.hikvision_virtual_indoor_station.entity.sensor.call.state.ringing": "Tocando",
    });
    assert.equal(callStateName(hass, "ringing"), "Tocando");
    assert.equal(callStateName(hass, "idle"), "idle");
  });
});

describe("configuration", () => {
  it("names a device, or none to show the first door station", () => {
    assert.deepEqual(checkConfig({ type: CARD, device_id: "d" }), { type: CARD, device_id: "d" });
    assert.deepEqual(checkConfig({ type: CARD }), { type: CARD });
    assert.throws(() => checkConfig(null));
    assert.throws(() => checkConfig({ type: CARD, device_id: 1 }));
  });

  it("of a new card is the first door station", () => {
    assert.deepEqual(stubConfig(homeAssistant(["front", "back"])), {
      type: `custom:${CARD}`,
      device_id: STATIONS.back.device,
    });
    assert.deepEqual(stubConfig(homeAssistant([])), { type: `custom:${CARD}` });
  });
});

describe("the main row", () => {
  const keys = (state, monitoring = false) =>
    mainActions(state, monitoring).map((action) => action.key);

  it("answers or refuses a ringing call, hangs up an answered one, monitors otherwise", () => {
    assert.deepEqual(keys("ringing"), ["answer", "reject", "ring"]);
    assert.deepEqual(keys("answered"), ["hang_up"]);
    assert.deepEqual(keys("idle"), ["monitor", "ring"]);
    assert.deepEqual(
      mainActions("ringing", false).map((action) => action.tone),
      ["accept", "decline", "neutral"],
    );
    assert.equal(mainActions("idle", true)[0].active, true);
  });

  it("names the buttons as the integration does, and the monitoring with the texts of the card", () => {
    const hass = {
      ...homeAssistant(["front"], {
        "component.hikvision_virtual_indoor_station.entity.button.answer.name": "Atender",
      }),
      language: "pt-BR",
    };
    assert.equal(actionName(hass, mainActions("ringing", false)[0]), "Atender");
    assert.equal(actionName(hass, mainActions("idle", false)[0]), "Monitorar");
    assert.equal(actionName(hass, mainActions("idle", true)[0]), "Parar");
    // Before the texts are loaded
    assert.equal(
      actionName(homeAssistant(["front"]), mainActions("answered", false)[0]),
      "hang_up",
    );
  });

  it("names the call it acts on", () => {
    const call = snapshot("ringing").call;
    assert.deepEqual(callMessage("entry_front", call, "answer"), {
      type: "hikvision_virtual_indoor_station/call",
      entry_id: "entry_front",
      call_id: "call-1",
      action: "answer",
    });
    assert.equal(callMessage("entry_front", call, "hang_up").action, "hangup");
    assert.equal(callMessage("entry_front", call, "reject").action, "reject");
  });
});

describe("the screen", () => {
  it("plays live only while it rings, a call is answered or someone monitors", () => {
    assert.deepEqual(screenOf("idle", false), { live: false, audible: false });
    // The visitor is seen while it rings, and heard once answered
    assert.deepEqual(screenOf("ringing", false), { live: true, audible: false });
    assert.deepEqual(screenOf("answered", false), { live: true, audible: true });
    assert.deepEqual(screenOf("idle", true), { live: true, audible: true });
  });
});

describe("the doors", () => {
  it("are those of the door station, numbered when there are several", () => {
    const texts = {
      "component.hikvision_virtual_indoor_station.entity.button.open_door.name": "Abrir porta",
    };
    const hass = homeAssistant(["front"], texts);
    hass.localize = (key, values) =>
      key.endsWith("open_door_numbered.name") ? `Abrir porta ${values.door}` : (texts[key] ?? "");
    assert.deepEqual(doorsOf(null), []);
    assert.deepEqual(doorsOf({ ...snapshot(null), doors: [1, 2] }), [1, 2]);
    assert.equal(doorName(hass, 1, 1), "Abrir porta");
    assert.equal(doorName(hass, 2, 2), "Abrir porta 2");
    assert.equal(doorName(homeAssistant(["front"]), 2, 2), "Open door 2");
    assert.equal(doorName(homeAssistant(["front"]), 1, 1), "Open door");
  });

  it("open with the number of the door", () => {
    assert.deepEqual(openDoorMessage("entry_front", 2), {
      type: "hikvision_virtual_indoor_station/open_door",
      entry_id: "entry_front",
      door: 2,
    });
  });
});

describe("talking", () => {
  it("goes with an answered call, or through the speaker while idle, never while it rings", () => {
    const withSpeaker = snapshot(null);
    assert.equal(talkAllowed("answered", snapshot("answered")), true);
    assert.equal(talkAllowed("idle", withSpeaker), true);
    assert.equal(talkAllowed("idle", { ...withSpeaker, speaker: false }), false);
    assert.equal(talkAllowed("idle", null), false);
    assert.equal(talkAllowed("ringing", snapshot("ringing")), false);
  });

  it("mutes the door while you talk: it hears and speaks by turns", () => {
    assert.deepEqual(screenOf("answered", false, true), { live: true, audible: false });
    assert.deepEqual(screenOf("idle", true, true), { live: true, audible: false });
  });

  it("has a text in every language for every way a talk can fail or end", () => {
    const reasons = ["talk_https", "talk_unsupported", "talk_denied", "talk_failed"];
    const ends = ["replaced", "device", "unloaded", "call_answered"];
    for (const texts of Object.values(TEXTS)) {
      for (const reason of [...reasons, ...ends]) assert.ok(talkMessage(texts, reason), reason);
    }
    // Nothing to tell: you stopped it, or its call ended, which the card shows
    assert.equal(talkMessage(TEXTS.en, "stopped"), null);
    assert.equal(talkMessage(TEXTS.en, "call_ended"), null);
    assert.equal(talkMessage(TEXTS.en, "something new"), TEXTS.en.talk_failed);
  });

  it("is held by default, or toggled", () => {
    assert.deepEqual(checkConfig({ type: CARD, talk_mode: "toggle" }).talk_mode, "toggle");
    assert.throws(() => checkConfig({ type: CARD, talk_mode: "shout" }));
  });
});

describe("the time of a call", () => {
  it("counts minutes and seconds since it was answered", () => {
    const answered = "2026-11-26T10:00:00+00:00";
    assert.equal(elapsed(answered, Date.parse(answered) + 65_000), "1:05");
    assert.equal(elapsed(answered, Date.parse(answered) - 1000), "0:00");
    assert.equal(elapsed(null, Date.now()), null);
  });
});

describe("the ringer", () => {
  /** An AudioContext that records the tones it plays. */
  function audio(state = "running") {
    const played = [];
    const context = {
      state,
      currentTime: 0,
      destination: {},
      resumed: 0,
      closed: 0,
      resume: async () => (context.resumed += 1),
      close: async () => (context.closed += 1),
      createOscillator: () => ({
        frequency: {},
        connect: (gain) => gain,
        start: () => {},
        stop: () => {},
      }),
      createGain: () => ({
        gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} },
        connect: () => {},
      }),
    };
    const create = context.createOscillator;
    context.createOscillator = () => {
      const oscillator = create();
      played.push(oscillator.frequency);
      return oscillator;
    };
    return { context, played };
  }

  it("rings its tones until stopped", () => {
    const { context, played } = audio();
    const ringer = new Ringer(() => context);
    ringer.start();
    ringer.start(); // once
    assert.equal(ringer.ringing, true);
    assert.equal(played.length, RING.tones.length);
    assert.deepEqual(
      played.map((frequency) => frequency.value),
      RING.tones,
    );
    ringer.stop();
    assert.equal(ringer.ringing, false);
    ringer.close();
    assert.equal(context.closed, 1);
  });

  it("is blocked until the page is tapped, and plays nothing meanwhile", () => {
    const { context, played } = audio("suspended");
    const ringer = new Ringer(() => context);
    ringer.start();
    assert.equal(ringer.blocked, true);
    assert.equal(played.length, 0);
    ringer.resume();
    assert.ok(context.resumed >= 2);
    ringer.stop();
  });
});

describe("the ringer button", () => {
  it("mutes the ringer of this browser, and says how to ring again", () => {
    const hass = { ...homeAssistant(["front"]), language: "pt-BR" };
    const [, , ring] = mainActions("ringing", false, false);
    assert.equal(ring.key, "ring");
    assert.equal(actionName(hass, ring), "Silenciar campainha");
    const muted = mainActions("idle", false, true)[1];
    assert.equal(muted.active, true);
    assert.equal(muted.icon, "mdi:bell-off");
    assert.equal(actionName(hass, muted), "Campainha");
  });
});

describe("the shortcuts", () => {
  const hass = {
    ...homeAssistant(["front"]),
    states: {
      "light.porch": { state: "on", attributes: { friendly_name: "Porch" } },
      "scene.welcome": {
        state: "unknown",
        attributes: { friendly_name: "Welcome", icon: "mdi:hand-wave" },
      },
      "lock.gate": { state: "unavailable", attributes: { friendly_name: "Gate" } },
    },
  };

  it("are entities, or entities with their own name and icon", () => {
    const config = checkConfig({
      type: CARD,
      shortcuts: ["light.porch", { entity: "scene.welcome", name: "Hello" }],
    });
    assert.deepEqual(shortcutsOf(config), [
      { entity: "light.porch" },
      { entity: "scene.welcome", name: "Hello" },
    ]);
    assert.deepEqual(shortcutsOf({ type: CARD }), []);
    assert.throws(() => checkConfig({ type: CARD, shortcuts: "light.porch" }));
    assert.throws(() => checkConfig({ type: CARD, shortcuts: [{ name: "No entity" }] }));
  });

  it("press buttons, turn scenes and scripts on, trigger automations, toggle the rest", () => {
    assert.deepEqual(shortcutService("button.bell"), {
      domain: "button",
      service: "press",
      data: { entity_id: "button.bell" },
    });
    assert.equal(shortcutService("scene.welcome").service, "turn_on");
    assert.equal(shortcutService("script.porch").service, "turn_on");
    assert.equal(shortcutService("automation.night").service, "trigger");
    assert.deepEqual(
      [shortcutService("light.porch").domain, shortcutService("light.porch").service],
      ["homeassistant", "toggle"],
    );
  });

  it("show the name and icon of their entity, and whether it is on", () => {
    assert.deepEqual(shortcutView(hass, { entity: "light.porch" }), {
      name: "Porch",
      icon: "mdi:lightbulb",
      active: true,
      available: true,
    });
    const scene = shortcutView(hass, { entity: "scene.welcome", name: "Hello" });
    assert.equal(scene.name, "Hello");
    assert.equal(scene.icon, "mdi:hand-wave");
    assert.equal(scene.active, false);
    assert.equal(shortcutView(hass, { entity: "lock.gate" }).available, false);
    assert.equal(shortcutView(hass, { entity: "switch.gone" }).available, false);
    assert.equal(shortcutView(hass, { entity: "switch.gone" }).name, "switch.gone");
  });
});

describe("the editor", () => {
  it("edits the door station, the way to talk and the shortcuts", () => {
    const config = {
      type: `custom:${CARD}`,
      device_id: "device_front",
      shortcuts: ["light.porch", { entity: "scene.welcome", name: "Hello" }],
    };
    assert.deepEqual(editorData(config), {
      device_id: "device_front",
      talk_mode: "hold",
      shortcuts: ["light.porch", "scene.welcome"],
    });
    // The names given in YAML stay; the default way to talk is left out
    assert.deepEqual(
      configFromEditor(config, {
        device_id: "device_back",
        talk_mode: "hold",
        shortcuts: ["scene.welcome", "switch.fan"],
      }),
      {
        type: `custom:${CARD}`,
        device_id: "device_back",
        shortcuts: [{ entity: "scene.welcome", name: "Hello" }, "switch.fan"],
      },
    );
    assert.deepEqual(configFromEditor({ type: CARD }, { talk_mode: "toggle", shortcuts: [] }), {
      type: CARD,
      talk_mode: "toggle",
    });
  });

  it("offers only the door stations of the integration, in the language of the user", () => {
    const schema = editorSchema({ ...homeAssistant(["front"]), language: "pt-BR" });
    assert.deepEqual(
      schema.map((field) => field.name),
      ["device_id", "talk_mode", "shortcuts"],
    );
    assert.deepEqual(schema[0].selector.device.filter, {
      integration: "hikvision_virtual_indoor_station",
    });
    assert.equal(schema[0].label, "Porteiro");
    assert.deepEqual(
      schema[1].selector.select.options.map((option) => option.value),
      ["hold", "toggle"],
    );
  });
});
