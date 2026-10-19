"""Bounded static, graph and frontend verification of the fixed integrated tree."""
import os
from pathlib import Path
import sys
from run_command import ROOT, RUN, record

PYTHON=ROOT/'backend/.venv/Scripts/python.exe'
env=os.environ.copy()
env['PYTHONPATH']=os.pathsep.join([str(ROOT/'backend/src'),str(ROOT/'backend/tests/integration'),str(ROOT/'backend')])
mode=sys.argv[1]
if mode=='cbm':
    source='/mnt/d/wt/gc-e310-regression/backend/src'
    project='gc-e310-validation-src'
    base=['wsl.exe','-d','Ubuntu-22.04','-u','root','--','env',
        'CBM_CACHE_DIR=/tmp/dianzi-cbm-gc-e310-validation-20261016','CBM_ALLOWED_ROOT='+source,
        '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp','cli']
    record('cbm_index',base+['index_repository','--repo-path',source,'--name',project,'--mode','full','--persistence','false'])
    record('cbm_schema',base+['get_graph_schema','--project',project])
    record('cbm_architecture',base+['get_architecture','--project',project])
    for label,name in [('bulk','ai_intel.knowledge.revisions.register_source_revision_blocks'),
        ('source','ai_intel.ingestion.source_documents.persist_source_response'),
        ('catalog','ai_intel.ingestion.catalog_documents.persist_catalog_documents'),
        ('handler','ai_intel.ingestion.source_jobs.build_source_page_handler'),
        ('publish','ai_intel.enrichment.publication.publish_enrichment_attempts'),
        ('inputs','ai_intel.enrichment.inputs.load_event_enrichment_inputs'),
        ('detail','ai_intel.api.knowledge_read_service.KnowledgeReadService.event_detail'),
        ('worker','ai_intel.workers.runtime.consume_job')]:
        record('cbm_trace_'+label,base+['trace_path','--project',project,'--function-name',project+'.'+name,'--direction','both','--depth','3','--include-evidence','true'])
    record('cbm_assets_index',base+['index_repository','--repo-path',source+'/ai_intel/assets','--name','gc-e310-validation-assets','--mode','full','--persistence','false'])
    record('cbm_assets_schema',base+['get_graph_schema','--project','gc-e310-validation-assets'])
    record('cbm_assets_architecture',base+['get_architecture','--project','gc-e310-validation-assets'])
elif mode=='static':
    for label,args in [('ruff',['ruff','check','src','--no-cache']),('format',['ruff','format','--check','src','--no-cache']),('mypy',['mypy','src','--cache-dir',str(RUN/'mypy_cache')])]:
        record('backend_'+label,[PYTHON,'-m',*args],ROOT/'backend',env)
elif mode=='frontend':
    record('frontend_install',['npm.cmd','ci','--offline','--ignore-scripts','--no-audit','--no-fund'],ROOT/'frontend')
    record('frontend_test',['npm.cmd','test','--','--reporter=json','--outputFile='+str(RUN/'frontend_vitest.json')],ROOT/'frontend')
    record('frontend_typecheck',['npm.cmd','run','typecheck'],ROOT/'frontend')
    record('frontend_lint',['npm.cmd','run','lint'],ROOT/'frontend')
    record('frontend_build',['npm.cmd','run','build','--','--outDir',str(RUN/'frontend_dist')],ROOT/'frontend')
elif mode=='pure':
    files=[]
    for part in ['unit','contract','security']:
        for path in sorted((ROOT/'backend/tests'/part).glob('test_*.py')):
            if path.name.startswith(('test_r06','test_r07','test_r08','test_r09','test_r11','test_r02','test_t05','test_t06','test_t07','test_t19','test_t21','test_t24','test_t26')):
                files.append(str(path))
    record('backend_directed_pure',[PYTHON,'-m','pytest',*files,'-m','not real_pg and not real_services and not real_search_tls','--no-cov','-q','-p','no:cacheprovider','--basetemp',str(RUN/'pure_tmp'),'--junitxml',str(RUN/'backend_directed_pure.xml')],ROOT/'backend',env)
else:
    raise SystemExit('unknown mode')
