"""仅执行本组件审查所需的有界本地检查。"""

import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = sys.executable
FILES = ["src/ai_intel/assets/fofa_relay.py", "tests/unit/test_r13_fofa_relay.py", "tests/contract/test_r13_fofa_relay_account_wire.py", "tests/security/test_r13_fofa_relay_boundaries.py"]
COMMANDS = [
    ("import_origin", "backend", [PYTHON, "-c", "import sys, ai_intel.assets.fofa_relay as relay; print(sys.version); print(relay.__file__)"]),
    ("author_artifact_verification", ".", [PYTHON, str(RUN / "verify_evidence.py")]),
    ("network_regressions", "backend", [PYTHON, "-m", "pytest", "tests/unit/test_r03_network_gateway.py", "tests/unit/test_r03_network_review_regressions.py", "tests/unit/test_r03_doh_resolver.py", "tests/security/test_t08_network_and_sources.py", "tests/security/test_r03_network_transport.py", "tests/contract/test_t08_network_redirects.py", "--no-cov", "-q", "-p", "no:cacheprovider", "--junitxml", str(RUN / "network_regressions.xml")]),
    ("previous_independent_boundaries", "backend", [PYTHON, "-m", "pytest", "D:/wt/r13-fofa-relay-review-1/reports/runs/recovery_r13_fofa_relay_review_1_20261016/test_independent_relay_boundaries.py", "--no-cov", "-q", "-p", "no:cacheprovider", "--junitxml", str(RUN / "previous_independent_boundaries.xml")]),
    ("independent_boundaries", "backend", [PYTHON, "-m", "pytest", str(RUN / "test_independent_relay_fix1.py"), "--no-cov", "-q", "-p", "no:cacheprovider", "--junitxml", str(RUN / "independent_boundaries.xml")]),
    ("ruff", "backend", [PYTHON, "-m", "ruff", "check", *FILES]),
    ("format", "backend", [PYTHON, "-m", "ruff", "format", "--check", *FILES]),
    ("mypy", "backend", [PYTHON, "-m", "mypy", FILES[0]]),
    ("git_identity", ".", ["git", "log", "-1", "--format=%H%n%D%n%aI%n%s"]),
    ("business_diff", ".", ["git", "diff", "1a52e17ffe327fb8a0c1d4f97372948a699910e3", "HEAD", "--", "backend", "config"]),
    ("business_frozen_check", ".", ["git", "diff", "--exit-code", "2e1f5029a8e153bdd8289ac20b67e50d51e30bca", "HEAD", "--", "backend", "config"]),
    ("protected_paths", ".", ["git", "diff", "--exit-code", "1a52e17ffe327fb8a0c1d4f97372948a699910e3", "HEAD", "--", "AGENTS.md", "docs", "contracts", "progress", "backend/pyproject.toml", "backend/uv.lock", "backend/migrations", "frontend", "backend/src/ai_intel/infrastructure", "backend/src/ai_intel/api"]),
    ("business_diff_check", ".", ["git", "diff", "--check", "1a52e17ffe327fb8a0c1d4f97372948a699910e3", "HEAD", "--", "backend", "config"]),
    ("rg_relay_callers", ".", ["rg", "-n", "FofaRelayClient|FofaRelayConfig|parse_relay_account_response|probe_account|fofa_relay", "backend/src", "backend/tests", "config"]),
    ("rg_gateway_callers", ".", ["rg", "-n", "create_network_gateway|OriginCredentials", "backend/src"]),
]
failed = []
for label, cwd, command in COMMANDS:
    result = subprocess.run([PYTHON, str(RUN / "run_command.py"), label, cwd, *command], cwd=ROOT, check=False)
    if result.returncode:
        failed.append(label)
print("Failed checks:", failed)
raise SystemExit(bool(failed))
