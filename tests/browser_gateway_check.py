"""Real browser + official UI + authenticated host-rewriting proxy.
The backend returns a WAV test tone, not AI-generated speech. GPU validation is separate.
"""
import asyncio
import io
import math
import shutil
import struct
import sys
import wave
from pathlib import Path

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deploy.gateway import create_app

PASSWORD = "test-password-not-a-real-secret"
DIST = ROOT / "vendor/fish-speech/awesome_webui/dist"


def test_wav():
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(24000)
        target.writeframes(b"".join(struct.pack("<h", int(5000 * math.sin(2 * math.pi * 440 * n / 24000))) for n in range(24000)))
    return output.getvalue()


async def main():
    requests = []
    fail = False
    async def defaults(request):
        return web.json_response({"model_family": "drama3", "chunk_length": 200,
            "max_new_tokens": 1024, "temperature": 0.8, "top_p": 0.8, "repetition_penalty": 1.2})
    async def tts(request):
        payload = await request.json()
        requests.append(payload)
        assert "Authorization" not in request.headers
        if fail:
            return web.json_response({"detail": "test unavailable"}, status=503)
        assert payload["format"] == "wav"
        return web.Response(body=test_wav(), content_type="audio/wav")
    upstream_app = web.Application()
    upstream_app.router.add_get("/ui", lambda _: web.FileResponse(DIST / "index.html"))
    upstream_app.router.add_get("/v1/tts/defaults", defaults)
    upstream_app.router.add_post("/v1/tts", tts)
    upstream = TestServer(upstream_app)
    await upstream.start_server()
    gateway = None
    async with ClientSession() as proxy_client:
        async def proxy(request):
            headers = {key: value for key, value in request.headers.items()
                       if key.lower() not in {"host", "connection", "content-length"}}
            headers["Host"] = "internal-backend:8080"
            if request.method == "POST":
                headers.pop("Authorization", None)  # Browser API must work on login cookie alone.
            async with proxy_client.request(request.method, str(gateway.make_url(request.rel_url)),
                    headers=headers, data=await request.read(), allow_redirects=False) as response:
                forwarded = {key: value for key, value in response.headers.items()
                             if key.lower() not in {"transfer-encoding", "content-length", "connection", "content-encoding"}}
                return web.Response(status=response.status, body=await response.read(), headers=forwarded)
        proxy_app = web.Application()
        proxy_app.router.add_route("*", "/{path:.*}", proxy)
        frontend = TestServer(proxy_app)
        await frontend.start_server()
        origin = str(frontend.make_url("/")).rstrip("/")
        gateway = TestServer(create_app("persona", PASSWORD, str(upstream.make_url("/")).rstrip("/"), origin))
        await gateway.start_server()
        try:
            async with async_playwright() as p:
                options = {"headless": True, "args": ["--no-sandbox"]}
                if shutil.which("chromium"):
                    options["executable_path"] = shutil.which("chromium")
                browser = await p.chromium.launch(**options)
                try:
                    for width in (1280, 390):
                        context = await browser.new_context(http_credentials={"username": "persona", "password": PASSWORD},
                                                            viewport={"width": width, "height": 900}, accept_downloads=True)
                        page = await context.new_page()
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        await page.goto(origin)
                        await page.get_by_label("Input Text", exact=True).fill("[excited] Hello from the browser test!")
                        await page.get_by_role("radio", name="wav", exact=True).click()
                        await page.get_by_role("button", name="Generate Audio", exact=True).click()
                        download_link = page.get_by_role("link", name="Download", exact=True)
                        await download_link.wait_for(timeout=15000)
                        assert requests[-1]["text"] == "[excited] Hello from the browser test!"
                        assert requests[-1]["references"] == []
                        await page.wait_for_function("document.querySelector('audio').readyState >= 2")
                        await page.evaluate("document.querySelector('audio').play()")
                        await page.wait_for_function("document.querySelector('audio').currentTime > 0.1")
                        async with page.expect_download() as info:
                            await download_link.click()
                        downloaded = await info.value
                        path = await downloaded.path()
                        assert Path(path).read_bytes() == test_wav()
                        fail = True
                        await page.get_by_role("button", name="Generate Audio", exact=True).click()
                        await page.get_by_text("Audio generation failed: Failed to generate audio", exact=True).wait_for()
                        fail = False
                        assert not errors, errors
                        await context.close()
                        print(f"PASS official Fish UI ({width}px): login cookie, rewritten Host, POST, WAV playback/download, visible failure")
                finally:
                    await browser.close()
        finally:
            await gateway.close()
            await frontend.close()
            await upstream.close()


if __name__ == "__main__":
    asyncio.run(main())
