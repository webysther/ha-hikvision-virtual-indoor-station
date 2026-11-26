// @ts-check
/**
 * The Hikvision Virtual Indoor Station dashboard: a strategy the frontend of Home
 * Assistant runs to build a view for each door station, with the indoor station card
 * and native cards. It also holds the helpers the card shares with it: finding the
 * door stations among the entities, and the texts.
 *
 * Plain JavaScript without build or dependencies, served by the integration
 * (dashboard.py). The functions are exported for the tests (tests/frontend).
 */

/** The domain of the integration, the platform of its entities. */
export const PLATFORM = "hikvision_virtual_indoor_station";

/** The type of the strategy: `strategy: { type: custom:hikvision-indoor-station }`. */
export const STRATEGY = "hikvision-indoor-station";

/** The custom element of the card: `type: custom:hikvision-indoor-station-card`. */
export const CARD = "hikvision-indoor-station-card";

/**
 * The entities of a door station the card and the dashboard use, by translation key
 * (the camera has none: it is the entity of the device).
 */
export const KEYS = ["call", "doorbell", "sip_registered", "answer", "hang_up", "reject"];

/**
 * @typedef {{
 *   entity_id: string,
 *   device_id?: string | null,
 *   platform?: string,
 *   translation_key?: string | null,
 *   hidden?: boolean,
 * }} EntityEntry An entity of the registry, as the frontend has it.
 * @typedef {{
 *   id: string,
 *   name?: string | null,
 *   name_by_user?: string | null,
 *   config_entries?: string[],
 *   primary_config_entry?: string | null,
 * }} DeviceEntry A device of the registry, as the frontend has it.
 * @typedef {{
 *   entities: Record<string, EntityEntry>,
 *   devices: Record<string, DeviceEntry>,
 *   states: Record<string, { state: string, attributes: Record<string, any> }>,
 *   localize?: (key: string, ...args: any[]) => string,
 *   loadBackendTranslation?: (category: string, integration: string) => Promise<any>,
 *   language?: string,
 *   connection?: any,
 *   callWS?: (message: Record<string, any>) => Promise<any>,
 * }} Hass The part of the `hass` object of the frontend these modules read.
 * @typedef {{
 *   device_id: string,
 *   entry_id: string | null,
 *   name: string,
 *   camera: string | null,
 *   entities: Record<string, string>,
 * }} Station A door station: its device, its config entry, its camera and its
 *   entities by translation key.
 */

/**
 * Return the door stations of the integration, sorted by name.
 *
 * @param {Hass} hass
 * @returns {Station[]}
 */
export function findStations(hass) {
  /** @type {Map<string, Station>} */
  const stations = new Map();
  for (const entry of Object.values(hass.entities ?? {})) {
    if (entry.platform !== PLATFORM || !entry.device_id) continue;
    const device = hass.devices?.[entry.device_id];
    if (!device) continue;
    let station = stations.get(device.id);
    if (!station) {
      station = {
        device_id: device.id,
        entry_id: device.primary_config_entry ?? device.config_entries?.[0] ?? null,
        name: device.name_by_user || device.name || device.id,
        camera: null,
        entities: {},
      };
      stations.set(device.id, station);
    }
    if (entry.entity_id.startsWith("camera.")) {
      station.camera = entry.entity_id;
    } else if (entry.translation_key && KEYS.includes(entry.translation_key)) {
      station.entities[entry.translation_key] = entry.entity_id;
    }
  }
  return [...stations.values()].sort((a, b) => a.name.localeCompare(b.name));
}

/**
 * Return the door station a card shows: the one of its device, or the first one.
 *
 * @param {Station[]} stations
 * @param {{ device_id?: string }} config
 */
export function stationOf(stations, config) {
  return config.device_id
    ? stations.find((station) => station.device_id === config.device_id)
    : stations[0];
}

/**
 * Return `hass` with the texts of the entities of the integration loaded, in the
 * language of the user.
 *
 * @param {Hass} hass
 * @returns {Promise<Hass>}
 */
export async function withTexts(hass) {
  if (!hass.loadBackendTranslation) return hass;
  const localize = await hass.loadBackendTranslation("entity", PLATFORM);
  return { ...hass, localize };
}

/**
 * Return a text of the integration in the language of the user, if the frontend
 * has it.
 *
 * @param {Hass} hass
 * @param {string} key e.g. "entity.button.answer.name"
 * @param {Record<string, string | number>} [values] The placeholders of the text, e.g. `{ door: 2 }`.
 */
export function translated(hass, key, values) {
  return hass.localize?.(`component.${PLATFORM}.${key}`, values) || undefined;
}

/**
 * The texts of the card and the dashboard that are not texts of the entities, by
 * language. The integration's own texts (strings.json) have no place for them.
 */
