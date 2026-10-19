"""Frozen source locations and fixture-only child environment."""

import os
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path("D:/wt/r16-r17-changes-review1")
RUN = Path(__file__).resolve().parent
PYTHON = "C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe"
BASELINE = "0291d197587141b9f7f5da0d01800d8cbdf58d11"
QUALIFIED = "14ce965b66fbf8f74221eb01e1426cf1636ea9fc"
MATERIAL = "f2c5ad7229d4ce04e95e4457466731319120285e"


def now():
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def environment():
    result = os.environ.copy()
    for key in tuple(result):
        if key.startswith(("TEST_", "DIANZI_TEST_")) or key in {
            "DATABASE_URL", "REDIS_URL", "GENERATION_API_KEY", "REVALIDATION_CURSOR_SIGNING_KEY",
        }:
            result.pop(key)
    result.update(
        APP_ENV="test", DATA_MODE="fixture", SOURCE_POLLING_ENABLED="false",
        ENRICHMENT_GENERATION_ENABLED="false", PYTHONIOENCODING="utf-8",
        PYTHONDONTWRITEBYTECODE="1", PYTEST_ADDOPTS="",
        PYTHONPATH=os.pathsep.join([
            str(ROOT / "backend/src"), str(ROOT), str(ROOT / "backend/tests/unit"),
            str(ROOT / "backend/tests/contract"), str(ROOT / "backend/tests/integration"),
            str(ROOT / "backend"), str(RUN), str(RUN.parent),
        ]),
    )
    return result
