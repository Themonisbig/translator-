# Fish Audio Drama 3 — private browser TTS on RunPod

Run the official **Fish Audio Drama 3 (35B-A3B)** model on a cloud NVIDIA GPU.
The official Fish browser demo lets you type expressive text, optionally upload
voice references with transcripts, then play or download generated speech.

This project now provides text-to-speech. The previous PersonaPlex conversation
app has been removed. A microphone conversation or automatic chatbot replies
would need additional speech-recognition and language-model components.

## Current readiness

See [deployment status](deploy/STATUS.md). CPU and browser fixture tests do not
prove GPU synthesis works. No live browser URL is claimed until the actual Drama 3
model has passed a GPU speech request.

## Try it after deployment

1. Open your Pod's **8080 HTTP** link from RunPod Connect (managed HTTPS), ending in `/ui`.
2. Sign in as **persona**, using the same web password stored in your existing
   RunPod `personaplex_web` secret.
3. Type a short sentence. For example: `[excited] Wow! This is absolutely amazing! [laughing] Let's go!`
4. Choose **wav** or **mp3**, then **Generate Audio**. Play or download the result.
5. For a particular voice, upload a short clean reference recording and its exact
   transcript. Use recordings you have permission to use. Speaker groups support
   multi-character scripts with `<|speaker:0|>` through `<|speaker:15|>`.

## Deploy

Follow [the RunPod guide](deploy/RUNPOD.md). A single 48GB **RTX 6000 Ada, L40 or L40S**
GPU is required. **A40 and RTX A6000 are unsuitable for this FP8 configuration.**
The setup script is dry-run by default, reuses existing secure bindings, and
checks stock and the current GPU quote against an explicit spending ceiling.
The previous $0.50/hour ceiling will reject current $0.74/hour compatible stock.

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
