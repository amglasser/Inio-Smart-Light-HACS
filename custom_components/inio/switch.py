"""Switch platform for the inio lamp."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODE_CONNECTED
from .coordinator import InioConfigEntry, InioCoordinator
from .entity import InioEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the connected-mode switch."""
    async_add_entities([InioConnectedModeSwitch(entry.runtime_data, entry)])


class InioConnectedModeSwitch(InioEntity, SwitchEntity):
    """Switch for the lamp's 'connected' mode (the schedule from the inio app)."""

    _attr_translation_key = "connected_mode"

    def __init__(self, coordinator: InioCoordinator, entry: InioConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_connected_mode"

    @property
    def is_on(self) -> bool:
        """Return true while the lamp follows its app schedule."""
        return self.coordinator.data.mode == MODE_CONNECTED

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Hand control to the lamp's app schedule."""
        await self.coordinator.async_set_connected(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Leave connected mode; the lamp stays on in static mode."""
        await self.coordinator.async_set_connected(False)
