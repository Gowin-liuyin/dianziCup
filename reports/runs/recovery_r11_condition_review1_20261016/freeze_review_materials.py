"""Stage only owned review artifacts and preserve their original raw bytes in a ZIP."""

import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/reviews/recovery/G-D-R11-condition-rules-review-1.md"
GENERATED = {"review_manifest.json", "raw_evidence.zip", "review_filelist.json"}
files = sorted([REPORT] + [path for path in RUN.iterdir()
                         if path.is_file() and path.name not in GENERATED])
for path in files:
    if not (path == REPORT or path.parent == RUN):
        raise SystemExit("owned file boundary violated")
    if path.name == "cache_cleanup_rejection.json":
        payload = json.JSONDecoder().raw_decode(path.read_text())[0]
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if path.suffix == ".json":
        json.loads(path.read_text(encoding="utf-8"))
relative_files = [path.relative_to(ROOT).as_posix() for path in files]
subprocess.run(["git", "add", "--", *relative_files], cwd=ROOT, check=True,
               capture_output=True)
entries = []
for path, relative in zip(files, relative_files, strict=True):
    raw = path.read_bytes()
    staged = subprocess.check_output(["git", "show", ":" + relative], cwd=ROOT)
    entries.append(dict(path=relative, raw_bytes=len(raw),
                        raw_sha256=hashlib.sha256(raw).hexdigest(),
                        git_blob_bytes=len(staged),
                        git_blob_sha256=hashlib.sha256(staged).hexdigest(),
                        expected_external_sha256=None))
manifest = dict(
    frozen_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    branch=subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
    frozen_source_sha="ddfbf8c631a7ea002865d6ae0c1385e63bd87674",
    author_material_sha="3865fd6a9c568b0d4e6b816e62eb808de5330427",
    author_entries_sha256="5dbcce2243ac2622309e21ab9809a7b81b48f442cf18aa3620fc7eeb2555342a",
    entries=entries,
    excluded_generated_caches=["pytest_cache/", "mypy_cache/", "ruff_cache/", "backend/.ruff_cache/"],
)
(RUN / "review_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
with zipfile.ZipFile(RUN / "raw_evidence.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        archive.writestr(path.relative_to(ROOT).as_posix(), path.read_bytes())
    archive.writestr((RUN / "review_manifest.json").relative_to(ROOT).as_posix(),
                     (RUN / "review_manifest.json").read_bytes())
with zipfile.ZipFile(RUN / "raw_evidence.zip") as archive:
    assert archive.testzip() is None
    for entry in entries:
        assert hashlib.sha256(archive.read(entry["path"])).hexdigest() == entry["raw_sha256"]
extra_paths = sorted((RUN / name).relative_to(ROOT).as_posix() for name in GENERATED)
filelist = dict(paths=sorted(relative_files + extra_paths),
                raw_archive_sha256=hashlib.sha256((RUN / "raw_evidence.zip").read_bytes()).hexdigest(),
                review_manifest_raw_sha256=hashlib.sha256((RUN / "review_manifest.json").read_bytes()).hexdigest())
(RUN / "review_filelist.json").write_text(json.dumps(filelist, indent=2) + "\n", encoding="utf-8")
subprocess.run(["git", "add", "--", *extra_paths], cwd=ROOT, check=True, capture_output=True)
assert not subprocess.check_output(["git", "diff", "--name-only", "--", "backend", "docs", "progress", "contracts", "config"], cwd=ROOT)
print(json.dumps({"frozen_at": manifest["frozen_at"], "count": len(filelist["paths"]),
                  "raw_archive_sha256": filelist["raw_archive_sha256"],
                  "review_manifest_raw_sha256": filelist["review_manifest_raw_sha256"]}, indent=2))
