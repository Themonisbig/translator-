"""Run Fish's unchanged server with optional CPU audio-codec placement.

Drama 3's FP8 speech model stays on CUDA. The official DAC implementation and
weights can run on host CPU, leaving GPU memory for long generated clips.
"auto" decodes short clips on the GPU and long ones on a CPU copy of the codec.
"""
import os
import runpy
import sys
from contextlib import nullcontext


def configure_codec_placement(manager, engine, device, float32, gpu_max_frames=256, oom_error=MemoryError):
    if device not in ("auto", "cpu", "cuda"):
        raise ValueError("FISH_CODEC_DEVICE must be auto, cpu or cuda")
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
    elif device == "auto":
        load_codec = manager.load_codec_model
        cpu_codec = []

        def load_on_both(checkpoint_path, gpu_device, precision):
            cpu_codec.append(load_codec(checkpoint_path, "cpu", float32))
            return load_codec(checkpoint_path, gpu_device, precision)

        manager.load_codec_model = load_on_both
        decode_on_gpu = engine.TTSInferenceEngine.decode_vq_tokens

        def decode_vq_tokens(self, codes):
            # Decoding memory grows with clip length (~0.7 GiB BF16 per 256 frames),
            # and 1024 frames exhausted a 48GB GPU next to the speech model.
            if codes.shape[-1] <= gpu_max_frames:
                try:
                    return decode_on_gpu(self, codes)
                except oom_error:
                    print(f"GPU codec out of memory at {codes.shape[-1]} frames; decoding on CPU.", flush=True)
            # The caller's CUDA autocast does not apply to CPU ops: this stays FP32.
            return cpu_codec[0].from_indices(codes.cpu()[None])[0].squeeze()

        engine.TTSInferenceEngine.decode_vq_tokens = decode_vq_tokens
        print(f"Fish DAC codec: CUDA up to {gpu_max_frames} frames, CPU FP32 beyond; "
              "Drama 3 speech model on CUDA.", flush=True)


if __name__ == "__main__":
    sys.path.insert(0, "/app/fish-speech")
    import torch
    import fish_speech.inference_engine as engine
    from tools.server import model_manager

    torch.set_num_threads(int(os.environ.get("FISH_CPU_THREADS", "8")))
    configure_codec_placement(model_manager, engine, os.environ.get("FISH_CODEC_DEVICE", "auto"), torch.float32,
                              int(os.environ.get("FISH_CODEC_GPU_MAX_FRAMES", "256")), torch.OutOfMemoryError)
    runpy.run_module("tools.api_server", run_name="__main__")
