import unittest
from types import SimpleNamespace
from deploy.launch import validate_gpu


class HardwareTests(unittest.TestCase):
    def gpu(self, capability, memory=48):
        return SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True,
            get_device_capability=lambda: capability,
            get_device_properties=lambda _: SimpleNamespace(total_memory=memory * 1024**3)))

    def test_prevents_old_ampere_from_expanding_fp8_to_out_of_memory_bf16(self):
        with self.assertRaisesRegex(RuntimeError, "SM89"):
            validate_gpu(self.gpu((8, 6)))

    def test_prevents_small_vram_before_downloading_weights(self):
        with self.assertRaisesRegex(RuntimeError, "48GB"):
            validate_gpu(self.gpu((8, 9), 24))
        validate_gpu(self.gpu((8, 9)))
