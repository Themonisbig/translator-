# Fish Drama 3 deployment status

Updated **2026-10-18, 13:08 UTC**. Official Fish Drama 3 is deployed and generating
speech on the cloud GPU. PersonaPlex has been replaced.

**Open the private demo:** https://v44qwhhq2i3ivi-8080.proxy.runpod.net/ui

**No login is required**, as authorized by the user (`WEB_AUTH_REQUIRED=0`). Anyone
with this URL can use the paid GPU. Existing secret bindings are retained for
optional password protection later. Anonymous HTTPS speech generation passed;
see [public-access-check.json](public-access-check.json) for current-image evidence.
Enter a short sentence, select **wav**, then **Generate Audio** and play the result.
For expressive speech try `[excited] Wow, this is amazing! I am so happy today!`.
Voice references with exact transcripts are supported by the official UI.

## Pending speed change (not yet deployed)

The audio decoder can now run on the GPU (`FISH_CODEC_DEVICE=auto`). Decoding on the
CPU was the largest part of each request: about 5.5 s of CPU time for the 4.37 s test
clip, measured on 4 CPU threads. Chunks over 256 frames (about 12 s) still decode on the CPU, and so does any chunk
that runs the GPU out of memory. It is tested on CPU against the real engine and codec
architecture, but **not yet on the GPU**. The running Pod still uses the image below
with `FISH_CODEC_DEVICE=cpu`. To deploy it, use the new image and set the Pod's
`FISH_CODEC_DEVICE` to `auto`.

## Active resources and cost

One Pod: **`v44qwhhq2i3ivi`**, Secure Cloud **NVIDIA L40**, US-KS-2, native host CUDA
13.0, 250GB host RAM, 32 vCPUs. Confirmed GPU rate **$0.82/hour**, within the user's
explicit approval. 80GB persistent `/workspace` plus 40GB container disk add about
$0.017/hour while running: approximately **$0.84/hour total**. GPU billing is active.

Stopping ends GPU charges but retains the 80GB volume at about **$16/month**
(prorated). Terminating/deleting removes the attached storage and model cache.
There is no network volume created by this project. Keep existing secret bindings.

## Actual GPU evidence

The initial image (`ed0f502…`) passed real speech requests through public HTTPS with
the same login cookie used by the browser. An independent CPU Whisper tiny.en
cross-check matched the words in all three clips:

| Check | Audio length | Generation time | Transcript |
| --- | ---: | ---: | --- |
| Plain speech | 4.37 s | 7.93 s | Exact normalized words matched |
| Excited speech | 8.22 s | 12.54 s | Exact normalized words matched |
| Synthetic voice reference | 3.81 s | 8.08 s | Exact normalized words matched |

Outputs were finite, non-silent, valid **44,100 Hz WAV** audio. The plain clip was
reused as reference audio with its transcript for the third request. This verifies
reference encoding and conditioned synthesis, not subjective voice similarity.
See the complete requests, results, timestamps and pinned versions in
[gpu-check.json](gpu-check.json). The repeatable optional test is
[tests/gpu_quality_check.py](../tests/gpu_quality_check.py).

Initial GPU codec decoding failed at 1024 frames due to VRAM exhaustion, including
with CUDA graphs disabled. The final profile runs the unchanged official DAC
codec in **FP32 on the cloud CPU**, and keeps the Drama 3 FP8 backbone and tower
on CUDA with graphs enabled. GPU peak in these requests was about **37.5 GiB**.
CPU BF16 was too slow on this host, so CPU autocasting is disabled for the codec.

A separate 1024-frame stress request also returned a valid 47.55-second WAV in
71.69 seconds with this adapter before the final image was published. That seeded
sample reached the frame limit with extra silence; its word accuracy was not
validated. It establishes memory behavior only. Without a reference, output and
voice can vary; start with short sentences and retry or supply a clean reference.

## Other verified checks and limits

- **22 CPU tests passed:** optional login/cookies, anonymous UI/API access, origin checks across a proxy,
  streaming, uploads, GPU guards, stock/price ceilings and codec placement.
- Official TypeScript/Vite production build passed.
- Chromium at 1280px and 390px passed both protected and no-login modes, generation
  POST, WAV playback, downloads and visible errors using fixture audio. These were not GPU model tests.
- All **137 vendored files** match the pinned official source unchanged.
- Final CUDA image dependency checks, official CLI, adapter CLI and model imports
  passed in [GitHub Actions](https://github.com/Themonisbig/translator-/actions/runs/39129295591).
- The RunPod deployment payload matches the current v2 schema. Native CUDA stock
  filtering and the spending ceiling prevent incompatible or over-budget creation.

Real GPU speech was checked through HTTPS API requests; browser UI playback was
checked separately with fixtures. Physical phones, every audio format, long
paragraphs, concurrent users and subjective acting/voice similarity remain untested.

## Reproducible deployment

Public image, verified anonymously pullable and running on the Pod:

`ghcr.io/themonisbig/personaplex-voice:963aa190e0d91221d223a9eabb53280ae99182f5`

OCI index: `sha256:3fa5299d45b30fd88c832cd9b62bc479db148895fbbe853682ec2df4c8b835b5`.

Normal startup is `python /app/deploy/launch.py`; no temporary model-code override
is needed. Model weights are cached in `/workspace/checkpoints/drama-3`. Existing
registry and secret names are retained for reuse. Follow [RUNPOD.md](RUNPOD.md)
for redeployment, startup, authentication and cleanup, and [UPSTREAM.md](../UPSTREAM.md)
for exact versions and the Fish Audio Community License.

The failed Community L40S Pod `omzyotzgavt78h` and its empty storage were deleted.
Its CUDA failure is recorded in [failed-gpu-check.json](failed-gpu-check.json).
Do not create a second Pod while this one is running.
