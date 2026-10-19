"""Record the recovery six-relation plan and public schema frozen body identities."""
import hashlib
import json
from review_runner import ROOT,RUN,run

paths=['docs/plan/01_scope_and_scoring.md','docs/plan/11_full_delivery_recovery_20261014.md',
       'docs/plan/12_recovery_task_cards_20261014.md','contracts/task_manifest.json',
       'contracts/schemas/public_api_v2.json']
entries=[]
for name in paths:
    raw=(ROOT/name).read_bytes()
    entries.append({'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
(RUN/'contract_read_supplement.json').write_text(json.dumps(entries,indent=2),encoding='utf-8')
run('scope_contract_evidence',['rg','-n','6\\.2|六类|R10|relation_type|source_revision|citations',*paths],ROOT)
print('supplemented contracts',len(entries))
