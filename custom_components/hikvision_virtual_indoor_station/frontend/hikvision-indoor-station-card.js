// @ts-check
/**
 * The Hikvision Virtual Indoor Station card: the screen of an indoor station, laid out
 * like a wall monitor. On top the door's camera; under it the state of the call and the
 * buttons it allows (answer and refuse while it rings, hang up while it is answered,
 * monitor while idle, mute the ringer); then push-to-talk and a key for each door.
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
 * @typedef {{ registered: boolean, doors: number[], speaker: boolean, call: Call | null }} Snapshot
 *   The state of a door station, as `subscribe` gives it (IndoorStation.snapshot).
 * @typedef {"idle" | "ringing" | "answered"} CallState The states of the call sensor.
 * @typedef {"answer" | "reject" | "hang_up" | "monitor" | "ring"} ActionKey
 * @typedef {{ key: ActionKey, icon: string, tone: "accept" | "decline" | "neutral", active?: boolean }} Action
 *   A button of the main row.
 * @typedef {"hold" | "toggle"} TalkMode Push-to-talk: talk while the button is held, or
 *   from one press to the next.
 * @typedef {{ entity: string, name?: string, icon?: string }} Shortcut A button of the card
 *   for another entity: a light, a scene, another door.
 * @typedef {{ type: string, device_id?: string, talk_mode?: TalkMode,
 *   shortcuts?: Array<string | Shortcut> }} CardConfig
 * @typedef {{ card: HTMLElement, screen: HTMLElement, name: HTMLElement, state: HTMLElement,
 *   warning: HTMLElement, actions: HTMLElement, talk: HTMLElement, doors: HTMLElement,
 *   shortcuts: HTMLElement }} Parts
 *   The parts of the card.
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
 * Return the buttons of the main row: those the state of the call allows.
 *
 * @param {CallState} state
 * @param {boolean} monitoring
 * @param {boolean} [ringMuted] Whether the ringer of this browser is muted.
 * @returns {Action[]}
 */
export function mainActions(state, monitoring, ringMuted = false) {
  /** @type {Action} */
  const ring = {
    key: "ring",
    icon: ringMuted ? "mdi:bell-off" : "mdi:bell",
    tone: "neutral",
    active: ringMuted,
  };
  if (state === "ringing") {
    return [
      { key: "answer", icon: "mdi:phone", tone: "accept" },
      { key: "reject", icon: "mdi:phone-cancel", tone: "decline" },
      ring,
    ];
  }
  if (state === "answered") return [{ key: "hang_up", icon: "mdi:phone-hangup", tone: "decline" }];
  return [
    {
      key: "monitor",
      icon: monitoring ? "mdi:monitor-off" : "mdi:monitor-eye",
      tone: "neutral",
      active: monitoring,
    },
    ring,
  ];
}

/**
 * Return the name of a button of the main row in the language of the user: the names
 * of the buttons of the integration, and the texts of the card for the others.
 *
 * @param {Hass} hass
 * @param {Action} action
 */
