"""The settings of the door station as entities, its inputs, and how loaded it is."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock

from aiohikvision import (
    DoorStationHealth,
    ImageCapability,
    ImageValue,
    Input,
    InputUse,
    Setting,
)
from aiohikvision.isapi.wire.faults import BadCredentials, DeviceRejected, Unreachable
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.select import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hikvision_virtual_indoor_station.const import (
    DOMAIN,
    SETTINGS_INTERVAL,
)

from .conftest import INFO


def _setting(key: str, channel: str = "1", **capability: object) -> Setting:
    return Setting(key, channel, ImageCapability(key, **capability))  # type: ignore[arg-type]


# As a DS-KD8003 (V3.7.3) offers them, with one setting that is no entity
SETTINGS = (
    _setting("day_night", options=("day", "night", "auto", "schedule")),
    _setting("brightness", minimum=0, maximum=100),
    _setting("power_line_frequency", options=("50hz", "60hz")),
    _setting("output_volume", minimum=0, maximum=10),
    _setting("open_time", "1", minimum=1, maximum=255),
    _setting("open_time", "2", minimum=1, maximum=255),
    _setting("door_voice_prompt"),
    _setting("door_voice_prompt_type", options=("long", "short", "doorIsOpen")),
    _setting("white_balance", options=("auto", "manual")),
)
VALUES = {
    ("day_night", "1"): ImageValue("IrcutFilterType", "auto"),
    ("brightness", "1"): ImageValue("brightnessLevel", "50"),
    ("power_line_frequency", "1"): ImageValue("powerLineFrequencyMode", "60hz"),
    ("output_volume", "1"): ImageValue("AudioOutVolumelist/AudioOutVlome/volume", "7"),
    ("open_time", "1"): ImageValue("openDuration", "1"),
    ("open_time", "2"): ImageValue("openDuration", "7"),
    ("door_voice_prompt", "1"): ImageValue("openDoorVoicePromptEnabled", "true"),
    ("door_voice_prompt_type", "1"): ImageValue(
        "openDoorVoicePromptType", "doorIsOpen"
    ),
    ("white_balance", "1"): ImageValue("WhiteBalanceStyle", "auto"),
}
BRIGHTNESS = "number.door_station_brightness"
SPEAKER = "number.door_station_speaker_volume"
DOOR_1_OPEN = "number.door_station_door_1_open_time"
DAY_NIGHT = "select.door_station_day_night_mode"
PROMPT_TYPE = "select.door_station_door_voice_prompt"
PROMPT = "switch.door_station_voice_prompt_when_a_door_opens"


@pytest.fixture
def settings(door: MagicMock) -> MagicMock:
    """Mock a door station with settings."""
    door.read_settings.return_value = SETTINGS
    door.read_setting_values.return_value = dict(VALUES)
    return door


async def _set_up(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_the_settings_are_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    settings: MagicMock,
) -> None:
    """Each setting it offers is a configuration entity, within its range or choices."""
    await _set_up(hass, entry)
    brightness = hass.states.get(BRIGHTNESS)
    assert brightness.state == "50.0"
    assert (brightness.attributes["min"], brightness.attributes["max"]) == (0, 100)
    assert hass.states.get(SPEAKER).state == "7.0"
    door_1 = hass.states.get(DOOR_1_OPEN)
    assert door_1.state == "1.0"
    assert door_1.attributes["unit_of_measurement"] == "s"
    assert hass.states.get("number.door_station_door_2_open_time").state == "7.0"
    day_night = hass.states.get(DAY_NIGHT)
    assert day_night.state == "auto"
    assert day_night.attributes["options"] == ["day", "night", "auto", "schedule"]
    # The door station's options in lower case: they are the keys of their names
    assert hass.states.get(PROMPT_TYPE).state == "doorisopen"
    assert hass.states.get(PROMPT).state == STATE_ON
    # A setting this integration does not name is no entity
    assert not hass.states.async_entity_ids("select.door_station_white_balance")
    # The settings of the camera that are rarely changed start disabled
    frequency = entity_registry.async_get("select.door_station_power_line_frequency")
    assert frequency.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entity_registry.async_get(BRIGHTNESS).entity_category == "config"


async def test_changing_the_settings(
    hass: HomeAssistant, entry: MockConfigEntry, settings: MagicMock
) -> None:
    """A change goes to the door station, in its own words, and shows at once."""
    await _set_up(hass, entry)
    by_ref = {setting.ref: setting for setting in SETTINGS}

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: BRIGHTNESS, ATTR_VALUE: 70},
        blocking=True,
    )
    settings.write_setting.assert_awaited_with(
        by_ref[("brightness", "1")], "brightnessLevel", "70"
    )
    assert hass.states.get(BRIGHTNESS).state == "70.0"

    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: PROMPT_TYPE, ATTR_OPTION: "short"},
        blocking=True,
    )
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: PROMPT_TYPE, ATTR_OPTION: "doorisopen"},
        blocking=True,
    )
    # The door station takes its own spelling back
    settings.write_setting.assert_awaited_with(
        by_ref[("door_voice_prompt_type", "1")], "openDoorVoicePromptType", "doorIsOpen"
    )

    await hass.services.async_call(
        "switch", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: PROMPT}, blocking=True
    )
    assert hass.states.get(PROMPT).state == STATE_OFF
    await hass.services.async_call(
        "switch", SERVICE_TURN_ON, {ATTR_ENTITY_ID: PROMPT}, blocking=True
    )
    settings.write_setting.assert_awaited_with(
        by_ref[("door_voice_prompt", "1")], "openDoorVoicePromptEnabled", "true"
    )
    assert hass.states.get(PROMPT).state == STATE_ON


async def test_a_change_the_door_station_refuses(
    hass: HomeAssistant, entry: MockConfigEntry, settings: MagicMock
) -> None:
    """The error says why, and the value stays what the door station has."""
    await _set_up(hass, entry)
    settings.write_setting.side_effect = DeviceRejected("badParameters", 400)
    with pytest.raises(HomeAssistantError) as raised:
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: SPEAKER, ATTR_VALUE: 9},
            blocking=True,
        )
    assert raised.value.translation_key == "setting_failed"
    assert hass.states.get(SPEAKER).state == "7.0"


async def test_a_setting_without_a_value_yet(
    hass: HomeAssistant, entry: MockConfigEntry, settings: MagicMock
) -> None:
    """A setting whose value was not read is written under its first element."""
    del settings.read_setting_values.return_value[("brightness", "1")]
    await _set_up(hass, entry)
    assert hass.states.get(BRIGHTNESS).state == STATE_UNAVAILABLE
    station = entry.runtime_data
    setting = next(s for s in SETTINGS if s.key == "brightness")
    await station.async_set_setting(setting, "60")
    settings.write_setting.assert_awaited_with(setting, "brightnessLevel", "60")
    assert hass.states.get(BRIGHTNESS).state == "60.0"


async def test_values_the_entities_do_not_take(
    hass: HomeAssistant, entry: MockConfigEntry, settings: MagicMock
) -> None:
    """A level that is no number, a choice it does not offer: their state is unknown."""
    settings.read_setting_values.return_value |= {
        ("brightness", "1"): ImageValue("brightnessLevel", "high"),
        ("day_night", "1"): ImageValue("IrcutFilterType", "eventTrigger"),
    }
    await _set_up(hass, entry)
    assert hass.states.get(BRIGHTNESS).state == STATE_UNKNOWN
    assert hass.states.get(DAY_NIGHT).state == STATE_UNKNOWN


async def test_the_settings_follow_the_door_station(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entry: MockConfigEntry,
    settings: MagicMock,
) -> None:
    """Changed on its web page, read again; unavailable while they cannot be read."""
    await _set_up(hass, entry)
    settings.read_setting_values.return_value = {
        **VALUES,
        ("day_night", "1"): ImageValue("IrcutFilterType", "night"),
    }
    settings.read_inputs.return_value = (
        replace(INFO.inputs[1], use=InputUse.DOOR_CONTACT),
    )
    freezer.tick(SETTINGS_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(DAY_NIGHT).state == "night"
    assert hass.states.get("sensor.door_station_input_2").state == "door_contact"
    # The same inputs again change nothing
    freezer.tick(SETTINGS_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.door_station_input_2").state == "door_contact"

    settings.read_setting_values.side_effect = Unreachable("timeout")
    freezer.tick(SETTINGS_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(DAY_NIGHT).state == STATE_UNAVAILABLE

    settings.read_setting_values.side_effect = BadCredentials("refused")
    freezer.tick(SETTINGS_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_a_single_door(
    hass: HomeAssistant, entry: MockConfigEntry, settings: MagicMock
) -> None:
    """With one door, its open time is not numbered."""
    one_door = replace(INFO, doors=(1,), outputs=INFO.outputs[:1])
    settings.read_info.return_value = one_door
    settings.read_settings.return_value = SETTINGS[:5]
    await _set_up(hass, entry)
    assert hass.states.get("number.door_station_door_open_time").state == "1.0"


async def test_the_inputs_and_the_load(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    loaded: MockConfigEntry,
    door: MagicMock,
) -> None:
    """The inputs that can change have a sensor; the CPU and the video sessions too."""
    assert hass.states.get("sensor.door_station_input_2").state == "disabled"
    assert hass.states.get("sensor.door_station_input_4").state == "disabled"
    # Inputs 1 and 3 read what they always read
    assert not hass.states.async_entity_ids("sensor.door_station_input_1")
    assert hass.states.get("sensor.door_station_cpu_usage").state == "88"
    assert hass.states.get("sensor.door_station_video_sessions").state == "5"

    door.read_health.return_value = DoorStationHealth(40, 1)
    door.read_inputs.return_value = ()
    freezer.tick(SETTINGS_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.door_station_cpu_usage").state == "40"
    assert hass.states.get("sensor.door_station_video_sessions").state == "1"
    # An input it no longer lists has no state
    assert hass.states.get("sensor.door_station_input_2").state == STATE_UNKNOWN


async def test_a_door_station_that_does_not_say_its_load(
    hass: HomeAssistant, entry: MockConfigEntry, door: MagicMock
) -> None:
    """Without its CPU or its sessions, no sensor for them; unlisted inputs all show."""
    door.read_health.return_value = DoorStationHealth()
    door.read_info.return_value = replace(
        INFO, inputs=(Input(1, "AI1", InputUse.DOOR_CONTACT),)
    )
    await _set_up(hass, entry)
    assert not hass.states.async_entity_ids("sensor.door_station_cpu_usage")
    assert not hass.states.async_entity_ids("sensor.door_station_video_sessions")
    assert hass.states.get("sensor.door_station_input_1").state == "door_contact"
