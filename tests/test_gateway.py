import asyncio
import time
import unittest
from unittest.mock import patch

from aiohttp import BasicAuth, FormData, web
from aiohttp.test_utils import TestClient, TestServer
from deploy.gateway import create_app, SESSION_COOKIE

PASSWORD = "test-password-not-a-real-secret"
AUTH = BasicAuth("persona", PASSWORD)


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.received = None
        self.release_audio = asyncio.Event()
        async def ui(request):
            return web.Response(text="official Fish demo", content_type="text/html")
        async def health(request):
            return web.json_response({"status": "ok"})
        async def echo(request):
            self.received = (request.method, dict(request.headers), await request.read())
            return web.Response(body=self.received[2], content_type=request.content_type)
        async def streaming(request):
            response = web.StreamResponse(headers={"Content-Type": "audio/wav"})
            await response.prepare(request)
            await response.write(b"first audio chunk")
            await self.release_audio.wait()
            await response.write(b"last audio chunk")
            return response
        async def error(request):
            return web.json_response({"detail": "Text is too long"}, status=400)
        app = web.Application()
        app.router.add_get("/ui", ui)
        app.router.add_get("/v1/health", health)
        app.router.add_post("/stream", streaming)
        app.router.add_post("/bad", error)
        app.router.add_route("*", "/echo", echo)
        self.upstream = TestServer(app)
        await self.upstream.start_server()
        self.client = TestClient(TestServer(create_app("persona", PASSWORD,
                     str(self.upstream.make_url("/")).rstrip("/"))))
        await self.client.start_server()

    async def asyncTearDown(self):
        self.release_audio.set()
        await self.client.close()
        await self.upstream.close()

    async def test_login_cookie_and_ui_redirect(self):
        for auth in (None, BasicAuth("persona", "wrong")):
            response = await self.client.get("/ui", auth=auth)
            self.assertEqual(response.status, 401)
        response = await self.client.get("/", auth=AUTH, allow_redirects=False)
        self.assertEqual(response.headers["Location"], "/ui")
        cookie = response.cookies[SESSION_COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")
        response = await self.client.get("/ui")
        self.assertEqual(await response.text(), "official Fish demo")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn("Authorization", response.request_info.headers)

    async def test_readiness_and_downstream_errors(self):
        response = await self.client.get("/healthz")
        self.assertEqual((await response.json())["model"], "fishaudio/drama-3")
        await self.upstream.close()
        response = await self.client.get("/healthz")
        self.assertEqual(response.status, 503)
        response = await self.client.get("/ui", auth=AUTH)
        self.assertEqual(response.status, 503)
        self.assertIn("loading", await response.text())

    async def test_post_json_and_delete_and_credentials_not_forwarded(self):
        response = await self.client.post("/echo", auth=AUTH, json={"text": "[excited] hello"})
        self.assertEqual(await response.json(), {"text": "[excited] hello"})
        self.assertNotIn("Authorization", self.received[1])
        self.assertNotIn("Cookie", self.received[1])
        response = await self.client.delete("/echo")
        self.assertEqual(response.status, 200)
        self.assertEqual(self.received[0], "DELETE")

    async def test_reference_multipart_bytes_preserved(self):
        form = FormData()
        form.add_field("text", "Reference transcript")
        form.add_field("audio", b"RIFF-reference-bytes", filename="voice.wav", content_type="audio/wav")
        response = await self.client.post("/echo", auth=AUTH, data=form)
        body = await response.read()
        self.assertIn(b"RIFF-reference-bytes", body)
        self.assertIn(b"Reference transcript", body)
        self.assertEqual(body, self.received[2])

    async def test_audio_stream_arrives_before_generation_finishes(self):
        response = await self.client.post("/stream", auth=AUTH)
        first = await asyncio.wait_for(response.content.readexactly(17), timeout=2)
        self.assertEqual(first, b"first audio chunk")
        self.assertIn(SESSION_COOKIE, response.cookies)
        self.release_audio.set()
        self.assertEqual(await response.read(), b"last audio chunk")

    async def test_upstream_error_status_and_message_preserved(self):
        response = await self.client.post("/bad", auth=AUTH)
        self.assertEqual(response.status, 400)
        self.assertEqual((await response.json())["detail"], "Text is too long")

    async def test_cross_origin_post_rejected(self):
        response = await self.client.post("/echo", auth=AUTH, headers={"Origin": "https://attacker.example"}, json={})
        self.assertEqual(response.status, 403)
        self.assertIsNone(self.received)

    async def test_public_origin_survives_host_rewriting_and_sets_secure_cookie(self):
        async with TestClient(TestServer(create_app("persona", PASSWORD,
                str(self.upstream.make_url("/")).rstrip("/"), public_origin="https://voice.example"))) as client:
            response = await client.post("/echo", auth=AUTH, json={"text": "hello"},
                                        headers={"Host": "internal:8080", "Origin": "https://voice.example"})
            self.assertEqual(response.status, 200)
            self.assertTrue(response.cookies[SESSION_COOKIE]["secure"])

    async def test_forged_and_expired_sessions_rejected(self):
        response = await self.client.get("/ui", headers={"Cookie": f"{SESSION_COOKIE}=1.fake.signature"})
        self.assertEqual(response.status, 401)
        response = await self.client.get("/ui", auth=AUTH)
        with patch("deploy.gateway.time.time", return_value=time.time() + 4000):
            response = await self.client.get("/ui")
        self.assertEqual(response.status, 401)

    def test_bad_configuration_rejected(self):
        with self.assertRaises(ValueError):
            create_app(password="short")
        for origin in ("https://user:pass@voice.example", "https://voice.example/path", "file:///tmp"):
            with self.assertRaises(ValueError):
                create_app(password=PASSWORD, public_origin=origin)
