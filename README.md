# inio for Home Assistant

A [HACS](https://hacs.xyz) custom integration for the **inio one** daylight lamp (jetlite technology).
It talks to the lamp over your local network — no cloud, no account.

> Unofficial. Not affiliated with inio / LS-Trafo. The lamp's local API is undocumented; see
> [How it works](#how-it-works) and [Limitations](#limitations).

## Features

| Entity | What it does |
|---|---|
| `light.inio_…` | On/off, brightness (0–100 %), color temperature (2,700–6,500 K) |
| `switch.inio_…_connected_mode` | Hands control to the lamp's app schedule ("connected" mode); turning it off keeps the lamp on in static mode |
| `switch.inio_…_room_sync` | Room Sync: while on, changes to this lamp are mirrored to the other inio lamps in the same area |
| `button.inio_…_sync_room_now` | Room Sync, one shot: pushes this lamp's state to the other inio lamps in the same area |
| `sensor.inio_…_mode` | `off` / `static` / `connected` |
| `sensor.inio_…_add_on` | `none` / `boost` / `relax` / `scenario` |
| `sensor.inio_…_warm_led_duty`, `…_cold_led_duty` | Raw LED duty cycles (diagnostic, disabled by default) |

Only the **newer, app-enabled inio one** has the local API. The older touch-only version sold at a discount
has no app control and will not work.

## Installation (HACS)

1. In HACS open the three-dot menu → **Custom repositories**.
2. Add `https://github.com/amglasser/Inio-Smart-Light-HACS` with category **Integration**.
3. Install **inio** from HACS and restart Home Assistant.
4. **Settings → Devices & services → Add integration → inio** and enter the lamp's IP address.

Give the lamp a fixed address (DHCP reservation) in your router. If it ever changes, use **Reconfigure**
on the integration entry.

Options (polling interval, default 15 s) are under the integration's **Configure** button.

## Room Sync

If you have several inio lamps in one room, Room Sync keeps their on/off state, brightness and color
temperature the same.

1. Assign all the lamps to the same **area** in Home Assistant (Settings → Areas). Room Sync uses the area of
   the lamp's light entity, falling back to the device's area.
2. **Sync room now** (button) copies the lamp's current state to the other lamps in the area once.
3. **Room sync** (switch) keeps doing that: turn it on for the lamp you want as the source. Switching it on
   also performs an initial sync. You can turn it on for every lamp in the room, so touching any of them
   updates the rest.

Notes:

- Changes made from Home Assistant are mirrored within about a second. Changes made on the lamp itself
  (touch) are noticed at the next poll, so up to the polling interval (15 s by default).
- If the source lamp is in connected mode, the other lamps are put into connected mode too.
- Small differences (under 3 % brightness or 100 K) are ignored, because brightness and color temperature are
  estimates. After Room Sync commands a lamp, that lamp is ignored for 20 s so lamps don't echo each other.
- Turning the switch on fails with a message if no other inio lamp is in the same area.

## How it works

The lamp serves a small JSON API on port 80. It has no authentication, so keep the lamp off guest networks.

| Purpose | Request |
|---|---|
| Mode and add-on | `GET /api/app/status` → `{"mode": "OFF\|STATIC\|CONNECTED", "addon": "NONE\|BOOST\|RELAX\|SCENARIO"}` |
| LED duty cycles | `GET /api/app/pwm_duty_get` → `{"warm": 0–100, "cold": 0–100}` |
| Set brightness / color temperature | `POST /api/app/light_color` with `{"brightness": 0–100, "kelvin": 2700–6500}` |
| Power button (off ↔ static, connected → off) | `PUT /api/interface/btn_short_manual` |
| Connect button (static ↔ connected) | `PUT /api/interface/btn_short_connect` |

The lamp reports only its raw warm/cold LED duty cycles, not the brightness and color temperature it was set
to. The integration estimates both from two calibration curves (`custom_components/inio/model.py`).
Checked against the original measurement table the estimates are close for brightness (mean error well under
1 point, worst case about 2) and typically within 30–100 K for color temperature (above 10 % brightness).
At very low brightness the color temperature estimate gets noisier.

## Behaviour notes

- Changing brightness or color temperature from Home Assistant moves the lamp out of connected mode into
  static mode, as the app does.
- A plain "turn on" leaves a lamp that is already on (including in connected mode) untouched.
- Commands are sent one at a time; the lamp's embedded web server does not like parallel requests.

## Limitations

- Boost, Relax and Scenario add-ons are shown as a sensor but cannot be started from Home Assistant yet —
  the endpoints for them are not known.
- Brightness and color temperature are estimates, see above.
- Firmware updates by the vendor could change the API.

## Development

```bash
pip install pytest aiohttp  # add homeassistant to also run the import smoke tests
pytest
```

The tests cover the HTTP client against a fake lamp and the calibration model; they do not need Home Assistant.

## Credits

Endpoint discovery and the calibration data come from
[homebridge-inio](https://github.com/reckter/homebridge-inio) by Hannes Güdelhöfer (Apache-2.0); see `NOTICE`.
Licensed under the MIT License.
