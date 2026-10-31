"""Test setup: import the pure-Python parts of the integration without Home Assistant.

``custom_components/inio/__init__.py`` imports Home Assistant, which is not needed
(or installed) to test the API client and the calibration model. Registering the
package skeleton in ``sys.modules`` lets ``api``, ``model`` and ``const`` be imported
without running ``__init__``.
"""

from __future__ import annotations

from pathlib import Path
import sys
import types

_ROOT = Path(__file__).resolve().parents[1] / "custom_components"
_PKG = _ROOT / "inio"

if "custom_components.inio" not in sys.modules:
    parent = types.ModuleType("custom_components")
    parent.__path__ = [str(_ROOT)]
    child = types.ModuleType("custom_components.inio")
    child.__path__ = [str(_PKG)]
    sys.modules["custom_components"] = parent
    sys.modules["custom_components.inio"] = child
