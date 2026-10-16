"""Locate synthetic SDK fixtures and keep their observations outside source files."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
RUN = Path(os.environ.get("SDK_TEST_EVIDENCE_DIR") or tempfile.mkdtemp(prefix="dianzi-sdk-tests-"))
RUN.mkdir(parents=True, exist_ok=True)
