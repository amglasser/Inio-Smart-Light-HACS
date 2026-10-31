"""Button platform for the inio lamp."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import InioConfigEntry, InioCoordinator
from .entity import InioEntity
from .room_sync import async_sync_from


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Room Sync button."""
    async_add_entities([InioSyncRoomButton(entry.runtime_data, entry)])


class InioSyncRoomButton(InioEntity, ButtonEntity):
    """Push this lamp's on/off, brightness and color temperature to its room."""

    _attr_translation_key = "sync_room"
    _attr_icon = "mdi:lightbulb-group"

    def __init__(self, coordinator: InioCoordinator, entry: InioConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_sync_room"

    async def async_press(self) -> None:
        """Copy this lamp's state to the other inio lamps in the same area."""
        await async_sync_from(self.hass, self._entry)
