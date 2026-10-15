"""Same-origin authenticated HTTP/WebSocket bridge; no speech model replacements."""
import asyncio
import hmac
import os
from urllib.parse import urlsplit
from aiohttp import BasicAuth, ClientError, ClientSession, ClientTimeout, WSMsgType, web

VOICES = {f"{kind}{sex}{n}.pt" for kind in ("NAT", "VAR")
          for sex in ("F", "M") for n in range(4 if kind == "NAT" else 5)}

@web.middleware
async def authenticate(request, handler):
    if request.path == "/healthz":
        return await handler(request)
    try:
        auth = BasicAuth.decode(request.headers.get("Authorization", ""))
        valid = (hmac.compare_digest(auth.login.encode(), request.app["username"].encode())
                 and hmac.compare_digest(auth.password.encode(), request.app["password"].encode()))
    except (ValueError, UnicodeError):
        valid = False
    if not valid:
        return web.Response(status=401, text="Sign in with your RunPod WEB_USERNAME and WEB_PASSWORD.",
                            headers={"WWW-Authenticate": 'Basic realm="PersonaPlex", charset="UTF-8"'})
    response = await handler(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

async def health(request):
    try:
        async with request.app["client"].get(request.app["upstream"] + "/", timeout=ClientTimeout(total=3)) as r:
            if r.status == 200:
                return web.json_response({"status": "ready"})
    except (ClientError, OSError, asyncio.TimeoutError):
        pass
    return web.json_response({"status": "loading", "message": "Model loading; check Pod logs."}, status=503)

async def bridge(request):
    if request.path == "/api/chat":
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host:
            raise web.HTTPForbidden(text="Use this site's own conversation page.")
        if request.query.get("voice_prompt") not in VOICES:
            raise web.HTTPBadRequest(text="Select one of the 18 packaged PersonaPlex voices.")
        if len(request.query.get("text_prompt", "")) > 1000:
            raise web.HTTPBadRequest(text="Personality instructions must be at most 1000 characters.")
        try:
            upstream = await request.app["client"].ws_connect(
                request.app["upstream"] + request.rel_url.path_qs, heartbeat=30,
                timeout=60, max_msg_size=4 * 1024 * 1024)
        except (ClientError, OSError, asyncio.TimeoutError):
            raise web.HTTPServiceUnavailable(text="Model unavailable or still loading. Check Pod logs and retry.")
        downstream = web.WebSocketResponse(heartbeat=30)
        await downstream.prepare(request)
        async def relay(source, target):
            async for msg in source:
                if msg.type == WSMsgType.BINARY:
                    await target.send_bytes(msg.data)
                elif msg.type == WSMsgType.TEXT:
                    await target.send_str(msg.data)
                elif msg.type == WSMsgType.ERROR:
                    break
        tasks = [asyncio.create_task(relay(upstream, downstream)),
                 asyncio.create_task(relay(downstream, upstream))]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await upstream.close()
            await downstream.close()
        return downstream
    try:
        async with request.app["client"].get(request.app["upstream"] + request.rel_url.path_qs) as r:
            return web.Response(status=r.status, body=await r.read(),
                                headers={"Content-Type": r.headers.get("Content-Type", "application/octet-stream")})
    except (ClientError, OSError, asyncio.TimeoutError):
        raise web.HTTPServiceUnavailable(text="PersonaPlex is loading or unavailable. Check RunPod logs and retry.")

async def client_context(app):
    async with ClientSession(timeout=ClientTimeout(total=None, sock_connect=10)) as session:
        app["client"] = session
        yield

def create_app(username=None, password=None, upstream="http://127.0.0.1:8998"):
    username = username or os.environ.get("WEB_USERNAME", "persona")
    password = password or os.environ.get("WEB_PASSWORD", "")
    if len(password) < 16:
        raise ValueError("Configure WEB_PASSWORD with at least 16 characters")
    app = web.Application(middlewares=[authenticate])
    app.update(username=username, password=password, upstream=upstream)
    app.cleanup_ctx.append(client_context)
    app.router.add_get("/healthz", health)
    app.router.add_get("/{path:.*}", bridge)
    return app

if __name__ == "__main__":
    # TLS is terminated by RunPod's managed HTTPS proxy. Do not expose 8998.
    web.run_app(create_app(), host="0.0.0.0", port=8080, access_log=None)
