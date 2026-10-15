# Current RunPod deployment

Status recorded on 2026-10-15.

- Active Pod: `0gsotvofrwom53`, `personaplex-voice`, EU-SE-1.
- GPU: one NVIDIA A40, approved and confirmed GPU rate **USD $0.59/hour**.
  Storage is billed separately: 80GB persistent volume and 30GB container disk.
- Browser address: https://0gsotvofrwom53-8080.proxy.runpod.net
- Login username: `persona`. Use the password in your RunPod `personaplex_web`
  secret. No credential values are recorded in this repository.
- Image: `ghcr.io/themonisbig/personaplex-voice:94287f5847a9012cc256f85e83e9e61f2755f15e`.
- Official model snapshot downloaded: `fdaf4090a61cb315c138a1faee287ffd6c716309`
  from `nvidia/personaplex-7b-v1`.

## Verified on the GPU

RunPod container logs confirm the updated password passed startup validation,
voice prompts downloaded, Mimi loaded, PersonaPlex 7B loaded, and official model
warmup completed. The upstream server then served the browser client on 8998;
the authenticated gateway started on 8080. Official warmup exercises audio
encoding, model generation and audio decoding on CUDA with synchronization.

The first failed Pod was stopped and then removed because its host could not
allocate a GPU on resume. Only the replacement above remains; do not create
additional Pods just to retry a browser connection.

## Remaining validation

This development environment's egress proxy returns CONNECT 403 for the RunPod
browser hostname. That is a block before reaching the application, not an observed
application error. The exact hostname has been saved in the environment network
draft. Review/save and publish that network change before retrying checks from
this environment.

External HTTPS readiness, browser authentication, a live microphone conversation,
interruption handling and physical-mobile audio have **not yet been verified**.
Model warmup is not a substitute for those end-to-end checks. Follow the GPU/browser
acceptance checklist in RUNPOD.md; do not claim live audio works until it passes.

The Pod is left running for the requested browser test. Stop it in RunPod when
finished to stop GPU charges; persistent storage may remain billable. Future
stop/start may require a new allocation if the host has no free GPUs.
