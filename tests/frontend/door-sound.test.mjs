// Tests of the door's sound of a call: node --test "tests/frontend/*.test.mjs"
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  DoorSpeaker,
  LEAD,
  MAX_LEAD,
  Upsampler,
  aLawSample,
  bytesOf,
  decodeFrame,
  muLawSample,
  startOf,
} from "../../custom_components/hikvision_virtual_indoor_station/frontend/door-sound.js";
import {
  aLaw,
  muLaw,
} from "../../custom_components/hikvision_virtual_indoor_station/frontend/talk-audio.js";

describe("G.711 decoding", () => {
  it("decodes every byte to the sample its encoder gives that byte back for", () => {
    // The encoders match the reference of ITU-T G.191 (talk-audio.test.mjs)
    for (let byte = 0; byte < 256; byte += 1) {
      if (byte !== 0x7f) assert.equal(muLaw(muLawSample(byte)), byte, `μ-law ${byte}`);
      assert.equal(aLaw(aLawSample(byte)), byte, `A-law ${byte}`);
    }
  });

  it("knows the ends and the silence of each law", () => {
    assert.equal(muLawSample(0x00), -32124);
    assert.equal(muLawSample(0x80), 32124);
    assert.equal(muLawSample(0xff), 0);
    assert.equal(aLawSample(0xaa), 32256);
    assert.equal(aLawSample(0x2a), -32256);
    assert.equal(aLawSample(0xd5), 8);
  });

  it("gives the browser's samples, in the law of the call", () => {
    const bytes = new Uint8Array([0xff, 0x80, 0x00]);
    assert.deepEqual([...decodeFrame(bytes, "G.711ulaw")], [0, 32124 / 32768, -32124 / 32768]);
    assert.equal(decodeFrame(new Uint8Array([0xaa]), "G.711alaw")[0], 32256 / 32768);
  });

  it("reads the sound as the integration sends it", () => {
    assert.deepEqual([...bytesOf(Buffer.from([1, 2, 255]).toString("base64"))], [1, 2, 255]);
  });
});

describe("Upsampler", () => {
  it("draws the line between the samples, from one piece to the next", () => {
    const upsampler = new Upsampler(16000, 8000);
    assert.deepEqual([...upsampler.push(Float32Array.from([0, 1]))], [0, 0.5, 1]);
    // The next piece starts halfway from the last sample of the one before
    assert.deepEqual([...upsampler.push(Float32Array.from([0, 0]))], [0.5, 0, 0, 0]);
  });

  it("keeps the rate over a long call, without drifting", () => {
    // 40 s of 40 ms pieces at 48 kHz: always 6 samples out per sample in, but for the
    // few between the last sample in and the next piece, which come with that piece
    const upsampler = new Upsampler(48000);
    let samples = 0;
    for (let piece = 1; piece <= 1000; piece += 1) {
      samples += upsampler.push(new Float32Array(320)).length;
      assert.equal(samples, piece * 1920 - 5);
    }
  });
});

describe("startOf", () => {
  it("plays right after the piece before", () => {
    assert.equal(startOf(10, 10.2), 10.2);
  });

  it("starts LEAD behind when the sound starts or ran out", () => {
    assert.equal(startOf(10, 0), 10 + LEAD);
    assert.equal(startOf(10, 9.9), 10 + LEAD);
  });

  it("drops what is too far ahead", () => {
    assert.equal(startOf(10, 10 + MAX_LEAD + 0.01), null);
  });
});

/** A Web Audio context of a test: it records what plays. */
function fakeContext(state = "running") {
  const context = {
    state,
    sampleRate: 8000,
    currentTime: 5,
    destination: {},
    started: /** @type {number[]} */ ([]),
    resume() {
      context.state = "running";
      return Promise.resolve();
    },
    close: () => Promise.resolve(),
    createGain: () => ({ gain: { value: 1 }, connect() {} }),
    createBuffer: (_channels, length) => ({ length, copyToChannel() {} }),
    createBufferSource: () => ({
      connect() {},
      start: (/** @type {number} */ at) => context.started.push(at),
    }),
  };
  return context;
}

describe("DoorSpeaker", () => {
  it("is held until a tap lets it play", () => {
    const context = fakeContext("suspended");
    const speaker = new DoorSpeaker(() => /** @type {any} */ (context));
    assert.ok(speaker.held);
    assert.equal(speaker.play(new Uint8Array(320), "G.711ulaw"), false);
    speaker.unlock();
    assert.equal(speaker.held, false);
  });

  it("plays the pieces one after the other, LEAD behind", () => {
    const context = fakeContext();
    const speaker = new DoorSpeaker(() => /** @type {any} */ (context));
    speaker.unlock();
    assert.ok(speaker.play(new Uint8Array(320).fill(0xff), "G.711ulaw"));
    assert.ok(speaker.play(new Uint8Array(320).fill(0xff), "G.711ulaw"));
    assert.deepEqual(context.started, [5 + LEAD, 5 + LEAD + 0.04]);
    speaker.reset();
    assert.equal(speaker.end, 0);
    speaker.close();
    assert.ok(speaker.held);
  });

  it("is silenced while you talk", () => {
    const speaker = new DoorSpeaker(() => /** @type {any} */ (fakeContext()));
    speaker.mute(true);
    speaker.unlock();
    assert.equal(speaker.gain?.gain.value, 0);
    speaker.mute(false);
    assert.equal(speaker.gain?.gain.value, 1);
  });
});
