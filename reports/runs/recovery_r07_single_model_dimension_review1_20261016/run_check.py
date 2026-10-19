"""Select frozen author regression commands and run them under the review environment."""

import json
from pathlib import Path
import sys

from review_run import ROOT, RUN, run

label = sys.argv[1]
author_run = ROOT / "reports/runs/recovery_r07_single_model_dimension_20261016"
aliases = {"new_103": "final_new_103", "original_236": "final_original_236",
    "original_47": "final_original_47", "root_causes_46": "final_original_46",
    "gateway_32": "final_review_32_recheck", "generation_17": "final_generation_17",
    "ruff": "final_ruff", "format": "final_format", "mypy": "final_mypy",
    "independent_baseline_red": "baseline_red2"}
recipe = json.loads((author_run / (aliases[label] + ".command.json")).read_text(encoding="utf-8"))
argv = [str(ROOT / "backend/.venv/Scripts/python.exe")]
for argument in recipe["argv"][1:]:
    argument = argument.replace("D:/wt/r07-single-field", ROOT.as_posix())
    if argument.endswith("/run_baseline_red.py"):
        argument = str(RUN / "run_review_baseline_red.py")
    if argument.startswith("--junitxml="):
        argument = "--junitxml=" + str(RUN / f"{label}.xml")
    argv.append(argument)
raise SystemExit(run(label, argv, ROOT / "backend"))
