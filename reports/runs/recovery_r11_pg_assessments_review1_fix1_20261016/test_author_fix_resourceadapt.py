"""Run frozen author fix tests with only this review's isolated resource fixture."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend/tests/integration"))
SOURCE = ROOT / "backend/tests/integration/test_r11_assessment_raw_rechecks_pg.py"
spec = importlib.util.spec_from_file_location("r11_review_author_raw_fix", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
for name, value in vars(module).items():
    if name.startswith("test_"):
        globals()[name] = value
