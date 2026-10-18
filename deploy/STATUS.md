# Fish Drama 3 deployment status

Updated 2026-10-18. PersonaPlex has been replaced with official Fish Audio Drama 3.

**No Pod is currently running and no live browser URL exists.** The attempted
Community L40S Pod `omzyotzgavt78h` and its empty attached storage were deleted after
CUDA initialization failed. The account was checked afterward: zero Pods and zero
network volumes. Earlier usage was billable; deleting it ends ongoing resource costs.

The image started, but CUDA `cuInit` returned 999 and PyTorch reported no usable GPU.
The result was the same with the host R550 driver, the official compatibility
libraries, and explicit selection of the allocated GPU. Device mappings and UVM
nodes were present. No model weights were downloaded and no Drama 3 audio was
produced. See [failed-gpu-check.json](failed-gpu-check.json).

A native-compatible **Secure L40 at $0.82/hour GPU** was listed with host
CUDA 13.2, 250GB RAM and 32 vCPUs, but went out of stock on the latest check. Planned storage adds about $0.017/hour: roughly
$0.84/hour total. It exceeds the approved $0.79/hour GPU cap by $0.03/hour, so no
replacement has been created without further authorization. Matching GPU capacity
will also need to be rechecked before creation.

Verified without a GPU:

- 17 CPU tests passed: secure login/session cookies, proxy origins, streaming audio,
  JSON/multipart uploads, GPU guards, stock filtering and spending ceilings.
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
