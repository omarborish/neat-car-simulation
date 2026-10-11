import os
from pathlib import Path
import subprocess
import sys
import unittest

from workspace_temp import WorkspaceTemp


class TrainingCommandTests(unittest.TestCase):
    def test_headless_training_exports_a_real_driver(self):
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "train.py").is_file(), "Training command has not been implemented")
        folder = WorkspaceTemp()
        self.addCleanup(folder.cleanup)
        env = os.environ.copy()
        env["SDL_VIDEODRIVER"] = env["SDL_AUDIODRIVER"] = "dummy"
        result = subprocess.run([sys.executable, "-B", str(root / "train.py"),
                                 "--generations", "1", "--output", folder.name],
                                cwd=root, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        from models import load_driver
        self.assertGreater(load_driver(Path(folder.name) / "classic.json").fitness, 0)


if __name__ == "__main__":
    unittest.main()
