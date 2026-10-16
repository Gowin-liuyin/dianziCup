"""SDK tests import only their worktree client package and explicit synthetic data."""

import sys
from pathlib import Path

SDK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SDK_ROOT))
