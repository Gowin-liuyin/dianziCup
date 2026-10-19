"""Verify material against frozen Git and isolate the three authorized source files."""
import hashlib
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUN=Path(__file__).resolve().parent
HEAD="5587deb124f06b9aa14fb7feb22cdc9493ae4883"
SOURCE="18d05f1c5842ed7a57f3be9f0351ede4af0b018a"
BASE="7a653880af12e4160ca8edf26fccbaf5d1e6f0f0"
def blob(ref,path):return subprocess.check_output(["git","show",f"{ref}:{path}"],cwd=ROOT)
def sha(value):return hashlib.sha256(value).hexdigest()
manifest_path="reports/runs/recovery_r17_sbom_workbench_fix1_20261016/raw_manifest.json"
raw=blob(HEAD,manifest_path);assert sha(raw)=="eac16b2332e1a1fb6e11d45999f3ccb6c1836a11d1dbe986c592c11ac5dd16f9"
manifest=json.loads(raw);assert len(manifest["members"])==136
members=[]
for item in manifest["members"]:
    value=blob(HEAD,item["path"]);assert sha(value)==item["sha256"] and len(value)==item["bytes"]
    members.append({**item,"verified_git":True,"checkout_equal_git":(ROOT/item["path"]).read_bytes()==value})
report_path="reports/tasks/R17-sbom-workbench-fix1.md"
assert sha(blob(HEAD,report_path))=="6875f503aee43c40a4df9c00924f92e8f34a30add47dcf805fea47d6002e55ac"
source_receipt=json.loads(blob(HEAD,"reports/runs/recovery_r17_sbom_workbench_fix1_20261016/source_receipt.json"))
assert len(source_receipt["source_files"])==3
assert all(blob(HEAD,path)==blob(SOURCE,path) for path in source_receipt["source_files"])
tree=subprocess.check_output(["git","rev-parse",f"{SOURCE}^{{tree}}"],cwd=ROOT,text=True).strip()
material_tree=subprocess.check_output(["git","rev-parse",f"{HEAD}^{{tree}}"],cwd=ROOT,text=True).strip();assert material_tree=="b45c27130647813d239e9d3d11d3efbf2768ff07"
old_paths=subprocess.check_output(["git","ls-tree","-r","--name-only",BASE,"frontend"],cwd=ROOT,text=True).splitlines()
tests=[path for path in old_paths if any(item in path for item in (".test.ts",".test.tsx",".spec.ts",".spec.tsx"))]
assert len(tests)==57 and all(blob(BASE,path)==blob(HEAD,path) for path in tests)
frontend_changed=subprocess.check_output(["git","diff","--name-only",BASE,HEAD,"--","frontend"],cwd=ROOT,text=True).splitlines()
assert set(frontend_changed)==set(source_receipt["source_files"])
protected=subprocess.check_output(["git","diff","--name-only",BASE,HEAD,"--","backend","contracts","frontend/package.json","frontend/package-lock.json",".gitattributes","progress"],cwd=ROOT,text=True);assert not protected.strip()
result={"head":HEAD,"material_tree":material_tree,"source":SOURCE,"source_tree":tree,"report_sha256":sha(blob(HEAD,report_path)),"manifest_sha256":sha(raw),"members":members,"members_count":136,"controls_count":2,"controls_match":(ROOT/manifest_path).read_bytes()==raw and (ROOT/manifest_path.replace('.json','.sha256')).read_bytes()==blob(HEAD,manifest_path.replace('.json','.sha256')),"source_files":source_receipt['source_files'],"old_tests_unchanged":len(tests),"protected_tracked_diff":protected,"checkout_byte_differences":[item['path'] for item in members if not item['checkout_equal_git']]}
(RUN/"material_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
print(json.dumps({key:value for key,value in result.items() if key!="members"},ensure_ascii=False));assert result["controls_match"]
