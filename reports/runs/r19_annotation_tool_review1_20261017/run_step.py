"""Dispatch a single offline review check without changing its assertions."""

import sys

from owned_checks_helper import PYTHON, RUN, execute

label, mode, *arguments = sys.argv[1:]
if mode == "python":
    command = [PYTHON, *arguments]
    cap = 10
elif mode == "cbm":
    command = [
        "C:/Windows/System32/wsl.exe", "--exec", "python3",
        "/mnt/d/wt/r19-annotation-tool-review-1/reports/runs/r19_annotation_tool_review1_20261017/linux_cbm_entry.py",
        label, *arguments,
    ]
    cap = 16
else:
    command = arguments
    cap = 10
raise SystemExit(execute(label, command, timeout=60, process_cap=cap))
