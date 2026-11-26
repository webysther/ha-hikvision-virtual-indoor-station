// @ts-check
/**
 * The Hikvision Virtual Indoor Station card: the screen of an indoor station, laid out
 * like a wall monitor. On top the door's camera; under it the state of the call and the
 * buttons it allows (answer and refuse while it rings, hang up while it is answered,
 * monitor while idle); then a key for each door and push-to-talk.
 *
 * The card follows its door station through the websocket command
 * `hikvision_virtual_indoor_station/subscribe` (the latest call and its id), and every
 * command names that call, so a late tap never touches the next visitor.
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
 *   started_at: string | null,
 *   answered_at: string | null,
 *   ended_at: string | null,
 * }} Call A call of the door station, as `subscribe` gives it.
 * @typedef {{ registered: boolean, doors: number[], speaker: boolean, call: Call | null }} Snapshot
 *   The state of a door station, as `subscribe` gives it (IndoorStation.snapshot).
 * @typedef {"idle" | "ringing" | "answered"} CallState The states of the call sensor.
 * @typedef {{ type: string, device_id?: string }} CardConfig
 */

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
    .header { display: flex; align-items: center; justify-content: space-between;
      padding: 12px 16px; gap: 8px; }
    .name { font-size: 1.2em; font-weight: 500; }
    .state { color: var(--secondary-text-color); }
    .state.ringing { color: var(--success-color, #43a047); font-weight: 500; }
    .state.answered { color: var(--primary-color); font-weight: 500; }
    .warning { padding: 0 16px 12px; color: var(--warning-color, #ffa600); }
  `;

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

    /** @param {any} config */
    setConfig(config) {
      this.#config = checkConfig(config);
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

    #render() {
      if (!this.#config) return;
      const root = this.shadowRoot ?? this.attachShadow({ mode: "open" });
      const hass = this.#hass && { ...this.#hass, localize: this.#localize ?? this.#hass.localize };
      const card = document.createElement("ha-card");
      const style = document.createElement("style");
      style.textContent = STYLE;
      if (!hass || !this.#station) {
        const warning = document.createElement("div");
        warning.className = "warning";
        warning.textContent = textsIn(hass?.language).no_station;
        card.append(warning);
        root.replaceChildren(style, card);
        return;
      }
      const state = callStateOf(this.#snapshot);
      const header = document.createElement("div");
      header.className = "header";
      const name = document.createElement("div");
      name.className = "name";
      name.textContent = this.#station.name;
      const status = document.createElement("div");
      status.className = `state ${state}`;
      status.textContent = callStateName(hass, state);
      header.append(name, status);
      card.append(header);
      root.replaceChildren(style, card);
    }

    getCardSize() {
      return 6;
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
