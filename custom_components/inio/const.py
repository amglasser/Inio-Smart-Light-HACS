"""Constants for the inio integration."""

from __future__ import annotations

DOMAIN = "inio"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 15  # seconds
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 300

# Lamp operating range (inio one: 2,700 - 6,500 K, brightness 0 - 100 %)
MIN_KELVIN = 2700
MAX_KELVIN = 6500
MAX_BRIGHTNESS_PCT = 100

# Lamp modes as reported by /api/app/status
MODE_OFF = "OFF"
MODE_STATIC = "STATIC"
MODE_CONNECTED = "CONNECTED"

# Add-ons as reported by /api/app/status
ADDON_NONE = "NONE"
ADDON_BOOST = "BOOST"
ADDON_RELAX = "RELAX"
ADDON_SCENARIO = "SCENARIO"

MANUFACTURER = "inio"
MODEL = "inio one"
