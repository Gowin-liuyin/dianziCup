"""Copy only prior reviewer probes; preserve original assertions and all frozen bytes."""
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUN=Path(__file__).resolve().parent
PRIOR=Path("D:/wt/r17-sbom-review1")
OLD_RUN=PRIOR/"reports/runs/recovery_r17_sbom_workbench_review1_20261016"
def sha(value):return hashlib.sha256(value).hexdigest()
def blob(ref,path):return subprocess.check_output(["git","show",f"{ref}:{path}"],cwd=ROOT)
rows=[]
old_manifest_path="reports/runs/recovery_r17_sbom_workbench_20261016/raw_manifest.json"
raw=blob("7a653880af12e4160ca8edf26fccbaf5d1e6f0f0",old_manifest_path)
assert sha(raw)=="d999188d6d884ce4dd25cb51c0aad5f1ce2478654e1a0e8adae109ac18c9b03d"
old=json.loads(raw)
for item in old["members"]:
    value=blob("7a653880af12e4160ca8edf26fccbaf5d1e6f0f0",item["path"])
    assert sha(value)==item["sha256"] and len(value)==item["bytes"]
    assert blob("5587deb124f06b9aa14fb7feb22cdc9493ae4883",item["path"])==value
    rows.append({**item,"verified":"Git old/new identical"})
for path in (old_manifest_path,old_manifest_path.replace(".json",".sha256")):
    value=blob("7a653880af12e4160ca8edf26fccbaf5d1e6f0f0",path)
    assert blob("5587deb124f06b9aa14fb7feb22cdc9493ae4883",path)==value
    rows.append({"path":path,"sha256":sha(value),"bytes":len(value),"verified":"Git control old/new identical"})
prior_raw=(OLD_RUN/"raw_manifest.json").read_bytes()
assert sha(prior_raw)=="d7f22390774e910a685c6db24d66beb2b63176e24b31fae7c4f7e09e7731aeb7"
prior=json.loads(prior_raw);assert len(prior["members"])==272
for item in prior["members"]:
    value=(PRIOR/item["path"]).read_bytes();assert sha(value)==item["sha256"] and len(value)==item["bytes"]
    rows.append({**item,"verified":"prior reviewer frozen raw"})
original=(OLD_RUN/"independent.spec.ts").read_bytes()
(RUN/"original_independent.spec.ts.txt").write_bytes(original)
adapted=original.decode().replace("26173","26573")
(RUN/"reviewer_resource_adapter.spec.ts").write_text(adapted,encoding="utf-8",newline="\n")
prefix=adapted.split("const unsafeUris = [",1)[0]
(RUN/"reviewer_fixture.ts").write_text(prefix.replace("async function fixture(","export async function fixture(").replace("async function clearAssertion(","export async function clearAssertion("),encoding="utf-8",newline="\n")
(RUN/"package.json").write_text('{"type":"module"}\n',encoding="utf-8",newline="\n")
for name in ("backend_dto_probe.ts","backend_purl_profile.py"):
    (RUN/(name+".original.txt")).write_bytes((OLD_RUN/name).read_bytes())
archive=subprocess.check_output(["git","archive","--format=zip","5be873ec38a41955b5a58e9762df4b866a7a9d63","backend/src"],cwd=ROOT)
target=RUN/"backend_git_probe"
with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
    assert all((target/item.filename).resolve().is_relative_to(target.resolve()) for item in bundle.infolist());bundle.extractall(target)
receipt={"prior_material_verified":len(rows),"prior_author_count":120,"prior_review_count":272,"mismatches":0,"original_spec_sha256":sha(original),"resource_only":"26173 -> 26573","original_assertions_unchanged":adapted.replace("26573","26173")==original.decode(),"reviewer_controls_sha256":{"manifest":sha(prior_raw),"checksum":sha((OLD_RUN/"raw_manifest.sha256").read_bytes())},"members":rows}
(RUN/"prior_protection_before.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8",newline="\n")
print(json.dumps({key:value for key,value in receipt.items() if key!="members"}));assert len(rows)==392
