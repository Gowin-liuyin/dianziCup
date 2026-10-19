"""Check the exact fixed source and material commit differences without changing Git state."""

import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
arguments = sys.argv[1:] or ["--cached"]
command = ["git", "diff", *arguments, "--check"]
print(json.dumps(dict(command=command, cwd=str(root))))
result = subprocess.run(command, cwd=root, capture_output=True)
print(result.stdout.decode("utf-8", errors="replace"))
print(result.stderr.decode("utf-8", errors="replace"))
sys.exit(result.returncode)
