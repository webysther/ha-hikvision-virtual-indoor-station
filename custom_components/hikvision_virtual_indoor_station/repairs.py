"""The fix of a phone that left Home Assistant: remove it from the door station."""

from __future__ import annotations

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
import probatio


class PhoneGoneRepairFlow(RepairsFlow):
    """Remove a phone, whose app left Home Assistant, from its door station."""

    def __init__(self, entry_id: str, subentry_id: str) -> None:
        """Fix the issue of one phone of a door station."""
        self.entry_id = entry_id
        self.subentry_id = subentry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Ask to remove the phone."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Remove the phone once confirmed; it can be added again with its app."""
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if entry is not None and self.subentry_id in entry.subentries:
                self.hass.config_entries.async_remove_subentry(entry, self.subentry_id)
            return self.async_create_entry(data={})
        issue = ir.async_get(self.hass).async_get_issue(self.handler, self.issue_id)
        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders=issue.translation_placeholders if issue else None,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Return the fix of a phone that left Home Assistant (the only fixable issue)."""
    data = data or {}
    return PhoneGoneRepairFlow(str(data.get("entry_id")), str(data.get("subentry_id")))
