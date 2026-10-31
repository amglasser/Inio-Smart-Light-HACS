"""Pure logic for Room Sync: what a lamp is "doing" and when two states differ.

No Home Assistant imports, so it can be unit tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from .const import MODE_CONNECTED, MODE_OFF

KIND_OFF = "off"
KIND_CONNECTED = "connected"
KIND_STATIC = "static"

# Brightness and color temperature are estimated from the LED duty cycles, so
# two readings of the same setting differ slightly. Changes smaller than these
# tolerances are treated as noise and do not trigger a sync.
BRIGHTNESS_TOLERANCE = 3  # percentage points
KELVIN_TOLERANCE = 100  # kelvin
# Below this brightness the color temperature estimate is too noisy to compare.
KELVIN_MIN_BRIGHTNESS = 10


@dataclass(frozen=True)
class SyncState:
    """What a lamp is doing, reduced to what Room Sync mirrors."""

    kind: str  # "off" | "connected" | "static"
    brightness: int  # 0-100, only meaningful for "static"
    kelvin: int  # 2700-6500, only meaningful for "static"


def snapshot(mode: str, brightness: int, kelvin: int) -> SyncState:
    """Reduce a lamp reading to a SyncState."""
    if mode == MODE_OFF:
        return SyncState(KIND_OFF, 0, kelvin)
    if mode == MODE_CONNECTED:
        return SyncState(KIND_CONNECTED, brightness, kelvin)
    return SyncState(KIND_STATIC, brightness, kelvin)


def significantly_different(a: SyncState, b: SyncState) -> bool:
    """Return True when going from a to b is a real change, not estimate noise."""
    if a.kind != b.kind:
        return True
    if a.kind != KIND_STATIC:
        # off and connected carry no brightness/kelvin that we mirror.
        return False
    if abs(a.brightness - b.brightness) >= BRIGHTNESS_TOLERANCE:
        return True
    if min(a.brightness, b.brightness) >= KELVIN_MIN_BRIGHTNESS:
        return abs(a.kelvin - b.kelvin) >= KELVIN_TOLERANCE
    return False
