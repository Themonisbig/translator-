# Fish Audio Drama 3 — browser TTS on RunPod

**Built with Fish Audio.**

Run the official **Fish Audio Drama 3 (35B-A3B)** model on a cloud NVIDIA GPU.
The official Fish browser demo lets you type expressive text, optionally upload
voice references with transcripts, then play or download generated speech.

This project now provides text-to-speech. The previous PersonaPlex conversation
app has been removed. A microphone conversation or automatic chatbot replies
would need additional speech-recognition and language-model components.

## Current readiness

Real Drama 3 GPU synthesis has passed through the authenticated public HTTPS
endpoint. Plain and excited sentences matched their requested words in an
independent transcript check. See [deployment status and evidence](deploy/STATUS.md)
for the current Pod, build and measured timings. CPU/browser fixture checks are
listed separately from these real model tests.

## Try it after deployment

1. Open your Pod's **8080 HTTP** link from RunPod Connect (managed HTTPS), ending in `/ui`.
2. The current demo opens **without a login**, as requested. Anyone with its URL
   can use the paid GPU. Password protection remains available with `WEB_AUTH_REQUIRED=1`.
3. Type a short sentence. For example: `[excited] Wow, this is amazing! I am so happy today!`
4. Choose **wav** or **mp3**, then **Generate Audio**. Play or download the result.
5. For a particular voice, upload a short clean reference recording and its exact
   transcript. Use recordings you have permission to use. Speaker groups support
   multi-character scripts with `<|speaker:0|>` through `<|speaker:15|>`.

Start with one sentence. The tested short clips took about 8–15 seconds to
generate; longer clips take longer. Without a voice reference, output can vary
and occasionally reach the generation limit with extra silence. Clean references
and exact transcripts help keep a consistent voice. Transcript checks do not
measure acting quality or prove support for every browser/device.

## Deploy

Follow [the RunPod guide](deploy/RUNPOD.md). A single 48GB **RTX 6000 Ada, L40 or L40S**
GPU is required. **A40 and RTX A6000 are unsuitable for this FP8 configuration.**
The official audio codec uses the cloud CPU in FP32 to leave GPU memory for the
Drama 3 model. Your personal computer only runs the browser.
The setup script is dry-run by default, reuses existing secure bindings, and
checks stock and the current GPU quote against an explicit spending ceiling.
The script's conservative $0.50/hour default rejects current $0.82/hour native-compatible stock.

Public weights need no new Fish API key. An existing Hugging Face token is optional
for download rate limits. Never commit credentials. Only the authenticated gateway
on port 8080 is public; the model server listens on loopback port 8090.

## Local development and CPU checks

Requirements: Python 3.12 and Node 22+. This development machine needs no GPU for
these checks and does not download the model.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
bash scripts/check.sh
python -m playwright install --with-deps chromium
python tests/browser_gateway_check.py
```

In this managed cloud workspace, set `UV_CACHE_DIR=/workspace/.cache/uv` and
`NPM_CONFIG_CACHE=/workspace/.cache/npm` when using uv/npm because the home directory
is read-only. The browser check can use preinstalled system Chromium.

GitHub Actions runs the tests, builds the unmodified official browser UI and the
CUDA container, validates imports/CLI/runtime requirements, then publishes versioned
images to the existing public GHCR package. Model weights and API keys never enter CI.

See [upstream versions and license](UPSTREAM.md). Drama 3 is available under the
Fish Audio Community License, which has hosted-service and commercial restrictions.
