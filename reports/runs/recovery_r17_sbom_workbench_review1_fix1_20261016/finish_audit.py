"""Restore this checkout's generated metadata and preserve prior evidence again."""
import hashlib
import json
import re
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUN=Path(__file__).resolve().parent
PRIOR=Path("D:/wt/r17-sbom-review1")
before=json.loads((RUN/"prior_protection_before.json").read_text(encoding="utf-8"))
for item in before["members"]:
    if item["verified"].startswith("Git"):
        value=subprocess.check_output(["git","show",f"HEAD:{item['path']}"],cwd=ROOT)
    else:value=(PRIOR/item["path"]).read_bytes()
    assert len(value)==item["bytes"] and hashlib.sha256(value).hexdigest()==item["sha256"]
old_control=PRIOR/"reports/runs/recovery_r17_sbom_workbench_review1_20261016"
assert hashlib.sha256((old_control/"raw_manifest.json").read_bytes()).hexdigest()==before["reviewer_controls_sha256"]["manifest"]
assert hashlib.sha256((old_control/"raw_manifest.sha256").read_bytes()).hexdigest()==before["reviewer_controls_sha256"]["checksum"]
path="frontend/tsconfig.tsbuildinfo"
original=subprocess.check_output(["git","show",f"HEAD:{path}"],cwd=ROOT)
(RUN/"own_generated_tsbuildinfo.sha256").write_text(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()+"\n",encoding="utf-8")
(ROOT/path).write_bytes(original)
patterns=[("private_key",r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),("github",r"\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{70,})\b"),("aws",r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),("openai_live_key",r"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}\b"),("stripe_live",r"\bsk_live_[A-Za-z0-9]{20,}\b")]
source_paths=json.loads((RUN/"material_audit.json").read_text(encoding="utf-8"))["source_files"]
paths=[ROOT/path for path in source_paths]+[path for path in RUN.rglob("*") if path.is_file() and "backend_git_probe" not in path.parts and path.suffix.lower() in {".py",".ts",".txt",".json",".log",".cjs",".md"} and path.name!="finish_audit.py"]
findings=[]
for artifact_path in paths:
    value=artifact_path.read_text(encoding="utf-8",errors="replace")
    for name,pattern in patterns:
        if re.search(pattern,value):findings.append({"path":artifact_path.relative_to(ROOT).as_posix(),"kind":name})
diff=subprocess.check_output(["git","diff","--name-only"],cwd=ROOT,text=True)
result={"prior_392_members_drift":0,"prior_reviewer_2_controls_drift":0,"old_report_and_PNG_protected":True,"tracked_diff":diff,"own_tsbuildinfo_restored":(ROOT/path).read_bytes()==original,"secret_scan":{"scope":"3 source files plus this reviewer text artifacts; exclude extracted immutable backend source, binaries, scanner definition","files":len(paths),"patterns":[name for name,_ in patterns],"findings":findings,"actual_credentials_acquired":0,"production_allscan":False},"paid_calls":0,"third_party_asset_scans":0,"status":subprocess.check_output(["git","status","--short"],cwd=ROOT,text=True)}
(RUN/"finish_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
print(json.dumps(result,ensure_ascii=False));assert not diff.strip() and not findings
