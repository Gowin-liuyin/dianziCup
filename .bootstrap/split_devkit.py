"""Split the merged reading edition of the devkit into its declared per-file sections.

Stages every section under .bootstrap/devkit-v1.0/, then materializes each file into the
repository root. Targets are created only when absent; existing files are compared and
either skipped (identical) or reported as conflicts without being touched.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

SECTION_HEADER_PATTERN = re.compile(r"^# 文件：`([^`]+)`\s*$")
FENCE_PATTERN = re.compile(r"^(`{3,})")
DISPLAY_SEPARATOR = "---"


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_valid_relative_target(path_text: str) -> tuple[bool, str]:
    if not path_text or path_text.strip() != path_text:
        return False, "empty or padded path"
    if path_text.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", path_text):
        return False, "absolute path"
    if path_text.startswith("\\\\"):
        return False, "UNC path"
    parts = path_text.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False, "empty/dot/dotdot component"
    return True, ""


def split_sections(source_lines: list[str]) -> list[dict]:
    sections: list[dict] = []
    fence_opener: str | None = None
    current: dict | None = None
    for line_number, line in enumerate(source_lines, start=1):
        fence_match = FENCE_PATTERN.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence_opener is None:
                fence_opener = marker
            elif marker[0] == fence_opener[0] and len(marker) >= len(fence_opener):
                fence_opener = None
            if current is not None:
                current["lines"].append(line)
            continue
        header_match = SECTION_HEADER_PATTERN.match(line) if fence_opener is None else None
        if header_match:
            if current is not None:
                sections.append(current)
            current = {"path": header_match.group(1), "header_line": line_number, "lines": []}
        elif current is not None:
            current["lines"].append(line)
    if current is not None:
        sections.append(current)
    return sections


def trim_section_body(lines: list[str]) -> list[str]:
    body = list(lines)
    while body and body[-1].strip() == "":
        body.pop()
    if body and body[-1].strip() == DISPLAY_SEPARATOR:
        body.pop()
        while body and body[-1].strip() == "":
            body.pop()
    return body


def strip_outer_display_fence(body: list[str], target_path: str) -> tuple[list[str], bool]:
    if target_path.endswith(".md"):
        return body, False
    non_blank = [index for index, line in enumerate(body) if line.strip()]
    if len(non_blank) < 2:
        return body, False
    first_index, last_index = non_blank[0], non_blank[-1]
    first_match = FENCE_PATTERN.match(body[first_index])
    last_match = FENCE_PATTERN.match(body[last_index])
    if not first_match or not last_match:
        return body, False
    if len(last_match.group(1)) < len(first_match.group(1)):
        return body, False
    inner = body[first_index + 1 : last_index]
    return inner, True


def main() -> int:
    repo_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    source_path = repo_root / "赛题九_Agent工程开发计划与执行提示词_完整版.md"
    staging_root = repo_root / ".bootstrap" / "devkit-v1.0"
    inventory_path = repo_root / "reports" / "runs" / "t01_materialization_inventory.json"

    source_lines = normalize_newlines(source_path.read_text(encoding="utf-8")).split("\n")
    sections = split_sections(source_lines)

    inventory: dict = {
        "source_path": str(source_path),
        "source_sha256": sha256_of(source_path),
        "section_count": len(sections),
        "staging_root": str(staging_root),
        "files": [],
        "invalid_paths": [],
        "duplicate_paths": [],
        "protected_files_after": {},
    }

    seen_targets: dict[str, int] = {}
    prepared: list[dict] = []
    for section in sections:
        target = section["path"]
        valid, reason = is_valid_relative_target(target)
        if not valid:
            inventory["invalid_paths"].append({"path": target, "reason": reason, "header_line": section["header_line"]})
            continue
        folded = target.replace("\\", "/").lower()
        if folded in seen_targets:
            inventory["duplicate_paths"].append({"path": target, "header_line": section["header_line"]})
            continue
        seen_targets[folded] = section["header_line"]
        body = trim_section_body(section["lines"])
        body, fence_stripped = strip_outer_display_fence(body, target)
        content = "\n".join(body) + "\n"
        prepared.append(
            {
                "path": target.replace("\\", "/"),
                "header_line": section["header_line"],
                "content": content,
                "outer_display_fence_stripped": fence_stripped,
            }
        )

    for entry in prepared:
        staged_file = staging_root / entry["path"]
        staged_file.parent.mkdir(parents=True, exist_ok=True)
        staged_file.write_text(entry["content"], encoding="utf-8", newline="\n")
        entry["staged_sha256"] = sha256_of(staged_file)

    for entry in prepared:
        target_file = repo_root / entry["path"]
        record = {
            "path": entry["path"],
            "header_line": entry["header_line"],
            "staged_sha256": entry["staged_sha256"],
            "outer_display_fence_stripped": entry["outer_display_fence_stripped"],
            "action": "",
        }
        if not target_file.exists():
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(entry["content"], encoding="utf-8", newline="\n")
            record["action"] = "created"
        else:
            existing_text = normalize_newlines(target_file.read_text(encoding="utf-8"))
            if existing_text == normalize_newlines(entry["content"]):
                record["action"] = "skipped_identical"
            elif existing_text.strip() == normalize_newlines(entry["content"]).strip():
                record["action"] = "skipped_newline_only_difference"
            else:
                record["action"] = "conflict_not_touched"
        inventory["files"].append(record)

    pdf_source = repo_root / "9 赛题九：网信产业应用赛道-智能体驱动的AI安全知识情报系统设计与实现（奇安信科技集团股份有限公司）.pdf"
    pdf_target = repo_root / "docs" / "references" / "competition_brief.pdf"
    pdf_record = {"source": str(pdf_source), "target": str(pdf_target), "action": ""}
    if not pdf_target.exists():
        pdf_target.parent.mkdir(parents=True, exist_ok=True)
        pdf_target.write_bytes(pdf_source.read_bytes())
        pdf_record["action"] = "copied"
    else:
        pdf_record["action"] = "target_exists"
    pdf_record["source_sha256"] = sha256_of(pdf_source)
    pdf_record["target_sha256"] = sha256_of(pdf_target)
    pdf_record["hash_match"] = pdf_record["source_sha256"] == pdf_record["target_sha256"]
    inventory["competition_brief_pdf"] = pdf_record

    for protected in [
        "AGENTS.md",
        "赛题九_Agent工程开发计划与执行提示词_完整版.md",
        "赛题九_编码Agent首次执行提示词.txt",
        pdf_source.name,
    ]:
        inventory["protected_files_after"][protected] = sha256_of(repo_root / protected)

    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")

    action_counts: dict[str, int] = {}
    for record in inventory["files"]:
        action_counts[record["action"]] = action_counts.get(record["action"], 0) + 1
    print(f"sections={len(sections)} prepared={len(prepared)}")
    print(f"actions={json.dumps(action_counts, ensure_ascii=False)}")
    print(f"invalid_paths={len(inventory['invalid_paths'])} duplicate_paths={len(inventory['duplicate_paths'])}")
    print(f"pdf_hash_match={pdf_record['hash_match']}")
    print(f"inventory={inventory_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
