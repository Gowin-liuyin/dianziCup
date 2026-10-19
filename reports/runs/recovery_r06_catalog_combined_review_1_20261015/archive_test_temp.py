"""Preserve synthetic test scratch files outside the repository scanner's inputs."""

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

RUN = Path(__file__).resolve().parent
SOURCE = RUN / "temp_pure"
DESTINATION = Path("D:/wt/r06-catalog-final-review-run-artifacts")
assert SOURCE.resolve() == RUN.resolve() / "temp_pure"
DESTINATION.mkdir(exist_ok=True)
archive = DESTINATION / "pure_regression_synthetic_temp.zip"
assert not archive.exists()
files = [path for path in SOURCE.rglob("*") if path.is_file()]
hashes = {str(path.relative_to(SOURCE)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
with ZipFile(archive, "w", ZIP_DEFLATED) as handle:
    for path in files:
        handle.write(path, str(path.relative_to(SOURCE)))
with ZipFile(archive) as handle:
    assert set(handle.namelist()) == set(hashes)
    assert all(hashlib.sha256(handle.read(name)).hexdigest() == value for name, value in hashes.items())
manifest = {"archive": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "file_count": len(files), "files_sha256": hashes, "verified_original_bytes": True}
(RUN / "synthetic_temp_archive_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in manifest.items() if key != "files_sha256"}))
