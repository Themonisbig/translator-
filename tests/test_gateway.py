import asyncio
import time
import unittest
from unittest.mock import patch
from aiohttp import BasicAuth, web
from aiohttp.test_utils import TestClient, TestServer
from deploy.gateway import create_app, SESSION_COOKIE

PASSWORD = "test-password-not-a-real-secret"
AUTH = BasicAuth("persona", PASSWORD)

class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async def home(request):
            return web.Response(text="official demo", content_type="text/html")
        async def chat(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            # Protocol fixture only: this is not model inference or an audio test.
            await ws.send_bytes(b"\x00")
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    await ws.send_bytes(msg.data)
            return ws
        app = web.Application()
        app.router.add_get("/", home)
        app.router.add_get("/api/chat", chat)
        self.upstream = TestServer(app)
        await self.upstream.start_server()
        gateway = create_app("persona", PASSWORD, str(self.upstream.make_url("/")).rstrip("/"))
        self.client = TestClient(TestServer(gateway))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        await self.upstream.close()

    async def test_requires_authentication_and_rejects_bad_password(self):
        for auth in (None, BasicAuth("persona", "incorrect")):
            response = await self.client.get("/", auth=auth)
            self.assertEqual(response.status, 401)
            self.assertIn("Basic", response.headers["WWW-Authenticate"])

    async def test_serves_authenticated_browser_and_readiness(self):
        response = await self.client.get("/", auth=AUTH)
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.text(), "official demo")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        health = await self.client.get("/healthz")
        self.assertEqual(await health.json(), {"status": "ready"})

    async def test_reports_loading_when_upstream_is_down(self):
        await self.upstream.close()
        response = await self.client.get("/healthz")
        self.assertEqual(response.status, 503)
        response = await self.client.get("/", auth=AUTH)
        self.assertEqual(response.status, 503)

    async def test_rejects_invalid_voice_and_oversize_prompt(self):
        for query in ({"voice_prompt": "../../outside.pt"},
                      {"voice_prompt": "NATF0.pt", "text_prompt": "x" * 1001}):
            response = await self.client.get("/api/chat", params=query, auth=AUTH)
            self.assertEqual(response.status, 400)

    async def test_rejects_cross_origin_websocket(self):
        response = await self.client.get("/api/chat?voice_prompt=NATF0.pt", auth=AUTH,
                                         headers={"Origin": "https://other.example"})
        self.assertEqual(response.status, 403)

    async def test_binary_websocket_bidirectional_bridge_and_disconnect(self):
        ws = await self.client.ws_connect("/api/chat?voice_prompt=NATF0.pt", auth=AUTH)
        self.assertEqual((await ws.receive(timeout=2)).data, b"\x00")
        payload = bytes(range(256))
        await ws.send_bytes(payload)
        self.assertEqual((await ws.receive(timeout=2)).data, payload)
        await ws.close()

    async def test_browser_session_authenticates_websocket_without_basic_header(self):
        login = await self.client.get("/", auth=AUTH)
        self.assertIn(SESSION_COOKIE, login.cookies)
        self.assertTrue(login.cookies[SESSION_COOKIE]["httponly"])
        self.assertEqual(login.cookies[SESSION_COOKIE]["samesite"], "Strict")
        ws = await self.client.ws_connect("/api/chat?voice_prompt=NATF0.pt")
        self.assertEqual((await ws.receive(timeout=2)).data, b"\x00")
        await ws.close()

    async def test_modified_and_expired_sessions_are_rejected(self):
        login = await self.client.get("/", auth=AUTH)
        token = login.cookies[SESSION_COOKIE].value
        self.client.session.cookie_jar.clear()
        invalid = token[:-1] + ("0" if token[-1] != "0" else "1")
        response = await self.client.get("/", headers={"Cookie": f"{SESSION_COOKIE}={invalid}"})
        self.assertEqual(response.status, 401)
        with patch("deploy.gateway.time.time", return_value=time.time() + 3601):
            response = await self.client.get("/", headers={"Cookie": f"{SESSION_COOKIE}={token}"})
            self.assertEqual(response.status, 401)

    async def test_public_origin_survives_proxy_host_rewrite(self):
        app = create_app("persona", PASSWORD, str(self.upstream.make_url("/")).rstrip("/"),
                         public_origin="https://voice.example")
        async with TestClient(TestServer(app)) as client:
            login = await client.get("/", auth=AUTH)
            self.assertTrue(login.cookies[SESSION_COOKIE]["secure"])
            token = login.cookies[SESSION_COOKIE].value
            headers = {"Host": "internal-backend:8080", "Origin": "https://voice.example",
                       "Cookie": f"{SESSION_COOKIE}={token}"}
            ws = await client.ws_connect("/api/chat?voice_prompt=NATF0.pt", headers=headers)
            self.assertEqual((await ws.receive(timeout=2)).data, b"\x00")
            await ws.close()
            headers["Origin"] = "https://other.example"
            response = await client.get("/api/chat?voice_prompt=NATF0.pt", headers=headers)
            self.assertEqual(response.status, 403)

    def test_rejects_untrusted_public_origin_configuration(self):
        for origin in ("https://user:password@voice.example", "https://voice.example/path",
                       "https://voice.example?other=1", "file:///tmp"):
            with self.assertRaises(ValueError):
                create_app(password=PASSWORD, public_origin=origin)

    def test_refuses_missing_or_weak_web_password(self):
        with self.assertRaises(ValueError):
            create_app(password="short")
