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
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hikvision_virtual_indoor_station.const import DOMAIN

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
