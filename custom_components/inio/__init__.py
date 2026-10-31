"""The inio daylight lamp integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InioClient
from .coordinator import InioConfigEntry, InioCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: InioConfigEntry) -> bool:
    """Set up an inio lamp from a config entry."""
    client = InioClient(entry.data[CONF_HOST], async_get_clientsession(hass))
    coordinator = InioCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: InioConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: InioConfigEntry) -> None:
    """Reload the entry when options (e.g. the polling interval) change."""
    await hass.config_entries.async_reload(entry.entry_id)
