"""Check only this run's files against approved test credentials without emitting them."""

import json

from run_checks import RUN, approved_test_url, now

configured = approved_test_url()
credential_values = [configured.render_as_string(hide_password=False), configured.password]
credential_bytes = [value.encode() for value in credential_values if value]
scanned = 0
leaks = []
for path in sorted(RUN.rglob("*")):
    if path.is_file() and "__pycache__" not in path.parts:
        scanned += 1
        content = path.read_bytes()
        if any(value in content for value in credential_bytes):
            leaks.append(path.relative_to(RUN).as_posix())
receipt = {"scanned_at": now(), "files_scanned": scanned, "leaking_files": leaks}
(RUN / "credential_scan.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps({"files_scanned": scanned, "leaking_file_count": len(leaks)}))
assert not leaks
