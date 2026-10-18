import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

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

    def auto_engine(self, gpu_decode):
        cpu_codec = Mock()
        cpu_codec.from_indices.return_value = [Mock(squeeze=Mock(return_value="cpu-audio"))]
        manager = SimpleNamespace(load_codec_model=Mock(side_effect=[cpu_codec, "gpu-codec"]))
        engine = SimpleNamespace(TTSInferenceEngine=type("Engine", (), {"decode_vq_tokens": gpu_decode}))
        configure_codec_placement(manager, engine, "auto", "fp32", gpu_max_frames=4, oom_error=MemoryError)
        self.assertEqual(manager.load_codec_model("codec.pth", "cuda:0", "bf16"), "gpu-codec")
        return engine.TTSInferenceEngine(), cpu_codec

    def test_auto_keeps_official_gpu_codec_and_an_fp32_cpu_copy(self):
        original = Mock(side_effect=["cpu-codec", "gpu-codec"])
        manager = SimpleNamespace(load_codec_model=original)
        engine = SimpleNamespace(TTSInferenceEngine=type("Engine", (), {"decode_vq_tokens": Mock()}))
        configure_codec_placement(manager, engine, "auto", "fp32")
        self.assertEqual(manager.load_codec_model("codec.pth", "cuda:0", "bf16"), "gpu-codec")
        self.assertEqual(original.call_args_list[0].args, ("codec.pth", "cpu", "fp32"))
        self.assertEqual(original.call_args_list[1].args, ("codec.pth", "cuda:0", "bf16"))

    def test_auto_decodes_short_clips_on_gpu(self):
        gpu = Mock(return_value="gpu-audio")
        engine, cpu_codec = self.auto_engine(lambda self, codes: gpu(codes))
        codes = MagicMock(shape=(10, 4))
        self.assertEqual(engine.decode_vq_tokens(codes), "gpu-audio")
        gpu.assert_called_once_with(codes)
        cpu_codec.from_indices.assert_not_called()

    def test_auto_decodes_long_clips_on_cpu_without_touching_gpu(self):
        gpu = Mock()
        engine, cpu_codec = self.auto_engine(lambda self, codes: gpu(codes))
        self.assertEqual(engine.decode_vq_tokens(MagicMock(shape=(10, 5))), "cpu-audio")
        gpu.assert_not_called()
        cpu_codec.from_indices.assert_called_once()

    def test_auto_falls_back_to_cpu_when_gpu_runs_out_of_memory(self):
        gpu = Mock(side_effect=MemoryError)
        engine, cpu_codec = self.auto_engine(lambda self, codes: gpu(codes))
        self.assertEqual(engine.decode_vq_tokens(MagicMock(shape=(10, 2))), "cpu-audio")
        gpu.assert_called_once()
        cpu_codec.from_indices.assert_called_once()

    def test_invalid_placement_fails_before_model_load(self):
        with self.assertRaisesRegex(ValueError, "FISH_CODEC_DEVICE"):
            configure_codec_placement(SimpleNamespace(), SimpleNamespace(), "remote", "fp32")
