# RunPod deployment

## 1. Personal authorization and secrets

These steps require your accounts and cannot be completed by code alone:

- Sign in to Hugging Face and accept the NVIDIA license for
  https://huggingface.co/nvidia/personaplex-7b-v1. Create a read token authorized
  for that gated model.
- Enable RunPod billing and review the current hourly GPU and storage rates.
- In RunPod's secret manager, create `personaplex_hf` with the Hugging Face token,
  and `personaplex_web` with a randomly generated password of at least 16 characters.
  The Pod environment references these as `{{ RUNPOD_SECRET_personaplex_hf }}`
  and `{{ RUNPOD_SECRET_personaplex_web }}`. Verify that your RunPod template/API
  resolves those references. If your RunPod interface uses a secret picker, bind
  the secrets using that picker rather than putting literal values into scripts.
- If using automated creation, make a RunPod API key and inject it securely as
  `RUNPOD_API_KEY` in the machine running the setup script. It is **not** needed
  inside the inference Pod. Do not send tokens or passwords in chat.

The script does not upload or invent secret values. Unresolved secret placeholders
cause startup to fail with a useful message instead of treating them as credentials.

## 2. Build and publish the container

The repository's GitHub Actions workflow runs CPU/browser checks, then builds and
pushes `ghcr.io/themonisbig/personaplex-voice:main` and a commit-SHA tag on main.
Check the Actions run actually succeeds before attempting deployment. GitHub
Packages may initially be private: make this package public in its settings, or
configure a RunPod registry credential for private image pulls. Registry credentials
must not be inserted into the image name or repository files.

Alternatively, build on any cloud Docker builder (no GPU or model token required):

```bash
docker build -t ghcr.io/themonisbig/personaplex-voice:main .
# Authenticate to GHCR securely using your platform's secret storage, then:
docker push ghcr.io/themonisbig/personaplex-voice:main
```

Prefer the immutable commit tag or digest for actual deployment. The CUDA image
is large; allow sufficient image build/pull time and 30+ GB container storage.

## 3. Provision

Default: one **NVIDIA A40 48GB**, Secure Cloud, at least 8 vCPUs/48GB host RAM,
30GB container disk and 80GB persistent volume mounted at `/workspace`.
48GB is a conservative deployment choice, not a claimed official minimum.
A6000, L40S, A100 80GB and H100 80GB are alternatives; availability and pricing vary.
Do not select Blackwell/RTX 5090 for this image: NVIDIA's README documents a separate
CUDA 13/PyTorch install path that conflicts with the pinned PyTorch <2.5 dependency.
No CPU offload is enabled by default to preserve the intended real-time workflow.

Inspect the safe offline plan:

```bash
python3 scripts/runpod_setup.py --image ghcr.io/themonisbig/personaplex-voice:COMMIT_SHA
```

After confirming image visibility, secret bindings, available GPU and current rates:

```bash
python3 scripts/runpod_setup.py \
  --image ghcr.io/themonisbig/personaplex-voice:COMMIT_SHA \
  --create --accept-billing
```

This creates a **billable** GPU Pod. It does not enforce a monetary budget or
retry a failed creation request. If the request times out, inspect your RunPod Pods
before retrying: creation may already have succeeded. It does not auto-delete your
Pod or storage. The API request shape was checked against current official SDK
source, but live provisioning and secret resolution require validation on your account.

If API access is unavailable, create a Pod in RunPod's dashboard with the same image,
GPU/storage settings and environment bindings:

| Variable | Value/source |
| --- | --- |
| `HF_TOKEN` | Hugging Face secret binding |
| `WEB_PASSWORD` | Browser-password secret binding |
| `WEB_USERNAME` | `persona` |
| `HF_HOME` | `/workspace/huggingface` |

Expose **8080 HTTP only**, not raw inference port 8998 or a public TCP port.
Keep the image's default command. No SSH or nested Docker daemon is needed in the Pod.
A Pod volume survives stop/start but is normally lost on termination; use a network
volume if you need cache persistence across replacing Pods. Cached gated model files
remain sensitive to the model license and should not be made public.

