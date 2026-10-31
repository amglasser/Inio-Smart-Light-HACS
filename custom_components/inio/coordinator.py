"""Data update coordinator for the inio integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import InioClient, InioError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_BRIGHTNESS_PCT,
    MAX_KELVIN,
    MIN_KELVIN,
    MODE_CONNECTED,
    MODE_OFF,
    MODE_STATIC,
)
from .model import estimate

_LOGGER = logging.getLogger(__name__)

# Time to let the lamp apply a change before reading its state back.
COMMAND_SETTLE_DELAY = 0.5
DEFAULT_KELVIN = 4000

type InioConfigEntry = ConfigEntry[InioCoordinator]


@dataclass(frozen=True)
class InioData:
    """Snapshot of the lamp state."""

    mode: str
    addon: str
    warm: float
    cold: float
    brightness: int  # 0-100 (estimated from PWM)
    kelvin: int  # 2700-6500 (estimated from PWM, last known value when dark)


class InioCoordinator(DataUpdateCoordinator[InioData]):
    """Polls the lamp and serialises commands to it."""

    config_entry: InioConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: InioConfigEntry, client: InioClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.title}",
            config_entry=entry,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self._last_kelvin = DEFAULT_KELVIN

    async def _async_update_data(self) -> InioData:
        try:
            status = await self.client.get_status()
            pwm = await self.client.get_pwm()
        except InioError as err:
            raise UpdateFailed(f"Error talking to the lamp: {err}") from err

        brightness, kelvin = estimate(pwm.warm, pwm.cold)
        if kelvin is None:
            kelvin = self._last_kelvin
        else:
            self._last_kelvin = kelvin
        return InioData(
            mode=status.mode,
            addon=status.addon,
            warm=pwm.warm,
            cold=pwm.cold,
            brightness=brightness,
            kelvin=kelvin,
        )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def _refresh_after_command(self) -> None:
        await asyncio.sleep(COMMAND_SETTLE_DELAY)
        await self.async_refresh()

    async def async_turn_on(
        self, brightness_pct: int | None = None, kelvin: int | None = None
    ) -> None:
        """Turn the lamp on, optionally setting brightness and/or color temperature."""
        try:
            if brightness_pct is None and kelvin is None:
                # Plain "turn on": leave a lamp that is already on (including
                # connected mode) alone, otherwise power it up manually.
                status = await self.client.get_status()
                if status.mode == MODE_OFF:
                    await self.client.set_mode(MODE_STATIC)
            else:
                await self.client.set_mode(MODE_STATIC)
                if brightness_pct is None or kelvin is None:
                    # Fill the missing value from what the lamp is doing right now.
                    await asyncio.sleep(COMMAND_SETTLE_DELAY)
                    pwm = await self.client.get_pwm()
                    current_brightness, current_kelvin = estimate(pwm.warm, pwm.cold)
                    if brightness_pct is None:
                        brightness_pct = current_brightness or MAX_BRIGHTNESS_PCT
                    if kelvin is None:
                        kelvin = current_kelvin or self._last_kelvin
                await self.client.set_light(
                    brightness_pct, max(MIN_KELVIN, min(MAX_KELVIN, kelvin))
                )
        except InioError as err:
            _LOGGER.error("Could not turn the lamp on: %s", err)
            raise
        await self._refresh_after_command()

    async def async_turn_off(self) -> None:
        """Turn the lamp off."""
        try:
            status = await self.client.set_mode(MODE_OFF)
        except InioError as err:
            _LOGGER.error("Could not turn the lamp off: %s", err)
            raise
        if status.mode != MODE_OFF:
            _LOGGER.warning("Lamp is still in mode %s after turning it off", status.mode)
        await self._refresh_after_command()

    async def async_set_connected(self, connected: bool) -> None:
        """Enter or leave connected (app schedule) mode.

        Leaving connected mode keeps the lamp on in static mode.
        """
        try:
            await self.client.set_mode(MODE_CONNECTED if connected else MODE_STATIC)
        except InioError as err:
            _LOGGER.error("Could not change connected mode: %s", err)
            raise
        await self._refresh_after_command()
