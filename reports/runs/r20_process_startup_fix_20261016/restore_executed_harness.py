"""Undo only recorded cosmetic formatter changes to the pre-repair harness archive."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

RUN = Path(__file__).resolve().parent
archive = RUN / "executed_harness"
texts = {
    name: (archive / name).read_text(encoding="utf-8")
    for name in (
        "measure_startup.py",
        "run_checks.py",
    )
}
before = {name: ast.dump(ast.parse(text)) for name, text in texts.items()}
active: str | None = None
old_lines: list[str] = []
new_lines: list[str] = []
replacements: dict[str, int] = dict.fromkeys(texts, 0)


def restore_group() -> None:
    if active is not None and old_lines:
        formatted = "\n".join(new_lines)
        original = "\n".join(old_lines)
        if texts[active].count(formatted) == 1:
            texts[active] = texts[active].replace(formatted, original, 1)
            replacements[active] += 1
        else:
            assert texts[active].count(original) == 1, (active, formatted)
    old_lines.clear()
    new_lines.clear()


for line in (RUN / "static_format_initial.log").read_text(encoding="utf-8").splitlines():
    if "--> " in line:
        restore_group()
        active = next((name for name in texts if name in line), None)
    removed = re.match(r"^\s+- (.*)$", line)
    added = re.match(r"^\d+\s+\+ (.*)$", line)
    if active is not None and removed:
        if new_lines:
            restore_group()
        old_lines.append(removed.group(1))
    elif active is not None and added:
        new_lines.append(added.group(1))
    else:
        restore_group()
restore_group()
records = {}
for name, text in texts.items():
    assert ast.dump(ast.parse(text)) == before[name]
    (archive / name).write_text(text, encoding="utf-8", newline="\n")
    records[name] = {
        "reversed_format_groups": replacements[name],
        "ast_equal_to_formatted_archive": True,
        "sha256": hashlib.sha256((archive / name).read_bytes()).hexdigest(),
    }
(RUN / "executed_archive_restoration.json").write_text(
    json.dumps(records, indent=2), encoding="utf-8"
)
print(json.dumps(records))
