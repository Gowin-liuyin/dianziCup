"""Independent bounded review; private resource values stay in captured process memory."""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = 'D:/dianzi/backend/.venv/Scripts/python.exe'
PWSH = 'C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'
DATABASE = 'test_dianzi_r12_ctx_fix1_20261016'
RUN_ID = 'r12_ctx_fix1_20261016'
PROJECT = 'dianzi-r12-conversation-context-fix1'
CLI = '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp'
SECRETS = set()
sys.path.insert(0, str(ROOT / 'backend/src'))
spec = importlib.util.spec_from_file_location('review_original_failure_hook', ROOT / 'backend/tests/conftest.py')
HOOK = importlib.util.module_from_spec(spec)
spec.loader.exec_module(HOOK)


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def save(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def run(label, command, env=None, timeout=300):
    if (RUN / (label + '.log')).exists() or (RUN / (label + '.command.json')).exists():
        raise RuntimeError('output label already exists')
    started, tick = now(), time.monotonic()
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=timeout)
    output = (result.stdout + result.stderr).decode('utf-8', errors='replace')

    for secret in SECRETS:
        output = output.replace(secret, '[redacted resource]')
    passwords = tuple(make_url(value).password for value in SECRETS if '://' in value)
    output = HOOK.redact_test_connection_output(output, tuple(value for value in passwords if value))
    (RUN / (label + '.log')).write_text(output, encoding='utf-8')
    receipt = dict(command=command, cwd=str(ROOT), started_at=started, ended_at=now(),
                   wall_seconds=time.monotonic()-tick, exit_code=result.returncode,
                   source_ref=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip())
    save(label+'.command.json', receipt)
    print(json.dumps(dict(label=label,exit_code=result.returncode,wall_seconds=receipt['wall_seconds'])))
    print(output[-1500:])
    return result.returncode


def environment(resources=False):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT/'backend/src'),str(ROOT/'backend'),str(ROOT/'backend/tests/integration'),str(RUN))),
               PYTHONIOENCODING='utf-8')
    env.pop('TEST_DATABASE_URL',None)
    if resources:
        if datetime.now(ZoneInfo('Asia/Shanghai')) >= datetime.fromisoformat('2026-10-17T21:49:15+08:00'):
            raise RuntimeError('resource authorization expired')
        script = "(Get-Content -LiteralPath 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText"
        captured = subprocess.run([PWSH,'-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=15)
        if captured.returncode:
            raise RuntimeError('resource reference capture failed')
        value=json.loads(captured.stdout)['TEST_DATABASE_URL']
        base=make_url(value)
        assert (base.host,base.port,base.database)==('127.0.0.1',25432,'test_dianzi_r01_20261014')
        assert base.username.startswith('test_') and base.password
        SECRETS.update((value,base.password))
        params=dict(host=base.host,port=base.port,user=base.username,password=base.password,connect_timeout=5,
                    options='-c statement_timeout=15000 -c lock_timeout=3000')
        with psycopg.connect(dbname=base.database,**params) as connection:
            connection.autocommit=True
            if connection.execute('SELECT 1 FROM pg_database WHERE datname=%s',(DATABASE,)).fetchone() is None:
                connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(DATABASE)))
        owned=base.set(database=DATABASE,query={})
        env['TEST_DATABASE_URL']=owned.render_as_string(hide_password=False)
        env['DIANZI_TEST_RUN_ID']=RUN_ID
        SECRETS.add(env['TEST_DATABASE_URL'])
        with psycopg.connect(dbname=DATABASE,**params) as connection:
            actual=connection.execute('SELECT current_database(), current_user').fetchone()
            assert actual==(DATABASE,base.username)
            connection.execute('CREATE EXTENSION IF NOT EXISTS vector')
            version=connection.execute('SHOW server_version').fetchone()[0]
        save('resource_receipt.json',dict(database=DATABASE,host=base.host,port=base.port,postgres_version=version,
             hook_loaded_before_capture=True,capture_memory_only=True,checked_at=now(),resource_slots=1,
             production_migration='not_run',test_ddl='legacy0019 plus only2conversation tables in UUIDschemas'))
    return env


def cbm():
    prefix=['wsl','--exec','/usr/bin/env','CBM_CACHE_DIR=/tmp/dianzi-cbm-r12-context-fix1-20261016',CLI,'cli']
    tasks=[('cbm_index',['index_repository','--repo-path','/mnt/d/wt/r12-conversation-context-fix1/backend/src','--name',PROJECT,'--mode','fast','--persistence','false']),
           ('cbm_assets_index',['index_repository','--repo-path','/mnt/d/wt/r12-conversation-context-fix1/backend/src/ai_intel/assets','--name',PROJECT+'-assets','--mode','fast','--persistence','false']),
           ('cbm_schema',['get_graph_schema','--project',PROJECT]),
           ('cbm_architecture',['get_architecture','--project',PROJECT,'--aspects','all'])]
    for method in ('admit','read_bundle','acknowledge_completed_turn'):
        tasks.append(('cbm_trace_'+method,['trace_path','--project',PROJECT,'--function-name',PROJECT+'.ai_intel.answering.conversation_context.ConversationContextService.'+method,'--direction','outbound','--depth','3','--format','json']))
    for label,args in tasks:
        run(label,prefix+args,timeout=60)