export function actionName(hass, action) {
  const texts = textsIn(hass.language);
  if (action.key === "monitor") return action.active ? texts.stop_monitor : texts.monitor;
  if (action.key === "ring") return action.active ? texts.unmute_ring : texts.mute_ring;
  return translated(hass, `entity.button.${action.key}.name`) ?? action.key;
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
  const STYLE = `
    ha-card { overflow: hidden; }
    .screen { position: relative; aspect-ratio: 16 / 9; background: #000; }
    .screen > * { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
    .header { display: flex; align-items: center; justify-content: space-between;
      padding: 12px 16px 4px; gap: 8px; }
    .name { font-size: 1.2em; font-weight: 500; }
    .state { color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
    .state.ringing { color: var(--success-color, #43a047); font-weight: 500; }
    .state.answered { color: var(--primary-color); font-weight: 500; }
    .warning { padding: 4px 16px; color: var(--warning-color, #ffa600); }
    .row { display: flex; flex-wrap: wrap; gap: 12px; padding: 12px 16px; justify-content: center; }
    .row:empty { display: none; }
    button { flex: 1 1 0; min-width: 96px; min-height: 56px; display: flex; flex-direction: column;
      align-items: center; justify-content: center; gap: 4px; border: none; border-radius: 12px;
      font: inherit; cursor: pointer; color: var(--primary-text-color);
      background: var(--secondary-background-color, #e0e0e0); }
    button:disabled { opacity: 0.5; cursor: default; }
    button.accept { background: var(--success-color, #43a047); color: #fff; }
    button.decline { background: var(--error-color, #db4437); color: #fff; }
    button.active { background: var(--primary-color); color: var(--text-primary-color, #fff); }
    .talk button { min-height: 72px; touch-action: none; user-select: none; -webkit-user-select: none; }
    .doors { border-top: 1px solid var(--divider-color); }
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
    /** @type {string | null} The command waiting for its answer: its buttons are disabled. */
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
     * Send a command, its buttons disabled until it is answered; a refusal is shown.
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

    /** @param {Action} action */
    #press(action) {
      const entry = this.#station?.entry_id;
      const call = this.#snapshot?.call;
      if (action.key === "monitor") {
        this.#monitoring = !this.#monitoring;
        this.#render();
      } else if (action.key === "ring") {
        this.#ringMuted = !this.#ringMuted;
        rememberRingMuted(this.#ringMuted);
        this.#render();
      } else if (entry && call) {
        this.#send(action.key, callMessage(entry, call, action.key));
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

    /** Build the parts of the card once: the screen keeps its stream across renders. */
    #build() {
      const root = this.shadowRoot ?? this.attachShadow({ mode: "open" });
      const style = document.createElement("style");
      style.textContent = STYLE;
      /** @param {string} tag @param {string} className */
      const part = (tag, className) => Object.assign(document.createElement(tag), { className });
      const card = document.createElement("ha-card");
      const header = part("div", "header");
      /** @type {Parts} */
      const parts = {
        card,
        screen: part("div", "screen"),
        name: part("div", "name"),
        state: part("div", "state"),
        warning: part("div", "warning"),
        actions: part("div", "row actions"),
        talk: part("div", "row talk"),
        doors: part("div", "row doors"),
        shortcuts: part("div", "row shortcuts"),
      };
      header.append(parts.name, parts.state);
      card.append(
        parts.screen,
        header,
        parts.warning,
        parts.actions,
        parts.talk,
        parts.doors,
        parts.shortcuts,
      );
      root.replaceChildren(style, card);
      parts.talk.append(this.#talkButton());
      return parts;
    }

    /** The push-to-talk button, built once: re-rendering it would drop the press in progress. */
    #talkButton() {
      const button = document.createElement("button");
      button.append(document.createElement("ha-icon"), document.createElement("span"));
      const hold = () => (this.#config?.talk_mode ?? "hold") === "hold";
      button.addEventListener("pointerdown", (event) => {
        if (!hold()) return;
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
      // The space bar, while the button has the focus: held to talk, as the pointer
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
        parts.screen.hidden = true;
        parts.talk.hidden = true;
        parts.name.textContent = "";
        parts.state.textContent = "";
        parts.warning.textContent = textsIn(hass?.language).no_station;
        parts.warning.hidden = false;
        parts.actions.replaceChildren();
        parts.doors.replaceChildren();
        parts.shortcuts.replaceChildren();
        this.#ringer.stop();
        return;
      }
      const texts = textsIn(hass.language);
      const state = callStateOf(this.#snapshot);
      const talking = this.#microphone !== null;
      parts.name.textContent = station.name;
      parts.state.className = `state ${state}`;
      const time =
        state === "answered" ? elapsed(this.#snapshot?.call?.answered_at, Date.now()) : null;
      parts.state.textContent = [callStateName(hass, state), time].filter(Boolean).join(" ");
      this.#tick(state === "answered");
      this.#ring(state === "ringing" && !this.#ringMuted);
      const warnings = [];
      if (this.#snapshot && !this.#snapshot.registered) warnings.push(texts.unregistered);
      if (this.#ringer.ringing && this.#ringer.blocked) warnings.push(texts.tap_for_sound);
      parts.warning.textContent = warnings.join(" ");
      parts.warning.hidden = !warnings.length;
      this.#renderScreen(hass, station, screenOf(state, this.#monitoring, talking));
      this.#renderActions(hass, state);
      this.#renderTalk(texts, talkAllowed(state, this.#snapshot), talking);
      this.#renderDoors(hass, station);
      this.#renderShortcuts(hass);
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
      const { screen: element } = /** @type {Parts} */ (this.#parts);
      const camera = station.camera ? hass.states[station.camera] : undefined;
      element.hidden = !camera;
      if (!camera) return;
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
        let image = element.querySelector("img");
        if (!image) element.replaceChildren((image = document.createElement("img")));
        if (picture && image.getAttribute("src") !== picture) image.src = picture;
        return;
      }
      if (!this.#stream) {
        this.#stream = document.createElement("ha-camera-stream");
        element.replaceChildren(this.#stream);
      }
      this.#stream.stateObj = camera;
      this.#stream.muted = !screen.audible;
      this.#stream.fitMode = "cover";
    }

    /** @param {Hass} hass @param {CallState} state */
    #renderActions(hass, state) {
      const { actions } = /** @type {Parts} */ (this.#parts);
      const call = this.#snapshot?.call;
      actions.replaceChildren(
        ...mainActions(state, this.#monitoring, this.#ringMuted).map((action) => {
          const button = document.createElement("button");
          button.className = `${action.tone}${action.active ? " active" : ""}`;
          const local = action.key === "monitor" || action.key === "ring";
          button.disabled = !local && (!call || this.#busy !== null);
          const icon = document.createElement("ha-icon");
          icon.setAttribute("icon", action.icon);
          const label = document.createElement("span");
          label.textContent = actionName(hass, action);
          button.append(icon, label);
          button.addEventListener("click", () => this.#press(action));
          return button;
        }),
      );
    }

    /** @param {Texts} texts @param {boolean} allowed @param {boolean} talking */
    #renderTalk(texts, allowed, talking) {
      const { talk } = /** @type {Parts} */ (this.#parts);
      // A talk the door ends by itself ends here too; one the state no longer allows stops
      if (talking && !allowed) this.#stopTalk();
      talk.hidden = !allowed;
      const button = /** @type {HTMLButtonElement} */ (talk.firstElementChild);
      button.className = talking ? "active" : "";
      button
        .querySelector("ha-icon")
        ?.setAttribute("icon", talking ? "mdi:microphone" : "mdi:microphone-outline");
      const label = button.querySelector("span");
      if (label) label.textContent = talking ? texts.talking : texts.talk;
    }

    /** @param {Hass} hass @param {Station} station */
    #renderDoors(hass, station) {
      const { doors } = /** @type {Parts} */ (this.#parts);
      const numbers = doorsOf(this.#snapshot);
      const entry = station.entry_id;
      doors.replaceChildren(
        ...numbers.map((door) => {
          const button = document.createElement("button");
          button.disabled = !entry || this.#busy !== null;
          const icon = document.createElement("ha-icon");
          icon.setAttribute("icon", "mdi:door-open");
          const label = document.createElement("span");
          label.textContent = doorName(hass, door, numbers.length);
          button.append(icon, label);
          button.addEventListener(
            "click",
            () => entry && this.#send(`door_${door}`, openDoorMessage(entry, door)),
          );
          return button;
        }),
      );
    }

    /** @param {Hass} hass */
    #renderShortcuts(hass) {
      const { shortcuts } = /** @type {Parts} */ (this.#parts);
      shortcuts.replaceChildren(
        ...shortcutsOf(/** @type {CardConfig} */ (this.#config)).map((shortcut) => {
          const view = shortcutView(hass, shortcut);
          const button = document.createElement("button");
          button.className = view.active ? "active" : "";
          button.disabled = !view.available;
          const icon = document.createElement("ha-icon");
          icon.setAttribute("icon", view.icon);
          const label = document.createElement("span");
          label.textContent = view.name;
          button.append(icon, label);
          button.addEventListener("click", () => {
            const { domain, service, data } = shortcutService(shortcut.entity);
            this.#hass?.callService?.(domain, service, data).catch((/** @type {any} */ err) => {
              this.#notify(err?.message ?? String(err));
            });
          });
          return button;
        }),
      );
    }

    getCardSize() {
      return 9;
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
