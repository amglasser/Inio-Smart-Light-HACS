"""Smoke test: every Home Assistant facing module imports cleanly.

Skipped automatically when Home Assistant is not installed (the other tests do not
need it). CI installs Home Assistant, so a broken import or a renamed HA API shows
up there.
"""

from __future__ import annotations

import importlib

import pytest

pytest.importorskip("homeassistant")

MODULES = [
    "coordinator",
    "entity",
    "light",
    "switch",
    "button",
    "room_sync",
    "syncstate",
    "sensor",
    "config_flow",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name: str) -> None:
    importlib.import_module(f"custom_components.inio.{name}")


def test_sensor_descriptions_are_consistent() -> None:
    from custom_components.inio.coordinator import InioData
    from custom_components.inio.sensor import ADDON_OPTIONS, MODE_OPTIONS, SENSORS

    data = InioData(
        mode="STATIC", addon="BOOST", warm=10.0, cold=20.0, brightness=30, kelvin=4000
    )
    values = {s.key: s.value_fn(data) for s in SENSORS}
    assert values["mode"] in MODE_OPTIONS
    assert values["addon"] in ADDON_OPTIONS
    assert values["warm_duty"] == 10.0
    assert values["cold_duty"] == 20.0
    # Unknown values map to None instead of raising inside Home Assistant.
    odd = InioData(
        mode="WEIRD", addon="WEIRD", warm=0.0, cold=0.0, brightness=0, kelvin=4000
    )
    assert {s.key: s.value_fn(odd) for s in SENSORS}["mode"] is None
