"""Build a guarded two-slice integration command from the proven merge procedure."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
script = (RUN / "integrate_reviewed_graph_app_migrations.py").read_text(encoding="utf-8")
script = script.replace('"48b56033cf5daf3ce8cfaa710c0acbda7cc2356e"', '"0532c4f58611e068fc7d5b03da984bc57dbad9f2"')
start = script.index("packages = [")
end = script.index("\nreceipt =", start)
script = script[:start] + '''packages = [
    ("r11_pure_sbom", "f6acedcd2b004671c317f55dd058f46e5e517de9", "reports/reviews/recovery/G-D-R11-sbom-review-1.md", "4ffa43d4d1d3a02773340cd37ed6c99efb90b8ce1f040c95817861e90084d5d3", "reports/runs/recovery_r11_sbom_review1_20261016/artifact_manifest.json", "ea25028a5f945e2c7c4efc66d7eb69d7cf8ef71ca44966b122ed58bac574b0e1", "G-D integrate reviewed pure SBOM evidence adapter"),
    ("r11_pure_conditions", "3865fd6a9c568b0d4e6b816e62eb808de5330427", "reports/reviews/recovery/G-D-R11-condition-rules-review-1.md", "dd8da52a460656e3a9a9f5a938129ee14860954a4eca9c6cf92592771ac0a7a5", "reports/runs/recovery_r11_condition_review1_20261016/review_filelist.json", "4317611410e3c667ccca08b958e6a1fa313f03dd9ea5626fd81f5f6b807d4104", "G-D integrate reviewed condition AST and rule eligibility"),
]''' + script[end:]
script = script.replace("graph_app_migrations_integration_receipt.json", "pure_sbom_conditions_integration_receipt.json")
script = script.replace('["git", "merge", "--no-ff", target, "-m", message]', '["git", "merge", "--quiet", "--no-ff", target, "-m", message]')
(RUN / "integrate_reviewed_pure_sbom_conditions.py").write_text(script, encoding="utf-8", newline="\n")
