# Fish Drama 3 deployment status

Updated 2026-10-18. The PersonaPlex deployment has been replaced in this repository.
Previous PersonaPlex GPU results do not validate Fish Drama 3 and were removed.

- Official Fish Drama 3 source and model revisions pinned in [UPSTREAM.md](../UPSTREAM.md).
- Existing RunPod secret bindings and public container registry are reused.
- No Fish GPU Pod has been created. No live browser URL exists yet.
- No real Drama 3 GPU synthesis or voice-cloning test has run yet.
- Compatible Community RTX 6000 Ada was quoted at $0.74/hour but sold out.
  Latest available compatible stock: **L40S at $0.79/hour** plus roughly $0.017/hour
  storage (about $0.81/hour total). Creating it requires authorization above the
  earlier GPU budget; a cost approval question is pending.
- Planned attached storage: 80GB persistent model cache and 40GB container disk;
  there is no separately created network volume.

Verified without a GPU:

- 17 CPU tests passed: authentication, signed/expired cookies, proxy-origin handling,
  streaming audio transport, JSON/multipart uploads, hardware guards and spending limits.
- Official UI TypeScript/Vite production build passed.
- Actual Chromium at desktop (1280px) and mobile (390px) widths passed login,
  generation POST, test-tone WAV playback/download and visible generation failure.
- All 137 vendored upstream files match the official pinned source unchanged.
- RunPod inventory: zero Pods and zero network volumes at the time of this check.

The browser tests use a clearly labeled audio fixture. GPU inference remains untested.
The CUDA container build, dependency checks, official server CLI and model imports
passed in [GitHub Actions](https://github.com/Themonisbig/translator-/actions/runs/39123136762).
The published image is anonymously pullable:

`ghcr.io/themonisbig/personaplex-voice:a51dee1947871d662ddc76b46f6270dbf9fd72a5`

OCI index digest: `sha256:35dda70e8b9a976c8bff388d2eb56eba7a5cedc48e330d1ef06fa6e06697d2f3`.

The deployment payload was also validated against the current official RunPod v2
OpenAPI schema, including a minimum host CUDA version of 12.8. The latest script
and 17 CPU tests passed after adding that host compatibility constraint.

To deploy after authorizing the higher current rate, use the immutable image above
with the commands in [the RunPod guide](RUNPOD.md). GPU synthesis and the live HTTPS
URL remain pending paid deployment; the prior PersonaPlex audio check is not reused.
