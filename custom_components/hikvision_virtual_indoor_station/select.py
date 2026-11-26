"""Settings of the door station that are a choice: day/night, WDR, voice prompt..."""

from __future__ import annotations

from aiohikvision import Setting
from aiohikvision.isapi.model.features.image import option_key
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndoorStationConfigEntry
from .setting import SettingEntity, settings_of
from .station import IndoorStation

# The station writes one setting at a time; each write is read back
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndoorStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a select for each choice the door station offers."""
    station = entry.runtime_data
    async_add_entities(
        SettingSelect(station, setting) for setting in settings_of(station, "select")
    )


class SettingSelect(SettingEntity, SelectEntity):
    """A choice of the door station, among those it offers.

    Its options are the door station's, in lower case (they are the keys of their
    translations: ``doorIsOpen`` is ``doorisopen``).
    """

    def __init__(self, station: IndoorStation, setting: Setting) -> None:
        """Create the select of one setting."""
        super().__init__(station, setting)
        # Each option and the value the door station takes for it
        self._values = {
            option_key(value): value for value in setting.capability.options
        }
        self._attr_options = list(self._values)

    @property
    def current_option(self) -> str | None:
        """The choice now; None when the door station names one it does not offer."""
        current = self.current
        option = option_key(current.value) if current is not None else None
        return option if option in self._values else None

    async def async_select_option(self, option: str) -> None:
        """Change the choice."""
        await self.async_change(self._values[option])
