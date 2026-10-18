"""Same-origin streaming Fish gateway with optional browser authentication."""
import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import time
from urllib.parse import urlsplit

from aiohttp import BasicAuth, ClientError, ClientSession, ClientTimeout, web

logger = logging.getLogger("fish.gateway")
SESSION_COOKIE = "fish_session"
SESSION_SECONDS = 3600
MAX_BODY = 50 * 1024 * 1024
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
               "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length"}


def valid_session(request):
    try:
        expires, nonce, signature = request.cookies.get(SESSION_COOKIE, "").split(".")
        if not time.time() < int(expires) <= time.time() + SESSION_SECONDS:
            return False
        expected = hmac.new(request.app["session_key"], f"{expires}.{nonce}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def set_session(request, response):
    payload = f"{int(time.time()) + SESSION_SECONDS}.{secrets.token_urlsafe(24)}"
    signature = hmac.new(request.app["session_key"], payload.encode(), hashlib.sha256).hexdigest()
    response.set_cookie(SESSION_COOKIE, f"{payload}.{signature}", max_age=SESSION_SECONDS,
                        httponly=True, samesite="Strict", path="/",
                        secure=request.app["public_origin"].startswith("https://") or request.secure)


def origin_allowed(request):
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        return False
    expected = request.app["public_origin"] or f"{request.scheme}://{request.host}"
    return not request.headers.get("Origin") or request.headers["Origin"] == expected


@web.middleware
async def authenticate(request, handler):
    if request.path == "/healthz":
        return await handler(request)
    if request.app["auth_required"]:
        try:
            auth = BasicAuth.decode(request.headers.get("Authorization", ""))
            valid = (hmac.compare_digest(auth.login.encode(), request.app["username"].encode())
                     and hmac.compare_digest(auth.password.encode(), request.app["password"].encode()))
        except (ValueError, UnicodeError):
            valid = False
        session = valid_session(request)
        if not valid and not session:
            return web.Response(status=401, text="Sign in using WEB_USERNAME and WEB_PASSWORD from RunPod secrets.",
                                headers={"WWW-Authenticate": 'Basic realm="Fish Drama 3", charset="UTF-8"'})
        request["new_session"] = valid and not session
    if request.method not in ("GET", "HEAD", "OPTIONS") and not origin_allowed(request):
        raise web.HTTPForbidden(text="Generate speech from this site's own page.")
    return await handler(request)


async def prepare_response(request, response):
    # Runs before streamed audio headers are sent, including on the first login.
    response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                             "X-Content-Type-Options": "nosniff"})
    if request.get("new_session"):
        set_session(request, response)
        # aiohttp has already serialized cookies by this prepare hook.
        response.headers.add("Set-Cookie", response.cookies[SESSION_COOKIE].OutputString())


async def health(request):
    try:
        async with request.app["client"].get(request.app["upstream"] + "/v1/health",
                                              timeout=ClientTimeout(total=3)) as response:
            if response.status == 200:
                return web.json_response({"status": "ready", "model": "fishaudio/drama-3"})
    except (ClientError, OSError, asyncio.TimeoutError):
        pass
    return web.json_response({"status": "loading", "message": "Drama 3 is downloading or loading; check Pod logs."}, status=503)


async def bridge(request):
    if request.path == "/":
        return web.Response(status=302, headers={"Location": "/ui"})
    headers = {key: value for key, value in request.headers.items()
               if key.lower() not in HOP_HEADERS | {"authorization", "cookie", "accept-encoding"}}
    # Bound reference uploads; response audio remains streamed with backpressure.
    body = await request.read() if request.can_read_body else None
    try:
        async with request.app["client"].request(request.method,
                request.app["upstream"] + request.rel_url.path_qs,
                headers=headers, data=body, allow_redirects=False) as remote:
            result_headers = {key: value for key, value in remote.headers.items()
                              if key.lower() not in HOP_HEADERS | {"set-cookie"}}
            response = web.StreamResponse(status=remote.status, headers=result_headers)
            await response.prepare(request)
            async for chunk in remote.content.iter_chunked(64 * 1024):
                await response.write(chunk)
            await response.write_eof()
            return response
    except (ClientError, OSError, asyncio.TimeoutError) as error:
        logger.warning("Fish upstream unavailable: %s", type(error).__name__)
        if 'response' in locals() and response.prepared:
            # A truncated audio response must not be presented as a successful file.
            if request.transport:
                request.transport.close()
            return response
        raise web.HTTPServiceUnavailable(text="Drama 3 is loading or unavailable. Check RunPod logs and retry.") from None


async def client_context(app):
    async with ClientSession(timeout=ClientTimeout(total=None, sock_connect=10), auto_decompress=False) as session:
        app["client"] = session
        yield


def create_app(username=None, password=None, upstream="http://127.0.0.1:8090", public_origin=None,
               *, auth_required=None):
    if auth_required is None:
        auth_required = os.environ.get("WEB_AUTH_REQUIRED", "1") != "0"
    username = username or os.environ.get("WEB_USERNAME", "persona")  # Reuse the existing login.
    password = password or os.environ.get("WEB_PASSWORD", "")
    if auth_required and (len(password) < 16 or password.startswith("{{")):
        raise ValueError("Configure WEB_PASSWORD with at least 16 characters")
    if public_origin is None:
        public_origin = os.environ.get("PUBLIC_ORIGIN", "")
        if not public_origin and os.environ.get("RUNPOD_POD_ID"):
            public_origin = f"https://{os.environ['RUNPOD_POD_ID']}-8080.proxy.runpod.net"
    if public_origin:
        parsed = urlsplit(public_origin)
        if (parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username
                or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("PUBLIC_ORIGIN must be an exact HTTP(S) origin without a path")
    app = web.Application(middlewares=[authenticate], client_max_size=MAX_BODY)
    app.update(username=username, password=password, auth_required=auth_required, upstream=upstream,
               public_origin=public_origin, session_key=secrets.token_bytes(32))
    app.cleanup_ctx.append(client_context)
    app.on_response_prepare.append(prepare_response)
    app.router.add_get("/healthz", health)
    app.router.add_route("*", "/{path:.*}", bridge)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8080, access_log=None)
