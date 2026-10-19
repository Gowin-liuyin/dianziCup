"""Run original bug-presence assertions with only the isolated resource origin adapted."""
import os
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
environment=dict(os.environ)
environment["R17_RECHECK_DIAGNOSTIC"]="1"
result=subprocess.run(["node","node_modules/@playwright/test/cli.js","test","--config=../reports/runs/recovery_r17_sbom_workbench_review1_fix1_20261016/playwright.review.cjs"],cwd=ROOT/"frontend",env=environment)
raise SystemExit(result.returncode)
