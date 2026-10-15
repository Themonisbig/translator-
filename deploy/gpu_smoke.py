"""Opt-in live HTTPS/WSS check against the deployed official GPU model.

Uses NVIDIA's checked-in audio fixture, never a simulated model. Credentials are
read only inside the Pod and are never logged. This is not a physical mic test.
"""
import asyncio
import json
import os
import time
import wave


async def run():
    import numpy as np
    import sphn
    from aiohttp import BasicAuth, ClientSession, ClientTimeout, WSMsgType

    origin = os.environ.get("PUBLIC_ORIGIN") or f"https://{os.environ['RUNPOD_POD_ID']}-8080.proxy.runpod.net"
    async with ClientSession(timeout=ClientTimeout(total=25)) as client:
        deadline = time.monotonic() + 1200
        while True:
            try:
                async with client.get(origin + "/healthz") as response:
                    if response.status == 200:
                        break
            except (OSError, asyncio.TimeoutError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("readiness_timeout")
            await asyncio.sleep(5)
        async with client.get(origin + "/", auth=BasicAuth(
                os.environ.get("WEB_USERNAME", "persona"), os.environ["WEB_PASSWORD"])) as response:
            if response.status != 200:
                raise RuntimeError(f"browser_login_http_{response.status}")
            if "personaplex_session" not in response.cookies:
                raise RuntimeError("browser_session_cookie_missing")
            await response.read()

        with wave.open("/app/smoke/input_assistant.wav") as source:
            if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (24000, 1, 2):
                raise RuntimeError("unsupported_test_fixture")
            samples = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(np.float32) / 32768
        samples = np.concatenate((samples, np.zeros(8 * 24000, dtype=np.float32)))
        params = {"voice_prompt": "NATF0.pt", "text_prompt":
                  "You are a wise and friendly teacher. Answer questions or provide advice in a clear and engaging way."}
        handshake = asyncio.Event()
        result = {"input_packets": 0, "output_audio_bytes": 0, "output_samples": 0,
                  "text_characters": 0, "audio_packets_during_input": 0, "peak": 0.0}
        sending = False
        # No Basic header here: validate the browser session cookie on WSS.
        async with client.ws_connect(origin.replace("https://", "wss://", 1) + "/api/chat",
                                     params=params, headers={"Origin": origin}, heartbeat=20) as ws:
            decoder = sphn.OpusStreamReader(24000)

            async def receive():
                async for message in ws:
                    if message.type != WSMsgType.BINARY or not message.data:
                        continue
                    kind, payload = message.data[0], message.data[1:]
                    if kind == 0:
                        handshake.set()
                    elif kind == 1:
                        result["output_audio_bytes"] += len(payload)
                        result["audio_packets_during_input"] += int(sending)
                        decoder.append_bytes(payload)
                        pcm = decoder.read_pcm()
                        result["output_samples"] += pcm.size
                        if pcm.size:
                            result["peak"] = max(result["peak"], float(np.max(np.abs(pcm))))
                    elif kind == 2:
                        result["text_characters"] += len(payload.decode("utf-8", errors="replace"))

            receiver = asyncio.create_task(receive())
            try:
                await asyncio.wait_for(handshake.wait(), timeout=120)
                print("GPU_SMOKE: authenticated WSS handshake passed; streaming official audio fixture", flush=True)
                encoder = sphn.OpusStreamWriter(24000)
                sending = True
                started = time.monotonic()
                for offset in range(0, samples.size, 1920):
                    if ws.closed:
                        raise RuntimeError("conversation_closed_while_sending")
                    encoder.append_pcm(samples[offset:offset + 1920])
                    packet = encoder.read_bytes()
                    if packet:
                        await ws.send_bytes(b"\x01" + packet)
                        result["input_packets"] += 1
                    # Preserve real-time duplex cadence rather than flooding GPU input.
                    await asyncio.sleep(max(0, started + (offset + 1920) / 24000 - time.monotonic()))
                sending = False
                await asyncio.sleep(3)
            finally:
                await ws.close()
                receiver.cancel()
                await asyncio.gather(receiver, return_exceptions=True)
        result["passed"] = bool(result["output_samples"] >= 24000 and result["text_characters"] > 0
                                and result["audio_packets_during_input"] > 0 and result["peak"] > 0.0001)
        print("GPU_SMOKE_RESULT: " + json.dumps(result), flush=True)
        if not result["passed"]:
            raise RuntimeError("generated_audio_checks_failed")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as error:
        # Exception reprs can contain request details; print only safe categories.
        status = getattr(error, "status", None)
        reason = str(error) if type(error) is RuntimeError else type(error).__name__
        print("GPU_SMOKE_FAILURE: " + json.dumps({"reason": reason, "http_status": status}), flush=True)
        raise SystemExit(1)
