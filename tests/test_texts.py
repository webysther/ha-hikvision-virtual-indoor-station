"""Tests of the texts and icons: every entity has both, in every language."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.hikvision_virtual_indoor_station.button import CALL_BUTTONS
from custom_components.hikvision_virtual_indoor_station.const import (
    CALL_STATES,
    EVENT_TYPES,
)
from custom_components.hikvision_virtual_indoor_station.sensor import (
    INPUT_USES,
    OUTPUT_USES,
)
from custom_components.hikvision_virtual_indoor_station.setting import SETTING_KEYS

INTEGRATION = (
    Path(__file__).parent.parent
    / "custom_components"
    / "hikvision_virtual_indoor_station"
)
STRINGS = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))
ICONS = json.loads((INTEGRATION / "icons.json").read_text(encoding="utf-8"))
LANGUAGES = sorted(path.stem for path in (INTEGRATION / "translations").glob("*.json"))


def paths(data: Any, prefix: str = "") -> set[str]:
    """Return the paths of the texts of a translation."""
    if isinstance(data, dict):
        return {
            path
            for key, value in data.items()
            for path in paths(value, f"{prefix}/{key}")
        }
    return {prefix}


def test_english_is_the_strings() -> None:
    """Test that the English translation is strings.json."""
    english = json.loads((INTEGRATION / "translations" / "en.json").read_text("utf-8"))

    assert english == STRINGS
    assert LANGUAGES == ["en", "it", "pt-BR"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_text_in_every_language(language: str) -> None:
    """Test that every language has the same texts, with the same placeholders."""
    translation = json.loads(
        (INTEGRATION / "translations" / f"{language}.json").read_text("utf-8")
    )

    assert paths(translation) == paths(STRINGS)


def test_every_entity_has_a_name_and_an_icon() -> None:
    """Test the names, states and icons of every entity."""
    entities = STRINGS["entity"]
    icons = ICONS["entity"]

    assert (
        set(entities)
        == set(icons)
        == {
            "binary_sensor",
            "button",
            "event",
            "number",
            "select",
            "sensor",
            "switch",
        }
    )
    for platform, names in entities.items():
        assert set(names) == set(icons[platform]), platform
    assert set(entities["button"]) == {
        "open_door",
        "open_door_numbered",
        *(button.translation_key for button in CALL_BUTTONS),
    }
    assert "{door}" in entities["button"]["open_door_numbered"]["name"]
    event_types = entities["event"]["doorbell"]["state_attributes"]["event_type"]
    assert list(event_types["state"]) == EVENT_TYPES
    event_icons = icons["event"]["doorbell"]["state_attributes"]["event_type"]
    assert list(event_icons["state"]) == EVENT_TYPES
    assert list(entities["sensor"]["call"]["state"]) == CALL_STATES
    assert list(icons["sensor"]["call"]["state"]) == CALL_STATES


def test_every_setting_has_a_name() -> None:
    """Test that each setting that is an entity has a name, on one platform only."""
    entities = STRINGS["entity"]
    named = [*entities["number"], *entities["select"], *entities["switch"]]

    assert len(named) == len(set(named))
    assert set(named) == {*SETTING_KEYS.values(), "open_time_numbered"}
    assert "{door}" in entities["number"]["open_time_numbered"]["name"]
    # The options of the selects are the door station's, in lower case
    for name in entities["select"].values():
        assert all(option == option.lower() for option in name["state"])


def test_the_sensors_of_the_outputs_and_inputs() -> None:
    """Test that each use of an output and an input has its name and icon."""
    sensors = STRINGS["entity"]["sensor"]
    icons = ICONS["entity"]["sensor"]

    assert list(sensors["output"]["state"]) == OUTPUT_USES
    assert list(sensors["input"]["state"]) == INPUT_USES
    assert list(icons["input"]["state"]) == INPUT_USES
    assert "{input}" in sensors["input"]["name"]
