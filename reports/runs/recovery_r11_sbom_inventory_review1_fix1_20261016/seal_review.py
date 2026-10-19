"""审查包精确bytes封存；真实参考值整文件扫描，合成参数ID精确分类。"""

import ast
import gzip
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from urllib.parse import quote

from review_runner_final import OLD_RUN, ROOT, RUN, approved_url, now
from write_review import REPORT

CODE = "6942c65efd5df013c077275cbb6d8cfec3585080"
MATERIAL = "5be873ec38a41955b5a58e9762df4b866a7a9d63"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def expected_parameter_names():
    tree = ast.parse((RUN / "test_review_probes.py").read_text(encoding="utf-8"))
    values = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str) and ("synthetic_password" in node.value or node.value.startswith("file:///C:/private/"))}
    names = {"test_sidecar_http_does_not_expose_protected_uri_values[" + value + "]" for value in values}
    key = "https://synthetic_user:synthetic_password@example.test/sbom"
    for depth in (1, 4, 12, 64):
        encoded = key
        for _ in range(depth):
            encoded = quote(encoded, safe="")
        names.add("test_bounded_decoding_hides_uri_at_and_beyond_limit[" + encoded + "]")
    return names


def main():
    started = now()
    url, source = approved_url()
    actual = {url.render_as_string(hide_password=False), url.render_as_string(hide_password=True), url.password or ""}
    for path in RUN.glob("*_database.json"):
        database = json.loads(path.read_bytes())["database"]
        target = url.set(database=database, query={})
        actual.update((target.render_as_string(hide_password=False), target.render_as_string(hide_password=True)))
    actual.discard("")
    names = expected_parameter_names()
    patterns = [
        re.compile(r"postgresql(?:\+[A-Za-z0-9_]+)?://[^\s\"'<>\\]+"),
        re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"'<>]*:[^\s\"'<>]*@"),
        re.compile(r"file:///C:/private/[^\s\"'<>]+"),
        re.compile(r"synthetic_password"),
    ]
    files = [REPORT] + sorted(path for path in RUN.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.name not in {"artifact_manifest.json", "seal_receipt.json", "seal_error.log", "scan_diagnosis.json", "scope_diff_receipt.json"})
    actual_hits = []
    unclassified = []
    classified = []
    entries = []
    expanded_count = 0
    for path in files:
        raw = path.read_bytes()
        expanded = gzip.decompress(raw) if path.suffix == ".gz" else raw
        expanded_count += 1
        relative = path.relative_to(ROOT).as_posix()
        if any(value.encode() in expanded for value in actual):
            actual_hits.append(relative)
        text = expanded.decode("utf-8", errors="replace")
        controlled_source = path.suffix == ".py" or path.name.endswith((".py.gz", ".executed.gz"))
        controlled_source |= path.parent.name in {"source_blobs", "final_source_blobs"} and "test_r11_" in path.name
        if controlled_source:
            if any(pattern.search(text) for pattern in patterns):
                classified.append({"path": relative, "reason": "explicit_synthetic_probe_frozen_test_or_review_harness_source", "raw_sha256": sha(raw)})
        else:
            if path.suffix == ".xml":
                document = ET.fromstring(text)
                for case in document.iter("testcase"):
                    if case.attrib.get("name") in names:
                        identifier = case.attrib["name"]
                        classified.append({"path": relative, "reason": "exact_original_parameter_id_only", "testcase_id_sha256": sha(identifier.encode()), "classname": case.attrib.get("classname", "")})
                        case.attrib["name"] = "[declared synthetic parameter]"
                text = ET.tostring(document, encoding="unicode")
            if path.name in {"pg_new.log", "pg_new.xml"}:
                for match in list(patterns[1].finditer(text)):
                    if sha(match[0].encode()) == "7ef8ebb8c14c33599fa38e0fdfd42af7cee31a70a1fce38c1f5eb07493c0630b":
                        assert match[0].endswith(":***@")
                        classified.append({"path": relative, "reason": "exact_masked_engine_repr_password_is_three_stars", "shape_sha256": sha(match[0].encode())})
                        text = text.replace(match[0], "[verified masked engine shape]")
            if any(pattern.search(text) for pattern in patterns):
                unclassified.append(relative)
        entry = {"path": relative, "bytes": len(raw), "sha256": sha(raw)}
        if path == REPORT:
            entry["exact_raw_copy"] = (RUN / "report_raw.md.gz").relative_to(ROOT).as_posix()
        if path.suffix == ".gz":
            entry["expanded_bytes"] = len(expanded)
            entry["expanded_sha256"] = sha(expanded)
        entries.append(entry)
    diagnostic = {"actual_value_matches": len(actual_hits), "actual_hit_paths": actual_hits, "unclassified_shapes": len(unclassified), "unclassified_paths": unclassified, "controlled_fixture_fields": classified}
    (RUN / "scan_diagnosis.json").write_bytes(json.dumps(diagnostic, indent=2).encode())
    assert not actual_hits and not unclassified, "scan found unclassified values; paths are in scan_diagnosis.json"
    tracked = git("diff", "--name-only").decode().splitlines()
    assert not tracked
    status = git("status", "--porcelain", "--untracked-files=all").decode().splitlines()
    allowed = {"reports/reviews/recovery/G-D-R11-sbom-inventory-review-1-recheck.md", RUN.relative_to(ROOT).as_posix() + "/"}
    assert all(line.startswith("?? ") and (line[3:].replace("\\", "/") == REPORT.relative_to(ROOT).as_posix() or line[3:].replace("\\", "/").startswith(RUN.relative_to(ROOT).as_posix() + "/")) for line in status)
    assert git("rev-parse", "HEAD").decode().strip() == MATERIAL
    assert gzip.decompress((RUN / "report_raw.md.gz").read_bytes()) == REPORT.read_bytes()
    old_manifest = json.loads((OLD_RUN / "artifact_manifest.json").read_bytes())
    for entry in old_manifest["entries"]:
        assert sha((OLD_RUN.parents[2] / entry["path"]).read_bytes()) == entry["sha256"]
    author = ROOT / "reports/runs/recovery_r11_sbom_inventory_privacy_fix1_20261016"
    controls = [{"path": (author / name).relative_to(ROOT).as_posix(), "sha256": sha((author / name).read_bytes()), "bytes": len((author / name).read_bytes())} for name in ("artifact_manifest.json", "seal_receipt.json")]
    scope = {"time": now(), "tracked_diff_paths": tracked, "status": status, "author_control_files": controls, "old97_unchanged": True}
    (RUN / "scope_diff_receipt.json").write_bytes(json.dumps(scope, indent=2).encode())
    for name in ("scan_diagnosis.json", "scope_diff_receipt.json"):
        path = RUN / name
        raw = path.read_bytes()
        entries.append({"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw), "sha256": sha(raw)})
    manifest = {"source_commit": CODE, "material_commit": MATERIAL, "report_raw_sha256": sha(REPORT.read_bytes()), "entries": entries}
    manifest_raw = json.dumps(manifest, indent=2, ensure_ascii=False).encode()
    (RUN / "artifact_manifest.json").write_bytes(manifest_raw)
    for entry in entries:
        assert sha((ROOT / entry["path"]).read_bytes()) == entry["sha256"]
    receipt = {"start": started, "end": now(), "source_commit": CODE, "material_commit": MATERIAL,
               "report_raw_sha256": sha(REPORT.read_bytes()), "report_gzip_sha256": sha((RUN / "report_raw.md.gz").read_bytes()),
               "manifest_sha256": sha(manifest_raw), "files": len(entries), "secret_reference_source": source,
               "actual_value_count": len(actual), "actual_value_matches": 0, "expanded_scan_files": expanded_count,
               "unclassified_shape_matches": 0, "classified_fixture_fields": len(classified), "all_indexed_bytes_verified": True,
               "old97_unchanged": True, "external_calls": 0, "fees": 0}
    (RUN / "seal_receipt.json").write_bytes(json.dumps(receipt, indent=2).encode())
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
