// @ts-check
/**
 * The Hikvision Virtual Indoor Station card: a standard card of the theme, laid out like
 * an indoor station. On top the door's camera with the state of the call; under it the
 * keys (answer and refuse while it rings, hang up while it is answered, monitor while
 * idle, push-to-talk, mute the ringer); then a key for each door and the shortcuts.
 *
 * The card follows its door station through the websocket command
 * `hikvision_virtual_indoor_station/subscribe` (the latest call and its id), and every
 * command names that call, so a late tap never touches the next visitor.
 *
 * The camera plays live only while the door rings, a call is answered or someone
 * monitors: a door station serves few streams at once, and every open dashboard would
 * hold one. Otherwise the card shows the camera's picture. The door's sound plays once
 * the call is answered or the monitoring starts, both taps, which browsers require
 * before a page plays sound; it is muted while you talk, as the door station hears
 * and speaks by turns.
 *
 * Plain JavaScript without build or dependencies, served by the integration
 * (dashboard.py). The functions are exported for the tests (tests/frontend).
 */
import {
  CARD,
  PLATFORM,
  TEXTS,
  findStations,
  stationOf,
  textsIn,
  translated,
  withTexts,
} from "./hikvision-indoor-station-dashboard.js";
import { Microphone } from "./talk.js";

export { CARD };

/**
 * @typedef {import("./hikvision-indoor-station-dashboard.js").Hass} Hass
 * @typedef {import("./hikvision-indoor-station-dashboard.js").Station} Station
 * @typedef {import("./talk.js").TalkEnd} TalkEnd
 * @typedef {typeof TEXTS.en} Texts
 * @typedef {{
 *   id: string,
 *   state: "ringing" | "answered" | "ended",
 *   caller: string | null,
 *   callee: string | null,
 *   end_reason: string | null,
 *   started_at?: string | null,
 *   answered_at?: string | null,
 *   ended_at?: string | null,
 * }} Call A call of the door station, as `subscribe` gives it.
 * @typedef {{ registered: boolean, doors: number[], locks?: number[], speaker: boolean,
 *   call: Call | null }} Snapshot
 *   The state of a door station, as `subscribe` gives it (IndoorStation.snapshot).
 * @typedef {"idle" | "ringing" | "answered"} CallState The states of the call sensor.
 * @typedef {"answer" | "reject" | "hang_up" | "monitor" | "talk" | "ring"} KeyName
 * @typedef {{ key: KeyName, icon: string, tone: "accept" | "decline" | "plain", enabled: boolean,
 *   active: boolean }} Key A key under the screen.
 * @typedef {"hold" | "toggle"} TalkMode Push-to-talk: talk while the button is held, or
 *   from one press to the next.
 * @typedef {{ entity: string, name?: string, icon?: string }} Shortcut A button of the card
 *   for another entity: a light, a scene, another door.
 * @typedef {{ type: string, device_id?: string, talk_mode?: TalkMode,
 *   shortcuts?: Array<string | Shortcut> }} CardConfig
 * @typedef {{ media: HTMLElement, name: HTMLElement, state: HTMLElement, warning: HTMLElement,
 *   keys: HTMLElement, extra: HTMLElement, buttons: Map<KeyName, HTMLButtonElement> }} Parts
 *   The parts of the card: the screen, the keys under it, the doors and shortcuts.
 */

/** The action of the websocket command `call` for each button of the call. */
export const CALL_ACTIONS = { answer: "answer", reject: "reject", hang_up: "hangup" };

/** How long the card waits for the frontend to define its camera stream, in ms. */
export const STREAM_WAIT = 5000;

/** Where the browser remembers that its ringer is muted (one choice per browser). */
export const RING_MUTED_KEY = `${PLATFORM}.ring_muted`;

/**
 * The ring of the browser: two tones, then a pause, again and again. Its own sound,
 * made by the browser: no recording is played.
 */
export const RING = { tones: [880, 660], tone: 0.4, period: 2.5, volume: 0.25 };

/**
 * Return the state of the call the card shows: an ended call leaves the station idle.
 *
 * @param {Snapshot | null} snapshot
 * @returns {CallState}
 */
export function callStateOf(snapshot) {
  const state = snapshot?.call?.state;
  return state === "ringing" || state === "answered" ? state : "idle";
}

/**
 * Return the name of the state of the call in the language of the user, from the
 * states of the call sensor.
 *
 * @param {Hass} hass
 * @param {CallState} state
 */
export function callStateName(hass, state) {
  return translated(hass, `entity.sensor.call.state.${state}`) ?? state;
}

/**
 * Return the label over the screen: the state of the call, with its time once answered,
 * or "Live" while someone monitors the door (the line is idle, but the screen is not).
 *
 * @param {Hass} hass
 * @param {CallState} state
 * @param {{ monitoring?: boolean, answeredAt?: string | null, now?: number }} [more]
 * @returns {{ text: string, tone: CallState | "live" }}
 */
