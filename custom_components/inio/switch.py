"""Switch platform for the inio lamp."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import MODE_CONNECTED
from .coordinator import InioConfigEntry, InioCoordinator
from .entity import InioEntity
from .room_sync import async_sync_from, current_state, is_suppressed
from .syncstate import SyncState, significantly_different

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            InioConnectedModeSwitch(coordinator, entry),
            InioRoomSyncSwitch(coordinator, entry),
        ]
    )


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


class InioRoomSyncSwitch(InioEntity, SwitchEntity, RestoreEntity):
    """While on, changes to this lamp are mirrored to the other lamps in its area."""

    _attr_translation_key = "room_sync"
    _attr_icon = "mdi:sync"

    def __init__(self, coordinator: InioCoordinator, entry: InioConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_room_sync"
        self._attr_is_on = False
        self._baseline: SyncState | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the switch; a restored 'on' just starts watching, it doesn't sync."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) and last.state == "on":
            self._attr_is_on = True
            self._baseline = current_state(self._entry)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start syncing, beginning with a push of this lamp's state to the room."""
        await async_sync_from(self.hass, self._entry)  # raises if no other lamps
        self._baseline = current_state(self._entry)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop syncing."""
        self._attr_is_on = False
        self._baseline = None
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Detect a real change on this lamp and propagate it."""
        if self._attr_is_on:
            self._check_for_change()
        super()._handle_coordinator_update()

    @callback
    def _check_for_change(self) -> None:
        state = current_state(self._entry)
        previous = self._baseline

        if previous is None or is_suppressed(self.hass, self._entry):
            # First reading, or the echo of a Room Sync command: just re-baseline.
            self._baseline = state
            return
        if not significantly_different(previous, state):
            return  # estimate noise; keep the old baseline so drift can't accumulate

        self._baseline = state
        self.hass.async_create_task(self._propagate())

    async def _propagate(self) -> None:
        try:
            await async_sync_from(self.hass, self._entry)
        except HomeAssistantError as err:
            _LOGGER.debug("Room Sync from %s skipped: %s", self._entry.title, err)
