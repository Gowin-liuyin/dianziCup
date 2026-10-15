"""只读取本工作包私密测试DSN进行全文/8字符片段检查，不接触产品凭据。"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
configuration = json.loads(Path("/tmp/dianzi-r04-api-20261015/connection.json").read_text())
database_url = configuration["TEST_DATABASE_URL"]
password = unquote(make_url(database_url).password or "")
values = {database_url, password}
fragments = {password[index:index+8] for index in range(len(password)-7)}
matches = []
files = list(RUN.rglob("*"))
report = ROOT / "reports/tasks/R04-knowledge-api.md"
if report.exists():
    files.append(report)
source = [ROOT / name for name in (
    "backend/src/ai_intel/api/app.py", "backend/src/ai_intel/api/knowledge_read_service.py",
    "backend/src/ai_intel/api/knowledge_routes.py", "backend/tests/unit/test_r04_knowledge_api_cursor.py",
    "backend/tests/integration/test_r04_knowledge_api_pg.py",
)]
files += source
manifest = []
windows_root = subprocess.check_output(["wslpath", "-w", str(ROOT)], text=True).strip()
for path in files:
    if not path.is_file() or path.name in {"private_test_secret_scan.json", "evidence_index.json"}:
        continue
    payload = path.read_bytes()
    if any(value and value.encode() in payload for value in values | fragments):
        matches.append(str(path.relative_to(ROOT)))
    relative = str(path.relative_to(ROOT))
    indexed = subprocess.run(["/mnt/c/Program Files/Git/cmd/git.exe", "-C", windows_root,
                              "show", ":"+relative], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    manifest.append({"path": relative, "captured_sha256": hashlib.sha256(payload).hexdigest(),
                     "captured_size_bytes": len(payload),
                     "git_blob_sha256": hashlib.sha256(indexed.stdout).hexdigest()
                     if indexed.returncode == 0 else None,
                     "git_blob_size_bytes": len(indexed.stdout) if indexed.returncode == 0 else None})
receipt = {"checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
           "scope": "own test DSN/password/full and all eight-character fragments; no product keys read",
           "files_checked": len(manifest), "matches": matches}
(RUN / "private_test_secret_scan.json").write_text(json.dumps(receipt, indent=2))
(RUN / "evidence_index.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(receipt))
raise SystemExit(1 if matches else 0)
