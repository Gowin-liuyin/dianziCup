"""Check audit document links, scope coverage, and independently recorded metadata."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from pypdf import PdfReader


def main() -> None:
    evidence_dir = Path(__file__).resolve().parent
    project_root = evidence_dir.parents[2]
    plan = project_root / "docs/plan/11_full_delivery_recovery_20261014.md"
    task_cards = project_root / "docs/plan/12_recovery_task_cards_20261014.md"
    audit = project_root / "reports/reviews/PLAN-AUDIT-20261014.md"
    documents = (plan, task_cards, audit)
    broken_links: list[str] = []
    checked_links = 0
    whitespace_errors: list[str] = []
    for document in documents:
        content = document.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if "://" in target or target.startswith("#"):
                continue
            checked_links += 1
            relative_target = target.split("#", 1)[0]
            if not (document.parent / relative_target).exists():
                broken_links.append(f"{document.name}: {target}")
        for line_number, line in enumerate(content.splitlines(), 1):
            if line.rstrip() != line:
                whitespace_errors.append(f"{document.name}:{line_number}")
    cards_text = task_cards.read_text(encoding="utf-8")
    original_tasks = set(re.findall(r"\| (T\d{2}) \|", cards_text))
    recovery_tasks = re.findall(r"^## (R\d{2}) ·", cards_text, flags=re.MULTILINE)
    plan_text = plan.read_text(encoding="utf-8")
    user_scenarios = set(re.findall(r"\| (U\d{2}) ", plan_text))
    requirements = set(re.findall(r"\| ([FPADREX]\d) \|", plan_text))
    documentation_checks = {
        "checked_local_links": checked_links,
        "broken_links": broken_links,
        "whitespace_errors": whitespace_errors,
        "original_task_mapping_count": len(original_tasks),
        "original_task_mapping_complete": original_tasks == {f"T{i:02d}" for i in range(60)},
        "recovery_task_header_count": len(recovery_tasks),
        "recovery_task_headers_complete": recovery_tasks == [f"R{i:02d}" for i in range(25)],
        "user_scenario_count": len(user_scenarios),
        "user_scenarios_complete": user_scenarios == {f"U{i:02d}" for i in range(1, 15)},
        "requirement_count": len(requirements),
        "requirements_complete": requirements
        == {"F1", "F2", "F3", "P1", "P2", "P3", "A1", "E1", "D1", "D2", "X1", "R1", "R2"},
    }
    duplicate_keys: list[str] = []

    def collect_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        counts = Counter(key for key, _ in pairs)
        duplicate_keys.extend(key for key, count in counts.items() if count > 1)
        return dict(pairs)

    state = json.loads(
        (project_root / "progress/task_state.json").read_text(encoding="utf-8"),
        object_pairs_hook=collect_duplicate_keys,
    )
    tasks = state["tasks"]
    status_counts = Counter(task["status"] for task in tasks.values())
    accepted_without_verification = [
        task_id
        for task_id, task in tasks.items()
        if task["status"] == "accepted" and "verification" not in task
    ]
    pdf_path = next(project_root.glob("9*.pdf"))
    reader = PdfReader(pdf_path)
    pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    source_files = list((project_root / "backend/src").rglob("*.py"))
    test_files = list((project_root / "backend/tests").rglob("*.py"))
    frontend_files = [path for path in (project_root / "frontend/src").rglob("*") if path.is_file()]
    docker_result = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    metadata = {
        "documentation_checks": documentation_checks,
        "state_status_counts": dict(status_counts),
        "accepted_without_verification": accepted_without_verification,
        "duplicate_json_keys": duplicate_keys,
        "independent_pdf_extraction": {
            "parser": "pypdf",
            "pages": len(reader.pages),
            "text_characters": len(pdf_text),
            "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        },
        "code_inventory": {
            "backend_source_files": len(source_files),
            "backend_test_files": len(test_files),
            "frontend_source_files": len(frontend_files),
        },
        "docker_info": {
            "command": ["docker", "info", "--format", "{{.ServerVersion}}"],
            "exit_code": docker_result.returncode,
            "stdout": docker_result.stdout,
            "stderr": docker_result.stderr,
        },
    }
    output = json.dumps(metadata, ensure_ascii=False, indent=2)
    (evidence_dir / "artifact_checks.json").write_text(output, encoding="utf-8")
    print(output)
    if broken_links or whitespace_errors or not all(
        documentation_checks[key]
        for key in (
            "original_task_mapping_complete",
            "recovery_task_headers_complete",
            "user_scenarios_complete",
            "requirements_complete",
        )
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
