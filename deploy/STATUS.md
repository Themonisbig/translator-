# Fish Drama 3 deployment status

Updated 2026-10-18. PersonaPlex has been replaced with official Fish Audio Drama 3.

**Active Pod: `v44qwhhq2i3ivi`, one Secure Cloud NVIDIA L40 in US-KS-2.**
The user approved up to $0.82/hour GPU plus storage; the actual GPU rate is confirmed
at **$0.82/hour**. Attached storage: 80GB persistent plus 40GB container disk, adding
about $0.017/hour while running (roughly $0.84/hour total). GPU billing is active.

Native host CUDA: **13.0**, meeting the image's CUDA 12.8 requirement. Host RAM:
250GB; vCPUs: 32. The pinned official model is downloaded and loads on CUDA.
Initial public HTTPS requests generated audio tokens but failed during GPU DAC
decoding with out-of-memory errors at 1024 frames, with graphs enabled and disabled.
The deployment is now testing official DAC CPU FP32 decoding, retaining the speech
model and audio-token tower on CUDA. Do not create duplicate Pods.

Browser address (login and UI validated; successful speech still pending):
https://v44qwhhq2i3ivi-8080.proxy.runpod.net/ui

Login: `persona` with your existing RunPod `personaplex_web` password.
No Drama 3 speech has passed a GPU test yet; wait for the actual GPU smoke result.

The earlier Community L40S Pod `omzyotzgavt78h` and its empty storage were deleted
after CUDA initialization failed, before any model download or audio generation.
See [failed-gpu-check.json](failed-gpu-check.json). This replacement uses native
CUDA support and the normal NVIDIA driver path.

Verified without a GPU:

- 20 CPU tests passed: secure login/session cookies, proxy origins, streaming audio,
  JSON/multipart uploads, GPU guards, stock filtering, spending ceilings and codec placement.
- Official UI TypeScript/Vite production build passed.
- Chromium at 1280px and 390px passed login, generation POST, test-tone WAV playback,
  downloads and visible errors. These are fixtures, not model inference.
- All 137 vendored files match the pinned official Fish source unchanged.
- CUDA container dependency checks, official CLI and model imports passed in
  [GitHub Actions](https://github.com/Themonisbig/translator-/actions/runs/39123136762).
- The deployment payload validates against the current official RunPod v2 schema.

Public, anonymously pullable image:

`ghcr.io/themonisbig/personaplex-voice:a51dee1947871d662ddc76b46f6270dbf9fd72a5`

OCI index digest: `sha256:35dda70e8b9a976c8bff388d2eb56eba7a5cedc48e330d1ef06fa6e06697d2f3`.

The existing registry name and RunPod secret bindings are retained for reuse.
See [the RunPod guide](RUNPOD.md) and [upstream versions/license](../UPSTREAM.md).
The script now defaults to Secure L40 and requires native CUDA 12.8+ inventory.
Its default spending ceiling stays conservatively at $0.50/hour until explicitly
raised for a paid creation. GPU synthesis remains unverified.
