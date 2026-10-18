import unittest
from unittest.mock import patch
from scripts.runpod_setup import build_payload, provision, hourly_quote, secret_ref

IMAGE = "ghcr.io/themonisbig/personaplex-voice:" + "a" * 40


class RunPodTests(unittest.TestCase):
    def test_reuses_only_secret_references_and_private_model_server(self):
        payload = build_payload(IMAGE)
        self.assertEqual(payload["env"]["WEB_PASSWORD"], "{{ RUNPOD_SECRET_personaplex_web }}")
        self.assertEqual(payload["ports"], ["8080/http"])
        self.assertFalse(payload["startSsh"])
        self.assertEqual(payload["gpu"]["count"], 1)
        self.assertEqual(payload["gpu"]["minCudaVersion"], "12.8")
        self.assertEqual(payload["env"]["FISH_DRAMA3_FP8_EXPERTS"], "1")
        self.assertEqual(payload["env"]["FISH_DRAMA3_CUDA_GRAPH"], "1")
        self.assertEqual(payload["env"]["FISH_CODEC_DEVICE"], "cpu")

    def test_old_gpu_and_unsafe_registry_rejected(self):
        for gpu in ("NVIDIA A40", "NVIDIA RTX A6000", "NVIDIA GeForce RTX 4090"):
            with self.assertRaises(ValueError):
                build_payload(IMAGE, gpu=gpu)
        with self.assertRaises(ValueError):
            build_payload("https://user:secret@registry/image")
        with self.assertRaises(ValueError):
            secret_ref("bad name")

    @patch("scripts.runpod_setup.request")
    @patch("scripts.runpod_setup.hourly_quote", return_value=0.74)
    def test_budget_limit_prevents_creation(self, quote, request):
        with self.assertRaisesRegex(RuntimeError, "exceeds"):
            provision("test-placeholder", build_payload(IMAGE), 0.50)
        request.assert_not_called()

    @patch("scripts.runpod_setup.request", return_value={"id": "test-pod"})
    @patch("scripts.runpod_setup.hourly_quote", return_value=0.74)
    def test_authorized_rate_creates_exactly_one_pod(self, quote, request):
        self.assertEqual(provision("test-placeholder", build_payload(IMAGE), 0.74)["id"], "test-pod")
        request.assert_called_once_with("POST", "/pods", "test-placeholder", build_payload(IMAGE))

    @patch("scripts.runpod_setup.request", return_value={"data": {"gpuTypes": [{"lowestPrice": None}]}})
    def test_no_stock_stops_deployment(self, request):
        with self.assertRaisesRegex(RuntimeError, "stock"):
            hourly_quote("test-placeholder", "NVIDIA L40", "COMMUNITY")
