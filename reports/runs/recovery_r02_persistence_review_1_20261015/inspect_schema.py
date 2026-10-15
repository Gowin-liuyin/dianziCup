from pathlib import Path
import importlib,hashlib,json,os
from sqlalchemy import create_engine,inspect,text
from ai_intel.knowledge import persistence_models
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.api.auth_state import auth_sessions
ROOT=Path(r'D:\dianzi\reports\runs\recovery_r02_persistence_review_1_20261015')
WT=Path(r'C:\Users\yinha\.codex\worktrees\recovery-r02-review\dianzi')
modules=['ai_intel.api.app','ai_intel.api.auth_state','ai_intel.api.authentication','ai_intel.knowledge.persistence','ai_intel.knowledge.revisions','ai_intel.knowledge.event_linking','ai_intel.enrichment.persistence_models']
paths={name:str(Path(importlib.import_module(name).__file__).resolve()) for name in modules}
assert all(Path(value).is_relative_to(WT/'backend/src') for value in paths.values())
engine=create_engine(os.environ['TEST_DATABASE_URL'],connect_args={'connect_timeout':5})
inspector=inspect(engine)
with engine.connect() as c:
    dbuser=c.execute(text('SELECT current_database(),current_user')).one()
    assert dbuser[0]==engine.url.database and dbuser[1]==engine.url.username
    head=c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
    assert head=='0009_enrichment_results'
    schema_indexes=inspector.get_indexes('claims')
    unique=[row for row in schema_indexes if row['name']=='ix_claims_field_fingerprint']
    assert unique and unique[0]['unique'] is True
    columns={col['name'] for col in inspector.get_columns('enrichment_results')}
    assert columns==set(enrichment_results.c.keys())
    constraints=inspector.get_unique_constraints('enrichment_results')
    checks=inspector.get_check_constraints('enrichment_results')
result={'head':head,'fingerprint_index':unique,'enrichment_columns':sorted(columns),'enrichment_uniques':constraints,'enrichment_checks':checks,'module_identity':paths,'sha256':{name:hashlib.sha256(Path(path).read_bytes()).hexdigest() for name,path in paths.items()}}
(ROOT/'actual_schema_module_identity.observed.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
engine.dispose()
