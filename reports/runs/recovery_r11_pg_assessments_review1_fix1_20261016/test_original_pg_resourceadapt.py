"""Run the original 33 cases unchanged with only a dedicated review resource fixture."""

import importlib.util
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[3] / "backend/tests/integration/test_r11_pg_assessments.py"
spec = importlib.util.spec_from_file_location("r11_review_original_pg", SOURCE)
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
for name, value in vars(original).items():
    if name.startswith("test_"):
        globals()[name] = value
