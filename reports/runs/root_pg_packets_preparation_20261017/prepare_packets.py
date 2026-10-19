"""Prepare frozen Root-only PG launch inputs without importing or running product code."""

import ast
import ctypes
import difflib
import hashlib
import importlib.util
import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = Path("D:/dianzi")
R10 = Path("D:/wt/r10-policy-review1-fix1")
R16 = Path("D:/wt/r16-r17-changes-review1")
QA = Path("D:/wt/r18-qa-reader-review1-closed-pairs")
QA_RUN = QA / "reports/runs/r18_trusted_qa_reader_review1_closed_pairs_20261017/pg_support_closed_pairs"
MOTHER = Path("D:/wt/r18-ports-review1/reports/runs/r18_plugin_production_ports_review1_20261017/pg_support")
R10_RUN = R10 / "reports/runs/r10_policy_review1_fix1_20261017/pg_support"
R16_RUN = R16 / "reports/runs/r16_r17_change_history_review1_fix1_20261017"
BASELINE = "0291d197587141b9f7f5da0d01800d8cbdf58d11"
R10_SOURCE = "986b01ea21b9cc51d5bd30bd569a8fc63af0d3ba"
R16_SOURCE = "14ce965b66fbf8f74221eb01e1426cf1636ea9fc"
PYTHON = "C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe"
CAPS = {"target": 2, "sampler": 1, "process_memory": 536870912,
        "job_memory": 1073741824, "cpu_cores": 2, "native_process": 9, "full_windows": 10}
DEADLINE = {"controller_seconds": 58, "child_cutoff_seconds": 48, "root_outer_seconds": 60}
CHECKS = []
INPUTS = {}


def check(name, condition):
    if not condition:
        raise RuntimeError("preparation_check_failed:" + name)
    CHECKS.append(name)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def frozen_file(path):
    path = path.resolve()
    raw = path.read_bytes()
    item = {"path": str(path), "raw_sha256": digest(raw), "bytes": len(raw),
            "mtime_ns": str(path.stat().st_mtime_ns)}
    INPUTS[str(path)] = item
    return item


def write(path, raw):
    path = path.resolve()
    check("write_inside_own_directory:" + path.name, path.is_relative_to(RUN))
    check("no_existing_output_overwrite:" + path.name, not path.exists())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def write_json(path, value):
    write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def python_tree(raw):
    return ast.dump(ast.parse(raw.decode("utf-8-sig")), include_attributes=False)


def replace_exact(raw, replacements):
    result = raw.decode("utf-8-sig")
    for old, new in replacements:
        check("one_exact_replacement:" + old, result.count(old) == 1)
        result = result.replace(old, new)
    return result.encode("utf-8")


def migrate_compatibility():
    records = []
    for worktree in (R10, R16, QA):
        for root_path in sorted((ROOT / "backend/migrations/versions").glob("*.py")):
            number = int(root_path.name.split("_", 1)[0])
            if number > 31:
                continue
            source_path = worktree / root_path.relative_to(ROOT)
            root_raw, source_raw = root_path.read_bytes(), source_path.read_bytes()
            root_normalized = root_raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            source_normalized = source_raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            same_ast = python_tree(root_raw) == python_tree(source_raw)
            check("whole_migration_ast:" + str(worktree) + ":" + root_path.name, same_ast)
            check("normalized_migration_raw:" + str(worktree) + ":" + root_path.name,
                  root_normalized == source_normalized)
            records.append({"worktree": str(worktree), "file": root_path.name,
                            "root": frozen_file(root_path), "source": frozen_file(source_path),
                            "raw_equal": root_raw == source_raw,
                            "newline_normalized_sha256": digest(root_normalized),
                            "whole_ast_sha256": digest(python_tree(root_raw).encode()),
                            "normalized_equal": True, "whole_ast_equal": same_ast})
    check("all_three_times31_migrations_compared", len(records) == 93)
    write_json(RUN / "migration_compatibility.json", {"root_head": "0031_public_task_bindings",
        "previous_head": "0030_revalidation_actor_bindings", "comparison": "full raw/newline-normalized/full AST; no execution",
        "records": records})


