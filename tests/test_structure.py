from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "compose.yaml",
    "UPSTREAMS.lock",
    "config/rtl_433/rtl_433.conf",
    "config/weewx/sdr.conf.example",
    "docker/weewx/Dockerfile",
    "docs/runbooks/gate-1-rf.md",
    "tests/fixtures/wh65b.sample.json",
]


class StructureTests(unittest.TestCase):
    def test_required_paths_exist(self):
        missing = [p for p in REQUIRED if not (ROOT / p).exists()]
        self.assertFalse(missing, f"Missing required paths: {missing}")


if __name__ == "__main__":
    unittest.main()
