"""Independent CBM index/schema/trace with an isolated cache and real receipts."""

import os
import sys

from review_runner import ROOT, receipt

BASE_COMMAND = [
    "wsl", "--exec", "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-r10-review1-fix2-20261016",
    "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json",
]
PROJECT = "dianzi-r10-projection-review1-fix2-backend"
arguments = sys.argv[1:]
if not arguments:
    code = receipt("cbm_index", BASE_COMMAND + ["index_repository", "--repo-path",
                   "/mnt/d/wt/r10-neo4j-projection-review1-fix2/backend/src", "--name", PROJECT,
                   "--mode", "fast"], ROOT, dict(os.environ))
else:
    name = arguments.pop(0)
    code = receipt(name, BASE_COMMAND + arguments + ["--project", PROJECT], ROOT, dict(os.environ))
raise SystemExit(code)
