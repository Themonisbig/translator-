# Current RunPod deployment

Verified on 2026-10-15.

- Active Pod: `0gsotvofrwom53`, `personaplex-voice`, EU-SE-1, one NVIDIA A40.
- Approved and confirmed GPU rate: **USD $0.59/hour**, plus storage.
- Storage: 80GB persistent `/workspace` and 30GB container disk.
- Browser address: https://0gsotvofrwom53-8080.proxy.runpod.net
- Username: `persona`. Use your existing RunPod `personaplex_web` password.
- Image: `ghcr.io/themonisbig/personaplex-voice:10af0f09fadbdfaf0ee705c31a448944209f9777`.
- [Passing CPU/browser checks and container build](https://github.com/Themonisbig/translator-/actions/runs/38797655684).
- Official model snapshot: `fdaf4090a61cb315c138a1faee287ffd6c716309`,
  `nvidia/personaplex-7b-v1`. Inference source remains unchanged.

## Browser connection fix

The gateway now validates the configured public origin across proxy Host rewriting.
HTTP Basic login establishes a signed HttpOnly session cookie, so the WebSocket
can authenticate even if the browser or proxy omits its Basic login header.
`PUBLIC_ORIGIN` is set to the actual public HTTPS origin. Refresh the page after
this update; sign in again if prompted, then click Start conversation.

Sixteen CPU checks and a real-browser regression test cover the rewritten host,
session-cookie WebSocket login, microphone packets and stopping the conversation.
These use a protocol fixture and are separate from the real GPU validation below.

## Verified against the actual GPU service

The opt-in test ran inside the Pod using its runtime credentials, with normal TLS
verification, through the **public HTTPS/WSS URL**. It passed health readiness,
HTTP login, the session-cookie WebSocket handshake and streamed NVIDIA's checked-in
audio fixture to the official GPU model at real-time cadence. Returned Opus audio
was decoded to non-silent PCM. No credentials or audio contents were logged.

Results in [last-gpu-check.json](last-gpu-check.json):

- 600 input packets; 124,275 generated audio bytes.
- 1,146,240 decoded samples at 24 kHz: **47.76 seconds** of generated audio.
- 466 text characters returned.
- 599 audio packets arrived while input was still streaming.
- PCM peak: 0.4064; overall result **passed**.

`RUN_GPU_SMOKE=1` enables this check after startup. It occupies the single active
conversation for about a minute after warmup. Wait for GPU_SMOKE_RESULT before
starting a personal conversation following a future restart.

## Remaining user-device checks

A physical microphone conversation, subjective voice quality, natural interruption
handling and physical mobile microphone/playback still need user testing. The
successful prerecorded streaming check does not establish those behaviors.
Choose a voice/personality, click Start conversation, grant microphone access, and
use headphones. Stop the conversation before changing voice or personality.

This development machine still has an egress restriction for the browser hostname;
public HTTPS/WSS validation was performed successfully from the GPU Pod instead.
That local restriction does not prevent browser access from your own device.

Only this Pod remains active. It is intentionally left running for user testing.
Stop the Pod in RunPod when finished to stop GPU charges; persistent storage may
remain billable. Future stop/start can require a new allocation if the host has
no free GPUs. Do not create a duplicate Pod just to retry a browser connection.