def prepare_r16():
    original_packet_path = R16_RUN / "pg_execution_packet.json"
    packet = json.loads(original_packet_path.read_bytes())
    check("r16_packet_fixed_source", packet["r16_source_sha"] == R16_SOURCE)
    check("r16_packet_fixed_ui", packet["r17_source_sha"] == "dd35f7a90bb8573e2acbd62319a62577804fcddd")
    check("r16_packet13_not14", packet["combined_collect_only_count"] == 13 and
          packet["author_tests_collected"] == 12 and packet["reviewer_sample_collected"] == 1)
    check("r16_packet_runtime_caps", packet["runtime_limits"] == {
        "controller_seconds": 58, "child_seconds": 48, "outer_seconds": 60,
        "process_memory_bytes": 536870912, "job_memory_bytes": 1073741824,
        "logical_cpu_max": 2, "full_windows_process_max": 10, "remaining_own_births_required": 0})
    for relative, expected in packet["actual_source_raw_hashes"].items():
        check("r16_author_source_raw:" + relative, frozen_file(R16 / relative)["raw_sha256"] == expected)
    for name, expected_key in (("test_review_pg_counterexamples.py", "reviewer_sample_raw_sha256"),
                               ("pg_collect_fixture_guard.py", "fixture_guard_raw_sha256")):
        check("r16_review_probe_raw:" + name, frozen_file(R16_RUN / name)["raw_sha256"] == packet[expected_key])
    report = R16 / "reports/reviews/recovery/G-E-R16-R17-change-history-review-1-recheck-fix1.md"
    frozen_file(report)
    frozen_file(R16_RUN / "input_manifest.json")
    collection = R16_RUN / "fix1_own_pg13_fixture_guard_collect.stdout.log"
    frozen_file(collection)
    nodes = []
    for line in collection.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("tests/integration/test_r16_change_history_http_pg.py::"):
            nodes.append(line)
        elif line == "::test_real_fixture_revision_remains_fixture_through_live_http_configuration":
            nodes.append(str(R16_RUN / "test_review_pg_counterexamples.py") + line)
    check("r16_exact13_distinct_leaf_nodes", len(nodes) == len(set(nodes)) == 13)
    support = RUN / "r16_pg_support"
    mother_packet = json.loads((MOTHER / "root_launch_packet.json").read_bytes())
    mother_admission = json.loads((MOTHER / "pg_controller_admission.json").read_bytes())
    check("mother_controller_hash", frozen_file(MOTHER / "run_pg_review.py")["raw_sha256"] == mother_packet["controller_raw_sha256"])
    check("mother_admission_hash", frozen_file(MOTHER / "pg_controller_admission.json")["raw_sha256"] == mother_packet["admission_raw_sha256"])
    changes = {
        "run_pg_review.py": [
            ('!= "root-batch17-review1"', '!= "r16-history-review1"'),
            ('run_id = "root_batch17_r1_"', 'run_id = "r16_change_history_http_"'),
            ('schema = "test_r05_root17_"', 'schema = "test_r16_review1_"'),
            ('"owner": "root-batch17-review1:"', '"owner": "r16-history-review1:"'),
            ('application_name="root_batch17_parent_sampler"', 'application_name="r16_history_parent_sampler"'),
            ('"-p", "task_pg_identity", *fixture_plugins,', '"-p", "task_pg_identity", *fixture_plugins,\n                   "-p", "reports.runs.r16_r17_change_history_review1_fix1_20261017.pg_collect_fixture_guard",'),
            ('none; original ports16 and independent sourcecycle2 unchanged; Root0031 exact dependency only',
             'none; original history12 and independent fixture-mode1 unchanged; Root0031 exact dependency only'),
        ],
        "pg_review_environment.py": [
            ('ROOT = Path("D:/wt/r18-ports-review1")', 'ROOT = Path("D:/wt/r16-r17-changes-review1")'),
            ('BASELINE = "9d8b222cd6cfcc87e618867c918a1b8fcdafa32f"', 'BASELINE = "' + BASELINE + '"'),
            ('QUALIFIED = "eea52940506fb19b07d452c25ec3a273b0e42cca"', 'QUALIFIED = "' + R16_SOURCE + '"'),
            ('MATERIAL = "ed962b76d36a39d474ae887033d3b71de2882fc6"', 'MATERIAL = "f2c5ad7229d4ce04e95e4457466731319120285e"'),
        ],
        "task_pg_identity.py": [
            ('r"root_batch17_r1_[a-f0-9]{12}"', 'r"r16_change_history_http_[a-f0-9]{12}"'),
            ('r"test_r05_root17_[a-f0-9]{12}"', 'r"test_r16_review1_[a-f0-9]{12}"'),
            ('"root-batch17-review1:"', '"r16-history-review1:"'),
        ],
    }
    helpers = ["batch13_process_metadata.py", "core_runtime_limits.py", "parent_lock_observation.py",
               "pg_phase_plugin.py", "process_identity.py", "worker_entry.py", "task_pg_identity.py",
               "pg_review_environment.py", "run_pg_review.py", "task_migration_entry.py"]
    for name in helpers:
        original = (MOTHER / name).read_bytes()
        check("mother_entry_admitted:" + name, digest(original) == mother_admission["entry_raw_sha256"][name])
        frozen_file(MOTHER / name)
        output = replace_exact(original, changes[name]) if name in changes else original
        write(support / name, output)
        if name in changes:
            patch = "".join(difflib.unified_diff(original.decode().splitlines(True), output.decode().splitlines(True),
                        fromfile=str(MOTHER / name), tofile=str(support / name)))
            write(RUN / (name + ".mother.diff"), patch.encode())
    migration = (support / "task_migration_entry.py").read_text()
    check("mother_no_r05_seed", "load_legacy" not in migration and "0031_public_task_bindings" in migration)
    write_json(support / "pg_batch_plan.json", {"groups": [{"label": "pg_history_original13", "nodes": nodes,
        "expected_cases": 13, "requires_repository_fixture_plugin": False}]})
    source_hashes = {}
    for relative_root in ("backend/src", "backend/migrations", "backend/tests"):
        for source_file in sorted((R16 / relative_root).rglob("*.py")):
            source_hashes[str(source_file.relative_to(R16))] = frozen_file(source_file)["raw_sha256"]
    for relative, expected in packet["actual_source_raw_hashes"].items():
        source_hashes[relative] = expected
    source_hashes[str((R16_RUN / "test_review_pg_counterexamples.py").relative_to(R16))] = packet["reviewer_sample_raw_sha256"]
    source_hashes[str((R16_RUN / "pg_collect_fixture_guard.py").relative_to(R16))] = packet["fixture_guard_raw_sha256"]
    source_hashes[str(original_packet_path.relative_to(R16))] = frozen_file(original_packet_path)["raw_sha256"]
    entries = {path.name: digest(path.read_bytes()) for path in support.iterdir() if path.is_file()}
    write_json(support / "pg_controller_admission.json", {"source_sha": R16_SOURCE, "source_baseline": BASELINE,
        "source_worktree": str(R16), "entry_raw_sha256": entries, "source_worktree_sha256": source_hashes})
    result = {"source_sha": R16_SOURCE, "root_baseline": BASELINE, "material_sha": packet["author_packet_material_sha"],
        "controller_path": str(support / "run_pg_review.py"), "controller_raw_sha256": digest((support / "run_pg_review.py").read_bytes()),
        "worker_entry_path": str(support / "worker_entry.py"), "worker_raw_sha256": digest((support / "worker_entry.py").read_bytes()),
        "admission_path": str(support / "pg_controller_admission.json"), "admission_raw_sha256": digest((support / "pg_controller_admission.json").read_bytes()),
        "allowed_labels": ["pg_history_original13"], "group_case_counts": [13], "deadline": DEADLINE,
        "resource_caps": CAPS, "root_required_environment": {
            "R18_REVIEW_PARENT_DATABASE_URL": "Root memory injection only", "DIANZI_REVIEW_RESOURCE_AUTHORIZED": "r16-history-review1",
            "R18_REVIEW_BATCH_ALLOWLIST": "JSON exact single-label", "R18_REVIEW_AUTHORIZED_UNTIL_UTC": "fresh UTC <=600s"},
        "source_oids_identity_only": [10451302, 10434264], "schema_head": "0031_public_task_bindings",
        "run_id_prefix": "r16_change_history_http_", "original_reviewer_packet": str(original_packet_path),
        "original_reviewer_packet_raw_sha256": digest(original_packet_path.read_bytes()),
        "oracle_changed": False, "prepared_not_run": True, "no_pg_or_secret_access": True}
    write_json(support / "root_launch_packet.json", result)
    return support / "root_launch_packet.json"


