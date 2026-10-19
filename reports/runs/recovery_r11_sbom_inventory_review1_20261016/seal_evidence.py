"""封存报告原bytes和完整run文件，按实际凭据值及形状校验公开材料。"""

import gzip
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/reviews/recovery/G-D-R11-sbom-inventory-review-1.md"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main():
    started = now()
    result = subprocess.run(
        [
            "wsl.exe",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--exec",
            "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ],
        capture_output=True,
        check=True,
    )
    configured = json.loads(result.stdout)
    credentials = []
    for key, value in configured.items():
        if isinstance(value, str):
            if any(word in key.lower() for word in ("password", "secret", "token", "access_key")):
                credentials.append(value)
            if "://" in value:
                credentials.append(value)
                password = urlsplit(value).password
                if password:
                    credentials.append(unquote(password))
    credentials = sorted({value for value in credentials if len(value) >= 8}, key=len, reverse=True)
    report = REPORT.read_text(encoding="utf-8")
    report = re.sub(r"\n最终报告封存写入时间：.*\n?", "\n", report)
    report += "\n最终报告封存写入时间：" + now() + "（Asia/Shanghai）。\n"
    REPORT.write_bytes(report.encode("utf-8"))
    raw = REPORT.read_bytes()
    (RUN / "report_raw.md.gz").write_bytes(gzip.compress(raw, mtime=0))
    (RUN / ".gitattributes").write_bytes(
        b"* -text whitespace=trailing-space,space-before-tab,cr-at-eol\n*.log -diff\n*.xml -diff\n"
    )
    source_status = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            "c0369e6b",
            "--",
            "backend",
            "docs",
            "contracts",
            "progress",
            "frontend",
        ],
        cwd=ROOT,
        capture_output=True,
    )
    assert source_status.returncode == 0
    items = [
        REPORT,
        *sorted(
            path
            for path in RUN.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.name not in {"artifact_manifest.json", "seal_receipt.json"}
        ),
    ]
    actual_value_hits = []
    shape_hits = []
    blocked_shapes = []
    dsn_pattern = re.compile(r"postgres(?:ql)?(?:\+[A-Za-z0-9_]+)?://[^\s\"'<>\\]+")
    token_pattern = re.compile(
        r"""(?i)(?:password|csrf_token|session_token|authorization|cookie)["']\s*:\s*["']([A-Za-z0-9_-]{24,})["']"""
    )
    entries = []
    for path in items:
        saved = path.read_bytes()
        content = gzip.decompress(saved) if path.suffix == ".gz" else saved
        for secret in credentials:
            if secret.encode() in content:
                actual_value_hits.append(path.relative_to(ROOT).as_posix())
        text = content.decode("utf-8", errors="replace")
        for match in dsn_pattern.finditer(text):
            value = match.group()
            classification = (
                "explicit_synthetic_fixture"
                if "synthetic" in value
                else "pytest_abbreviated_synthetic_fixture"
                if path.name
                in {
                    "pg_compatibility.log",
                    "pg_compatibility.xml",
                    "pg_probes_second.log",
                    "pg_probes_second.xml",
                }
                and value.startswith("postgresql://" + "synth...")
                else "password_masked_test_engine_repr"
                if ":***@" in value
                else "unclassified_connection_shape"
            )
            item = {"path": path.relative_to(ROOT).as_posix(), "kind": classification}
            shape_hits.append(item)
            if classification == "unclassified_connection_shape":
                blocked_shapes.append(item)
        for _match in token_pattern.finditer(text):
            blocked_shapes.append(
                {"path": path.relative_to(ROOT).as_posix(), "kind": "credential_value_shape"}
            )
        entries.append(
            {"path": path.relative_to(ROOT).as_posix(), "bytes": len(saved), "sha256": sha(saved)}
        )
    assert not actual_value_hits, "actual credential found in material"
    assert not blocked_shapes, "unclassified credential shape found in material"
    assert gzip.decompress((RUN / "report_raw.md.gz").read_bytes()) == REPORT.read_bytes()
    manifest = {
        "code_commit": "0892b6af7fbc0c16651aeb25f14493fb4c3fa48d",
        "material_commit": "c0369e6b7cb71c19f7594da8737e6bb3717893f3",
        "report_path": REPORT.relative_to(ROOT).as_posix(),
        "entries": entries,
        "excluded_self_referential": ["artifact_manifest.json", "seal_receipt.json"],
    }
    manifest_raw = json.dumps(manifest, indent=2, ensure_ascii=False).encode()
    (RUN / "artifact_manifest.json").write_bytes(manifest_raw)
    receipt = {
        "start": started,
        "end": now(),
        "argv": [sys.executable, str(__file__)],
        "cwd": str(Path.cwd()),
        "exit_code": 0,
        "status": "needs_changes",
        "report_sha256": sha(raw),
        "report_raw_copy": "report_raw.md.gz",
        "report_gzip_sha256": sha((RUN / "report_raw.md.gz").read_bytes()),
        "manifest_sha256": sha(manifest_raw),
        "entry_count": len(entries),
        "actual_dynamic_values_scanned": len(credentials),
        "actual_value_hits": actual_value_hits,
        "shape_hits": shape_hits,
        "blocked_shapes": blocked_shapes,
        "source_scope_diff_exit": source_status.returncode,
        "runtime": {
            "python": sys.version,
            **{
                name: version(name)
                for name in ("sqlalchemy", "pytest", "packageurl-python", "pydantic", "jsonschema")
            },
        },
    }
    (RUN / "seal_receipt.json").write_bytes(json.dumps(receipt, indent=2).encode())
    print(
        json.dumps(
            {
                key: receipt[key]
                for key in (
                    "start",
                    "end",
                    "exit_code",
                    "status",
                    "report_sha256",
                    "report_gzip_sha256",
                    "manifest_sha256",
                    "entry_count",
                    "actual_dynamic_values_scanned",
                    "actual_value_hits",
                    "blocked_shapes",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
