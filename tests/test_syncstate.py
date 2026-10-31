"""Tests for the pure Room Sync logic."""

from __future__ import annotations

from custom_components.inio.syncstate import (
    BRIGHTNESS_TOLERANCE,
    KELVIN_TOLERANCE,
    SyncState,
    significantly_different,
    snapshot,
)


def test_snapshot_kinds() -> None:
    assert snapshot("OFF", 0, 4000).kind == "off"
    assert snapshot("CONNECTED", 40, 3000).kind == "connected"
    assert snapshot("STATIC", 40, 3000) == SyncState("static", 40, 3000)
    assert snapshot("WEIRD", 40, 3000).kind == "static"


def test_kind_change_is_significant() -> None:
    off = SyncState("off", 0, 4000)
    static = SyncState("static", 50, 4000)
    assert significantly_different(off, static)
    assert significantly_different(static, SyncState("connected", 50, 4000))


def test_static_noise_is_ignored() -> None:
    a = SyncState("static", 50, 4000)
    assert not significantly_different(a, SyncState("static", 51, 4040))
    assert significantly_different(
        a, SyncState("static", 50 + BRIGHTNESS_TOLERANCE, 4000)
    )
    assert significantly_different(
        a, SyncState("static", 50, 4000 + KELVIN_TOLERANCE)
    )


def test_kelvin_ignored_when_dim() -> None:
    a = SyncState("static", 5, 2700)
    b = SyncState("static", 5, 5000)
    assert not significantly_different(a, b)


def test_off_and_connected_ignore_brightness() -> None:
    assert not significantly_different(
        SyncState("connected", 10, 3000), SyncState("connected", 90, 5000)
    )
    assert not significantly_different(
        SyncState("off", 0, 3000), SyncState("off", 0, 5000)
    )
