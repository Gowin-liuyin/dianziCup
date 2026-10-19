"""Compare frozen Git bytes, checkout representation and preserved raw archives separately."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from run_command import ROOT,RUN


def blob(ref,path):
    result=subprocess.run(['git','show',ref+':'+path],cwd=ROOT,capture_output=True,check=False)
    return result.stdout if result.returncode==0 else None


def sha(value):
    return hashlib.sha256(value).hexdigest()


packages=[
 ('bulk','bdebeca358f0cfd63630b223dee64647b5280687','reports/runs/recovery_r06_bulk_source_evidence_20261016/artifact_manifest.json'),
 ('publication','9e722c944cf83086ffd30ad24a708172c13da189','reports/runs/recovery_r07_publication_combined_fix_20261016/artifact_manifest.json'),
 ('aggregate','a76374ca9200945441a83421050eceef00db47d8','reports/runs/recovery_r08_cache_ttl_fix1_20261016/artifact_manifest.json'),
 ('inventory','bc8798cf5efc81e210a429884930ca545af43ad8','reports/runs/recovery_r11_asset_inventory_20261016/artifact_manifest.json'),
 ('graph','65497b14cb5c24c6d780f675a70af3ee4019d8db','reports/runs/recovery_r17_graph_ui_fix1_20261016/artifact_manifest.json'),
]
audit=[]
for name,ref,manifest_path in packages:
    raw_manifest=blob(ref,manifest_path)
    manifest=json.loads(raw_manifest)
    item=dict(package=name,material_sha=ref,manifest_path=manifest_path,manifest_git_sha256=sha(raw_manifest),
        manifest_checkout_sha256=sha((ROOT/manifest_path).read_bytes()),manifest_head_blob_equal=blob('HEAD',manifest_path)==raw_manifest,entries=[])
    zip_entries={}
    if name=='bulk':
        archived=manifest['frozen_byte_archive']
        raw=blob(ref,archived['path'])
        item['archive_matches']=sha(raw)==archived['sha256']
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            zip_entries={n:archive.read(n) for n in archive.namelist()}
    entries=[]
    for key in ['artifacts','files','source','evidence','code_files','source_proofs']:
        for entry in manifest.get(key,[]):
            if not isinstance(entry,dict) or 'path' not in entry: continue
            expected=entry.get('sha256') or entry.get('raw_sha256') or entry.get('git_blob_sha256')
            if expected is None: continue
            path=entry['path']
            frozen=blob(ref,path)
            raw=zip_entries.get(path)
            row=dict(path=path,expected_sha256=expected,basis=entry.get('basis',key),
                frozen_git_sha256=sha(frozen) if frozen is not None else None,
                git_match=frozen is not None and sha(frozen)==expected,
                checkout_sha256=sha((ROOT/path).read_bytes()) if (ROOT/path).is_file() else None,
                archived_raw_sha256=sha(raw) if raw is not None else None,
                archived_raw_match=raw is not None and sha(raw)==expected)
            git_expected=entry.get('frozen_blob_sha256') or entry.get('lf_sha256') or expected
            row['manifest_git_expected_sha256']=git_expected
            row['git_representation_match']=frozen is not None and sha(frozen)==git_expected
            row['raw_or_documented_git_basis_match']=row['archived_raw_match'] or row['git_match'] or row['git_representation_match']
            if path.startswith(('backend/src/','backend/tests/','frontend/src/','frontend/e2e/')):
                row['integrated_git_blob_equal']=frozen is not None and blob('HEAD',path)==frozen
            entries.append(row)
    item['entries']=entries
    item['raw_archive_entries']=[]
    for entry in manifest.get('raw_evidence_archives',[]):
        packed=blob(ref,entry['archive_path'])
        raw=gzip.decompress(packed)
        item['raw_archive_entries'].append(dict(path=entry['path'],archive_path=entry['archive_path'],
            archive_matches=sha(packed)==entry['archive_sha256'],raw_matches=sha(raw)==entry['sha256'],raw_bytes=len(raw)))
    audit.append(item)
(RUN/'author_frozen_material_audit_v2.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')

paths=['backend/src/ai_intel/enrichment/signals.py','backend/tests/unit/test_r07_public_signals.py','backend/tests/unit/test_r07_public_signals_fix1.py',
    'backend/src/ai_intel/enrichment/inputs.py','backend/src/ai_intel/enrichment/publication.py']
identity=[]
for path in paths:
    frozen=blob('9e722c944cf83086ffd30ad24a708172c13da189',path)
    integrated=blob('HEAD',path)
    identity.append(dict(path=path,frozen_sha256=sha(frozen),integrated_sha256=sha(integrated),exact_git_blob_equal=frozen==integrated,
        checkout_raw_sha256=sha((ROOT/path).read_bytes())))
for path in ['backend/src/ai_intel/infrastructure/process_limits.py','backend/tests/unit/test_r20_native_cpu_guard.py',
    'backend/src/ai_intel/infrastructure/models/generation.py','backend/src/ai_intel/enrichment/model_fields.py','backend/src/ai_intel/api/app.py','backend/src/ai_intel/workers/runtime.py']:
    old=blob('8a1b04d48346d8550f0326a77f003246a0ebbab5',path)
    current=blob('HEAD',path)
    identity.append(dict(path=path,old_8a_sha256=sha(old),integrated_sha256=sha(current),exact_git_blob_equal=old==current))
(RUN/'integrated_source_identity_v2.json').write_text(json.dumps(identity,indent=2),encoding='utf-8')
original=Path('D:/dianzi/reports/runs/recovery_gc_integrated_8a_validation_20261016/backend_full_pure.xml')
parsed=ET.fromstring(original.read_bytes())
failed=[]
for case in parsed.findall('.//testcase'):
    failure=case.find('failure')
    if failure is not None and 'test_r20_native_cpu_guard' in case.get('classname',''):
        failed.append(dict(classname=case.get('classname'),name=case.get('name'),failure_message=failure.get('message'),failure_text=failure.text))
(RUN/'inherited_8a_cpu_failures_v2.json').write_text(json.dumps(dict(source_sha='8a1b04d48346d8550f0326a77f003246a0ebbab5',original_junit_sha256=sha(original.read_bytes()),rerun=False,failures=failed),indent=2),encoding='utf-8')
attrs=blob('HEAD','.gitattributes').decode('utf-8')
(RUN/'attributes_audit_v2.json').write_text(json.dumps(dict(virtual_conflict_markers_present=any(line.startswith(('<<<<<<<','=======','>>>>>>>')) for line in attrs.splitlines()),
    integrated_git_sha256=sha(blob('HEAD','.gitattributes')),inventory_frozen_git_sha256=sha(blob(packages[3][1],'.gitattributes'))),indent=2),encoding='utf-8')
print(json.dumps(dict(packages=[dict(package=x['package'],entries=len(x['entries']),git_representation_mismatch=sum(not e['git_representation_match'] for e in x['entries']),basis_mismatch=sum(not e['raw_or_documented_git_basis_match'] for e in x['entries']),raw_archive_mismatch=sum(not e['archive_matches'] or not e['raw_matches'] for e in x['raw_archive_entries']),source_drift=sum(e.get('integrated_git_blob_equal') is False for e in x['entries'])) for x in audit],publication_identity=all(x['exact_git_blob_equal'] for x in identity[:5]),inherited_cpu_failures=len(failed)),indent=2))
