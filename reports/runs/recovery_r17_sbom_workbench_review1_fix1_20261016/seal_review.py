"""Seal only reviewer artifacts and exact-byte evidence without attribute changes."""
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUN=Path(__file__).resolve().parent
ZONE=timezone(timedelta(hours=8))
started=datetime.now(ZONE).isoformat(timespec="seconds")
HEAD="5587deb124f06b9aa14fb7feb22cdc9493ae4883"
report=ROOT/"reports/reviews/recovery/G-E-R17-sbom-workbench-review-1-recheck.md"
assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()==HEAD
assert not subprocess.check_output(["git","diff","--name-only"],cwd=ROOT,text=True).strip()
patterns=[("private_key",r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),("github",r"\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{70,})\b"),("aws",r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),("openai_live_key",r"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}\b"),("stripe_live",r"\bsk_live_[A-Za-z0-9]{20,}\b")]
sources=json.loads((RUN/"material_audit.json").read_text(encoding="utf-8"))["source_files"]
paths=[ROOT/path for path in sources]+[report]+[path for path in RUN.rglob('*') if path.is_file() and 'backend_git_probe' not in path.parts and path.suffix.lower() in {'.py','.ts','.txt','.json','.log','.cjs','.md'} and path.name not in {'finish_audit.py','seal_review.py','raw_manifest.json'}]
findings=[]
for path in paths:
    value=path.read_text(encoding="utf-8",errors="replace")
    for name,pattern in patterns:
        if re.search(pattern,value):findings.append({"path":path.relative_to(ROOT).as_posix(),"kind":name})
scan={"scope":"3 source files plus this review text artifacts and report; exclude binary/extracted backend/scanner definitions","files":len(paths),"patterns":[name for name,_ in patterns],"findings":findings,"actual_credentials_acquired":0,"production_allscan":False}
(RUN/"final_secret_scan.json").write_text(json.dumps(scan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n");assert not findings
report_sha=hashlib.sha256(report.read_bytes()).hexdigest()
(RUN/"report.sha256").write_text(report_sha+"\n",encoding="utf-8",newline="\n")
unit=json.loads((RUN/"unit_all.json").read_text(encoding="utf-8"))
edge=json.loads((RUN/"edge_acceptance.json").read_text(encoding="utf-8"))
diagnostic=json.loads((RUN/"edge_original_diagnostic.json").read_text(encoding="utf-8"))
summary={"head":HEAD,"source_sha":"18d05f1c5842ed7a57f3be9f0351ede4af0b018a","verdict":"limited_ship","must1":"closed","unit":{"passed":unit['numPassedTests'],"failed":unit['numFailedTests'],"skipped":unit['numPendingTests']},"edge_acceptance":edge['stats'],"original_bug_presence_diagnostic":diagnostic['stats'],"secret_scan":scan,"report_sha256":report_sha,"actual_credentials_acquired":0,"paid_calls":0,"third_party_asset_scans":0}
assert summary['unit']['passed']==557 and summary['unit']['failed']==0
assert edge['stats']['expected']==66 and edge['stats']['unexpected']==0 and edge['stats']['skipped']==0
assert diagnostic['stats']['expected']==0 and diagnostic['stats']['unexpected']==2
(RUN/"verification_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
finished=datetime.now(ZONE).isoformat(timespec="seconds")
receipt={"command":[sys.executable,*sys.argv],"cwd":str(ROOT),"started_at":started,"finished_at":finished,"exit_code":0,"log":"seal_review.log","code_target":HEAD}
(RUN/"seal_review.command.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
(RUN/"seal_review.log").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
excluded={RUN/'raw_manifest.json',RUN/'raw_manifest.sha256',RUN/'review_raw_snapshot.zip'}
raw_paths=sorted([report,*[path for path in RUN.rglob('*') if path.is_file() and path not in excluded]],key=lambda path:path.as_posix())
with zipfile.ZipFile(RUN/'review_raw_snapshot.zip','w',compression=zipfile.ZIP_DEFLATED) as bundle:
    for path in raw_paths:bundle.write(path,path.relative_to(ROOT).as_posix())
members=[]
for path in [*raw_paths,RUN/'review_raw_snapshot.zip']:
    value=path.read_bytes();members.append({"path":path.relative_to(ROOT).as_posix(),"sha256":hashlib.sha256(value).hexdigest(),"bytes":len(value)})
manifest={"run_id":RUN.name,"created_at":finished,"code_target":HEAD,"source_sha":summary['source_sha'],"report_sha256":report_sha,"data_mode":"synthetic_isolated_independent_recheck","verdict":"limited_ship","members":members}
raw=(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n").encode();(RUN/'raw_manifest.json').write_bytes(raw)
manifest_sha=hashlib.sha256(raw).hexdigest();(RUN/'raw_manifest.sha256').write_text(manifest_sha+"\n",encoding="utf-8",newline="\n")
for item in members:
    value=(ROOT/item['path']).read_bytes();assert len(value)==item['bytes'] and hashlib.sha256(value).hexdigest()==item['sha256']
with zipfile.ZipFile(RUN/'review_raw_snapshot.zip') as bundle:
    for path in raw_paths:assert bundle.read(path.relative_to(ROOT).as_posix())==path.read_bytes()
print(json.dumps({"report":str(report),"report_sha256":report_sha,"raw_manifest_sha256":manifest_sha,"members":len(members),"members_plus_controls":len(members)+2,"verdict":"limited_ship","must1":"closed","raw_archive":"review_raw_snapshot.zip","secret_scan_findings":len(findings)},ensure_ascii=False))
