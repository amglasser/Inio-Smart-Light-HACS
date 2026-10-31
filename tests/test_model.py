"""Tests for the PWM -> brightness / kelvin estimation."""

from __future__ import annotations

import pytest

from custom_components.inio.model import MIN_TOTAL, estimate, expected_pwm


@pytest.mark.parametrize("brightness", [5, 10, 25, 50, 75, 100])
@pytest.mark.parametrize("kelvin", [3000, 3500, 4000, 4600, 5500, 6200, 6500])
def test_roundtrip(brightness: int, kelvin: int) -> None:
    warm, cold = expected_pwm(brightness, kelvin)
    est_brightness, est_kelvin = estimate(warm, cold)
    assert abs(est_brightness - brightness) <= 2
    assert est_kelvin is not None
    assert abs(est_kelvin - kelvin) <= 150


def test_dark_lamp_has_no_kelvin() -> None:
    brightness, kelvin = estimate(0.0, 0.0)
    assert brightness == 0
    assert kelvin is None
    assert MIN_TOTAL > 0


def test_extremes_clamped() -> None:
    brightness, kelvin = estimate(100.0, 100.0)
    assert brightness == 100
    assert kelvin is not None
    assert 2700 <= kelvin <= 6500


def test_pure_warm_and_pure_cold() -> None:
    _, warm_k = estimate(60.0, 0.0)
    _, cold_k = estimate(0.0, 60.0)
    assert warm_k is not None and cold_k is not None
    assert warm_k <= 3000
    assert cold_k >= 6400
