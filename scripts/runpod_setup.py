#!/usr/bin/env python3
"""Plan or provision a Drama 3 GPU Pod, with a checked hourly price ceiling."""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.runpod.io/v2"

def secret_ref(name):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("Secret names must be letters, digits and underscores")
    return "{{ RUNPOD_SECRET_" + name + " }}"

COMPATIBLE_GPUS = ("NVIDIA RTX 6000 Ada Generation", "NVIDIA L40", "NVIDIA L40S")


def build_payload(image, gpu=COMPATIBLE_GPUS[0], hf_secret="personaplex_hf", web_secret="personaplex_web", cloud="COMMUNITY", auth_required=True):
    if not re.fullmatch(r"[a-z0-9][a-z0-9./_-]*(?::[A-Za-z0-9_.-]+|@sha256:[a-f0-9]{64})", image):
        raise ValueError("Supply a tagged or digest-pinned registry image, without credentials")
    if gpu not in COMPATIBLE_GPUS:
        raise ValueError("Choose a supported 48GB SM89+ GPU: RTX 6000 Ada, L40 or L40S")
    if cloud not in ("COMMUNITY", "SECURE"):
        raise ValueError("Choose COMMUNITY or SECURE cloud")
    env = {"WEB_PASSWORD": secret_ref(web_secret), "WEB_USERNAME": "persona",
           "HF_HOME": "/workspace/huggingface", "MODEL_DIR": "/workspace/checkpoints/drama-3",
           "FISH_DRAMA3_FP8_EXPERTS": "1", "FISH_DRAMA3_CUDA_GRAPH": "1",
           "FISH_CODEC_DEVICE": "cpu", "FISH_CPU_THREADS": "8",
           "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True", "RUN_GPU_SMOKE": "1"}
    if hf_secret:
        env["HF_TOKEN"] = secret_ref(hf_secret)
    env["WEB_AUTH_REQUIRED"] = "1" if auth_required else "0"
    if not auth_required:
        env.pop("WEB_PASSWORD")
    return {
        "name": "fish-drama3-tts", "image": image, "cloud": cloud, "startSsh": False,
        "gpu": {"id": gpu, "count": 1, "minRamPerGpu": 64, "minVcpuCountPerGpu": 8, "minCudaVersion": "12.8"},
        "disk": 40, "mounts": {"persistent": {"size": 80, "path": "/workspace"}},
        "ports": ["8080/http"], "env": env,
    }


