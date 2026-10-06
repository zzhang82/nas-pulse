import unittest
from pathlib import Path
import tempfile
from nas_pulse.config import Config

class TestConfig(unittest.TestCase):
    def test_config_defaults(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            Config.save(
                dest_path=env_file,
                nas_ip="192.168.1.50",
                nas_port=5001,
                nas_user="doctor",
                nas_password="secret_password",
                nas_secure=True,
                nas_cert_verify=False,
            )

            self.assertTrue(env_file.exists())
            cfg = Config(env_file)
            self.assertEqual(cfg.nas_ip, "192.168.1.50")
            self.assertEqual(cfg.nas_port, 5001)
            self.assertEqual(cfg.nas_user, "doctor")
            self.assertEqual(cfg.nas_password, "secret_password")
            self.assertTrue(cfg.nas_secure)
            self.assertFalse(cfg.nas_cert_verify)
            self.assertTrue(cfg.is_configured)
            self.assertEqual(cfg.validate(), [])

if __name__ == "__main__":
    unittest.main()
