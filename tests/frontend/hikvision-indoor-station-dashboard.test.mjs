// Tests of the indoor station dashboard: node --test tests/frontend
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  CARD,
  TEXTS,
  findStations,
  generateDashboard,
  stationOf,
  textsIn,
  translated,
  viewPath,
  withTexts,
} from "../../custom_components/hikvision_virtual_indoor_station/frontend/hikvision-indoor-station-dashboard.js";
import { STATIONS, homeAssistant } from "./fixtures.mjs";

describe("findStations", () => {
  it("finds each door station with its entry, camera and entities, by name", () => {
    const stations = findStations(homeAssistant(["front", "back"]));
    assert.deepEqual(
      stations.map((station) => station.name),
      ["Back gate", "Front door"],
    );
    const front = stations[1];
    assert.equal(front.device_id, STATIONS.front.device);
    assert.equal(front.entry_id, STATIONS.front.entry);
    assert.equal(front.camera, STATIONS.front.camera);
    assert.equal(front.entities.call, STATIONS.front.entities.call);
    assert.equal(front.entities.answer, STATIONS.front.entities.answer);
    // The doors come from the door station itself, not from its buttons
    assert.equal(front.entities.open_door, undefined);
  });

  it("ignores the entities of other integrations, even on the same device", () => {
    const [front] = findStations(homeAssistant(["front"]));
    assert.equal(front.entities.call, STATIONS.front.entities.call);
    assert.equal(findStations(homeAssistant([])).length, 0);
  });

  it("prefers the name the user gave the device", () => {
    const hass = homeAssistant(["front"]);
    hass.devices[STATIONS.front.device].name_by_user = "Entrance";
    assert.equal(findStations(hass)[0].name, "Entrance");
  });
});

describe("stationOf", () => {
  const stations = findStations(homeAssistant(["front", "back"]));

  it("returns the door station of the device, or the first one", () => {
    assert.equal(stationOf(stations, { device_id: STATIONS.front.device })?.name, "Front door");
    assert.equal(stationOf(stations, {})?.name, "Back gate");
    assert.equal(stationOf(stations, { device_id: "gone" }), undefined);
  });
});

describe("texts", () => {
  it("are in the language of the user, its base language, or English", () => {
    assert.equal(textsIn("pt-BR").activity, "Atividade");
    assert.equal(textsIn("it-IT").activity, "Attività");
    assert.equal(textsIn("de").activity, "Activity");
    assert.equal(textsIn(undefined).activity, "Activity");
  });

  it("exist in every language", () => {
    for (const [language, texts] of Object.entries(TEXTS)) {
      assert.deepEqual(Object.keys(texts).sort(), Object.keys(TEXTS.en).sort(), language);
    }
  });

  it("of the entities come from the integration", async () => {
    const hass = homeAssistant(["front"], {
      "component.hikvision_virtual_indoor_station.entity.button.answer.name": "Atender",
    });
    assert.equal(translated(hass, "entity.button.answer.name"), "Atender");
    assert.equal(translated(hass, "entity.button.reject.name"), undefined);
    // Loaded for the integration when the frontend can
    const loaded = await withTexts({
      ...hass,
      loadBackendTranslation: async (category, integration) => (key) =>
        `${category}:${integration}:${key}`,
    });
    assert.equal(loaded.localize("k"), "entity:hikvision_virtual_indoor_station:k");
    assert.equal(await withTexts(hass), hass);
  });
});

describe("viewPath", () => {
  it("comes from the name, without accents, unique among the views", () => {
    const taken = new Set();
    assert.equal(viewPath("Portão da Frente", taken), "portao-da-frente");
    assert.equal(viewPath("Portão da frente!", taken), "portao-da-frente-2");
    assert.equal(viewPath("***", taken), "door-station");
  });
});

describe("generateDashboard", () => {
  it("has a view for each door station: the card and its activity", () => {
    const { views } = generateDashboard(homeAssistant(["front", "back"]));
    assert.deepEqual(
      views.map((view) => view.title),
      ["Back gate", "Front door"],
    );
    assert.deepEqual(
      views.map((view) => view.path),
      ["back-gate", "front-door"],
    );
    const [card, activity] = views[1].sections;
    assert.deepEqual(card.cards, [{ type: `custom:${CARD}`, device_id: STATIONS.front.device }]);
    assert.deepEqual(activity.cards[1].target.entity_id, [
      STATIONS.front.entities.doorbell,
      STATIONS.front.entities.call,
      STATIONS.front.entities.sip_registered,
    ]);
  });

  it("shows the visits of a door station: its charts and the weeks of its counters", () => {
    const { views } = generateDashboard(homeAssistant(["front", "back"]));
    const visits = views[1].sections[2];
    assert.equal(visits.cards[0].heading, "Visits");
    assert.deepEqual(
      visits.cards.slice(1, 3).map((card) => [card.type, card.entity, card.show_name]),
      [
        ["picture-entity", STATIONS.front.entities.visits_by_hour, false],
        ["picture-entity", STATIONS.front.entities.visits_by_day, false],
      ],
    );
    assert.deepEqual(visits.cards[3], {
      type: "statistics-graph",
      entities: [STATIONS.front.entities.visits, STATIONS.front.entities.missed_visits],
      period: "week",
      stat_types: ["change"],
      chart_type: "bar",
      days_to_show: 91,
      grid_options: { columns: 12 },
    });
    // A door station whose visits the frontend does not have yet: no section for them
    assert.equal(views[0].sections.length, 2);
  });

  it("shows the charts alone when the counters are not there", () => {
    const hass = homeAssistant(["front"]);
    for (const key of ["visits", "missed_visits"]) {
      delete hass.entities[STATIONS.front.entities[key]];
    }
    const visits = generateDashboard(hass).views[0].sections[2];
    assert.deepEqual(
      visits.cards.map((card) => card.type),
      ["heading", "picture-entity", "picture-entity"],
    );
  });

  it("says how to add a door station when there is none", () => {
    const { views } = generateDashboard({ ...homeAssistant([]), language: "pt-BR" });
    assert.match(views[0].cards[0].content, /Nenhum porteiro/);
  });
});