def audit():
    author=ROOT/'reports/runs/recovery_r12_conversation_context_20261016'
    checked=[]
    for name in ('material_manifest.json','caller_source_manifest.json','implementation_source_manifest.json'):
        entries=json.loads((author/name).read_text(encoding='utf-8'))
        results=[]
        for entry in entries:
            path=(author if name=='material_manifest.json' else ROOT)/entry['path']
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            blob=subprocess.check_output(['git','hash-object','--path='+entry['path'],str(path)],cwd=ROOT).decode().strip() if name!='material_manifest.json' else None
            results.append(dict(path=entry['path'],raw_match=digest==entry['sha256'],clean_blob_match=blob==entry.get('clean_filter_blob') if blob else None))
        checked.append(dict(manifest=name,sha256=hashlib.sha256((author/name).read_bytes()).hexdigest(),count=len(entries),results=results))
    report=ROOT/'reports/tasks/R12-conversation-context.md'
    source_author=Path('D:/wt/r12-conversation-context')
    original_checks=[]
    for entry in json.loads((author/'implementation_source_manifest.json').read_text(encoding='utf-8')):
        original_checks.append(dict(path=entry['path'],original_author_raw_match=hashlib.sha256((source_author/entry['path']).read_bytes()).hexdigest()==entry['sha256'],review_raw_sha256=hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest()))
    save('source_audit.json',dict(checked_at=now(),checked=checked,source_author_original_checks=original_checks,author_report_original_sha256=hashlib.sha256((source_author/'reports/tasks/R12-conversation-context.md').read_bytes()).hexdigest(),author_report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
         code_commit='6259db6d98d67c1be274370ce20775133a8b0520',material_commit='f557df069a0e0eb74194557ebdb9be338d9a5b0e'))
    print(json.dumps([(item['manifest'],item['count'],sum(not x['raw_match'] for x in item['results'])) for item in checked]))


def cleanup(env):
    base=make_url(env['TEST_DATABASE_URL'])
    with psycopg.connect(dbname=DATABASE,host=base.host,port=base.port,user=base.username,password=base.password,connect_timeout=3) as connection:
        schemas=connection.execute("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'test_r12_fix1_%' OR nspname LIKE 'test_r05_fix1_%'").fetchall()
        sessions=connection.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()',(DATABASE,)).fetchone()[0]
    save('release_receipt.json',dict(checked_at=now(),own_schemas=schemas,other_own_database_sessions=sessions,resource_slot_released=not schemas and sessions==0,db_retained=True))
    assert not schemas and sessions==0
    hits=[]
    for path in [*RUN.rglob('*'), ROOT/'reports/tasks/R12-conversation-context-fix1.md', *map(lambda value: ROOT/value, ('backend/src/ai_intel/answering/conversation_context.py', 'backend/src/ai_intel/answering/conversation_contracts.py', 'backend/src/ai_intel/answering/conversation_models.py', 'backend/src/ai_intel/answering/evidence_bundle.py'))]:
        if path.is_file():
            body=path.read_bytes()
            for value in SECRETS:
                if value and value.encode() in body:
                    hits.append(str(path.relative_to(RUN)))
    save('secret_scan.json',dict(exact_dsn_password_hits=hits,scanned_at=now(),username_policy='public test marker collisions classified by context; no all-ignore'))
    assert not hits


def final_scan():
    script="(Get-Content -LiteralPath 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText"
    captured=subprocess.run([PWSH,'-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=15)
    assert captured.returncode==0
    base_value=json.loads(captured.stdout)['TEST_DATABASE_URL']
    base=make_url(base_value)
    assert (base.host,base.port,base.database)==('127.0.0.1',25432,'test_dianzi_r01_20261014')
    owned_value=base.set(database=DATABASE,query={}).render_as_string(hide_password=False)
    hits=[]
    username_contexts=[]
    fragments={base.password[i:i+8] for i in range(len(base.password)-7)}
    for path in [*RUN.rglob('*'), ROOT/'reports/tasks/R12-conversation-context-fix1.md', *map(lambda value: ROOT/value, ('backend/src/ai_intel/answering/conversation_context.py', 'backend/src/ai_intel/answering/conversation_contracts.py', 'backend/src/ai_intel/answering/conversation_models.py', 'backend/src/ai_intel/answering/evidence_bundle.py'))]:
        if not path.is_file() or path.name=='final_secret_scan.json': continue
        body=path.read_bytes().decode('utf-8',errors='replace')
        for value in (base_value,owned_value,base.password):
            if value and value in body: hits.append(dict(path=str(path.relative_to(RUN)),kind='exact_dsn_or_password'))
        present=sum(fragment in body for fragment in fragments)
        if present: hits.append(dict(path=str(path.relative_to(RUN)),kind='password_8char_fragment',count=present))
        for match in re.finditer(re.escape(base.username),body):
            nearby=body[max(0,match.start()-100):match.end()+130]
            classification='masked_connection_username' if ':***' in nearby else ('public_database_test_marker' if 'test_dianzi_r01_20261014' in nearby else 'unclassified')
            username_contexts.append(dict(path=str(path.relative_to(RUN)),line=body.count('\n',0,match.start())+1,
                offset=match.start(),classification=classification,
                context=HOOK.redact_test_connection_output(nearby,(base.password,base_value,owned_value))))
            if classification=='unclassified': hits.append(dict(path=str(path.relative_to(RUN)),kind='unclassified_username_context'))
    save('final_secret_scan.json',dict(checked_at=now(),exact_and_password_fragment_hits=hits,
         username_context_classifications=username_contexts,no_global_ignore=True,pg_connections_opened=0))
    assert not hits
    print(json.dumps(dict(secret_hits=len(hits),classified_username_contexts=len(username_contexts))))


if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='audit': audit()
    elif mode=='cbm': cbm()
    elif mode=='scan': final_scan()
    else:
        env=environment(mode.startswith('pg'))
        command=[PYTHON,*sys.argv[2:]]
        code=run(mode,command,env=env,timeout=600)
        if mode.startswith('pg'): cleanup(env)
        sys.exit(code)
