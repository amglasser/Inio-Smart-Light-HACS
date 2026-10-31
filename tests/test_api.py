"""Tests for the inio HTTP client against a fake lamp."""

from __future__ import annotations

import asyncio

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from custom_components.inio import api as api_module
from custom_components.inio.api import InioClient, InioConnectionError
from custom_components.inio.model import estimate, expected_pwm


class FakeLamp:
    """Minimal emulation of the lamp's local API."""

    def __init__(self) -> None:
        self.mode = "OFF"
        self.addon = "NONE"
        self.brightness = 60
        self.kelvin = 4200
        self.calls: list[tuple[str, str, object]] = []

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/api/app/status", self.status)
        app.router.add_get("/api/app/pwm_duty_get", self.pwm)
        app.router.add_put("/api/interface/btn_short_manual", self.manual)
        app.router.add_put("/api/interface/btn_short_connect", self.connect)
        app.router.add_post("/api/app/light_color", self.light_color)
        return app

    async def status(self, request: web.Request) -> web.Response:
        self.calls.append(("GET", request.path, None))
        return web.json_response({"mode": self.mode, "addon": self.addon})

    async def pwm(self, request: web.Request) -> web.Response:
        self.calls.append(("GET", request.path, None))
        if self.mode == "OFF":
            return web.json_response({"warm": 0, "cold": 0})
        warm, cold = expected_pwm(self.brightness, self.kelvin)
        return web.json_response({"warm": warm, "cold": cold})

    async def manual(self, request: web.Request) -> web.Response:
        self.calls.append(("PUT", request.path, None))
        self.mode = "STATIC" if self.mode == "OFF" else "OFF"
        return web.Response(text="")

    async def connect(self, request: web.Request) -> web.Response:
        self.calls.append(("PUT", request.path, None))
        if self.mode == "STATIC":
            self.mode = "CONNECTED"
        elif self.mode == "CONNECTED":
            self.mode = "STATIC"
        return web.Response(text="")

    async def light_color(self, request: web.Request) -> web.Response:
        body = await request.json()
        self.calls.append(("POST", request.path, body))
        self.brightness = body["brightness"]
        self.kelvin = body["kelvin"]
        return web.Response(text="")


@pytest.fixture(autouse=True)
def fast_lamp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_module, "BUTTON_SETTLE_DELAY", 0)
    monkeypatch.setattr(api_module, "SETTLE_POLL_DELAY", 0)


def run(coro):
    return asyncio.run(coro)


async def _with_lamp(lamp: FakeLamp, scenario) -> None:
    server = TestServer(lamp.app())
    await server.start_server()
    try:
        async with aiohttp.ClientSession() as session:
            client = InioClient(server.host, session, port=server.port)
            await scenario(client)
    finally:
        await server.close()


def test_status_and_pwm() -> None:
    lamp = FakeLamp()
    lamp.mode = "STATIC"

    async def scenario(client: InioClient) -> None:
        status = await client.get_status()
        assert (status.mode, status.addon) == ("STATIC", "NONE")
        pwm = await client.get_pwm()
        brightness, kelvin = estimate(pwm.warm, pwm.cold)
        assert abs(brightness - 60) <= 2
        assert kelvin is not None and abs(kelvin - 4200) <= 150

    run(_with_lamp(lamp, scenario))


def test_set_mode_transitions() -> None:
    lamp = FakeLamp()

    async def scenario(client: InioClient) -> None:
        assert (await client.set_mode("STATIC")).mode == "STATIC"
        assert (await client.set_mode("CONNECTED")).mode == "CONNECTED"
        assert (await client.set_mode("STATIC")).mode == "STATIC"
        assert (await client.set_mode("OFF")).mode == "OFF"
        # From OFF straight to CONNECTED needs both buttons.
        assert (await client.set_mode("CONNECTED")).mode == "CONNECTED"
        assert (await client.set_mode("OFF")).mode == "OFF"
        # Already there: no button presses.
        before = len(lamp.calls)
        assert (await client.set_mode("OFF")).mode == "OFF"
        assert all(c[0] == "GET" for c in lamp.calls[before:])

    run(_with_lamp(lamp, scenario))


def test_set_light_payload_is_clamped_json() -> None:
    lamp = FakeLamp()
    lamp.mode = "STATIC"

    async def scenario(client: InioClient) -> None:
        await client.set_light(150, 9000)
        await client.set_light(35, 2000)

    run(_with_lamp(lamp, scenario))
    posts = [c for c in lamp.calls if c[0] == "POST"]
    assert posts[0][2] == {"brightness": 100, "kelvin": 6500}
    assert posts[1][2] == {"brightness": 35, "kelvin": 2700}


def test_connection_error() -> None:
    async def scenario() -> None:
        async with aiohttp.ClientSession() as session:
            client = InioClient("127.0.0.1", session, port=9)  # nothing listens here
            with pytest.raises(InioConnectionError):
                await client.get_status()

    run(scenario())


def test_bad_status_payload() -> None:
    async def bad_status(request: web.Request) -> web.Response:
        return web.json_response({"nope": 1})

    async def scenario() -> None:
        app = web.Application()
        app.router.add_get("/api/app/status", bad_status)
        server = TestServer(app)
        await server.start_server()
        try:
            async with aiohttp.ClientSession() as session:
                client = InioClient(server.host, session, port=server.port)
                with pytest.raises(InioConnectionError):
                    await client.get_status()
        finally:
            await server.close()

    run(scenario())
