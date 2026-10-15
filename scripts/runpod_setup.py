#!/usr/bin/env python3
"""Plan or provision one GPU Pod using RunPod's official SDK v2 request shape."""
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

def build_payload(image, gpu="NVIDIA A40", hf_secret="personaplex_hf", web_secret="personaplex_web"):
    if not re.fullmatch(r"[a-z0-9][a-z0-9./_-]*(?::[A-Za-z0-9_.-]+|@sha256:[a-f0-9]{64})", image):
        raise ValueError("Supply a tagged or digest-pinned registry image, without credentials")
    if gpu not in ("NVIDIA A40", "NVIDIA RTX A6000", "NVIDIA L40S", "NVIDIA A100 80GB PCIe", "NVIDIA H100 80GB HBM3"):
        raise ValueError("Choose a supported 48GB+ Ampere/Ada/Hopper GPU")
    return {
        "name": "personaplex-voice", "image": image, "cloud": "SECURE", "startSsh": False,
        "gpu": {"id": gpu, "count": 1, "minRamPerGpu": 48, "minVcpuCountPerGpu": 8},
        "disk": 30, "mounts": {"persistent": {"size": 80, "path": "/workspace"}},
        "ports": ["8080/http"],
        "env": {"HF_TOKEN": secret_ref(hf_secret), "WEB_PASSWORD": secret_ref(web_secret),
                "WEB_USERNAME": "persona", "HF_HOME": "/workspace/huggingface"},
    }

def request(method, path, token, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=body, method=method,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json"})
    # Preserve TLS verification. Never print request headers or API response bodies (may contain secrets).
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"RunPod returned HTTP {exc.code}. Check API access, balance, GPU inventory and secret bindings.") from None
    except urllib.error.URLError:
        raise RuntimeError("Cannot reach api.runpod.io. Check network policy and connectivity.") from None

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="ghcr.io/themonisbig/personaplex-voice:main")
    parser.add_argument("--gpu", default="NVIDIA A40")
    parser.add_argument("--hf-secret", default="personaplex_hf")
    parser.add_argument("--web-secret", default="personaplex_web")
    parser.add_argument("--create", action="store_true", help="Create a billable Pod; default is dry run")
    parser.add_argument("--accept-billing", action="store_true", help="Acknowledge GPU and storage charges at RunPod's current rates")
    parser.add_argument("--status", metavar="POD_ID", help="Read an existing Pod status; never creates a Pod")
    args = parser.parse_args(argv)
    if args.status:
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.status):
            parser.error("Invalid Pod ID")
        token = os.environ.get("RUNPOD_API_KEY")
        if not token:
            parser.error("Set RUNPOD_API_KEY securely in your runtime")
        pod = request("GET", "/pods/" + args.status, token)
        print(json.dumps({k: pod.get(k) for k in ("id", "name", "status")}, indent=2))
        print(f"Expected proxy URL (verify in RunPod Connect): https://{args.status}-8080.proxy.runpod.net")
        return 0
    payload = build_payload(args.image, args.gpu, args.hf_secret, args.web_secret)
    if not args.create:
        print(json.dumps(payload, indent=2))
        print("DRY RUN: nothing created. Review RunPod pricing, secret bindings and image availability first.")
        return 0
    if not args.accept_billing:
        parser.error("Provisioning costs money. Review current RunPod pricing, then use --create --accept-billing")
    token = os.environ.get("RUNPOD_API_KEY")
    if not token:
        parser.error("Set RUNPOD_API_KEY securely in your runtime; never put it in source code")
    # Deliberately no POST retries: timeout may mean a Pod was already created.
    try:
        pod = request("POST", "/pods", token, payload)
    except Exception:
        print("Creation outcome uncertain if a timeout occurred. Inspect RunPod Pods before retrying to avoid duplicate charges.", file=sys.stderr)
        raise
    pod_id = pod.get("id")
    if not pod_id or not re.fullmatch(r"[a-zA-Z0-9_-]+", str(pod_id)):
        raise RuntimeError("RunPod response lacked a valid Pod ID; inspect the console before retrying")
    print("Created Pod:", pod_id)
    print(f"Expected proxy URL (not yet validated): https://{pod_id}-8080.proxy.runpod.net")
    print("Wait for /healthz to report ready; sign in as persona with your WEB_PASSWORD. Stop the Pod when finished.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError) as exc:
        sys.exit(str(exc))
