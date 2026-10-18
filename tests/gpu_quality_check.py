"""Optional real GPU/HTTPS checks with CPU Whisper transcript cross-checks.

Run inside the GPU runtime with its existing secret bindings. Whisper tiny.en is
only a validation aid; the TTS server does not need or use a Whisper model.
"""
import asyncio
import base64
import io
import json
import os
import re
import time
from pathlib import Path

PLAIN_TEXT = "Hello world. My name is Alex. This is a voice test."
CASES = [
    ("plain", PLAIN_TEXT, 1234),
    ("energetic", "[excited] Wow, this is amazing! I am so happy today!", 2026),
    ("reference", "Today is a wonderful day. Welcome to the voice demo.", 1234),
]


def words(value):
    return re.findall(r"[a-z0-9]+", re.sub(r"\[[^]]*\]", "", value).lower())


async def main():
    import numpy as np
    import soundfile as sf
    import torch
    import torchaudio
    from aiohttp import BasicAuth, ClientSession, ClientTimeout
    from transformers import pipeline

    torch.set_num_threads(8)
    origin = os.environ.get("PUBLIC_ORIGIN") or f"https://{os.environ['RUNPOD_POD_ID']}-8080.proxy.runpod.net"
    async with ClientSession(timeout=ClientTimeout(total=600)) as client:
        for _ in range(360):
            try:
                async with client.get(origin + "/healthz", timeout=ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        break
            except (OSError, asyncio.TimeoutError):
                pass
            await asyncio.sleep(5)
        else:
            raise RuntimeError("readiness_timeout")

        auth_required = os.environ.get("WEB_AUTH_REQUIRED", "1") != "0"
        auth = BasicAuth(os.environ.get("WEB_USERNAME", "persona"), os.environ["WEB_PASSWORD"]) if auth_required else None
        async with client.get(origin + "/ui", auth=auth) as response:
            assert response.status == 200
            await response.read()
        async with client.get(origin + "/v1/tts/defaults") as response:
            assert (await response.json())["model_family"] == "drama3"
        asr = pipeline("automatic-speech-recognition", model="openai/whisper-tiny.en",
                       device=-1, dtype=torch.float32)
        cases = CASES[-1:] if os.environ.get("QUALITY_REFERENCE_ONLY") == "1" else CASES
        results = []
        for name, text, seed in cases:
            references = []
            if name == "reference":
                references = [{
                    "audio": base64.b64encode(Path("/workspace/fish-plain.wav").read_bytes()).decode(),
                    "text": PLAIN_TEXT,
                }]
            started = time.monotonic()
            async with client.post(origin + "/v1/tts", headers={"Origin": origin}, json={
                    "text": text, "format": "wav", "seed": seed, "references": references}) as response:
                if response.status != 200:
                    print("QUALITY_CASE_ERROR " + json.dumps({"case": name, "http": response.status}), flush=True)
                    raise RuntimeError("speech_request_failed")
                data = await response.read()
            elapsed = time.monotonic() - started
            samples, rate = sf.read(io.BytesIO(data), dtype="float32")
            assert len(samples) > rate and np.all(np.isfinite(samples)) and np.max(np.abs(samples)) > 0.001
            Path(f"/workspace/fish-{name}.wav").write_bytes(data)
            waveform = torchaudio.functional.resample(torch.from_numpy(samples), rate, 16000).numpy()
            transcript = asr({"array": waveform, "sampling_rate": 16000},
                             chunk_length_s=20, stride_length_s=3)["text"]
            result = {
                "case": name, "text": text, "seed": seed, "sample_rate": rate,
                "audio_seconds": round(len(samples) / rate, 2),
                "generation_seconds": round(elapsed, 2),
                "peak": round(float(np.max(np.abs(samples))), 4),
                "transcript": transcript, "transcript_matches": words(text) == words(transcript),
                "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            results.append(result)
            Path("/workspace/fish-quality-check.json").write_text(json.dumps(results, indent=2) + "\n")
            print("QUALITY_CASE " + json.dumps(result), flush=True)
        assert all(result["transcript_matches"] for result in results), "transcript_mismatch_requires_review"


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        print("QUALITY_ERROR " + type(error).__name__ + ": " + str(error)[:200], flush=True)
        raise SystemExit(1)
