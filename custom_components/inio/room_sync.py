"""Room Sync: mirror one inio lamp's state onto the other inio lamps in its area."""

from __future__ import annotations

import asyncio
import logging
import time

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .coordinator import InioConfigEntry
from .syncstate import KIND_CONNECTED, KIND_OFF, SyncState, snapshot

_LOGGER = logging.getLogger(__name__)

# After Room Sync commands a lamp, its next state changes are the echo of our own
# command and must not be mirrored back.
SUPPRESS_SECONDS = 20.0


def _suppress_map(hass: HomeAssistant) -> dict[str, float]:
    return hass.data.setdefault(DOMAIN, {}).setdefault("suppress", {})


def suppress(hass: HomeAssistant, entry: InioConfigEntry) -> None:
    """Ignore this lamp's changes for a short while."""
    _suppress_map(hass)[entry.entry_id] = time.monotonic() + SUPPRESS_SECONDS


def is_suppressed(hass: HomeAssistant, entry: InioConfigEntry) -> bool:
    """Return True while this lamp is still settling after a Room Sync command."""
    return time.monotonic() < _suppress_map(hass).get(entry.entry_id, 0.0)


def area_of(hass: HomeAssistant, entry: InioConfigEntry) -> str | None:
    """Return the area id of the lamp (its light entity, else its device)."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    entity_id = ent_reg.async_get_entity_id("light", DOMAIN, f"{entry.entry_id}_light")
    if entity_id and (entity := ent_reg.async_get(entity_id)):
        if entity.area_id:
            return entity.area_id
        if entity.device_id and (device := dev_reg.async_get(entity.device_id)):
            return device.area_id

    device = dev_reg.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    return device.area_id if device else None


def siblings(hass: HomeAssistant, entry: InioConfigEntry) -> list[InioConfigEntry]:
    """Return the other loaded inio lamps that are in the same area."""
    area = area_of(hass, entry)
    if area is None:
        return []
    return [
        other
        for other in hass.config_entries.async_loaded_entries(DOMAIN)
        if other.entry_id != entry.entry_id
        and getattr(other, "runtime_data", None) is not None
        and area_of(hass, other) == area
    ]


def current_state(entry: InioConfigEntry) -> SyncState:
    """Return the lamp's current state as a SyncState."""
    data = entry.runtime_data.data
    return snapshot(data.mode, data.brightness, data.kelvin)


async def _apply(target: InioConfigEntry, state: SyncState) -> None:
    coordinator = target.runtime_data
    if state.kind == KIND_OFF:
        await coordinator.async_turn_off()
    elif state.kind == KIND_CONNECTED:
        await coordinator.async_set_connected(True)
    else:
        await coordinator.async_turn_on(max(1, state.brightness), state.kelvin)


async def async_sync_from(hass: HomeAssistant, source: InioConfigEntry) -> int:
    """Push the source lamp's state to the other lamps in its area.

    Returns the number of lamps that were updated. Raises HomeAssistantError when
    there is nothing to sync with.
    """
    targets = siblings(hass, source)
    if not targets:
        raise HomeAssistantError(
            "No other inio lamps in the same area. Assign the lamps to the same "
            "area in Home Assistant first."
        )

    state = current_state(source)
    for target in targets:
        suppress(hass, target)

    results = await asyncio.gather(
        *(_apply(target, state) for target in targets), return_exceptions=True
    )

    # Re-arm: the echo arrives after the command and the follow-up refresh.
    for target in targets:
        suppress(hass, target)

    failed = 0
    for target, result in zip(targets, results, strict=True):
        if isinstance(result, Exception):
            failed += 1
            _LOGGER.warning("Room Sync could not update %s: %s", target.title, result)
    if failed == len(targets):
        raise HomeAssistantError("Room Sync could not reach any of the other lamps.")
    return len(targets) - failed