def bind_packet(path, expected_root):
    packet = json.loads(path.read_bytes())
    check("packet_required_keys:" + str(path), all(key in packet for key in (
        "source_sha", "controller_path", "controller_raw_sha256", "admission_path", "admission_raw_sha256",
        "allowed_labels", "root_required_environment")))
    if path.parent == QA_RUN:
        check("qa_packet_fixed_source", packet["source_sha"] == "07664fd7f328803ade6f30372bfd04c395033a42")
        check("qa_packet_fixed_controller", packet["controller_raw_sha256"] == "aa7d94bcd52e49ee05b3381077f0cdec825f1892cef85db16a05e7979a106c0b")
        check("qa_packet_fixed_admission", packet["admission_raw_sha256"] == "fdbc913cc261aefceecd0258414f6a348ea4d492136f862363c6c056d118cf35")
        check("qa_flat_packet_limits", [packet[name] for name in (
            "target_soft_cap", "parent_sampler_cap", "physical_cap", "native_active_cap", "full_windows_cap",
            "controller_seconds", "child_cutoff_seconds", "outer_seconds", "process_memory_bytes",
            "job_memory_bytes", "cpu_cores_maximum")] == [2, 1, 3, 9, 10, 58, 48, 60, 536870912, 1073741824, 2])
    else:
        check("packet_fixed_limits:" + str(path), packet["deadline"] == DEADLINE and packet["resource_caps"] == CAPS)
        check("packet_group_counts:" + str(path), len(packet["allowed_labels"]) == len(packet["group_case_counts"]))
    controller = Path(packet["controller_path"])
    directory = controller.parent
    admission_path = Path(packet["admission_path"])
    admission = json.loads(admission_path.read_bytes())
    check("packet_controller_content:" + str(path), frozen_file(controller)["raw_sha256"] == packet["controller_raw_sha256"])
    check("packet_admission_content:" + str(path), frozen_file(admission_path)["raw_sha256"] == packet["admission_raw_sha256"])
    check("packet_admission_schema:" + str(path), isinstance(admission["entry_raw_sha256"], dict) and
          isinstance(admission["source_worktree_sha256"], dict) and admission["source_sha"] == packet["source_sha"])
    source_root = expected_root
    if "source_worktree" in admission:
        check("admission_source_root:" + str(path), Path(admission["source_worktree"]).resolve() == source_root.resolve())
    environment_path = directory / ("review_checks.py" if path.parent == QA_RUN else "pg_review_environment.py")
    environment_tree = ast.parse(environment_path.read_bytes())
    constants = {node.targets[0].id: node.value for node in environment_tree.body if isinstance(node, ast.Assign)
                 and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}
    root_value = constants["ROOT"]
    check("environment_root_ast:" + str(path), isinstance(root_value, ast.Call) and
          isinstance(root_value.func, ast.Name) and root_value.func.id == "Path" and
          len(root_value.args) == 1 and Path(ast.literal_eval(root_value.args[0])).resolve() == source_root.resolve())
    check("environment_source_ast:" + str(path), ast.literal_eval(constants["QUALIFIED"]) == packet["source_sha"])
    frozen = [frozen_file(path), frozen_file(admission_path)]
    for relative, expected in admission["entry_raw_sha256"].items():
        item = frozen_file(directory / relative)
        check("entry_content:" + str(path) + ":" + relative, item["raw_sha256"] == expected)
        frozen.append(item)
    for relative, expected in admission["source_worktree_sha256"].items():
        item = frozen_file(source_root / relative)
        check("source_content:" + str(path) + ":" + relative, item["raw_sha256"] == expected)
        frozen.append(item)
    groups = json.loads((directory / "pg_batch_plan.json").read_bytes())["groups"]
    expected_counts = [g["expected_cases"] for g in groups] if path.parent == QA_RUN else packet["group_case_counts"]
    check("batch_plan_matches_packet:" + str(path), [(g["label"], len(g["nodes"]), g["expected_cases"]) for g in groups] ==
          [(label, count, count) for label, count in zip(packet["allowed_labels"], expected_counts)])
    if path.parent == QA_RUN:
        check("qa_exact19_unique_original_nodes", sum(expected_counts) == packet["planned_cases"] == 19 and
              len({node for group in groups for node in group["nodes"]}) == 19)
        check("qa_12entries_255source", len(admission["entry_raw_sha256"]) == 12 and len(admission["source_worktree_sha256"]) == 255)
    return {"packet_path": str(path.resolve()), "packet_raw_sha256": digest(path.read_bytes()),
        "source_sha": packet["source_sha"], "source_root": str(source_root), "support_root": str(directory),
        "controller_path": str(controller), "entry_path": str(directory / "worker_entry.py"),
        "admission_path": str(admission_path), "authority_header": packet["root_required_environment"]["DIANZI_REVIEW_RESOURCE_AUTHORIZED"],
        "groups": {g["label"]: g["expected_cases"] for g in groups}, "frozen_files": frozen}


