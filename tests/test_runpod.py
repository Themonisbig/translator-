import contextlib
import io
import unittest
from unittest.mock import patch
from scripts.runpod_setup import build_payload, main, secret_ref

class RunPodTests(unittest.TestCase):
    def test_only_gateway_exposed_and_secrets_are_references(self):
        payload = build_payload("ghcr.io/themonisbig/personaplex-voice:main")
        self.assertEqual(payload["ports"], ["8080/http"])
        self.assertEqual(payload["gpu"]["count"], 1)
        self.assertEqual(payload["mounts"]["persistent"]["path"], "/workspace")
        self.assertEqual(payload["env"]["HF_TOKEN"], "{{ RUNPOD_SECRET_personaplex_hf }}")
        self.assertFalse(payload["startSsh"])

    def test_rejects_unpinned_images_bad_names_and_blackwell(self):
        with self.assertRaises(ValueError):
            build_payload("image-without-tag")
        with self.assertRaises(ValueError):
            secret_ref("bad name")
        with self.assertRaises(ValueError):
            build_payload("test/image:main", gpu="NVIDIA RTX 5090")

    def test_default_is_offline_dry_run(self):
        with patch("scripts.runpod_setup.request") as request, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([]), 0)
            request.assert_not_called()

    def test_creation_requires_billing_acknowledgement(self):
        with patch("scripts.runpod_setup.request") as request, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(["--create"])
            request.assert_not_called()

    def test_creation_uses_v2_shape_and_does_not_log_credentials(self):
        with patch.dict("os.environ", {"RUNPOD_API_KEY": "fake-test-only"}), \
             patch("scripts.runpod_setup.request", return_value={"id": "testpod"}) as request, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--create", "--accept-billing"]), 0)
            self.assertEqual(request.call_args.args[:2], ("POST", "/pods"))
            self.assertNotIn("fake-test-only", output.getvalue())
