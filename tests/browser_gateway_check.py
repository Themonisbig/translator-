"""Real browser through a host-rewriting proxy; protocol fixture, no AI inference."""
import asyncio
import shutil
import sys
from pathlib import Path

from aiohttp import ClientSession, WSMsgType, web
from aiohttp.test_utils import TestServer
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deploy.gateway import create_app

PASSWORD = "test-password-not-a-real-secret"
DIST = ROOT / "vendor/personaplex/client/dist"


async def relay(source, target):
    async for message in source:
        if message.type == WSMsgType.BINARY:
            await target.send_bytes(message.data)
        elif message.type == WSMsgType.TEXT:
            await target.send_str(message.data)


async def main():
    received_audio = asyncio.Event()

    async def chat(request):
        # Only a transport fixture: a genuine model is required for GPU validation.
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.send_bytes(b"\x00")
        async for message in ws:
            if message.type == WSMsgType.BINARY and message.data[:1] == b"\x01":
                received_audio.set()
        return ws

    upstream_app = web.Application()
    upstream_app.router.add_get("/api/chat", chat)
    upstream_app.router.add_get("/", lambda _: web.FileResponse(DIST / "index.html"))
    upstream_app.router.add_static("/", DIST)
    upstream = TestServer(upstream_app)
    await upstream.start_server()
    gateway = None

    async with ClientSession() as proxy_client:
        async def proxy(request):
            headers = {k: v for k, v in request.headers.items()
                       if k.lower() not in {"host", "connection", "upgrade", "sec-websocket-key",
                                             "sec-websocket-version", "sec-websocket-extensions"}}
            headers["Host"] = "internal-backend:8080"
            target = str(gateway.make_url(request.rel_url))
            if request.headers.get("Upgrade", "").lower() == "websocket":
                # Reproduce browsers/proxies that do not resend HTTP Basic login.
                headers.pop("Authorization", None)
                async with proxy_client.ws_connect(target, headers=headers) as remote:
                    browser_ws = web.WebSocketResponse()
                    await browser_ws.prepare(request)
                    tasks = [asyncio.create_task(relay(remote, browser_ws)),
                             asyncio.create_task(relay(browser_ws, remote))]
                    try:
                        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    finally:
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                        await browser_ws.close()
                    return browser_ws
            async with proxy_client.get(target, headers=headers) as response:
                forwarded = {"Content-Type": response.headers.get("Content-Type", "application/octet-stream")}
                for name in ("Set-Cookie", "WWW-Authenticate", "Cache-Control"):
                    if name in response.headers:
                        forwarded[name] = response.headers[name]
                return web.Response(status=response.status, body=await response.read(), headers=forwarded)

        proxy_app = web.Application()
        proxy_app.router.add_get("/{path:.*}", proxy)
        frontend = TestServer(proxy_app)
        await frontend.start_server()
        public_origin = str(frontend.make_url("/")).rstrip("/")
        gateway = TestServer(create_app("persona", PASSWORD,
                            str(upstream.make_url("/")).rstrip("/"), public_origin=public_origin))
        await gateway.start_server()
        try:
            async with async_playwright() as p:
                options = {"headless": True, "args": ["--no-sandbox", "--use-fake-ui-for-media-stream",
                                                      "--use-fake-device-for-media-stream"]}
                if shutil.which("chromium"):
                    options["executable_path"] = shutil.which("chromium")
                browser = await p.chromium.launch(**options)
                try:
                    context = await browser.new_context(http_credentials={"username": "persona", "password": PASSWORD})
                    page = await context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(public_origin)
                    await page.get_by_role("button", name="Start conversation", exact=True).click()
                    await page.get_by_role("status").get_by_text("connected", exact=True).wait_for(timeout=15000)
                    await asyncio.wait_for(received_audio.wait(), timeout=10)
                    await page.get_by_role("button", name="Stop conversation", exact=True).click()
                    await page.get_by_role("status").get_by_text("disconnected", exact=True).wait_for()
                    assert not errors, errors
                    print("PASS browser proxy: login cookie, rewritten host, WebSocket handshake, microphone packets, stop")
                    await context.close()
                finally:
                    await browser.close()
        finally:
            await gateway.close()
            await frontend.close()
            await upstream.close()


if __name__ == "__main__":
    asyncio.run(main())
