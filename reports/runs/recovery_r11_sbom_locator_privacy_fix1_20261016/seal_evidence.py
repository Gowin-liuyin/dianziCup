"""绑定源码、原红、真实回归及精确原字节；凭据只用于内存否定扫描。"""

import ast
import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
import xml.etree.ElementTree as ET
from collections import Counter

from run_checks import DATABASE, ROOT, RUN, now, read_test_reference

BASE = "6aeeeec5489b92bb49613fe5daa4eec379182348"
SOURCE = "dcbc3d928b26f6755a5bfa71a3b70f71527bd832"
REPORT = ROOT / "reports/tasks/R11-sbom-locator-privacy-fix1.md"
SOURCE_FILES = [
    "backend/src/ai_intel/assets/sbom_inventory.py",
    "backend/tests/unit/test_r11_sbom_locator_privacy.py",
]


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT).decode().strip()


def main():
    source = read_test_reference()
    secrets = [source.render_as_string(hide_password=False), source.password]
    secrets.extend(
        source.set(database=database).render_as_string(hide_password=False)
        for database in (DATABASE, DATABASE + "_mig")
    )
    username = source.username
    counts = {}
    for path in sorted(RUN.glob("*.xml")):
        suites = ET.parse(path).getroot().iter("testsuite")
        total = Counter()
        for suite in suites:
            total.update(
                {
                    key: int(suite.get(key, "0"))
                    for key in ("tests", "failures", "errors", "skipped")
                }
            )
        counts[path.name] = dict(total)
    (RUN / "test_counts.json").write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
    preserved = subprocess.run(
        [
            "git",
            "diff",
            "--exit-code",
            BASE,
            "--",
            "backend/tests",
            ":(exclude)backend/tests/unit/test_r11_sbom_locator_privacy.py",
        ],
        cwd=ROOT,
        capture_output=True,
    )
    assert preserved.returncode == 0
    source_entries = []
    for name in SOURCE_FILES:
        path = ROOT / name
        blob = subprocess.check_output(["git", "show", SOURCE + ":" + name], cwd=ROOT)
        source_entries.append(
            {
                "path": name,
                "working_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "git_blob_sha256": hashlib.sha256(blob).hexdigest(),
                "lf_normalized_working_matches_git": path.read_bytes().replace(b"\r\n", b"\n")
                == blob,
                "git_object": git("rev-parse", SOURCE + ":" + name),
            }
        )
    assert all(entry["lf_normalized_working_matches_git"] for entry in source_entries)
    proof = {
        "base_commit": BASE,
        "source_commit": SOURCE,
        "source_tree": git("rev-parse", SOURCE + "^{tree}"),
        "business_file_count": 1,
        "old_tracked_tests_unchanged": True,
        "source_files": source_entries,
        "recorded_at": now(),
        "original_probe_sha256": hashlib.sha256(
            (RUN / "original_probe_frozen.py").read_bytes()
        ).hexdigest(),
    }
    assert (
        proof["original_probe_sha256"]
        == "7e26ef18e236f915447e413784adf8b650b69d257db31afd004a2bebedebd62d"
    )
    original_nodes = ast.parse((RUN / "original_probe_frozen.py").read_text(encoding="utf-8"))
    adapted_nodes = ast.parse(
        (RUN / "adapted_tests/test_default_inventory_api.py").read_text(encoding="utf-8")
    )

    def behavior_functions(module):
        return {
            node.name: ast.dump(node)
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        }

    assert behavior_functions(original_nodes) == behavior_functions(adapted_nodes)
    proof["original_probe_test_functions_ast_equal"] = True
    proof["adapted_probe_sha256"] = hashlib.sha256(
        (RUN / "adapted_tests/test_default_inventory_api.py").read_bytes()
    ).hexdigest()
    proof["test_fixture_adaptation"] = "owned_database_and_nullpool_only_default_app_unchanged"
    (RUN / "source_proof.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    excluded = {"artifact_manifest.json", "credential_scan.json", "evidence_exact_raw.tar.gz"}
    paths = [
        path
        for path in sorted(RUN.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.name not in excluded
    ]
    paths += [ROOT / name for name in SOURCE_FILES] + [REPORT]
    exact_matches, lexical = [], []
    for path in paths:
        raw = path.read_bytes()
        if any(secret and secret.encode() in raw for secret in secrets):
            exact_matches.append(path.relative_to(ROOT).as_posix())
        text = raw.decode("utf-8", errors="replace")
        locations = []
        for number, line in enumerate(text.splitlines(), start=1):
            if username not in line:
                continue
            if "source.username.startswith" in line:
                kind = "ownership_guard_prefix_literal"
            else:
                occurrences = list(re.finditer(re.escape(username), line))
                if all(
                    match.end() < len(line) and re.match(r"[A-Za-z0-9_]", line[match.end()])
                    for match in occurrences
                ):
                    kind = "prefix_inside_longer_test_symbol_or_path"
                else:
                    kind = "requires_review"
            locations.append(
                {
                    "line": number,
                    "count": line.count(username),
                    "classification": kind,
                    "sanitized_context": line.replace(
                        username, "[database username lexical match]"
                    )[:240],
                }
            )
        if locations:
            lexical.append({"path": path.relative_to(ROOT).as_posix(), "matches": locations})
    scan = {
        "recorded_at": now(),
        "scanned_files": len(paths),
        "actual_dsn_or_password_matches": exact_matches,
        "username_lexical_occurrences": lexical,
        "unclassified_username_match_count": sum(
            item["classification"] == "requires_review"
            for entry in lexical
            for item in entry["matches"]
        ),
    }
    (RUN / "credential_scan.json").write_text(json.dumps(scan, indent=2) + "\n", encoding="utf-8")
    assert not exact_matches and scan["unclassified_username_match_count"] == 0
    paths.append(RUN / "credential_scan.json")
    archive = RUN / "evidence_exact_raw.tar.gz"
    with (
        archive.open("wb") as output,
        gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as zipped,
        tarfile.open(fileobj=zipped, mode="w") as tar,
    ):
        for path in paths:
            raw = path.read_bytes()
            info = tarfile.TarInfo(path.relative_to(ROOT).as_posix())
            info.size = len(raw)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(raw))
    paths.append(archive)
    manifest = {
        "recorded_at": now(),
        "source_commit": SOURCE,
        "source_tree": proof["source_tree"],
        "raw_archive": archive.relative_to(ROOT).as_posix(),
        "entries": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in paths
        ],
    }
    (RUN / "artifact_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "artifacts": len(paths),
                "actual_credential_matches": len(exact_matches),
                "unclassified_username_matches": scan["unclassified_username_match_count"],
            }
        )
    )


if __name__ == "__main__":
    main()
