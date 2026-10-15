"""Supervise the official inference server and authenticated browser gateway."""
import asyncio
import os
import signal
import sys
from pathlib import Path

async def main():
    for name in ("HF_TOKEN", "WEB_PASSWORD"):
        value = os.environ.get(name, "")
        if not value or value.startswith("{{"):
            raise SystemExit(f"Missing runtime secret: {name}. Configure RunPod secrets.")
    if len(os.environ["WEB_PASSWORD"]) < 16:
        raise SystemExit("WEB_PASSWORD must contain at least 16 characters.")
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPU unavailable. Deploy on an NVIDIA RunPod GPU Pod.")
    major, _ = torch.cuda.get_device_capability()
    if major >= 10:
        raise SystemExit("Blackwell is not supported by this CUDA 12.4 image; use Ampere/Ada/Hopper.")
    Path(os.environ.get("HF_HOME", "/workspace/huggingface")).mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "moshi.server", "--host", "127.0.0.1",
               "--port", "8998", "--static", "/app/client/dist",
               "--hf-repo", "nvidia/personaplex-7b-v1"]
    children = [await asyncio.create_subprocess_exec(*command),
                await asyncio.create_subprocess_exec(sys.executable, "/app/deploy/gateway.py")]
    tasks = [asyncio.create_task(p.wait()) for p in children]
    smoke = None
    if os.environ.get("RUN_GPU_SMOKE") == "1":
        smoke = await asyncio.create_subprocess_exec(sys.executable, "/app/deploy/gpu_smoke.py")
    loop = asyncio.get_running_loop()
    def stop():
        for p in children:
            if p.returncode is None:
                p.terminate()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop)
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        code = next(iter(done)).result()
    finally:
        stop()
        if smoke is not None and smoke.returncode is None:
            smoke.terminate()
            await smoke.wait()
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=15)
        except asyncio.TimeoutError:
            for p in children:
                if p.returncode is None:
                    p.kill()
            await asyncio.gather(*tasks)
    return code or 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
