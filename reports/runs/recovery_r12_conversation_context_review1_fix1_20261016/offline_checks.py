"""Independent caller trace and exact metadata inventory, without database connections."""
import hashlib
import sys
from review_runner import ROOT,RUN,PROJECT,CLI,run,save,now
from ai_intel.answering.conversation_models import (
    qa_conversations,qa_conversation_turns,OWNERSHIP_FUNCTION_DDL,OWNERSHIP_TRIGGER_DDLS,IMMUTABILITY_FUNCTION_DDL,IMMUTABILITY_TRIGGER_DDL,
)

if len(sys.argv)==1:
    prefix=['wsl','--exec','/usr/bin/env','CBM_CACHE_DIR=/tmp/dianzi-cbm-r12-context-review1-fix1-20261016',CLI,'cli']
    run('cbm_assets_writer',prefix+['trace_path','--project',PROJECT+'-assets','--function-name',PROJECT+'-assets.inventory.InventoryService.import_manifest','--direction','outbound','--depth','2','--format','json'],timeout=60)
    run('cbm_existing_ask',prefix+['trace_path','--project',PROJECT,'--function-name',PROJECT+'.ai_intel.answering.service.GroundedQuestionService.ask','--direction','outbound','--depth','3','--format','json'],timeout=60)
    run('callers_rg',['rg','-n','ConversationContextService|build_question_evidence|conversation_models|conversation_contracts|GroundedQuestionService|lock_candidate_authorities|_lock_input_parents|save_document_revision|import_manifest','backend/src'],timeout=30)
tables=[]
for table in (qa_conversations,qa_conversation_turns):
    constraints=[]
    for constraint in table.constraints:
        item=dict(name=constraint.name,kind=type(constraint).__name__,columns=[col.name for col in constraint.columns])
        if hasattr(constraint,'sqltext'): item['check_sql']=str(constraint.sqltext)
        if hasattr(constraint,'elements'):
            item.update(foreign_keys=[fk.target_fullname for fk in constraint.elements],deferrable=constraint.deferrable,initially=constraint.initially,use_alter=constraint.use_alter)
        constraints.append(item)
    tables.append(dict(name=table.name,columns=[dict(name=col.name,type=str(col.type),nullable=col.nullable,primary_key=col.primary_key,foreign_keys=sorted(fk.target_fullname for fk in col.foreign_keys)) for col in table.columns],constraints=sorted(constraints,key=lambda c:(c['kind'],c['name'] or '')),indexes=sorted(i.name for i in table.indexes)))
save('metadata_authority.json',dict(checked_at=now(),code_commit='1e210090d74d1444101330f0c8b8637ad1dd50a3',tables=tables,
    ownership_function_ddl=OWNERSHIP_FUNCTION_DDL,ownership_trigger_ddls=OWNERSHIP_TRIGGER_DDLS,immutability_function_ddl=IMMUTABILITY_FUNCTION_DDL,immutability_trigger_ddl=IMMUTABILITY_TRIGGER_DDL,
    ddl_sha256=hashlib.sha256((OWNERSHIP_FUNCTION_DDL+'\n'.join(OWNERSHIP_TRIGGER_DDLS)).encode()).hexdigest(),production_migration='not_run',connections=0))
