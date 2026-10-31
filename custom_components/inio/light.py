"""Light platform for the inio lamp."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MAX_BRIGHTNESS_PCT, MAX_KELVIN, MIN_KELVIN, MODE_OFF
from .coordinator import InioConfigEntry, InioCoordinator
from .entity import InioEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the lamp's light entity."""
    async_add_entities([InioLight(entry.runtime_data, entry)])


class InioLight(InioEntity, LightEntity):
    """The lamp as a tunable-white light."""

    _attr_name = None  # use the device name
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN

    def __init__(self, coordinator: InioCoordinator, entry: InioConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_light"

    @property
    def is_on(self) -> bool:
        """Return true if the lamp is on (static or connected mode)."""
        return self.coordinator.data.mode != MODE_OFF

    @property
    def brightness(self) -> int | None:
        """Return the brightness (1-255), estimated from the LED duty cycles."""
        if not self.is_on:
            return None
        return round(self.coordinator.data.brightness * 255 / MAX_BRIGHTNESS_PCT)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin, estimated from the duty cycles."""
        if not self.is_on:
            return None
        return self.coordinator.data.kelvin

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the lamp's mode and active add-on."""
        data = self.coordinator.data
        return {"inio_mode": data.mode.lower(), "inio_addon": data.addon.lower()}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the lamp on, optionally with brightness and color temperature."""
        brightness_pct: int | None = None
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            brightness_pct = max(
                1, round(brightness * MAX_BRIGHTNESS_PCT / 255)
            )
        await self.coordinator.async_turn_on(
            brightness_pct, kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the lamp off."""
        await self.coordinator.async_turn_off()
