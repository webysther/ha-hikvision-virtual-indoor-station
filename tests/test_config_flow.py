"""The config flow: add a door station, refuse what is not one, sign in again."""

from __future__ import annotations

from unittest.mock import MagicMock

from aiohikvision import NotADoorStation
from aiohikvision.isapi.wire.faults import (
    BadCredentials,
    DeviceRejected,
    LockedOut,
    NotIsapi,
    Unreachable,
)
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryState,
    SubentryFlowResult,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hikvision_virtual_indoor_station.const import (
    CONF_DO_NOT_DISTURB,
    CONF_OPEN_DOOR,
    DOMAIN,
    MOBILE_APP,
    SUBENTRY_EXTENSION,
)

from .conftest import DOOR_IP, ENTRY_DATA, UNIQUE_ID

USER_INPUT = {CONF_HOST: f" {DOOR_IP} ", CONF_USERNAME: "admin", CONF_PASSWORD: "pw"}


async def test_adding_a_door_station(hass: HomeAssistant, door: MagicMock) -> None:
    """The address and account give an entry named as the door station names itself."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Door Station"
    assert result["data"] == {
        CONF_HOST: DOOR_IP,
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "pw",
        "port": 80,
    }
    assert result["result"].unique_id == UNIQUE_ID


@pytest.mark.parametrize(
    ("fault", "error"),
    [
        (BadCredentials("no"), "invalid_auth"),
        (LockedOut("locked"), "locked_out"),
        (NotADoorStation("a camera"), "not_door_station"),
        (NotIsapi("no ISAPI"), "not_isapi"),
        (Unreachable("timeout"), "cannot_connect"),
        (DeviceRejected("HTTP 500", 500), "unknown"),
    ],
)
async def test_errors_then_success(
    hass: HomeAssistant, door: MagicMock, fault: Exception, error: str
) -> None:
    """Each refusal shows its error, and the form can be sent again."""
    door.read_info.side_effect = fault
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    door.read_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_a_door_station_added_twice(
    hass: HomeAssistant, door: MagicMock, entry: MockConfigEntry
) -> None:
    """The same door station is refused; its new address is kept."""
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "192.0.2.11"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.0.2.11"


async def test_signing_in_again(
    hass: HomeAssistant, door: MagicMock, loaded: MockConfigEntry
) -> None:
    """A refused account is asked again; a wrong password shows its error first."""
    result = await loaded.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    door.read_info.side_effect = BadCredentials("no")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    door.read_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "new"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert loaded.data == {**ENTRY_DATA, CONF_PASSWORD: "new"}


async def test_signing_in_to_another_door(
    hass: HomeAssistant, door: MagicMock, loaded: MockConfigEntry
) -> None:
    """The account of another door station is refused."""
    other = MagicMock(wraps=door.read_info.return_value)
    other.identity.stable_id = "another"
    result = await loaded.start_reauth_flow(hass)
    door.read_info.return_value = other
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "pw"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"


async def test_reconfiguring(
    hass: HomeAssistant, door: MagicMock, loaded: MockConfigEntry
) -> None:
    """A new address of the same door station; an error shows first."""
    result = await loaded.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    door.read_info.side_effect = Unreachable("timeout")
    changes = {CONF_HOST: "192.0.2.11 ", CONF_USERNAME: "admin", CONF_PASSWORD: "pw"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], changes)
    assert result["errors"] == {"base": "cannot_connect"}
    door.read_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], changes)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert loaded.data[CONF_HOST] == "192.0.2.11"
    assert loaded.data[CONF_PASSWORD] == "pw"


async def test_reconfiguring_to_another_door(
    hass: HomeAssistant, door: MagicMock, loaded: MockConfigEntry
) -> None:
    """The address of another door station is refused."""
    other = MagicMock(wraps=door.read_info.return_value)
    other.identity.stable_id = "another"
    result = await loaded.start_reconfigure_flow(hass)
    door.read_info.return_value = other
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.0.2.12", CONF_USERNAME: "a", CONF_PASSWORD: "b"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert loaded.data[CONF_HOST] == DOOR_IP


def phone(hass: HomeAssistant, name: str = "Pixel") -> str:
    """Add a phone with the Home Assistant app, and return its device id."""
    app = MockConfigEntry(domain=MOBILE_APP)
    app.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=app.entry_id, identifiers={(MOBILE_APP, name)}, name=name
    )
    return device.id


async def add_phone(
    hass: HomeAssistant, entry: MockConfigEntry, device_id: str, **settings: bool
) -> SubentryFlowResult:
    """Add a phone to a door station as its extension."""
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_EXTENSION), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: device_id, **settings}
    )


async def test_adding_a_phone(
    hass: HomeAssistant, loaded: MockConfigEntry, door: MagicMock
) -> None:
    """A phone becomes an extension named after it, once, without a reload."""
    pixel = phone(hass)
    result = await add_phone(hass, loaded, pixel)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (extension,) = loaded.subentries.values()
    assert extension.title == "Pixel"
    assert extension.unique_id == pixel
    assert dict(extension.data) == {
        CONF_DEVICE_ID: pixel,
        CONF_DO_NOT_DISTURB: False,
        CONF_OPEN_DOOR: True,
    }
    # A call in progress goes on: the door station is not set up again
    await hass.async_block_till_done()
    assert loaded.state is ConfigEntryState.LOADED
    assert door.read_info.call_count == 1
    result = await add_phone(hass, loaded, pixel)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # A phone that left the device registry keeps its id as its name
    result = await add_phone(hass, loaded, "gone", do_not_disturb=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "gone"


async def test_changing_a_phone(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    """What a phone may do changes; the phone stays the same."""
    pixel = phone(hass)
    await add_phone(hass, loaded, pixel)
    (subentry_id,) = loaded.subentries
    result = await loaded.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DO_NOT_DISTURB: True, CONF_OPEN_DOOR: False}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert dict(loaded.subentries[subentry_id].data) == {
        CONF_DEVICE_ID: pixel,
        CONF_DO_NOT_DISTURB: True,
        CONF_OPEN_DOOR: False,
    }
