"""Run local-only pure/static checks without depending on WSL credential retrieval."""

import os
import sys

from review_runner import PYTHON, ROOT, run

environment = os.environ.copy()
environment["PYTHONPATH"] = str(ROOT / "backend/src")
raise SystemExit(run(sys.argv[1], [str(PYTHON), *sys.argv[2:]], ROOT / "backend", environment, 240))
