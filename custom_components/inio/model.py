"""Estimate brightness and color temperature from the lamp's PWM duty values.

The inio one's local API exposes the raw warm/cold LED PWM duty cycles
(``/api/app/pwm_duty_get``) but not the brightness / color temperature the lamp
was set to. Both are recovered from two calibration curves:

* ``TOTAL``: warm + cold PWM sum for brightness 0..100 -> brightness
* ``RATIO``: cold / (warm + cold) per 10 K step      -> color temperature

``expected_pwm`` runs the same curves forward and is used by the tests.
"""

from __future__ import annotations

from bisect import bisect_left
from itertools import accumulate

from .const import MAX_BRIGHTNESS_PCT, MAX_KELVIN, MIN_KELVIN
from .model_data import KELVIN_START, KELVIN_STEP, RATIO, TOTAL

# The measured ratio curve has small non-monotonic wiggles; the running maximum
# is a safe monotone envelope for the inverse lookup.
_RATIO_MONO: tuple[float, ...] = tuple(accumulate(RATIO, max))

# Below this PWM sum the lamp is effectively dark, so the ratio (and therefore
# the color temperature) is meaningless.
MIN_TOTAL = 0.5


def _inverse_index(xs: tuple[float, ...], x: float) -> float:
    """Return the fractional index at which the non-decreasing ``xs`` reaches ``x``."""
    if x <= xs[0]:
        return 0.0
    if x >= xs[-1]:
        return float(len(xs) - 1)
    i = bisect_left(xs, x)  # xs[i - 1] < x <= xs[i]
    lo, hi = xs[i - 1], xs[i]
    return (i - 1) + (x - lo) / (hi - lo)


def estimate(warm: float, cold: float) -> tuple[int, int | None]:
    """Return ``(brightness_pct, kelvin)`` for the given warm/cold PWM values.

    ``kelvin`` is ``None`` when the lamp is (nearly) dark.
    """
    total = max(warm, 0.0) + max(cold, 0.0)
    brightness = round(_inverse_index(TOTAL, total))
    brightness = max(0, min(MAX_BRIGHTNESS_PCT, brightness))
    if total < MIN_TOTAL:
        return brightness, None

    ratio = max(cold, 0.0) / total
    index = _inverse_index(_RATIO_MONO, ratio)
    kelvin = KELVIN_START + index * KELVIN_STEP
    kelvin = int(round(kelvin / 10.0) * 10)
    return brightness, max(MIN_KELVIN, min(MAX_KELVIN, kelvin))


def _interp(values: tuple[float, ...], index: float) -> float:
    index = max(0.0, min(float(len(values) - 1), index))
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    frac = index - lower
    return values[lower] * (1 - frac) + values[upper] * frac


def expected_pwm(brightness: float, kelvin: float) -> tuple[float, float]:
    """Return the expected ``(warm, cold)`` PWM values for a setting."""
    total = _interp(TOTAL, brightness)
    ratio = _interp(RATIO, (kelvin - KELVIN_START) / KELVIN_STEP)
    return total * (1 - ratio), total * ratio
