"""Run Fish's unchanged server with optional CPU audio-codec placement.

Drama 3's FP8 speech model stays on CUDA. The official DAC implementation and
weights can run on host CPU, leaving GPU memory for long generated clips.
"""
import os
import runpy
import sys
from contextlib import nullcontext


def configure_codec_placement(manager, engine, device, float32):
    if device not in ("cpu", "cuda"):
        raise ValueError("FISH_CODEC_DEVICE must be cpu or cuda")
    if device == "cpu":
        load_codec = manager.load_codec_model

        def load_on_cpu(checkpoint_path, _device, _precision):
            return load_codec(checkpoint_path, "cpu", float32)

        manager.load_codec_model = load_on_cpu
        original_autocast = engine.autocast_exclude_mps

        def codec_autocast(device_type, dtype):
            # BF16 CPU convolutions are very slow on hosts without native support.
            if device_type == "cpu":
                return nullcontext()
            return original_autocast(device_type, dtype)

        engine.autocast_exclude_mps = codec_autocast
        print("Fish DAC codec: CPU FP32; Drama 3 speech model remains on CUDA.", flush=True)


if __name__ == "__main__":
    sys.path.insert(0, "/app/fish-speech")
    import torch
    import fish_speech.inference_engine as engine
    from tools.server import model_manager

    torch.set_num_threads(int(os.environ.get("FISH_CPU_THREADS", "8")))
    configure_codec_placement(model_manager, engine, os.environ.get("FISH_CODEC_DEVICE", "cpu"), torch.float32)
    runpy.run_module("tools.api_server", run_name="__main__")
