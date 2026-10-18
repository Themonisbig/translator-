"""Download pinned Drama 3 weights and supervise the official API plus gateway."""
import asyncio
import os
import signal
import sys
from pathlib import Path

MODEL_ID = "fishaudio/drama-3"
MODEL_REVISION = "b2b5ee998034b2975720906c815e7fb0e9f007bd"


def validate_gpu(torch):
    if not torch.cuda.is_available():
        raise RuntimeError("Drama 3 requires an NVIDIA CUDA GPU. This machine has no usable CUDA GPU.")
    if torch.cuda.get_device_capability() < (8, 9):
        raise RuntimeError("Single-GPU Drama 3 FP8 needs SM89+: RTX 6000 Ada / L40 / L40S. A40 and RTX A6000 cannot run this configuration.")
    if torch.cuda.get_device_properties(0).total_memory < 44 * 1024**3:
        raise RuntimeError("Drama 3 requires a 48GB-class GPU or larger.")


async def main():
    password = os.environ.get("WEB_PASSWORD", "")
    if len(password) < 16 or password.startswith("{{"):
        raise SystemExit("Bind WEB_PASSWORD to the existing RunPod web secret (at least 16 characters).")
    import torch
    validate_gpu(torch)
    from huggingface_hub import snapshot_download
    checkpoint = Path(os.environ.get("MODEL_DIR", "/workspace/checkpoints/drama-3"))
    checkpoint.mkdir(parents=True, exist_ok=True)
    print(f"Downloading/verifying {MODEL_ID} revision {MODEL_REVISION}; first startup needs roughly 40GB of weights.", flush=True)
    # Public, ungated weights; HF_TOKEN is optional and supplied only at runtime.
    await asyncio.to_thread(snapshot_download, repo_id=MODEL_ID, revision=MODEL_REVISION,
                            local_dir=str(checkpoint))
    if not (checkpoint / "codec.pth").is_file():
        raise RuntimeError("Pinned model snapshot is missing codec.pth")
    os.environ["FISH_DRAMA3_FP8_EXPERTS"] = "1"
    command = [sys.executable, "tools/api_server.py", "--listen", "127.0.0.1:8090",
               "--llama-checkpoint-path", str(checkpoint), "--device", "cuda:0",
               "--max-text-length", os.environ.get("MAX_TEXT_LENGTH", "5000"), "--workers", "1"]
    children = []
    smoke = None
    tasks = []
    def stop():
        for child in children:
            if child.returncode is None:
                child.terminate()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop)
    try:
        # Start the login/readiness gateway even while the official model warms up.
        children.append(await asyncio.create_subprocess_exec(sys.executable, "/app/deploy/gateway.py"))
        children.append(await asyncio.create_subprocess_exec(*command, cwd="/app/fish-speech"))
        tasks = [asyncio.create_task(child.wait()) for child in children]
        if os.environ.get("RUN_GPU_SMOKE") == "1":
            smoke = await asyncio.create_subprocess_exec(sys.executable, "/app/deploy/gpu_smoke.py")
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        code = next(iter(done)).result()
    finally:
        stop()
        if smoke is not None and smoke.returncode is None:
            smoke.terminate()
            await smoke.wait()
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=20)
        except asyncio.TimeoutError:
            for child in children:
                if child.returncode is None:
                    child.kill()
            await asyncio.gather(*tasks)
    return code or 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
