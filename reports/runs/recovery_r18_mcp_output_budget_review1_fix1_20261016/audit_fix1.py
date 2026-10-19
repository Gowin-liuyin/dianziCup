"""Read-only independent audit of frozen fix1 bytes and all protected old evidence."""

import hashlib
import json
import subprocess
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
AUTHOR = Path("D:/wt/r18-mcp-output-budget-fix1")
SOURCE = "c691a0d5d0e06a4cc52567e1e816cd49cb0b1e7f"
MATERIAL = "260942efc77168683b2b978747a19c3c9fedce3e"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main() -> None:
    assert git("rev-parse", "HEAD").decode().strip() == MATERIAL
    assert (
        git("rev-parse", SOURCE + "^{tree}").decode().strip()
        == "9980da61338eb7b2b9202f98aa0c1055af1f9f70"
    )
    assert (
        git("rev-parse", MATERIAL + "^{tree}").decode().strip()
        == "b2444f8a03aadfef01e40a96eb79c2f60597b079"
    )
    relative = "reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/artifact_manifest.json"
    raw = (AUTHOR / relative).read_bytes()
    assert sha(raw) == "3186563c35bff534b0e2b332148a58b0035d657d983677943291ce90a85121e6"
    manifest = json.loads(raw)
    assert len(manifest["files"]) == 76
    for entry in manifest["files"]:
        assert sha((AUTHOR / entry["path"]).read_bytes()) == entry["raw_sha256"], entry["path"]
        assert sha(git("show", MATERIAL + ":" + entry["path"])) == entry["git_blob_sha256"], entry[
            "path"
        ]
    report = "reports/tasks/R18-mcp-output-budget-fix1.md"
    assert (
        sha((AUTHOR / report).read_bytes())
        == "7d31de97e01ea592740e2b9fc69a8021225a4fe641801e41d0fa42aa9fc6abd6"
    )
    protected = []
    specifications = [
        (
            "r18-client-sdk",
            "recovery_r18_client_sdk_20261016",
            "c381854c08a66ccf0f5e22644e3e852e7aa3a17cd4a1ab1eaeccf9663089e6fb",
            "artifacts",
            "raw_sha256",
            86,
        ),
        (
            "r18-sdk-client-review1",
            "recovery_r18_sdk_cli_review1_20261016",
            "03ff1575004f98269b25397653b54930096e21d57146681d7ee8b42c31faa687",
            "artifacts",
            "raw_sha256",
            83,
        ),
        (
            "r18-sdk-client-fix1",
            "recovery_r18_sdk_client_fix1_20261016",
            "265539c8e9978eb28c36f8e017d323e4f91707dec8819f7a9b10b5166b387558",
            "files",
            "sha256",
            110,
        ),
        (
            "r18-mcp-adapter",
            "recovery_r18_mcp_adapter_20261016",
            "ec8a015d3c645688efe906980538ae5b155663230a39b2d4d226493d2783f05c",
            "files",
            "sha256",
            89,
        ),
        (
            "r18-mcp-output-budget",
            "recovery_r18_mcp_output_budget_20261016",
            "a8d0fff9f413188b5143f11b169a566e3c392f08a2b0b7e0cb63d42301a02b93",
            "files",
            "raw_sha256",
            91,
        ),
        (
            "r18-mcp-output-budget-review1",
            "recovery_r18_mcp_output_budget_review1_20261016",
            "e8b75e1ad8f83075a29c7f8dcf772ee5bea20102967976bbb1ded68a896ef28a",
            "files",
            "raw_sha256",
            86,
        ),
    ]
    for directory, run_name, expected, field, hash_field, count in specifications:
        root = Path("D:/wt") / directory
        filename = "artifact_manifest_material.json" if count == 91 else "artifact_manifest.json"
        raw = (root / "reports/runs" / run_name / filename).read_bytes()
        assert sha(raw) == expected
        entries = json.loads(raw)[field]
        assert len(entries) == count
        for entry in entries:
            assert sha((root / entry["path"]).read_bytes()) == entry[hash_field], entry["path"]
        protected.append({"manifest": expected, "members": count, "all_raw_unchanged": True})
    assert sum(entry["members"] for entry in protected) == 545
    changes = (
        git(
            "diff",
            "--numstat",
            "f246815bd678c624a11f784de5dc2b3c83981cde",
            SOURCE,
            "--",
            "sdk/python",
        )
        .decode()
        .splitlines()
    )
    assert changes == ["2\t0\tsdk/python/ai_intel_client/mcp_adapter.py"]
    for name in ("__init__.py", "models.py", "cli.py", "client.py"):
        path = "sdk/python/ai_intel_client/" + name
        assert git("show", SOURCE + ":" + path) == git(
            "show", "6d85742b0114cc5e304e88b2aa930755ccce9bc9:" + path
        )
    before = json.loads(
        (
            AUTHOR
            / "reports/runs/recovery_r18_mcp_output_budget_fix1_20261016"
            / "before_fix_output_manifest.json"
        ).read_bytes()
    )
    assert len(before["files"]) == 6
    red_byte_modes = []
    for entry in before["files"]:
        path = (
            "reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/" + entry["preserved_name"]
        )
        raw = (AUTHOR / path).read_bytes()
        assert sha(raw) == entry["sha256"]
        expected_blob = raw if path.endswith(".log") else raw.replace(b"\r\n", b"\n")
        assert git("show", MATERIAL + ":" + path) == expected_blob
        snapshot = RUN / (entry["preserved_name"] + ".raw")
        snapshot.write_bytes(raw)
        red_byte_modes.append(
            {
                "path": path,
                "author_raw_sha256": sha(raw),
                "git_byte_mode": "exact_raw" if path.endswith(".log") else "LF",
                "own_raw_copy": snapshot.name,
            }
        )
    for name, expected in json.loads((RUN / "copied_probe_hashes.json").read_bytes()):
        assert sha((RUN / name).read_bytes()) == expected
        assert (
            sha(
                (
                    AUTHOR / "reports/runs/recovery_r18_mcp_output_budget_fix1_20261016" / name
                ).read_bytes()
            )
            == expected
        )
    contract_path = Path("D:/dianzi/docs/decisions/CR-R18_public_envelopes_and_output_budget.md")
    contract = contract_path.read_bytes()
    assert b"4ccc4337586137a407359a1c4a59dc5d92081a2f4b50ee32cc53fac16095d50b" in contract
    (RUN / "root_cr_r18_snapshot.md").write_bytes(contract)
    observation = {
        "source_sha": SOURCE,
        "source_tree": "9980da61338eb7b2b9202f98aa0c1055af1f9f70",
        "material_sha": MATERIAL,
        "material_tree": "b2444f8a03aadfef01e40a96eb79c2f60597b079",
        "new76_raw_and_git_verified": True,
        "old545": protected,
        "original_six_author_raw_red_outputs_preserved": red_byte_modes,
        "sdk_core4_unchanged": True,
        "product_diff": changes,
        "root_cr_sha256": sha(contract),
    }
    (RUN / "material_observation.json").write_bytes(
        json.dumps(observation, indent=2).encode() + b"\n"
    )
    print(json.dumps(observation, indent=2))


if __name__ == "__main__":
    main()