export function screenLabel(
  hass,
  state,
  { monitoring = false, answeredAt, now = Date.now() } = {},
) {
  if (state === "idle" && monitoring) return { text: textsIn(hass.language).live, tone: "live" };
  const time = state === "answered" ? elapsed(answeredAt, now) : null;
  return { text: [callStateName(hass, state), time].filter(Boolean).join(" "), tone: state };
}

/**
 * Return how long a call has been answered, as minutes and seconds ("1:05").
 *
 * @param {string | null | undefined} since When it was answered (ISO 8601).
 * @param {number} now In ms since the epoch.
 */
export function elapsed(since, now) {
  const start = since ? Date.parse(since) : NaN;
  if (Number.isNaN(start)) return null;
  const seconds = Math.max(0, Math.floor((now - start) / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/**
 * Return the keys under the screen, as on an indoor station: always the same ones in the
 * same places, lit when the state allows them. Answer is green and hang up red; hang up
 * refuses a call that rings, and ends one that is answered.
 *
 * @param {{ state: CallState, monitoring?: boolean, ringMuted?: boolean, talkable?: boolean,
 *   talking?: boolean }} now
 * @returns {Key[]}
 */
export function deviceKeys({
  state,
  monitoring = false,
  ringMuted = false,
  talkable = false,
  talking = false,
}) {
  return [
    {
      key: "answer",
      icon: "mdi:phone",
      tone: "accept",
      enabled: state === "ringing",
      active: false,
    },
    {
      key: state === "ringing" ? "reject" : "hang_up",
      icon: "mdi:phone-hangup",
      tone: "decline",
      enabled: state !== "idle",
      active: false,
    },
    {
      key: "monitor",
      icon: monitoring ? "mdi:video-off-outline" : "mdi:video-outline",
      tone: "plain",
      enabled: state === "idle",
      active: monitoring,
    },
    {
      key: "talk",
      icon: talking ? "mdi:microphone" : "mdi:microphone-outline",
      tone: "plain",
      enabled: talkable,
      active: talking,
    },
    {
      key: "ring",
      icon: ringMuted ? "mdi:volume-off" : "mdi:volume-high",
      tone: "plain",
      enabled: true,
      active: ringMuted,
    },
  ];
}

/**
 * Return the name of a key in the language of the user: the names of the buttons of the
 * integration for the call, the texts of the card for the others.
 *
 * @param {Hass} hass
 * @param {Key} key
 */
export function keyName(hass, key) {
  const texts = textsIn(hass.language);
  if (key.key === "monitor") return key.active ? texts.stop_monitor : texts.monitor;
  if (key.key === "talk") return key.active ? texts.talking : texts.talk;
  if (key.key === "ring") return key.active ? texts.unmute_ring : texts.mute_ring;
  return translated(hass, `entity.button.${key.key}.name`) ?? key.key;
}

/**
 * Return what the screen shows: the live camera or its picture, and whether the door's
 * sound plays. It is muted while you talk: the door station hears and speaks by turns.
 *
 * @param {CallState} state
 * @param {boolean} monitoring
 * @param {boolean} [talking]
 */
export function screenOf(state, monitoring, talking = false) {
  return {
    live: state !== "idle" || monitoring,
    audible: (state === "answered" || monitoring) && !talking,
  };
}

/**
 * Return whether you can talk to the door: with an answered call, or through the door's
 * speaker while idle. Not while it rings: the call is answered first.
 *
 * @param {CallState} state
 * @param {Snapshot | null} snapshot
 */
export function talkAllowed(state, snapshot) {
  return state === "answered" || (state === "idle" && Boolean(snapshot?.speaker));
}

/**
 * Return the text of why a talk could not start or ended, or null when there is nothing
 * to tell: you stopped it, or its call ended (the card shows that already).
 *
 * @param {Texts} texts
 * @param {string} reason A code of talk.js (talk_https, …) or a TalkEnd.
 */
export function talkMessage(texts, reason) {
  if (reason === "stopped" || reason === "call_ended") return null;
  const known = /** @type {Record<string, string>} */ (texts);
  return known[reason] ?? texts.talk_failed;
}

/**
 * Return the websocket message of a button of the call, naming the call it acts on.
 *
 * @param {string} entryId
 * @param {Call} call
 * @param {"answer" | "reject" | "hang_up"} key
 */
export function callMessage(entryId, call, key) {
  return {
    type: `${PLATFORM}/call`,
    entry_id: entryId,
    call_id: call.id,
    action: CALL_ACTIONS[key],
  };
}

/**
 * Return the doors of the door station: their numbers, from the door station itself.
 *
 * @param {Snapshot | null} snapshot
 * @returns {number[]}
 */
export function doorsOf(snapshot) {
  return snapshot?.doors ?? [];
}

/**
 * Return the doors that open: those whose output drives a lock (not a doorbell, nor
 * nothing), as the door station's I/O settings say.
 *
 * @param {Snapshot | null} snapshot
 * @returns {number[]}
 */
export function locksOf(snapshot) {
  return snapshot?.locks ?? doorsOf(snapshot);
}

/**
 * Return the name of the key of a door, as the integration names its buttons: numbered
 * when the door station has several doors.
 *
 * @param {Hass} hass
 * @param {number} door
 * @param {number} count
 */
export function doorName(hass, door, count) {
  return count > 1
    ? (translated(hass, "entity.button.open_door_numbered.name", { door }) ?? `Open door ${door}`)
    : (translated(hass, "entity.button.open_door.name") ?? "Open door");
}

/**
 * Return the websocket message that opens a door.
 *
 * @param {string} entryId
 * @param {number} door
 */
export function openDoorMessage(entryId, door) {
  return { type: `${PLATFORM}/open_door`, entry_id: entryId, door };
}

/**
 * Check the configuration of the card.
 *
 * @param {any} config
 * @returns {CardConfig}
 */
export function checkConfig(config) {
  if (!config || typeof config !== "object") throw new Error("Invalid configuration");
  if (config.device_id !== undefined && typeof config.device_id !== "string") {
    throw new Error("device_id must be the ID of a device of Hikvision Virtual Indoor Station");
  }
  if (config.talk_mode !== undefined && !["hold", "toggle"].includes(config.talk_mode)) {
    throw new Error("talk_mode must be hold or toggle");
  }
  if (config.shortcuts !== undefined) {
    const valid = (/** @type {any} */ item) =>
      typeof item === "string" ||
      (item && typeof item === "object" && typeof item.entity === "string");
    if (!Array.isArray(config.shortcuts) || !config.shortcuts.every(valid)) {
      throw new Error("shortcuts must be a list of entities, or of { entity, name, icon }");
    }
  }
  return config;
}

/**
 * Return the shortcuts of a card, each as `{ entity, name?, icon? }`.
 *
 * @param {CardConfig} config
 * @returns {Shortcut[]}
 */
export function shortcutsOf(config) {
  return (config.shortcuts ?? []).map((item) =>
    typeof item === "string" ? { entity: item } : item,
  );
}

/**
 * The action of a shortcut, by the domain of its entity: buttons are pressed, scenes and
 * scripts turned on, automations triggered; anything else is toggled.
 */
export const SHORTCUT_SERVICES = /** @type {Record<string, [string, string]>} */ ({
  button: ["button", "press"],
  input_button: ["input_button", "press"],
  scene: ["scene", "turn_on"],
  script: ["script", "turn_on"],
  automation: ["automation", "trigger"],
});

/** The icon of a shortcut whose entity has none of its own, by domain. */
export const SHORTCUT_ICONS = /** @type {Record<string, string>} */ ({
  light: "mdi:lightbulb",
  switch: "mdi:toggle-switch-variant",
  lock: "mdi:lock",
  cover: "mdi:garage",
  scene: "mdi:palette",
  script: "mdi:script-text",
  automation: "mdi:robot",
  button: "mdi:gesture-tap-button",
});

/**
 * Return the service a shortcut calls.
 *
 * @param {string} entityId
 */
export function shortcutService(entityId) {
  const [domain, service] = SHORTCUT_SERVICES[entityId.split(".")[0]] ?? [
    "homeassistant",
    "toggle",
  ];
  return { domain, service, data: { entity_id: entityId } };
}

/**
 * Return how a shortcut shows: its name, its icon, and whether its entity is on.
 *
 * @param {Hass} hass
 * @param {Shortcut} shortcut
 */
export function shortcutView(hass, shortcut) {
  const state = hass.states[shortcut.entity];
  const domain = shortcut.entity.split(".")[0];
  return {
    name: shortcut.name ?? state?.attributes.friendly_name ?? shortcut.entity,
    icon:
      shortcut.icon ?? state?.attributes.icon ?? SHORTCUT_ICONS[domain] ?? "mdi:gesture-tap-button",
    active: ["on", "open", "unlocked"].includes(state?.state ?? ""),
    available: Boolean(state) && state?.state !== "unavailable",
  };
}

/**
 * Return the values of the editor of a card: the shortcuts as their entities.
 *
 * @param {CardConfig} config
 */
export function editorData(config) {
  return {
    device_id: config.device_id,
    talk_mode: config.talk_mode ?? "hold",
    shortcuts: shortcutsOf(config).map((shortcut) => shortcut.entity),
  };
}

/**
 * Return the configuration the editor makes: the shortcuts keep the names and icons
 * given in YAML, and the defaults are left out.
 *
 * @param {CardConfig} config
 * @param {{ device_id?: string, talk_mode?: TalkMode, shortcuts?: string[] }} value
 * @returns {CardConfig}
 */
export function configFromEditor(config, value) {
  const given = new Map(shortcutsOf(config).map((shortcut) => [shortcut.entity, shortcut]));
  /** @type {CardConfig} */
  const result = { type: config.type };
  if (value.device_id) result.device_id = value.device_id;
  if (value.talk_mode && value.talk_mode !== "hold") result.talk_mode = value.talk_mode;
  const shortcuts = (value.shortcuts ?? []).map((entity) => {
    const shortcut = given.get(entity);
    return shortcut && (shortcut.name || shortcut.icon) ? shortcut : entity;
  });
  if (shortcuts.length) result.shortcuts = shortcuts;
  return result;
}

/**
 * Return the form of the editor: the door station, the way to talk, the shortcuts.
 *
 * @param {Hass} hass
 */
export function editorSchema(hass) {
  const texts = textsIn(hass.language);
  return [
    {
      name: "device_id",
      label: texts.editor_device,
      selector: { device: { filter: { integration: PLATFORM } } },
    },
    {
      name: "talk_mode",
      label: texts.editor_talk_mode,
      selector: {
        select: {
          mode: "list",
          options: [
            { value: "hold", label: texts.talk_hold },
            { value: "toggle", label: texts.talk_toggle },
          ],
        },
      },
    },
    { name: "shortcuts", label: texts.editor_shortcuts, selector: { entity: { multiple: true } } },
  ];
}

/**
 * Return the configuration of a new card: the first door station.
 *
 * @param {Hass} hass
 * @returns {CardConfig}
 */
export function stubConfig(hass) {
  const station = findStations(hass)[0];
  return station
    ? { type: `custom:${CARD}`, device_id: station.device_id }
    : { type: `custom:${CARD}` };
}

/**
 * The ringer of the browser: it rings while the door station rings. Browsers let a page
 * play sound only after a tap on it: until then it is `blocked`, and `resume` (called on
 * a tap) lets it ring.
 */
export class Ringer {
  /** @param {() => AudioContext} [createContext] */
  constructor(createContext = () => new AudioContext()) {
    this.createContext = createContext;
    /** @type {AudioContext | null} */
    this.context = null;
    /** @type {ReturnType<typeof setInterval> | null} */
    this.timer = null;
  }

  get ringing() {
    return this.timer !== null;
  }

  /** Whether the browser holds the sound until a tap on the page. */
  get blocked() {
    return this.context?.state === "suspended";
  }

  start() {
    if (this.timer) return;
    this.context ??= this.createContext();
    this.resume();
    this.#ring();
    this.timer = setInterval(() => this.#ring(), RING.period * 1000);
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  resume() {
    this.context?.resume().catch(() => {});
  }

  close() {
    this.stop();
    this.context?.close().catch(() => {});
    this.context = null;
  }

  /** One ring: its tones one after the other, each fading in and out. */
  #ring() {
    const context = this.context;
    if (!context || context.state !== "running") return;
    RING.tones.forEach((frequency, index) => {
      const start = context.currentTime + index * RING.tone;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(RING.volume, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + RING.tone);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(start);
      oscillator.stop(start + RING.tone);
    });
  }
}

if (typeof customElements !== "undefined") {
  // A standard card of the theme, laid out like an indoor station: the door's camera on
  // top, its name and the state of the call over it, and a row of keys under it, green to
  // answer and red to hang up. The rest takes the colors of the theme.
  const STYLE = `
    ha-card { overflow: hidden; }
    .screen { position: relative; aspect-ratio: 16 / 9; background: #000; }
    .media, .media > * { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
    .overlay { position: absolute; inset: 0 0 auto 0; display: flex; align-items: center;
      justify-content: space-between; gap: 8px; padding: 8px 12px; font-size: 14px; color: #fff;
      background: linear-gradient(rgba(0, 0, 0, 0.6), transparent); pointer-events: none; }
    .name { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .chip { padding: 2px 10px; border-radius: 999px; white-space: nowrap;
      background: rgba(0, 0, 0, 0.45); font-variant-numeric: tabular-nums; }
    .chip.ringing { background: var(--success-color, #43a047);
      animation: pulse 1s ease-in-out infinite; }
    .chip.answered { background: var(--info-color, #039be5); }
    .chip.live { background: var(--error-color, #db4437); }
    .warning { position: absolute; inset: auto 0 0 0; padding: 6px 12px; font-size: 13px;
      background: rgba(0, 0, 0, 0.7); color: var(--warning-color, #ffa600); }
    .keys { display: flex; justify-content: space-around; align-items: flex-start; gap: 2px;
      padding: 8px 8px 4px; }
    .keys.extra { flex-wrap: wrap; justify-content: center; padding-bottom: 8px;
      border-top: 1px solid var(--divider-color); }
    .keys:empty { display: none; }
    .key { flex: 1 1 0; min-width: 56px; max-width: 96px; display: flex; flex-direction: column;
      align-items: center; gap: 4px; padding: 6px 2px; border: none; border-radius: 12px;
      background: none; color: var(--primary-text-color); font: inherit; font-size: 11px;
      cursor: pointer; -webkit-tap-highlight-color: transparent; }
    .key ha-icon { --mdc-icon-size: 28px; }
    .key .caption { color: var(--secondary-text-color); line-height: 1.2; text-align: center; }
    .key:hover:not(:disabled), .key:focus-visible {
      background: var(--secondary-background-color); outline: none; }
    .key:disabled { opacity: 0.38; cursor: default; }
    .key.accept { color: var(--success-color, #43a047); }
    .key.decline { color: var(--error-color, #db4437); }
    .key.active, .key.active .caption { color: var(--primary-color); }
    .key.talk { touch-action: none; user-select: none; -webkit-user-select: none; }
    .key.talk.active { background: var(--secondary-background-color); }
    @keyframes pulse { 50% { opacity: 0.6; } }
  `;

  /**
   * Have the frontend define its camera stream, which it loads with its picture cards.
   *
   * @param {string} camera
   */
  async function loadCameraStream(camera) {
    if (customElements.get("ha-camera-stream")) return true;
    try {
      const helpers = await /** @type {any} */ (window).loadCardHelpers();
      await helpers.createCardElement({
        type: "picture-entity",
        entity: camera,
        camera_view: "live",
      });
    } catch (_err) {
      /* the helpers are missing: the timeout below decides */
    }
    const timeout = new Promise((resolve) => setTimeout(() => resolve(false), STREAM_WAIT));
    return Promise.race([customElements.whenDefined("ha-camera-stream").then(() => true), timeout]);
  }

  /**
   * Have the frontend define its forms, which it loads with the editors of its own
   * cards: the editor of a tile has one.
   */
  async function loadForms() {
    if (customElements.get("ha-form")) return;
    const helpers = await /** @type {any} */ (window).loadCardHelpers();
    helpers.createCardElement({ type: "tile", entity: "sun.sun" });
    await customElements.whenDefined("hui-tile-card");
    await /** @type {any} */ (customElements.get("hui-tile-card")).getConfigElement();
  }

  /** Return whether this browser muted its ringer; a page without storage rings. */
  function ringMutedHere() {
    try {
      return localStorage.getItem(RING_MUTED_KEY) === "1";
    } catch (_err) {
      return false;
    }
  }

  /** @param {boolean} muted */
  function rememberRingMuted(muted) {
    try {
      if (muted) localStorage.setItem(RING_MUTED_KEY, "1");
      else localStorage.removeItem(RING_MUTED_KEY);
    } catch (_err) {
      /* remembered for this page only */
    }
  }

  /**
   * Return a key: its icon over its caption.
   *
   * @param {string} className
   */
  function keyElement(className) {
    const button = document.createElement("button");
    button.className = className;
    const caption = document.createElement("span");
    caption.className = "caption";
    button.append(document.createElement("ha-icon"), caption);
    return button;
  }

  /**
   * Show a key: its icon, its caption, and whether it can be pressed.
   *
   * @param {HTMLButtonElement} button
   * @param {{ icon: string, name: string, className: string, enabled: boolean }} look
   */
  function showKey(button, look) {
    button.className = look.className;
    button.disabled = !look.enabled;
    button.title = look.name;
    button.setAttribute("aria-label", look.name);
    button.querySelector("ha-icon")?.setAttribute("icon", look.icon);
    const caption = button.querySelector(".caption");
    if (caption && caption.textContent !== look.name) caption.textContent = look.name;
  }

  class IndoorStationCard extends HTMLElement {
    /** @type {CardConfig | undefined} */
    #config;
    /** @type {Hass | undefined} */
    #hass;
    /** @type {Station | undefined} */
    #station;
    /** @type {Snapshot | null} */
    #snapshot = null;
    /** @type {(() => void) | null} */
    #unsubscribe = null;
    /** @type {string | null} The entry the subscription follows. */
    #subscribed = null;
    /** @type {Hass["localize"]} */
    #localize;
    /** Whether someone monitors the door outside a call. */
    #monitoring = false;
    /** @type {string | null} The command waiting for its answer: its keys are disabled. */
    #busy = null;
    /** @type {Parts | null} */
    #parts = null;
    /** @type {any} The live camera, kept while it plays: rebuilding it restarts the stream. */
    #stream = null;
    /** @type {boolean | null} Whether the frontend defined its camera stream, once known. */
    #streamDefined = null;
    #ringMuted = ringMutedHere();
    #ringer = new Ringer();
    /** @type {Microphone | null} The talk in progress. */
    #microphone = null;
    /** @type {ReturnType<typeof setInterval> | null} Ticks the time of an answered call. */
    #clock = null;

    constructor() {
      super();
      // A tap on the card lets the browser play the ring and the microphone
      this.addEventListener("pointerdown", () => {
        this.#ringer.resume();
        this.#microphone?.resume();
      });
    }

    /** @param {any} config */
    setConfig(config) {
      this.#config = checkConfig(config);
      if (this.#hass) this.#station = stationOf(findStations(this.#hass), this.#config);
      this.#render();
    }

    /** @param {Hass} hass */
    set hass(hass) {
      const first = !this.#hass;
      this.#hass = hass;
      if (first) {
        withTexts(hass).then(({ localize }) => {
          this.#localize = localize;
          this.#render();
        });
      }
      this.#station = this.#config ? stationOf(findStations(hass), this.#config) : undefined;
      this.#follow();
      this.#render();
    }

    connectedCallback() {
      this.#follow();
    }

    disconnectedCallback() {
      this.#stop();
      this.#stopTalk();
      this.#ringer.close();
      this.#monitoring = false;
      this.#stream?.remove();
      this.#stream = null;
      if (this.#clock) clearInterval(this.#clock);
      this.#clock = null;
    }

    /** Subscribe to the state of the door station of the card, once. */
    #follow() {
      const entry = this.#station?.entry_id ?? null;
      if (!this.isConnected || !this.#hass?.connection || entry === this.#subscribed) return;
      this.#stop();
      if (!entry) return;
      this.#subscribed = entry;
      this.#hass.connection
        .subscribeMessage(
          (/** @type {Snapshot} */ snapshot) => {
            // A new call ends the monitoring: its screen takes over
            if (callStateOf(snapshot) !== "idle") this.#monitoring = false;
            this.#snapshot = snapshot;
            this.#render();
          },
          { type: `${PLATFORM}/subscribe`, entry_id: entry },
        )
        .then((/** @type {() => void} */ unsubscribe) => {
          if (this.#subscribed === entry) this.#unsubscribe = unsubscribe;
          else unsubscribe();
        })
        .catch(() => {
          // The entry is not loaded: the state stays unknown until it is
          if (this.#subscribed === entry) this.#subscribed = null;
        });
    }

    #stop() {
      this.#unsubscribe?.();
      this.#unsubscribe = null;
      this.#subscribed = null;
      this.#snapshot = null;
    }

    /** The `hass` of the card, with the texts of the integration once loaded. */
    get #texts() {
      return this.#hass && { ...this.#hass, localize: this.#localize ?? this.#hass.localize };
    }

    /** @param {string | null} message */
    #notify(message) {
      if (!message) return;
      this.dispatchEvent(
        new CustomEvent("hass-notification", {
          detail: { message },
          bubbles: true,
          composed: true,
        }),
      );
    }

    /**
     * Send a command, its keys disabled until it is answered; a refusal is shown.
     *
     * @param {string} key
     * @param {Record<string, any>} message
     */
    async #send(key, message) {
      if (!this.#hass?.callWS || this.#busy) return;
      this.#busy = key;
      this.#render();
      try {
        await this.#hass.callWS(message);
      } catch (err) {
        this.#notify(/** @type {any} */ (err)?.message ?? String(err));
      } finally {
        this.#busy = null;
        this.#render();
      }
    }

    /** @param {KeyName} key */
    #press(key) {
      const entry = this.#station?.entry_id;
      const call = this.#snapshot?.call;
      if (key === "monitor") {
        this.#monitoring = !this.#monitoring;
        this.#render();
      } else if (key === "ring") {
        this.#ringMuted = !this.#ringMuted;
        rememberRingMuted(this.#ringMuted);
        this.#render();
      } else if ((key === "answer" || key === "reject" || key === "hang_up") && entry && call) {
        this.#send(key, callMessage(entry, call, key));
      }
    }

    /** Start talking to the door: with the call if one is answered, through its speaker otherwise. */
    async #startTalk() {
      const entry = this.#station?.entry_id;
      const connection = this.#hass?.connection;
      if (this.#microphone || !entry || !this.#hass || !connection) return;
      const texts = textsIn(this.#hass.language);
      const microphone = new Microphone({ connection }, entry, (/** @type {TalkEnd} */ reason) => {
        if (this.#microphone === microphone) this.#microphone = null;
        this.#notify(talkMessage(texts, reason));
        this.#render();
      });
      this.#microphone = microphone;
      this.#render();
      try {
        await microphone.start();
      } catch (err) {
        if (this.#microphone === microphone) this.#microphone = null;
        this.#notify(talkMessage(texts, /** @type {any} */ (err)?.message ?? "talk_failed"));
        this.#render();
      }
    }

    #stopTalk() {
      const microphone = this.#microphone;
      if (!microphone) return;
      this.#microphone = null;
      this.#render();
      microphone.stop();
    }

    /** Build the card once: the screen keeps its stream and the keys their presses. */
    #build() {
      const root = this.shadowRoot ?? this.attachShadow({ mode: "open" });
      const style = document.createElement("style");
      style.textContent = STYLE;
      /** @param {string} tag @param {string} className */
      const part = (tag, className) => Object.assign(document.createElement(tag), { className });
      const card = document.createElement("ha-card");
      const screen = part("div", "screen");
      const overlay = part("div", "overlay");
      /** @type {Parts} */
      const parts = {
        media: part("div", "media"),
        name: part("div", "name"),
        state: part("div", "chip"),
        warning: part("div", "warning"),
        keys: part("div", "keys"),
        extra: part("div", "keys extra"),
        buttons: new Map(),
      };
      overlay.append(parts.name, parts.state);
      screen.append(parts.media, overlay, parts.warning);
      card.append(screen, parts.keys, parts.extra);
      root.replaceChildren(style, card);
      for (const name of /** @type {KeyName[]} */ ([
        "answer",
        "hang_up",
        "monitor",
        "talk",
        "ring",
      ])) {
        const button = name === "talk" ? this.#talkKey() : keyElement("key");
        if (name !== "talk") {
          // The key of hang up refuses a call that rings: its name says which it does
          button.addEventListener("click", () =>
            this.#press(/** @type {KeyName} */ (button.dataset.key)),
          );
        }
        button.dataset.key = name;
        parts.buttons.set(name, button);
        parts.keys.append(button);
      }
      return parts;
    }

    /** The key of push-to-talk: held to talk, or pressed once to talk and once to stop. */
    #talkKey() {
      const button = keyElement("key talk");
      const hold = () => (this.#config?.talk_mode ?? "hold") === "hold";
      button.addEventListener("pointerdown", (event) => {
        if (!hold() || button.disabled) return;
        button.setPointerCapture?.(event.pointerId);
        this.#startTalk();
      });
      for (const end of ["pointerup", "pointercancel"]) {
        button.addEventListener(end, () => hold() && this.#stopTalk());
      }
      button.addEventListener("click", () => {
        if (hold()) return;
        if (this.#microphone) this.#stopTalk();
        else this.#startTalk();
      });
      // The space bar, while the key has the focus: held to talk, as the pointer
      button.addEventListener("keydown", (event) => {
        if (event.key !== " " || event.repeat || !hold()) return;
        event.preventDefault();
        this.#startTalk();
      });
      button.addEventListener("keyup", (event) => {
        if (event.key !== " " || !hold()) return;
        event.preventDefault();
        this.#stopTalk();
      });
      return button;
    }

    #render() {
      if (!this.#config) return;
      const hass = this.#texts;
      const parts = (this.#parts ??= this.#build());
      const station = this.#station;
      if (!hass || !station) {
        parts.name.textContent = "";
        parts.state.textContent = "";
        parts.state.hidden = true;
        parts.warning.textContent = textsIn(hass?.language).no_station;
        parts.warning.hidden = false;
        parts.keys.hidden = true;
        parts.extra.replaceChildren();
        this.#ringer.stop();
        return;
      }
      const texts = textsIn(hass.language);
      const state = callStateOf(this.#snapshot);
      const talking = this.#microphone !== null;
      const talkable = talkAllowed(state, this.#snapshot);
      // A talk the state no longer allows stops; one the door ends ends by itself
      if (talking && !talkable) this.#stopTalk();
      parts.keys.hidden = false;
      parts.state.hidden = false;
      parts.name.textContent = station.name;
      const label = screenLabel(hass, state, {
        monitoring: this.#monitoring,
        answeredAt: this.#snapshot?.call?.answered_at,
      });
      parts.state.className = `chip ${label.tone}`;
      parts.state.textContent = label.text;
      this.#tick(state === "answered");
      this.#ring(state === "ringing" && !this.#ringMuted);
      const warnings = [];
      if (this.#snapshot && !this.#snapshot.registered) warnings.push(texts.unregistered);
      if (this.#ringer.ringing && this.#ringer.blocked) warnings.push(texts.tap_for_sound);
      parts.warning.textContent = warnings.join(" ");
      parts.warning.hidden = !warnings.length;
      this.#renderScreen(
        hass,
        station,
        screenOf(state, this.#monitoring, this.#microphone !== null),
      );
      this.#renderKeys(hass, state, talkable);
      this.#renderExtra(hass, station);
    }

    /** @param {boolean} answered Tick every second while a call is answered. */
    #tick(answered) {
      if (answered && !this.#clock) this.#clock = setInterval(() => this.#render(), 1000);
      if (!answered && this.#clock) {
        clearInterval(this.#clock);
        this.#clock = null;
      }
    }

    /** @param {boolean} ring */
    #ring(ring) {
      if (ring) this.#ringer.start();
      else this.#ringer.stop();
    }

    /**
     * @param {Hass} hass
     * @param {Station} station
     * @param {{ live: boolean, audible: boolean }} screen
     */
    #renderScreen(hass, station, screen) {
      const { media } = /** @type {Parts} */ (this.#parts);
      const camera = station.camera ? hass.states[station.camera] : undefined;
      if (!camera) {
        media.replaceChildren();
        return;
      }
      if (screen.live && this.#streamDefined === null) {
        // Once: the frontend defines its camera stream with its picture cards
        this.#streamDefined = false;
        loadCameraStream(station.camera ?? "").then((defined) => {
          this.#streamDefined = defined;
          this.#render();
        });
      }
      if (!screen.live || !this.#streamDefined) {
        // The camera's picture: outside a call, or while (or if never) the stream loads
        this.#stream?.remove();
        this.#stream = null;
        const picture = camera.attributes.entity_picture;
        let image = media.querySelector("img");
        if (!image) media.replaceChildren((image = document.createElement("img")));
        if (picture && image.getAttribute("src") !== picture) image.src = picture;
        return;
      }
      if (!this.#stream) {
        this.#stream = document.createElement("ha-camera-stream");
        media.replaceChildren(this.#stream);
      }
      this.#stream.stateObj = camera;
      this.#stream.muted = !screen.audible;
      this.#stream.fitMode = "cover";
    }

    /** @param {Hass} hass @param {CallState} state @param {boolean} talkable */
    #renderKeys(hass, state, talkable) {
      const { buttons } = /** @type {Parts} */ (this.#parts);
      const hasCall = Boolean(this.#snapshot?.call);
      const keys = deviceKeys({
        state,
        monitoring: this.#monitoring,
        ringMuted: this.#ringMuted,
        talkable,
        talking: this.#microphone !== null,
      });
      keys.forEach((key, index) => {
        const name = /** @type {KeyName} */ (
          ["answer", "hang_up", "monitor", "talk", "ring"][index]
        );
        const button = /** @type {HTMLButtonElement} */ (buttons.get(name));
        const ofCall = index < 2;
        // What the key does now: hang up refuses a call that rings
        if (name !== "talk") button.dataset.key = key.key;
        showKey(button, {
          icon: key.icon,
          name: keyName(hass, key),
          className: `key ${key.tone}${key.active ? " active" : ""}${name === "talk" ? " talk" : ""}`,
          enabled: key.enabled && (!ofCall || (hasCall && this.#busy === null)),
        });
      });
    }

    /** The doors and the shortcuts, under the keys. @param {Hass} hass @param {Station} station */
    #renderExtra(hass, station) {
      const { extra } = /** @type {Parts} */ (this.#parts);
      const numbers = doorsOf(this.#snapshot);
      const locks = locksOf(this.#snapshot);
      const entry = station.entry_id;
      const doors = numbers.map((door) => {
        const button = keyElement("key");
        showKey(button, {
          icon: "mdi:key-variant",
          name: doorName(hass, door, numbers.length),
          className: "key",
          // A door whose output rings a doorbell, or drives nothing, does not open
          enabled: Boolean(entry) && this.#busy === null && locks.includes(door),
        });
        button.addEventListener(
          "click",
          () => entry && this.#send(`door_${door}`, openDoorMessage(entry, door)),
        );
        return button;
      });
      const shortcuts = shortcutsOf(/** @type {CardConfig} */ (this.#config)).map((shortcut) => {
        const view = shortcutView(hass, shortcut);
        const button = keyElement("key");
        showKey(button, {
          icon: view.icon,
          name: view.name,
          className: `key${view.active ? " active" : ""}`,
          enabled: view.available,
        });
        button.addEventListener("click", () => {
          const { domain, service, data } = shortcutService(shortcut.entity);
          this.#hass?.callService?.(domain, service, data).catch((/** @type {any} */ err) => {
            this.#notify(err?.message ?? String(err));
          });
        });
        return button;
      });
      extra.replaceChildren(...doors, ...shortcuts);
    }

    getCardSize() {
      return 7;
    }

    /** @param {Hass} hass */
    static getStubConfig(hass) {
      return stubConfig(hass);
    }

    static async getConfigElement() {
      await loadForms();
      return document.createElement(`${CARD}-editor`);
    }
  }

  /** The editor of the card: the door station, the way to talk, the shortcuts. */
  class IndoorStationCardEditor extends HTMLElement {
    /** @type {CardConfig | undefined} */
    #config;
    /** @type {Hass | undefined} */
    #hass;
    /** @type {any} */
    #form;

    /** @param {CardConfig} config */
    setConfig(config) {
      this.#config = config;
      this.#render();
    }

    /** @param {Hass} hass */
    set hass(hass) {
      this.#hass = hass;
      this.#render();
    }

    #render() {
      if (!this.#hass || !this.#config) return;
      if (!this.#form) {
        this.#form = document.createElement("ha-form");
        this.#form.computeLabel = (/** @type {{ name: string, label?: string }} */ field) =>
          field.label ?? field.name;
        this.#form.addEventListener("value-changed", (/** @type {CustomEvent} */ event) => {
          event.stopPropagation();
          const config = configFromEditor(
            /** @type {CardConfig} */ (this.#config),
            event.detail.value,
          );
          this.dispatchEvent(
            new CustomEvent("config-changed", {
              detail: { config },
              bubbles: true,
              composed: true,
            }),
          );
        });
        this.append(this.#form);
      }
      this.#form.hass = this.#hass;
      this.#form.schema = editorSchema(this.#hass);
      this.#form.data = editorData(this.#config);
    }
  }

  customElements.get(CARD) || customElements.define(CARD, IndoorStationCard);
  customElements.get(`${CARD}-editor`) ||
    customElements.define(`${CARD}-editor`, IndoorStationCardEditor);

  // Listed in the card picker, with a preview
  const pickable = /** @type {any} */ (window).customCards ?? [];
  /** @type {any} */ (window).customCards = pickable;
  if (!pickable.some((/** @type {{ type: string }} */ item) => item.type === CARD)) {
    pickable.push({
      type: CARD,
      name: "Hikvision Virtual Indoor Station",
      description: textsIn(document.documentElement.lang || navigator.language).description,
      preview: true,
      documentationURL:
        "https://github.com/webysther/ha-hikvision-virtual-indoor-station#dashboard-and-card",
    });
  }
}
