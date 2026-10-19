"""Preserve original source/test bytes and generate reviewable raw-byte evidence manifests."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from run_checks import ROOT, RUN, git, now, write_json

BASE = "71e594cb958bd93d21fb7ed66574b3cba4cc47e1"
OLD_TEST = "backend/tests/unit/test_r07_public_signals_fix1.py"
SOURCE = "backend/src/ai_intel/enrichment/signals.py"


def digest(content):
    return {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
            "git_raw_blob": hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()}


if sys.argv[1] == "baseline_public":
    path = "backend/tests/unit/test_r07_public_signals.py"
    content = git("show", BASE + ":" + path)
    (RUN / "old_public_test.original.raw").write_bytes(content)
    write_json(RUN / "old_public_test_identity.json", {"at": now(), "path": path,
        "git_blob": git("rev-parse", BASE + ":" + path).decode().strip(), **digest(content)})
elif sys.argv[1] == "baseline":
    originals = []
    for name, path in (("old_test", OLD_TEST), ("old_source", SOURCE)):
        content = git("show", BASE + ":" + path)
        (RUN / (name + ".original.raw")).write_bytes(content)
        originals.append({"path": path, "git_blob": git("rev-parse", BASE + ":" + path).decode().strip(), **digest(content)})
    write_json(RUN / "baseline_identity.json", {"at": now(), "base": BASE, "originals": originals,
        "branch": git("branch", "--show-current").decode().strip(),
        "status": git("status", "--short").decode(),
        "ponytail_skill": digest(Path("C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail/SKILL.md").read_bytes()),
    })
else:
    paths = [p for p in RUN.rglob("*") if p.is_file() and p.name != "artifact_manifest.json" and "__pycache__" not in p.parts]
    paths += [ROOT / "reports/tasks/R07-cvss-authority-scope-fix.md", ROOT / "docs/decisions/CR-R07_cvss_authority_scope.md"]
    paths += [ROOT / SOURCE, ROOT / OLD_TEST, ROOT / "backend/tests/unit/test_r07_public_signals.py",
              ROOT / "backend/tests/unit/test_r07_cvss_authority_scope_fix.py",
              ROOT / "backend/tests/contract/test_r07_cvss_authority_scope_contract.py",
              ROOT / "backend/tests/integration/test_r07_cvss_authority_scope_fix_pg.py"]
    artifacts = [{"path": p.relative_to(ROOT).as_posix(), **digest(p.read_bytes())} for p in sorted(paths)]
    write_json(RUN / "artifact_manifest.json", {"at": now(), "base": BASE,
        "head": git("rev-parse", "HEAD").decode().strip(), "artifacts": artifacts,
        "filelist_sha256": hashlib.sha256("\n".join(a["path"] for a in artifacts).encode()).hexdigest()})
    print(json.dumps({"artifacts": len(artifacts)}))
