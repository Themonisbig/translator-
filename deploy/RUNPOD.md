# RunPod deployment

## Hardware and costs

Use one **NVIDIA RTX 6000 Ada Generation**, **L40**, or **L40S**, with 48GB VRAM,
at least 64GB host RAM and 8 vCPUs. Drama 3's official FP8 kernels require SM89+.
A40 and RTX A6000 are SM86 and cannot run this single-GPU configuration.
Python 3.12 / Torch 2.8 / CUDA 12.8 follow the official dependency lockfile.
By default, the setup requires a host reporting CUDA 12.8 or newer. For datacenter
L40/L40S on R550/CUDA 12.4 hosts, `--cuda-forward-compat` selects the official
`cuda-compat-12-8` userspace driver already included by NVIDIA's base image, via
`/usr/local/cuda/compat`. NVIDIA's image driver checks remain enabled; no host
driver is changed. This option is restricted to L40/L40S, and real GPU testing is
still required. The default stock catalog view describes Secure Cloud; availability
must be scoped to `cloud=COMMUNITY` and the actual CUDA constraint.
Do not enable `--compile` for Drama 3.

On 2026-10-18, the lowest available compatible Community GPU quote was
**$0.74/hour** for RTX 6000 Ada initially; that stock then sold out. The latest
available compatible quote is **$0.79/hour for L40S**, above the previous authorized
budget. Prices and stock change. Check before creating; no higher rate is implicitly approved.

The script requests 80GB persistent `/workspace` (roughly 40GB model weights) and
40GB container disk. **Storage is billed separately.** The current official
[RunPod pricing](https://docs.runpod.io/pods/pricing) lists $0.10/GB/month for both
while running: about **$12/month equivalent**, or **$0.017/hour** for 120GB total.
With a $0.79 GPU, that is roughly **$0.81/hour while running**. A stopped 80GB volume
is $0.20/GB/month: **$16/month equivalent** while it remains. Billing is prorated;
RunPod's live creation quote is authoritative. Stopping ends GPU charges but leaves paid persistent storage.
Terminate/delete the Pod to delete its attached volume when finished. No network
volume is created. Deleting its model cache means downloading the weights again.

## Secure configuration

Keep the existing RunPod secrets:

- `personaplex_web`: existing private browser password, at least 16 characters.
- `personaplex_hf`: optional existing Hugging Face read token (public model).

Names are kept for reuse; the application now runs Fish. The script uses
`{{ RUNPOD_SECRET_name }}` references only. Do not paste secret values into code,
Docker build arguments, commands, logs or chat. Set `RUNPOD_API_KEY` securely in the
cloud environment if provisioning from there. No Fish hosted API credential is needed.

## Automated setup

First wait for a passing **CPU checks and container** run:
https://github.com/Themonisbig/translator-/actions

Use the immutable full commit tag from the successful container build:

```bash
python scripts/runpod_setup.py --quote --gpu 'NVIDIA L40S'
python scripts/runpod_setup.py --image ghcr.io/themonisbig/personaplex-voice:COMMIT_SHA
```

Both commands are read-only or dry-run. After explicitly approving a current GPU
rate, create exactly one Pod (example ceiling, not an authorization):

```bash
python scripts/runpod_setup.py \
  --image ghcr.io/themonisbig/personaplex-voice:COMMIT_SHA \
  --gpu 'NVIDIA L40S' --cuda-forward-compat \
  --max-hourly 0.79 --create --accept-billing
```

The legacy public image package is reused to avoid needing a new registry login.
New commit tags contain only Fish Drama 3, not PersonaPlex. Prefer immutable tags.
There are no automatic POST retries: if creation times out, inspect Pods before
retrying so you do not accidentally pay for duplicates.

The automatic stock/price check precedes creation but is not a contractual rate
reservation. Verify the resulting Pod quote in RunPod. Host RAM/CPU constraints can
reduce the available pool; a rejected allocation creates no usable deployment.

## Startup and browser

1. The image validates CUDA hardware, downloads the pinned public
   `fishaudio/drama-3` revision to `/workspace/checkpoints/drama-3`, then starts the
   official model server and authenticated gateway. First boot can take 10–30+
   minutes depending on image pull, download speed and model warmup.
2. Expose **8080 HTTP** only. RunPod Connect supplies
   `https://POD_ID-8080.proxy.runpod.net/ui` with managed TLS for desktop/mobile.
   The internal API on 8090 must stay private. No SSH port is requested.
3. Before the download finishes, the proxy may return 502 because the gateway
   has not started yet. Once it starts, `/healthz` returns 503 while the model
   warms up and 200 with `model: fishaudio/drama-3` when the official API is ready. Login is `persona` / your existing web password.
4. `RUN_GPU_SMOKE=1` runs a real speech request through the public HTTPS URL using
   the browser session cookie. Wait for **GPU_SMOKE_PASS** in logs before trying
   your own generation. It writes `/workspace/fish-gpu-check.json` and a WAV result.
   This validates actual model output, not subjective voice quality or every device.
5. In the official UI, enter a short sentence, optionally add voice references,
   choose wav/mp3, and generate. A new random voice may be chosen without a reference.
   Emotion tags include `[excited]`, `[whisper]`, `[angry]`, and `[laughing]`.

The gateway derives its exact public origin from `RUNPOD_POD_ID`. For a custom
HTTPS domain set `PUBLIC_ORIGIN=https://your-host` (no trailing slash). Login cookies
are HttpOnly, signed, Secure on HTTPS and SameSite Strict; mutating cross-origin
requests are blocked even when the hosting proxy rewrites Host.

## Troubleshooting and cleanup

- **503/loading:** check Pod logs for model download progress, disk space, CUDA
  errors or a failed secret binding. Do not create another Pod to retry.
- **401:** use the existing web password; refresh/re-login after a container restart.
- **403:** open the actual public `/ui` URL; ensure PUBLIC_ORIGIN matches its origin.
- **Generation fails:** inspect model logs, start with one short sentence and no
  reference, then try a clean reference with an exact transcript. Limit is 5,000
  text characters and 50MB per HTTP upload; model context limits also apply.
- **GPU_SMOKE_FAIL:** real inference has not passed. Inspect logs; do not treat a
  visible web page or successful container build as proof the model works.
- **Wrong GPU/VRAM:** use one of the supported cards; the launcher exits before a
  large download if hardware is unsuitable.
- **No further costs wanted:** terminate/delete the Pod, then inspect Pods and
  Storage for leftovers. Stopping alone keeps persistent-volume charges.

To build the image yourself: `bash scripts/build_image.sh` (Docker Buildx, about
15–25GB free disk). It needs no model token at build time. Inside the container,
`python /app/deploy/gpu_smoke.py` reruns the real public HTTPS synthesis check.