def request(method, path, token, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(("https://api.runpod.io/graphql" if path == "/graphql" else API + path), data=body, method=method,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json"})
    # Preserve TLS verification. Never print request headers or API response bodies (may contain secrets).
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"RunPod returned HTTP {exc.code}. Check API access, balance, GPU inventory and secret bindings.") from None
    except urllib.error.URLError:
        raise RuntimeError("Cannot reach api.runpod.io. Check network policy and connectivity.") from None

def hourly_quote(token, gpu, cloud):
    from urllib.parse import quote
    inventory = request("GET", "/catalog/gpus/" + quote(gpu) +
                        "?include=AVAILABILITY&product=POD&cloud=" + cloud + "&minCudaVersion=12.8&count=1", token)
    if inventory.get("availability") not in ("LOW", "MEDIUM", "HIGH"):
        raise RuntimeError("No GPU stock with native CUDA 12.8+ in this cloud; no Pod created")
    # Official GraphQL inventory pricing; catalog headline prices can list unavailable hosts.
    query = "query { gpuTypes(input:{id:" + json.dumps(gpu) + "}) { id lowestPrice(input:{gpuCount:1,secureCloud:" + ("true" if cloud == "SECURE" else "false") + "}) { uninterruptablePrice stockStatus } } }"
    result = request("POST", "/graphql", token, {"query": query})
    if result.get("errors"):
        raise RuntimeError("RunPod price lookup failed; no Pod created")
    matches = result.get("data", {}).get("gpuTypes", [])
    price = matches[0].get("lowestPrice") if matches else None
    if not price or price.get("uninterruptablePrice") is None or price.get("stockStatus") not in ("Low", "Medium", "High"):
        raise RuntimeError("Compatible GPU has no available quoted stock; no Pod created")
    return float(price["uninterruptablePrice"])


def provision(token, payload, ceiling):
    if not 0 < ceiling <= 100:
        raise ValueError("Set a positive --max-hourly rate in USD")
    rate = hourly_quote(token, payload["gpu"]["id"], payload["cloud"])
    if rate > ceiling:
        raise RuntimeError(f"GPU quote ${rate:.2f}/hour exceeds your ${ceiling:.2f}/hour limit. Nothing created.")
    print(f"GPU quote: ${rate:.2f}/hour; storage and container disk billed separately by RunPod.")
    # No POST retries: a timed-out creation can still have succeeded.
    try:
        return request("POST", "/pods", token, payload)
    except Exception:
        print("Creation outcome uncertain if a timeout occurred. Inspect RunPod Pods before retrying to avoid duplicate charges.", file=sys.stderr)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="ghcr.io/themonisbig/personaplex-voice:main")
    parser.add_argument("--gpu", default="NVIDIA L40", choices=COMPATIBLE_GPUS)
    parser.add_argument("--cloud", default="SECURE", choices=("COMMUNITY", "SECURE"))
    parser.add_argument("--hf-secret", default="personaplex_hf", help="Existing optional HF secret name; empty disables it")
    parser.add_argument("--web-secret", default="personaplex_web", help="Existing web password secret; values never enter the image")
    parser.add_argument("--no-login", action="store_true", help="Allow anyone with the HTTPS URL to use your paid GPU without a login")
    parser.add_argument("--max-hourly", type=float, default=0.50, help="USD GPU ceiling, excludes storage; checked before creation")
    parser.add_argument("--create", action="store_true", help="Create one billable Pod; default is dry run")
    parser.add_argument("--accept-billing", action="store_true", help="Acknowledge separate GPU and storage charges")
    parser.add_argument("--status", metavar="POD_ID")
    parser.add_argument("--quote", action="store_true", help="Read current stock/pricing without creating anything")
    args = parser.parse_args(argv)
    if args.status or args.quote or args.create:
        token = os.environ.get("RUNPOD_API_KEY")
        if not token:
            parser.error("Set RUNPOD_API_KEY securely in your runtime")
    if args.status:
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.status):
            parser.error("Invalid Pod ID")
        pod = request("GET", "/pods/" + args.status, token)
        print(json.dumps({k: pod.get(k) for k in ("id", "name", "status", "cost")}, indent=2))
        print(f"Expected proxy URL (verify in RunPod Connect): https://{args.status}-8080.proxy.runpod.net")
        return 0
    payload = build_payload(args.image, args.gpu, args.hf_secret, args.web_secret, args.cloud, not args.no_login)
    if args.quote:
        print(f"Current available GPU quote: ${hourly_quote(token, args.gpu, args.cloud):.2f}/hour, plus storage.")
        return 0
    if not args.create:
        print(json.dumps(payload, indent=2))
        print(f"DRY RUN: nothing created. GPU ceiling ${args.max_hourly:.2f}/hour, excluding storage.")
        return 0
    if not args.accept_billing:
        parser.error("Creation is billable. Supply --create --accept-billing and an authorized --max-hourly rate")
    pod = provision(token, payload, args.max_hourly)
    pod_id = pod.get("id")
    if not pod_id or not re.fullmatch(r"[a-zA-Z0-9_-]+", str(pod_id)):
        raise RuntimeError("RunPod response lacked a valid Pod ID; inspect the console before retrying")
    print("Created Pod:", pod_id)
    print(f"Expected proxy URL (not yet validated): https://{pod_id}-8080.proxy.runpod.net/ui")
    print("First load downloads about 40GB. Wait for /healthz ready.")
    print("Browser access: no login; anyone with the URL can use this GPU." if args.no_login else
          "Sign in as persona with your existing web password.")
    print("Stop ends GPU charges; terminate/delete the Pod to remove its attached paid storage too.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError) as exc:
        sys.exit(str(exc))