export const TEXTS = {
  en: {
    description: "The indoor station of a Hikvision door station: answer, talk, open the door.",
    no_station: "No door station yet: add one in Settings → Devices & services.",
    activity: "Activity",
    monitor: "Monitor",
    stop_monitor: "Stop monitoring",
    unregistered: "The door station is not registered with Home Assistant: it cannot call.",
    talk: "Push to talk",
    talking: "Talking…",
    talk_https: "Talking needs Home Assistant opened over HTTPS.",
    talk_unsupported: "This browser cannot send its microphone.",
    talk_denied: "The browser was not allowed to use the microphone.",
    talk_failed: "The door station did not open its speaker.",
    replaced: "Someone else is talking to the door station.",
    device: "The door station ended the talk.",
    unloaded: "The integration was reloaded: talk again.",
    call_answered: "A call was answered: talk again, with the call.",
    mute_ring: "Mute ringer",
    unmute_ring: "Ring",
    tap_for_sound: "Tap the card to let the browser ring.",
  },
  it: {
    description: "Il posto interno di un citofono Hikvision: rispondi, parla, apri la porta.",
    no_station: "Ancora nessun citofono: aggiungine uno in Impostazioni → Dispositivi e servizi.",
    activity: "Attività",
    monitor: "Monitora",
    stop_monitor: "Interrompi",
    unregistered: "Il citofono non è registrato in Home Assistant: non può chiamare.",
    talk: "Premi per parlare",
    talking: "Stai parlando…",
    talk_https: "Per parlare serve Home Assistant aperto in HTTPS.",
    talk_unsupported: "Questo browser non può inviare il microfono.",
    talk_denied: "Il browser non ha il permesso di usare il microfono.",
    talk_failed: "Il citofono non ha aperto il suo altoparlante.",
    replaced: "Qualcun altro sta parlando al citofono.",
    device: "Il citofono ha chiuso la conversazione.",
    unloaded: "L'integrazione è stata ricaricata: parla di nuovo.",
    call_answered: "Una chiamata è stata risposta: parla di nuovo, con la chiamata.",
    mute_ring: "Silenzia suoneria",
    unmute_ring: "Suoneria",
    tap_for_sound: "Tocca la scheda per far suonare il browser.",
  },
  "pt-BR": {
    description: "O monitor interno de um porteiro Hikvision: atender, falar, abrir a porta.",
    no_station: "Nenhum porteiro ainda: adicione um em Configurações → Dispositivos e serviços.",
    activity: "Atividade",
    monitor: "Monitorar",
    stop_monitor: "Parar",
    unregistered: "O porteiro não está registrado no Home Assistant: ele não consegue chamar.",
    talk: "Aperte para falar",
    talking: "Falando…",
    talk_https: "Para falar, abra o Home Assistant por HTTPS.",
    talk_unsupported: "Este navegador não consegue enviar o microfone.",
    talk_denied: "O navegador não tem permissão para usar o microfone.",
    talk_failed: "O porteiro não abriu o alto-falante.",
    replaced: "Outra pessoa está falando com o porteiro.",
    device: "O porteiro encerrou a fala.",
    unloaded: "A integração foi recarregada: fale de novo.",
    call_answered: "Uma chamada foi atendida: fale de novo, pela chamada.",
    mute_ring: "Silenciar campainha",
    unmute_ring: "Campainha",
    tap_for_sound: "Toque no card para o navegador poder tocar.",
  },
};

/**
 * Return the texts in a language, or in English when there are none in it.
 *
 * @param {string | undefined} language e.g. "pt-BR", "it-IT"
 * @returns {typeof TEXTS.en}
 */
export function textsIn(language) {
  const languages = /** @type {Record<string, typeof TEXTS.en>} */ (TEXTS);
  if (!language) return TEXTS.en;
  return languages[language] ?? languages[language.split("-")[0]] ?? TEXTS.en;
}

/**
 * Return the view of a door station: the card, and its activity.
 *
 * @param {Station} station
 * @param {Hass} hass
 */
export function stationView(station, hass) {
  const texts = textsIn(hass.language);
  const activity = ["doorbell", "call", "sip_registered"]
    .map((key) => station.entities[key])
    .filter(Boolean);
  return {
    title: station.name,
    path: station.device_id,
    icon: "mdi:doorbell-video",
    type: "sections",
    max_columns: 2,
    sections: [
      { type: "grid", cards: [{ type: `custom:${CARD}`, device_id: station.device_id }] },
      {
        type: "grid",
        cards: [
          { type: "heading", heading: texts.activity },
          { type: "logbook", target: { entity_id: activity }, hours_to_show: 48 },
        ],
      },
    ],
  };
}

/**
 * Return the dashboard: a view for each door station.
 *
 * @param {Hass} hass
 */
export function generateDashboard(hass) {
  const stations = findStations(hass);
  if (!stations.length) {
    const texts = textsIn(hass.language);
    return { views: [{ cards: [{ type: "markdown", content: texts.no_station }] }] };
  }
  return { views: stations.map((station) => stationView(station, hass)) };
}

if (typeof customElements !== "undefined") {
  /** The dashboard: `strategy: { type: custom:hikvision-indoor-station }`. */
  class IndoorStationDashboardStrategy extends HTMLElement {
    /** @param {object} _config @param {Hass} hass */
    static async generate(_config, hass) {
      return generateDashboard(await withTexts(hass));
    }
  }

  /** A view of one door station: `strategy: { type: ..., device_id }`. */
  class IndoorStationViewStrategy extends HTMLElement {
    /** @param {{ device_id?: string }} config @param {Hass} hass */
    static async generate(config, hass) {
      const station = stationOf(findStations(hass), config);
      return station
        ? stationView(station, await withTexts(hass))
        : generateDashboard(hass).views[0];
    }
  }

  /** @param {string} tag @param {CustomElementConstructor} strategy */
  const define = (tag, strategy) => customElements.get(tag) || customElements.define(tag, strategy);
  define(`ll-strategy-dashboard-${STRATEGY}`, IndoorStationDashboardStrategy);
  define(`ll-strategy-view-${STRATEGY}`, IndoorStationViewStrategy);

  // Listed in the Add dashboard dialog
  const strategies = /** @type {any} */ (window).customStrategies ?? [];
  /** @type {any} */ (window).customStrategies = strategies;
  if (!strategies.some((/** @type {{ type: string }} */ item) => item.type === STRATEGY)) {
    strategies.push({
      type: STRATEGY,
      strategyType: "dashboard",
      name: "Hikvision Virtual Indoor Station",
      description: textsIn(document.documentElement.lang || navigator.language).description,
      documentationURL:
        "https://github.com/webysther/ha-hikvision-virtual-indoor-station#dashboard-and-card",
    });
  }
}
