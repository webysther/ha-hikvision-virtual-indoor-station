// Fixtures of the tests of the frontend: door stations as Home Assistant's frontend has them.

const PLATFORM = "hikvision_virtual_indoor_station";

/**
 * The door stations: the device, its config entry, its name and the object IDs of
 * its entities by translation key (the camera has none).
 */
export const STATIONS = {
  front: {
    device: "device_front",
    entry: "entry_front",
    name: "Front door",
    camera: "camera.front_door",
    entities: {
      call: "sensor.front_door_call",
      doorbell: "event.front_door_doorbell",
      sip_registered: "binary_sensor.front_door_sip_registration",
      answer: "button.front_door_answer",
      hang_up: "button.front_door_hang_up",
      reject: "button.front_door_reject",
      open_door: "button.front_door_open_door",
      visits: "sensor.front_door_visits",
      missed_visits: "sensor.front_door_missed_visits",
      visits_by_hour: "image.front_door_visits_by_hour",
      visits_by_day: "image.front_door_visits_by_day",
    },
  },
  back: {
    device: "device_back",
    entry: "entry_back",
    name: "Back gate",
    camera: "camera.back_gate",
    entities: {
      call: "sensor.back_gate_call",
      doorbell: "event.back_gate_doorbell",
      sip_registered: "binary_sensor.back_gate_sip_registration",
    },
  },
};

/**
 * Return the `hass` of a frontend with these door stations, an entity of another
 * integration on the same device, and a device of another integration.
 *
 * @param {Array<keyof typeof STATIONS>} names
 * @param {Record<string, string>} [texts] The texts `localize` knows.
 */
export function homeAssistant(names = ["front"], texts = {}) {
  /** @type {Record<string, any>} */
  const entities = {
    "sensor.other": { entity_id: "sensor.other", device_id: "device_other", platform: "other" },
  };
  /** @type {Record<string, any>} */
  const devices = {
    device_other: { id: "device_other", name: "Other", config_entries: ["entry_other"] },
  };
  /** @type {Record<string, any>} */
  const states = {};
  for (const name of names) {
    const station = STATIONS[name];
    devices[station.device] = {
      id: station.device,
      name: station.name,
      name_by_user: null,
      config_entries: [station.entry],
      primary_config_entry: station.entry,
    };
    entities[station.camera] = {
      entity_id: station.camera,
      device_id: station.device,
      platform: PLATFORM,
      translation_key: null,
    };
    for (const [key, entityId] of Object.entries(station.entities)) {
      entities[entityId] = {
        entity_id: entityId,
        device_id: station.device,
        platform: PLATFORM,
        translation_key: key,
      };
      states[entityId] = { state: "unknown", attributes: {} };
    }
    // An entity of another integration on the device of the door station
    entities[`sensor.${name}_bridge`] = {
      entity_id: `sensor.${name}_bridge`,
      device_id: station.device,
      platform: "hikvision_bridge",
      translation_key: "call",
    };
  }
  return {
    entities,
    devices,
    states,
    language: "en",
    localize: (/** @type {string} */ key) => texts[key] ?? "",
  };
}
