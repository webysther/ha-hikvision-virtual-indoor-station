// @ts-check
/**
 * The door's sound during an answered call, as the integration hands it on from the call
 * (SIP): 40 ms of G.711 at a time, decoded here and played with Web Audio. Browsers whose
 * camera player has no G.711 (Home Assistant's HLS, on an iPad) hear the visitor so.
 *
 * The door sends its packets in a burst of about 200 ms at the start, then one every 33 ms
 * (median), up to 106 ms late (the measures of aiohikvision's DEVICE_FINDINGS): the sound
 * plays a little behind (LEAD), and a backlog beyond MAX_LEAD is dropped so that it stays
 * close to the visitor.
 */

import { RATE } from "./talk-audio.js";

/** Seconds the sound plays behind its arrival: room for the door's late packets. */
export const LEAD = 0.12;

/** Seconds ahead beyond which a piece is dropped, to keep the sound close to the visitor. */
export const MAX_LEAD = 0.4;

/**
 * Return a μ-law byte as a 16-bit sample, as ITU-T G.711 decodes it.
 *
 * @param {number} byte
 */
export function muLawSample(byte) {
  const value = ~byte & 0xff;
  const exponent = (value >> 4) & 0x07;
  const magnitude = ((((value & 0x0f) << 3) + 0x84) << exponent) - 0x84;
  return value & 0x80 ? -magnitude : magnitude;
}

/**
 * Return an A-law byte as a 16-bit sample, as ITU-T G.711 decodes it.
 *
 * @param {number} byte
 */
export function aLawSample(byte) {
  const value = byte ^ 0x55;
  const exponent = (value >> 4) & 0x07;
  const mantissa = (value & 0x0f) << 4;
  const magnitude = exponent ? (mantissa + 0x108) << (exponent - 1) : mantissa + 8;
  return value & 0x80 ? magnitude : -magnitude;
}

/**
 * Return G.711 bytes as samples of the browser (-1 to 1).
 *
 * @param {Uint8Array} bytes
 * @param {string} codec "G.711ulaw" or "G.711alaw".
 */
export function decodeFrame(bytes, codec) {
  const decode = codec === "G.711alaw" ? aLawSample : muLawSample;
  const samples = new Float32Array(bytes.length);
  for (let i = 0; i < bytes.length; i += 1) samples[i] = decode(bytes[i]) / 0x8000;
  return samples;
}

/**
 * Return the bytes of a base64 text, as the integration sends the sound.
 *
 * @param {string} text
 */
export function bytesOf(text) {
  return Uint8Array.from(atob(text), (character) => character.charCodeAt(0));
}

/**
 * Brings 8 kHz sound up to the rate of the browser, joining each piece to the one before:
 * each sample out lies on the straight line between the two samples in around it. Where
 * a sample out lies is counted from the start of the sound, so that no rounding piles up
 * over a call.
 */
export class Upsampler {
  /**
   * @param {number} outputRate The rate of the browser's audio.
   * @param {number} [inputRate]
   */
  constructor(outputRate, inputRate = RATE) {
    this.outputRate = outputRate;
    this.inputRate = inputRate;
    /** Samples out so far, and samples in before the next piece. */
    this.produced = 0;
    this.consumed = 0;
    this.last = 0;
  }

  /**
   * Return a piece at the output rate.
   *
   * @param {Float32Array} input
   */
  push(input) {
    /** @param {number} index -1 is the last sample of the piece before. */
    const at = (index) => (index < 0 ? this.last : input[index]);
    const output = [];
    for (;;) {
      const position = (this.produced * this.inputRate) / this.outputRate - this.consumed;
      if (position > input.length - 1) break;
      const index = Math.floor(position);
      const share = position - index;
      output.push(share ? at(index) * (1 - share) + at(index + 1) * share : at(index));
      this.produced += 1;
    }
    this.consumed += input.length;
    this.last = input[input.length - 1] ?? this.last;
    return Float32Array.from(output);
  }
}

/**
 * Return when a piece plays on the clock of the player: right after the one before, LEAD
 * from now when the sound starts or ran out, or null when it is too far ahead.
 *
 * @param {number} now The time of the player.
 * @param {number} end When what is scheduled ends.
 */
export function startOf(now, end) {
  if (end < now) return now + LEAD;
  return end > now + MAX_LEAD ? null : end;
}

/**
 * Plays the door's sound of a call. Browsers play sound only once a tap allowed it:
 * `unlock()` is called within one (answering, a tap on the card).
 */
export class DoorSpeaker {
  /** @param {() => AudioContext} [createContext] */
  constructor(createContext = () => new AudioContext()) {
    this.createContext = createContext;
    /** @type {AudioContext | null} */
    this.context = null;
    /** @type {GainNode | null} */
    this.gain = null;
    /** @type {Upsampler | null} */
    this.upsampler = null;
    this.end = 0;
    this.muted = false;
  }

  /** Whether the browser holds the sound until a tap. */
  get held() {
    return this.context?.state !== "running";
  }

  /** Let the sound play: within a tap, the only place browsers allow it. */
  unlock() {
    if (!this.context) {
      const context = this.createContext();
      this.context = context;
      this.gain = context.createGain();
      this.gain.connect(context.destination);
      this.upsampler = new Upsampler(context.sampleRate);
      this.mute(this.muted);
    }
    this.context.resume().catch(() => {});
  }

  /**
   * Silence the door, or let it be heard again: the door station hears and speaks by turns.
   *
   * @param {boolean} muted
   */
  mute(muted) {
    this.muted = muted;
    if (this.gain) this.gain.gain.value = muted ? 0 : 1;
  }

  /**
   * Play a piece of the door's sound; false when it does not play (held, or too far ahead).
   *
   * @param {Uint8Array} bytes
   * @param {string} codec
   */
  play(bytes, codec) {
    const { context, gain, upsampler } = this;
    if (!context || !gain || !upsampler || context.state !== "running") return false;
    const samples = upsampler.push(decodeFrame(bytes, codec));
    const start = startOf(context.currentTime, this.end);
    if (start === null || !samples.length) return false;
    const buffer = context.createBuffer(1, samples.length, context.sampleRate);
    buffer.copyToChannel(samples, 0);
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(gain);
    source.start(start);
    this.end = start + samples.length / context.sampleRate;
    return true;
  }

  /** The call is over: what is scheduled plays out, and the next call starts afresh. */
  reset() {
    this.end = 0;
    if (this.context) this.upsampler = new Upsampler(this.context.sampleRate);
  }

  close() {
    this.context?.close().catch(() => {});
    this.context = null;
    this.gain = null;
    this.upsampler = null;
    this.end = 0;
  }
}