## 4. Readiness and HTTPS

Watch Pod logs for successful downloads, CUDA model loading/warmup and server startup.
The first start downloads gated model and voice assets; it can take many minutes.
`HF_TOKEN` must be authorized for the accepted model license. Model errors stop the
supervisor so the service does not remain falsely healthy.

In RunPod **Connect**, select HTTP service port 8080. Its managed proxy supplies a
trusted HTTPS URL, usually `https://POD_ID-8080.proxy.runpod.net`. A printed pattern
is not proof of deployment; use the URL RunPod actually provides.

```bash
curl --fail https://YOUR_ACTUAL_RUNPOD_HOST/healthz
# Expected once model warmup is complete: {"status": "ready"}
python3 scripts/runpod_setup.py --status YOUR_POD_ID
```

Health is intentionally unauthenticated and contains no prompts/credentials. It
verifies upstream HTTP availability after official model warmup; **it does not
verify generated audio**. All browser assets and the chat WebSocket require browser
Basic authentication. Username is `persona`; password comes from `personaplex_web`.
The browser caches Basic credentials; close the browser session or rotate the secret
to revoke access. Use only the HTTPS URL for remote access.

## 5. Required GPU/browser acceptance test (not yet executed)

1. Confirm GPU allocation and CUDA startup in logs, then `/healthz` returns ready.
2. Open HTTPS on desktop, authenticate, choose NATF0 and the default assistant prompt.
3. Click Start conversation, grant microphone permission, confirm status reaches
   connected and the AI produces intelligible spoken responses to your live speech.
4. Speak while the AI is speaking; verify it listens and handles interruptions
   without waiting for a manual recording turn. Test pauses and backchannels.
5. Stop; confirm microphone use ends. Start again with NATM1 and the energetic,
   funny, hyperactive preset; confirm voice/style changes.
6. Repeat from real mobile Safari/Chrome over HTTPS. Confirm playback unlocks
   after the user gesture, microphone permission works and no horizontal overflow
   prevents controls. CPU tests use mobile viewport sizes, not physical devices.
7. Disconnect/reconnect the network; verify visible status/error and successful retry.

Record GPU type, image SHA, readiness, each result and any latency/voice issues.
Do not label full-duplex audio working until these tests pass on a GPU.

## Troubleshooting and costs

- **401 login:** use the browser password, not your Hugging Face token.
- **503/loading:** inspect logs; downloads/warmup may still be running.
- **HF 401/403/gated model:** accept the license and check token access/secret binding.
- **CUDA unavailable:** use a GPU Pod with NVIDIA runtime, not a CPU instance.
- **OOM:** switch to a supported higher-memory GPU. CPU offload is an official
  option but is not configured or tested here and may affect real-time speed.
- **WebSocket fails:** only expose 8080 through the HTTPS proxy; check auth and model
  logs. One concurrent conversation is supported; other sessions may wait/time out.
- **No microphone:** use HTTPS, permit microphone access, and test a current browser.
- **Echo/feedback:** wear headphones; keep browser audio processing enabled.
- Stop the Pod in RunPod after testing to stop GPU charges. Storage may still incur
  charges while stopped. Terminate/delete only after preserving any wanted cache or
  recordings and reviewing what storage will be destroyed.

## Builds behind an enterprise TLS proxy

Normal cloud builders need no special flags. In a restricted environment, pass the
platform's trusted public CA certificate through the optional BuildKit `build_ca`
secret and forward the supported proxy variables. This preserves certificate
verification and does not embed proxy credentials or the extra CA in the image:

```bash
docker build --build-arg HTTP_PROXY --build-arg HTTPS_PROXY --build-arg NO_PROXY \
  --secret id=build_ca,src=/path/to/trusted-proxy-ca.crt -t personaplex-voice .
```

If the build daemon cannot resolve the proxy hostname, configure the builder's
network/DNS using the platform-provided proxy address. Never disable TLS, npm
integrity checks or package signature verification.
