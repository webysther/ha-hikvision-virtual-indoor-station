// Tests of the indoor station card: node --test tests/frontend
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  CARD,
  callStateName,
  callStateOf,
  checkConfig,
  stubConfig,
} from "../../custom_components/hikvision_virtual_indoor_station/frontend/hikvision-indoor-station-card.js";
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
