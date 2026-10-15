# Official implementation provenance

Vendored from https://github.com/NVIDIA/personaplex at commit
`3428dfd95309a7f3c84fd93259ded0f810d1ff91` (inspected 2026-10-15).
Upstream MIT license is retained at vendor/personaplex/LICENSE-MIT.
Model weights are not included; accept the NVIDIA Open Model license on
https://huggingface.co/nvidia/personaplex-7b-v1 before using them.

The model, inference server, Opus protocol, audio encoder/decoder, and streaming
architecture are unchanged. Browser-only changes: energetic prompt preset,
mobile layout, microphone/audio startup error, microphone track cleanup,
same-origin WebSocket address and /api configuration default, connection timeout/status and stop controls.
The original unmodified browser client was built successfully before modifications.

RunPod provisioning payload follows official runpod/runpod-python SDK source,
commit `1d7ae99f4e478fa932ec616b0ac7fe18998a78c6`, specifically
runpod/api/ctl_commands.py:create_pod and runpod/api/rest.py.
It uses the current `/v2/pods` API at api.runpod.io, not older REST v1 examples.
The live RunPod API and secret interpolation remain unvalidated without access.
