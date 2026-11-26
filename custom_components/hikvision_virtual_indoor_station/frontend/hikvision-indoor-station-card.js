// @ts-check
/**
 * The Hikvision Virtual Indoor Station card: the screen of an indoor station, laid out
 * like a wall monitor. On top the door's camera; under it the state of the call and the
 * buttons it allows (answer and refuse while it rings, hang up while it is answered,
 * monitor while idle); then a key for each door.
 *
 * The card follows its door station through the websocket command
 * `hikvision_virtual_indoor_station/subscribe` (the latest call and its id), and every
 * command names that call, so a late tap never touches the next visitor.
 *
 * The camera plays live only while the door rings, a call is answered or someone
 * monitors: a door station serves few streams at once, and every open dashboard would
 * hold one. Otherwise the card shows the camera's picture. The door's sound plays once
 * the call is answered or the monitoring starts, both taps, which browsers require
 * before a page plays sound.
 *
 * Plain JavaScript without build or dependencies, served by the integration
 * (dashboard.py). The functions are exported for the tests (tests/frontend).
 */
import {
  CARD,
  PLATFORM,
  findStations,
  stationOf,
  textsIn,
  translated,
  withTexts,
} from "./hikvision-indoor-station-dashboard.js";

export { CARD };

/**
 * @typedef {import("./hikvision-indoor-station-dashboard.js").Hass} Hass
 * @typedef {import("./hikvision-indoor-station-dashboard.js").Station} Station
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
 * @typedef {"answer" | "reject" | "hang_up" | "monitor"} ActionKey
 * @typedef {{ key: ActionKey, icon: string, tone: "accept" | "decline" | "neutral", active?: boolean }} Action
 *   A button of the main row.
 * @typedef {{ type: string, device_id?: string }} CardConfig
 * @typedef {{ card: HTMLElement, screen: HTMLElement, name: HTMLElement, state: HTMLElement,
 *   warning: HTMLElement, actions: HTMLElement, doors: HTMLElement }} Parts The parts of the card.
 */

/** The action of the websocket command `call` for each button of the call. */
export const CALL_ACTIONS = { answer: "answer", reject: "reject", hang_up: "hangup" };

/** How long the card waits for the frontend to define its camera stream, in ms. */
export const STREAM_WAIT = 5000;

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
 * Return the buttons of the main row: those the state of the call allows.
 *
 * @param {CallState} state
 * @param {boolean} monitoring
 * @returns {Action[]}
 */
export function mainActions(state, monitoring) {
  if (state === "ringing") {
    return [
      { key: "answer", icon: "mdi:phone", tone: "accept" },
      { key: "reject", icon: "mdi:phone-cancel", tone: "decline" },
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
  ];
}

/**
 * Return the name of a button of the main row in the language of the user: the names
 * of the buttons of the integration, and the texts of the card for monitoring.
 *
 * @param {Hass} hass
 * @param {Action} action
 */
export function actionName(hass, action) {
  const texts = textsIn(hass.language);
  if (action.key === "monitor") return action.active ? texts.stop_monitor : texts.monitor;
  return translated(hass, `entity.button.${action.key}.name`) ?? action.key;
}

/**
 * Return what the screen shows: the live camera or its picture, and whether the door's
 * sound plays.
 *
 * @param {CallState} state
 * @param {boolean} monitoring
 */
export function screenOf(state, monitoring) {
  return { live: state !== "idle" || monitoring, audible: state === "answered" || monitoring };
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
  return config;
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

if (typeof customElements !== "undefined") {
  const STYLE = `
    ha-card { overflow: hidden; }
    .screen { position: relative; aspect-ratio: 16 / 9; background: #000; }
    .screen > * { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
    .header { display: flex; align-items: center; justify-content: space-between;
      padding: 12px 16px 4px; gap: 8px; }
    .name { font-size: 1.2em; font-weight: 500; }
    .state { color: var(--secondary-text-color); }
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
      this.#monitoring = false;
      this.#stream?.remove();
      this.#stream = null;
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
        const text = /** @type {any} */ (err)?.message ?? String(err);
        this.dispatchEvent(
          new CustomEvent("hass-notification", {
            detail: { message: text },
            bubbles: true,
            composed: true,
          }),
        );
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
      } else if (entry && call) {
        this.#send(action.key, callMessage(entry, call, action.key));
      }
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
      const parts = {
        card,
        screen: part("div", "screen"),
        name: part("div", "name"),
        state: part("div", "state"),
        warning: part("div", "warning"),
        actions: part("div", "row actions"),
        doors: part("div", "row doors"),
      };
      header.append(parts.name, parts.state);
      card.append(parts.screen, header, parts.warning, parts.actions, parts.doors);
      root.replaceChildren(style, card);
      return parts;
    }

    #render() {
      if (!this.#config) return;
      const hass = this.#texts;
      const parts = (this.#parts ??= this.#build());
      const station = this.#station;
      if (!hass || !station) {
        parts.screen.hidden = true;
        parts.name.textContent = "";
        parts.state.textContent = "";
        parts.warning.textContent = textsIn(hass?.language).no_station;
        parts.actions.replaceChildren();
        parts.doors.replaceChildren();
        return;
      }
      const state = callStateOf(this.#snapshot);
      parts.name.textContent = station.name;
      parts.state.className = `state ${state}`;
      parts.state.textContent = callStateName(hass, state);
      parts.warning.textContent =
        this.#snapshot && !this.#snapshot.registered ? textsIn(hass.language).unregistered : "";
      parts.warning.hidden = !parts.warning.textContent;
      this.#renderScreen(hass, station, screenOf(state, this.#monitoring));
      this.#renderActions(hass, state);
      this.#renderDoors(hass, station);
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
        ...mainActions(state, this.#monitoring).map((action) => {
          const button = document.createElement("button");
          button.className = `${action.tone}${action.active ? " active" : ""}`;
          button.disabled = action.key !== "monitor" && (!call || this.#busy !== null);
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

    getCardSize() {
      return 8;
    }

    /** @param {Hass} hass */
    static getStubConfig(hass) {
      return stubConfig(hass);
    }
  }

  customElements.get(CARD) || customElements.define(CARD, IndoorStationCard);

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
