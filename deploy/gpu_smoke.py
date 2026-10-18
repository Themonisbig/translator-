"""Opt-in real GPU synthesis through the public HTTPS endpoint. Never logs secrets."""
import asyncio
import io
import json
import os
import time
from pathlib import Path


async def run():
    import numpy as np
    import soundfile as sf
    from aiohttp import BasicAuth, ClientSession, ClientTimeout
    origin = os.environ.get("PUBLIC_ORIGIN") or f"https://{os.environ['RUNPOD_POD_ID']}-8080.proxy.runpod.net"
    async with ClientSession(timeout=ClientTimeout(total=600)) as client:
        deadline = time.monotonic() + 1800
        while True:
            try:
                async with client.get(origin + "/healthz", timeout=ClientTimeout(total=15)) as response:
                    if response.status == 200:
                        break
            except (OSError, asyncio.TimeoutError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("readiness_timeout")
            await asyncio.sleep(5)
        async with client.get(origin + "/ui", auth=BasicAuth(
                os.environ.get("WEB_USERNAME", "persona"), os.environ["WEB_PASSWORD"])) as response:
            if response.status != 200 or "fish_session" not in response.cookies:
                raise RuntimeError(f"browser_login_failed_http_{response.status}")
            await response.read()
        # Deliberately no Basic header: validate the same cookie used by the browser.
        async with client.get(origin + "/v1/tts/defaults") as response:
            defaults = await response.json()
            if defaults.get("model_family") != "drama3":
                raise RuntimeError("wrong_model_family")
        started = time.monotonic()
        async with client.post(origin + "/v1/tts", headers={"Origin": origin}, json={
                "text": "[excited] Hello! Fish Drama three is ready. Let's make something amazing!",
                "format": "wav", "seed": 42, "references": []}) as response:
            if response.status != 200:
                raise RuntimeError(f"tts_http_{response.status}")
            audio = await response.read()
        samples, rate = sf.read(io.BytesIO(audio), dtype="float32")
        peak = float(np.max(np.abs(samples))) if samples.size else 0.0
        if samples.size < rate or peak < 0.001 or not np.all(np.isfinite(samples)):
            raise RuntimeError("empty_silent_or_invalid_audio")
        output = Path("/workspace/fish-smoke.wav")
        output.write_bytes(audio)
        result = {"model": "fishaudio/drama-3", "public_https": True, "cookie_auth": True,
                  "sample_rate": rate, "audio_seconds": round(len(samples) / rate, 2),
                  "bytes": len(audio), "peak": round(peak, 4),
                  "generation_seconds": round(time.monotonic() - started, 2),
                  "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        Path("/workspace/fish-gpu-check.json").write_text(json.dumps(result, indent=2) + "\n")
        print("GPU_SMOKE_PASS " + json.dumps(result), flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as error:
        print("GPU_SMOKE_FAIL " + type(error).__name__ + ": " + str(error)[:160], flush=True)
        raise SystemExit(1)
