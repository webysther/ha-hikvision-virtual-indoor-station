"""The settings of the door station as entities (number, select and switch).

The door station says which settings it offers and their choices or ranges (aiohikvision
reads its capabilities once, at setup); SettingsCoordinator follows their values. An
entity exists for each offered setting this integration names (SETTING_KEYS): the image
of its camera, its volumes, how long each door stays open, and what it says when a door
opens. They are configuration: they change the door station itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from aiohikvision import ImageValue, Setting
from homeassistant.const import EntityCategory

from .entity import IndoorStationEntity

if TYPE_CHECKING:
    from .station import IndoorStation

# The settings that are entities: aiohikvision's key of each one, and the key of its
# entity (its unique ID is <serial>_<key>, with the door's number for a door's setting).
SETTING_KEYS: Final = {
    # The image of its camera
    "day_night": "day_night",
    "day_night_sensitivity": "day_night_sensitivity",
    "brightness": "brightness",
    "contrast": "contrast",
    "saturation": "saturation",
    "sharpness": "sharpness",
    "wdr": "wdr",
    "wdr_level": "wdr_level",
    "blc": "blc",
    "blc_area": "blc_area",
    "power_line_frequency": "power_line_frequency",
    # Its volumes: the microphone, the speaker, and the speaker during a call
    "input_volume": "microphone_volume",
    "output_volume": "speaker_volume",
    "talk_volume": "talk_volume",
    # How long each door stays open
    "open_time": "open_time",
    # What it says when a door opens
    "door_voice_prompt": "door_voice_prompt",
    "door_voice_prompt_type": "door_voice_prompt_type",
}
# The source of the settings that belong to a door: their channel is the door's number.
DOOR_SOURCE: Final = "door"


def settings_of(station: IndoorStation, platform: str) -> list[Setting]:
    """Return the settings of a platform that the door station offers, as entities."""
    assert station.settings is not None  # created before the platforms
    return [
        setting
        for setting in station.settings.settings
        if setting.key in SETTING_KEYS and setting.spec.platform == platform
    ]


class SettingEntity(IndoorStationEntity):
    """A setting of the door station.

    Unavailable while the door station does not answer, or while its value is unknown.
    """

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, station: IndoorStation, setting: Setting) -> None:
        """Name the entity by its setting, and a door's setting by its door."""
        key = SETTING_KEYS[setting.key]
        is_door = setting.spec.source == DOOR_SOURCE
        super().__init__(station, f"{key}_{setting.channel}" if is_door else key)
        self.setting = setting
        if is_door and len(station.info.doors) > 1:
            self._attr_translation_key = f"{key}_numbered"
            self._attr_translation_placeholders = {"door": setting.channel}
        else:
            self._attr_translation_key = key
        self._attr_entity_registry_enabled_default = setting.spec.enabled_default

    @property
    def current(self) -> ImageValue | None:
        """The value of the setting, as last read or written."""
        assert self.station.settings is not None
        return self.station.settings.data.values.get(self.setting.ref)

    @property
    def available(self) -> bool:
        """Available while the door station answers and the value is known."""
        settings = self.station.settings
        return (
            super().available
            and settings is not None
            and settings.last_update_success
            and self.current is not None
        )

    async def async_added_to_hass(self) -> None:
        """Follow the values of the settings too."""
        await super().async_added_to_hass()
        assert self.station.settings is not None
        self.async_on_remove(
            self.station.settings.async_add_listener(self.async_write_ha_state)
        )

    async def async_change(self, value: str) -> None:
        """Change the setting on the door station."""
        await self.station.async_set_setting(self.setting, value)
