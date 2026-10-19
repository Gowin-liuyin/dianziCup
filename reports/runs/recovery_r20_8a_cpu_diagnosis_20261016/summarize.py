"""Summarize saved observations without launching further workers."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]


def events(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.startswith("{")]


def main() -> None:
    summaries = []
    for path in sorted(RUN.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if "sample_id" not in value:
            continue
        samples = events(value["stdout"])
        guard_path = RUN / value["sample_id"] / "guard.stdout.jsonl"
        guard = events(guard_path.read_text(encoding="utf-8")) if guard_path.exists() else []
        target_pid = next((sample["pid"] for sample in samples if sample.get("event") == "entry"), None)
        target = next((process for process in value["processes"] if process["pid"] == target_pid), None)
        summary = {key: value[key] for key in ("sample_id", "argv", "cwd", "started_at", "ended_at", "wall_seconds", "exit_code", "outer_timeout", "observed_process_count", "observed_cpu_seconds")}
        summary.update(primary_worker_samples=4 if value["sample_id"] == "original_four" else 1,
                       sample_validity="misconfigured coverage: import cost only, tracing inactive" if value["sample_id"].startswith("coverage_") and not value["sample_id"].startswith("coverage_valid_") else "valid for stated scenario",
                       events=[sample for sample in samples if sample["event"] != "api"],
                       target_final=target["final"] if target else None,
                       guard_events=guard,
                       guard_stderr=(guard_path.parent / "guard.stderr.log").read_text(encoding="utf-8") if guard_path.exists() else None,
                       result_lines=[line for line in value["stdout"].splitlines() if line.startswith(("TREE ", "RESULT ", "PDF_RESULT ", "UNSUPERVISED_RESULT"))],
                       all_observed_signaled=all(process["final"]["signaled"] for process in value["processes"]),
                       failed_get_process_times=[(process["pid"], process["final"]) for process in value["processes"] if not process["final"]["success"]],
                       discovery_errors=value["discovery_errors"])
        summaries.append(summary)
    original = ET.parse(RUN / "original_four.xml").getroot()
    cases = [{"name": case.attrib["name"], "seconds": float(case.attrib["time"]),
              "failure": case.find("failure").attrib.get("message") if case.find("failure") is not None else None}
             for case in original.iter("testcase")]
    totals = {"primary_worker_samples": sum(row["primary_worker_samples"] for row in summaries),
              "observed_process_instances": sum(row["observed_process_count"] for row in summaries),
              "observed_cpu_seconds": sum(row["observed_cpu_seconds"] for row in summaries),
              "sample_wall_seconds_sum": sum(row["wall_seconds"] for row in summaries),
              "all_observed_signaled": all(row["all_observed_signaled"] for row in summaries),
              "outer_timeout_count": sum(row["outer_timeout"] for row in summaries)}
    identity = {"python": sys.executable, "version": sys.version, "platform": platform.platform(),
                "head": "8a1b04d48346d8550f0326a77f003246a0ebbab5",
                "locked_environment": "uv sync --locked --offline; editable root project installed by uv sync"}
    sources = ["backend/src/ai_intel/infrastructure/process_limits.py", "backend/src/ai_intel/ingestion/parsing/_pdf_worker.py",
               "backend/src/ai_intel/ingestion/parsing/pdf_text.py", "backend/src/ai_intel/infrastructure/models/semantic.py",
               "backend/tests/unit/test_r20_native_cpu_guard.py", "backend/tests/unit/test_r20_process_startup.py",
               "backend/pyproject.toml", "backend/uv.lock", "docs/references/competition_brief.pdf"]
    identity["sources"] = [{"path": path, "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()} for path in sources]
    summary = {"totals": totals, "identity": identity, "original_test_cases": cases, "samples": summaries,
               "sampling_limitations": ["Toolhelp discovery at nominal 5ms can miss a process which starts and exits before a snapshot.",
                                         "All counts and CPU totals are observed process instances, not a proof of every kernel helper or a universal CPU cap.",
                                         "Instrumented code adds imports, JSON serialization and logging; absolute entry CPU includes that diagnostic work.",
                                         "time.monotonic() on this interpreter shows approximately 15.625ms quantization; no hard scheduling bound inferred."]}
    (RUN / "execution_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(totals))
    for row in summaries:
        print(row["sample_id"], row["target_final"], row["events"], row["result_lines"])
    print(cases)


if __name__ == "__main__":
    main()
