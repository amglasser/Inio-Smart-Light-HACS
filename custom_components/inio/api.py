"""Local HTTP client for the inio one daylight lamp.

The lamp serves an undocumented JSON API on port 80 of its LAN address. The
endpoints used here were discovered by the community homebridge-inio plugin
(Apache-2.0, https://github.com/reckter/homebridge-inio).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
from typing import Any

import aiohttp

from .const import (
    MAX_BRIGHTNESS_PCT,
    MAX_KELVIN,
    MIN_KELVIN,
    MODE_CONNECTED,
    MODE_OFF,
    MODE_STATIC,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 6  # seconds
SETTLE_POLL_DELAY = 0.1  # seconds between PWM reads while the lamp is fading
SETTLE_MAX_READS = 12
BUTTON_SETTLE_DELAY = 0.4  # seconds to let the lamp process a "button press"


class InioError(Exception):
    """Base error for the inio client."""


class InioConnectionError(InioError):
    """The lamp could not be reached or returned an unusable answer."""


@dataclass(frozen=True)
class InioStatus:
    """Operating mode of the lamp."""

    mode: str
    addon: str


@dataclass(frozen=True)
class InioPwm:
    """Raw LED duty cycles (0..100) of the warm and cold LED channels."""

    warm: float
    cold: float


class InioClient:
    """Thin async client for one lamp."""

    def __init__(
        self, host: str, session: aiohttp.ClientSession, port: int = 80
    ) -> None:
        self._base_url = f"http://{host}:{port}" if port != 80 else f"http://{host}"
        self._session = session
        # The lamp's embedded web server is happiest with one request at a time.
        self._lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        """Return the lamp's base URL."""
        return self._base_url

    async def _request(
        self, method: str, path: str, *, json_body: dict[str, Any] | None = None
    ) -> Any:
        url = f"{self._base_url}{path}"
        async with self._lock:
            try:
                async with asyncio.timeout(REQUEST_TIMEOUT):
                    async with self._session.request(
                        method, url, json=json_body
                    ) as response:
                        response.raise_for_status()
                        text = await response.text()
            except (aiohttp.ClientError, TimeoutError) as err:
                raise InioConnectionError(
                    f"{method} {path} failed: {err!r}"
                ) from err
        text = text.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return text

    async def get_status(self) -> InioStatus:
        """Read the lamp's mode and active add-on."""
        data = await self._request("GET", "/api/app/status")
        if not isinstance(data, dict) or "mode" not in data:
            raise InioConnectionError(f"Unexpected status payload: {data!r}")
        return InioStatus(mode=str(data["mode"]), addon=str(data.get("addon", "NONE")))

    async def get_pwm(self, settle: bool = True) -> InioPwm:
        """Read the LED duty cycles, optionally waiting until they stop changing."""
        previous = await self._read_pwm()
        if not settle:
            return previous
        for _ in range(SETTLE_MAX_READS):
            await asyncio.sleep(SETTLE_POLL_DELAY)
            current = await self._read_pwm()
            if current == previous:
                return current
            previous = current
        _LOGGER.debug("Lamp PWM did not settle, using last reading %s", previous)
        return previous

    async def _read_pwm(self) -> InioPwm:
        data = await self._request("GET", "/api/app/pwm_duty_get")
        try:
            return InioPwm(warm=float(data["warm"]), cold=float(data["cold"]))
        except (TypeError, KeyError, ValueError) as err:
            raise InioConnectionError(f"Unexpected PWM payload: {data!r}") from err

    async def press_manual(self) -> None:
        """Emulate a short press on the manual (power) button."""
        await self._request("PUT", "/api/interface/btn_short_manual")

    async def press_connect(self) -> None:
        """Emulate a short press on the 'connected' (app schedule) button."""
        await self._request("PUT", "/api/interface/btn_short_connect")

    async def set_light(self, brightness: int, kelvin: int) -> None:
        """Set brightness (0-100 %) and color temperature (2700-6500 K).

        The lamp must already be in STATIC mode for this to be visible.
        """
        payload = {
            "brightness": max(0, min(MAX_BRIGHTNESS_PCT, int(round(brightness)))),
            "kelvin": max(MIN_KELVIN, min(MAX_KELVIN, int(round(kelvin)))),
        }
        await self._request("POST", "/api/app/light_color", json_body=payload)

    async def set_mode(self, target: str) -> InioStatus:
        """Move the lamp to OFF, STATIC or CONNECTED and return the resulting status.

        The two buttons behave like the physical ones: ``manual`` toggles between
        OFF and STATIC (and switches CONNECTED off), ``connect`` toggles between
        STATIC and CONNECTED.
        """
        status = await self.get_status()
        if status.mode == target:
            return status

        pressed = False
        if target == MODE_OFF:
            await self.press_manual()
            pressed = True
        elif target == MODE_CONNECTED:
            if status.mode == MODE_OFF:
                await self.press_manual()
                await asyncio.sleep(BUTTON_SETTLE_DELAY)
            await self.press_connect()
            pressed = True
        elif target == MODE_STATIC:
            if status.mode == MODE_OFF:
                await self.press_manual()
                pressed = True
            elif status.mode == MODE_CONNECTED:
                await self.press_connect()
                pressed = True
        else:
            raise InioError(f"Unknown target mode: {target}")

        if pressed:
            await asyncio.sleep(BUTTON_SETTLE_DELAY)
        return await self.get_status()
