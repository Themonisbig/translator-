import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from deploy.api_server import configure_codec_placement


class CodecPlacementTests(unittest.TestCase):
    def test_cpu_codec_preserves_official_loader_and_uses_fp32_without_autocast(self):
        original = Mock(return_value="official-codec")
        manager = SimpleNamespace(load_codec_model=original)
        original_autocast = Mock()
        engine = SimpleNamespace(autocast_exclude_mps=original_autocast)
        configure_codec_placement(manager, engine, "cpu", "fp32")
        self.assertEqual(manager.load_codec_model("codec.pth", "cuda:0", "bf16"), "official-codec")
        original.assert_called_once_with("codec.pth", "cpu", "fp32")
        with engine.autocast_exclude_mps("cpu", "bf16"):
            original_autocast.assert_not_called()
        engine.autocast_exclude_mps("cuda", "bf16")
        original_autocast.assert_called_once_with("cuda", "bf16")

    def test_cuda_placement_does_not_override_upstream(self):
        original = Mock()
        manager = SimpleNamespace(load_codec_model=original)
        configure_codec_placement(manager, SimpleNamespace(), "cuda", "fp32")
        self.assertIs(manager.load_codec_model, original)

    def test_invalid_placement_fails_before_model_load(self):
        with self.assertRaisesRegex(ValueError, "FISH_CODEC_DEVICE"):
            configure_codec_placement(SimpleNamespace(), SimpleNamespace(), "remote", "fp32")
