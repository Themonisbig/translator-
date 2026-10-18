# Fish Drama 3 deployment status

Updated 2026-10-18. The PersonaPlex deployment has been replaced in this repository.
Previous PersonaPlex GPU results do not validate Fish Drama 3 and were removed.

- Official Fish Drama 3 source and model revisions pinned in [UPSTREAM.md](../UPSTREAM.md).
- Existing RunPod secret bindings and public container registry are reused.
- No Fish GPU Pod has been created. No live browser URL exists yet.
- No real Drama 3 GPU synthesis or voice-cloning test has run yet.
- Compatible Community RTX 6000 Ada stock was quoted at $0.74/hour plus storage.
  Creating it requires authorization above the earlier $0.50/hour GPU ceiling.
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
The CUDA container build/publication is pending GitHub Actions.
