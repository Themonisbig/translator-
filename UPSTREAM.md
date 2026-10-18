# Official Fish Audio Drama 3

The `vendor/fish-speech` snapshot is the unmodified official source:
https://github.com/fishaudio/fish-speech

- Source commit: `541566932abbaebcb0a40e562a1f846738383f38`.
- Model: https://huggingface.co/fishaudio/drama-3
- Model revision: `b2b5ee998034b2975720906c815e7fb0e9f007bd`.
- Official browser UI: `awesome_webui`, served by `tools/api_server.py` at `/ui`.
- Runtime: Python 3.12, Torch 2.8.0, CUDA 12.8, the official frozen `uv.lock`.
- Single GPU: NVIDIA SM89+ with 48GB-class VRAM. RTX 6000 Ada, L40 or L40S.
  The earlier A40 (SM86) would expand FP8 weights into BF16 and will not fit this
  single-GPU setup. Compilation stays disabled, as required by Drama 3.
- This is the 35B-A3B Drama 3 model, not S2-Pro and not the hosted Fish API.
- Checkpoints are downloaded at runtime to the persistent volume, never Git or images.

The code and Drama 3 model use the Fish Audio Community License v1.0, included in
[vendor/fish-speech/LICENSE](vendor/fish-speech/LICENSE). Personal non-commercial
experimentation is covered by that license; public hosted services and other
commercial uses can require a separate Fish Audio license. Read its terms before
expanding beyond this private demo. “Open weights” does not mean unrestricted use.

Our changes are only the Docker wrapper, authenticated HTTP gateway, lifecycle,
RunPod setup, documentation and tests. Upstream speech inference and browser UI
are unchanged. `deploy/api_server.py` selects CPU placement for the official DAC
codec in FP32 on 48GB hosts; the Drama 3 backbone and tower remain on CUDA. This keeps
long-clip decoding activations out of GPU memory without changing the model or
codec implementation. `deploy/check_runtime.py` honors the one protobuf constraint override
explicitly present in the official project, and rejects other missing/conflicting
runtime dependencies.

The previous PersonaPlex source and runtime have been removed. The existing public
GHCR package name `personaplex-voice` and RunPod secret names are retained as reusable
infrastructure; new image versions contain Fish Drama 3 only.
