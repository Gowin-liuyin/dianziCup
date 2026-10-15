"""Keep one unchanged legacy test's fixed report output inside this batch's owned run."""

from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
LEGACY_OUTPUT = ROOT / "reports/runs/recovery_r07_enrichment_execution_20261016/nvd_input_budget_observation.json"
ORIGINAL_WRITE_TEXT = Path.write_text


def write_owned_artifact(path, *args, **kwargs):
    if path == LEGACY_OUTPUT:
        path = RUN / "nvd_regression_observation.json"
    return ORIGINAL_WRITE_TEXT(path, *args, **kwargs)


def pytest_sessionstart(session):
    Path.write_text = write_owned_artifact


def pytest_sessionfinish(session, exitstatus):
    Path.write_text = ORIGINAL_WRITE_TEXT
