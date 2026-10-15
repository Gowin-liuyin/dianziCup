"""Choose only owned artifacts and verify each staged blob against its byte manifest."""

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/tasks/R07-public-signals.md"
NOW = datetime.now().astimezone().isoformat(timespec="seconds")
text = REPORT.read_text(encoding="utf-8").replace("recorded_response_receipt.json/replay.log", "recorded_response_receipt.json/recorded_response_replay.log")
text = re.sub(r"最后更新时间：[^\n]+", "最后更新时间：" + NOW, text)
text += "\n" + NOW + "，更正复放日志文件名、词法秘密检查和精确Git blob封存；首次创建时间不变，产品代码未变。\n"
REPORT.write_bytes(text.encode())
files = sorted(path for path in RUN.iterdir() if path.is_file() and path.name != "artifact_manifest.json")
finding_count = 0
url_findings = []
for path in [REPORT, *files, ROOT / "backend/src/ai_intel/enrichment/signals.py",
             ROOT / "backend/src/ai_intel/enrichment/signal_sources.py",
             ROOT / "backend/tests/unit/test_r07_public_signals.py",
             ROOT / "backend/tests/contract/test_r07_public_signal_sources.py"]:
    body = path.read_text(encoding="utf-8-sig", errors="replace")
    finding_count += len(re.findall(r"sk-[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", body))
    url_findings.extend(hashlib.sha256(token.encode()).hexdigest() for token in
                        re.findall(r"https?://[^/\s\"'<>]+:[^/@\s\"'<>]+@", body))
assert finding_count == 0
classified = json.loads((RUN / "lexical_url_classification.json").read_bytes())
known = {value for row in classified["url_shapes_in_case_names"] for value in row["token_hashes"]}
assert all(value in known for value in url_findings)
scan = {"scanned_at": NOW, "files": len(files) + 5, "lexical_findings": finding_count,
        "credential_url_shape_findings": len(url_findings), "unclassified_url_shapes": 0,
        "classification_ref": "lexical_url_classification.json",
        "limitation": "Explicit URL-rejection fixture literals/prefixes; no credentials read; root must perform exact-secret scan before integration/push."}
(RUN / "lexical_secret_scan.json").write_bytes((json.dumps(scan, indent=2) + "\n").encode())
files = sorted(path for path in RUN.iterdir() if path.is_file() and path.name != "artifact_manifest.json")
manifest = {"created_at": NOW, "code_sha": "7142c38620150d5f2b7d81963389bdf8b725c316",
            "report": {"path": REPORT.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest()},
            "artifact_files": [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in files],
            "json_metadata_normalization": "LF; data retained; .log and three CRLF original JUnit files preserved",
            "excluded": ["outside-Git public original publisher bodies", ".coverage/pyc/mypy/CBM caches"]}
(RUN / "artifact_manifest.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode())
paths = [REPORT.relative_to(ROOT).as_posix(), *(path.relative_to(ROOT).as_posix() for path in files),
         (RUN / "artifact_manifest.json").relative_to(ROOT).as_posix()]
subprocess.run(["git", "add", "--", *paths], cwd=ROOT, check=True)
for path in [REPORT, *files, RUN / "artifact_manifest.json"]:
    staged = subprocess.check_output(["git", "show", ":" + path.relative_to(ROOT).as_posix()], cwd=ROOT)
    assert staged == path.read_bytes(), path
print(json.dumps({"sealed_at": NOW, "files": len(files), "report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
                  "lexical_secret_scan": scan, "staged_blobs_match": True}, ensure_ascii=False))