def main():
    started, monotonic_start = datetime.now(timezone(timedelta(hours=8))).isoformat(), time.monotonic()
    spec = importlib.util.spec_from_file_location("preparation_native_limits", RUN / "core_runtime_limits.py")
    limits = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(limits)
    limits.MEMORY_TOTAL, limits.CPU_RATE = 1073741824, 20000 // os.cpu_count()
    job = limits.OwnedJob()
    actual = job.query(9, limits.ExtendedLimits)
    actual.basic.flags |= 0x8
    actual.basic.active_limit = 9
    check("native_nine_process_limit", bool(job.kernel.SetInformationJobObject(job.handle, 9, ctypes.byref(actual), ctypes.sizeof(actual))))
    job.kernel.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    watchdog = threading.Timer(9, lambda: job.kernel.TerminateJobObject(job.handle, 124))
    watchdog.daemon = True
    watchdog.start()
    try:
        migrate_compatibility()
        r16_packet_path = prepare_r16()
        bindings = [bind_packet(QA_RUN / "root_launch_packet.json", QA),
                    bind_packet(R10_RUN / "root_launch_packet.json", R10), bind_packet(r16_packet_path, R16)]
        check("r10_fixed_source", bindings[1]["source_sha"] == R10_SOURCE)
        root_schema_files = [item for item in INPUTS.values() if Path(item["path"]).is_relative_to(ROOT / "backend/migrations")]
        for binding in bindings:
            binding["frozen_files"].extend(root_schema_files)
        write_json(RUN / "launch_bindings.json", {"schema_version": "root-pg-packets-preparation-1",
            "root_baseline": BASELINE, "deadline": DEADLINE, "resource_caps": CAPS,
            "source_oids_identity_only": [10451302, 10434264], "packets": bindings})
        bindings_sha = digest((RUN / "launch_bindings.json").read_bytes())
        template = (RUN / "launch_root_pg_packet.template.ps1").read_bytes()
        write(RUN / "launch_root_pg_packet.ps1", replace_exact(template, [("__BINDINGS_RAW_SHA256__", bindings_sha)]))
        for path in sorted(RUN.rglob("*.py")):
            ast.parse(path.read_bytes(), filename=str(path))
            CHECKS.append("syntax_only:" + str(path.relative_to(RUN)))
        parser_command = ["C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe", "-NoLogo", "-NoProfile", "-File", str(RUN / "syntax_only.ps1")]
        parsed = subprocess.run(parser_command, capture_output=True, timeout=max(0.1, 8.5 - (time.monotonic() - monotonic_start)),
            env={"SystemRoot": "C:/Windows", "WINDIR": "C:/Windows", "PATH": "C:/Windows/System32", "TEMP": str(RUN), "TMP": str(RUN)})
        write(RUN / "syntax.stdout.log", parsed.stdout)
        write(RUN / "syntax.stderr.log", parsed.stderr)
        check("powershell_parse_exit_zero", parsed.returncode == 0)
        write_json(RUN / "input_manifest.json", {"prepared_at": started, "files": list(INPUTS.values())})
        receipt = {"started_at": started, "ended_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "elapsed_seconds": time.monotonic() - monotonic_start, "exit_code": 0,
            "watchdog_seconds": 9, "outer_seconds": 10, "check_count": len(CHECKS), "checks": CHECKS,
            "business_tests_executed": 0, "pg_connected": False, "secrets_read": False,
            "job_limits": {"process_memory_bytes": 536870912, "job_memory_bytes": 1073741824,
                "native_process_max": 9, "logical_cpu_max": 2, "usage": job.usage()},
            "powershell_parse_argv": parser_command, "powershell_parse_exit_code": parsed.returncode,
            "launch_bindings_raw_sha256": bindings_sha}
        write_json(RUN / "preparation_receipt.json", receipt)
        print(json.dumps({"exit_code": 0, "elapsed_seconds": receipt["elapsed_seconds"],
            "check_count": len(CHECKS), "business_tests_executed": 0, "pg_connected": False}))
    finally:
        watchdog.cancel()


if __name__ == "__main__":
    main()
