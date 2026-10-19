"""交付后只读校验，不再修改已封存报告或raw材料。"""

import gzip
import hashlib
import json
import subprocess

from review_runner_final import OLD_RUN, ROOT, RUN, approved_url, now
from write_review import REPORT


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    started = now()
    raw = (RUN / "artifact_manifest.json").read_bytes()
    manifest = json.loads(raw)
    receipt_raw = (RUN / "seal_receipt.json").read_bytes()
    receipt = json.loads(receipt_raw)
    assert sha(raw) == receipt["manifest_sha256"]
    files = [ROOT / entry["path"] for entry in manifest["entries"]]
    for path, entry in zip(files, manifest["entries"], strict=True):
        assert len(path.read_bytes()) == entry["bytes"] and sha(path.read_bytes()) == entry["sha256"]
        if "expanded_sha256" in entry:
            assert sha(gzip.decompress(path.read_bytes())) == entry["expanded_sha256"]
    assert gzip.decompress((RUN / "report_raw.md.gz").read_bytes()) == REPORT.read_bytes()
    assert sha(REPORT.read_bytes()) == receipt["report_raw_sha256"]
    assert sha((RUN / "test_fix1_probes.py").read_bytes()) == "1b6862cd8b1b35572513ff698788768d826d8bfc885146021c66f510bd87a8d5"
    url, reference = approved_url()
    actual = {url.render_as_string(hide_password=False), url.render_as_string(hide_password=True), url.password or ""}
    for path in RUN.glob("*_database.json"):
        target = url.set(database=json.loads(path.read_bytes())["database"], query={})
        actual.update((target.render_as_string(hide_password=False), target.render_as_string(hide_password=True)))
    actual.discard("")
    files += [RUN / "artifact_manifest.json", RUN / "seal_receipt.json"]
    for path in files:
        content = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
        assert not any(value.encode() in content for value in actual), "private reference match"
    old = json.loads((OLD_RUN / "artifact_manifest.json").read_bytes())
    for entry in old["entries"]:
        assert sha((OLD_RUN.parents[2] / entry["path"]).read_bytes()) == entry["sha256"]
    result = subprocess.run(["git", "diff", "--exit-code", "--", "backend", "docs", "frontend", "progress", ".gitattributes"], cwd=ROOT, capture_output=True, check=True)
    assert not result.stdout
    print(json.dumps({"start": started, "end": now(), "source": receipt["source_commit"], "material": receipt["material_commit"],
                      "report_sha256": sha(REPORT.read_bytes()), "report_gzip_sha256": receipt["report_gzip_sha256"],
                      "manifest_sha256": sha(raw), "seal_receipt_sha256": sha(receipt_raw),
                      "verified_indexed_files": len(manifest["entries"]), "actual_scan_files_including_two_controls": len(files),
                      "actual_reference_values": len(actual), "actual_matches": 0, "unclassified_shapes": receipt["unclassified_shape_matches"],
                      "old97_unchanged": True, "tracked_scope_diff": 0, "resource": reference}, indent=2))


if __name__ == "__main__":
    main()
