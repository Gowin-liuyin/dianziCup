"""Resume the four remaining reviewed targets without rewriting the first failure receipt."""

from pathlib import Path

RUN = Path(__file__).parent
source = (RUN / "integrate_reviewed_persistent_slices.py").read_text(encoding="utf-8")
source = source.replace(
    'assert git("rev-parse", "HEAD") == "136fbaef337036d95229aa4976c1ba49b2e6b04c"',
    'assert git("rev-parse", "HEAD") == "fcfe0c9fbe89cf5e8c64804c577c59b8d99bb30b"',
)
initial = 'receipt = {"started_at": now(), "before_sha": git("rev-parse", "HEAD"), "scope": "limited reviewed services; no stage or whole-card acceptance", "push_attempts": 0, "packages": []}'
assert initial in source
source = source.replace(initial, 'receipt = json.loads((RUN / "persistent_slices_integration_receipt.json").read_text(encoding="utf-8"))\nreceipt["resumed_at"] = now()')
source = source.replace('for name, target, report, manifest, expected, message in packages:', 'for name, target, report, manifest, expected, message in packages[1:]:')
destination = RUN / "continue_reviewed_persistent_slices.py"
assert not destination.exists()
destination.write_text(source, encoding="utf-8", newline="\n")
exec(compile(source, str(destination), "exec"), {"__file__": str(destination)})
