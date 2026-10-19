"""Small new synthetic probes for cross-field IDs, latest hashes and Windows junctions."""
import hashlib
import itertools
import json
import os
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from run_checks import ROOT,RUN,PYTHON,now

sys.path.insert(0,str(ROOT))
from scripts.annotation.prepare import digest
OLD=Path('C:/Users/yinha/AppData/Local/Temp/r19-review-only-synthetic-9d7uhd1i')
TEST=Path(tempfile.mkdtemp(prefix='r19-fix1-review-extra-synthetic-')).resolve()
base=json.loads((OLD/'base_synthetic.json').read_text(encoding='utf-8'))
RECORDS=[]

def write(name,value):
    path=TEST/(name+'.json')
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return path

def cli(name,args,expected,code=None):
    argv=[PYTHON,str(ROOT/'scripts/annotation/prepare.py'),*map(str,args)]
    start=now()
    p=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=False)
    record={'name':name,'argv':argv,'cwd':str(ROOT),'started_at':start,'ended_at':now(),
        'expected_exit':expected,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,
        'expectation_met':p.returncode==expected and (code is None or code in p.stderr)}
    if code is not None: record['expected_error_code']=code
    if '--output' in args:
        output=Path(args[args.index('--output')+1]); record['output_exists']=output.exists()
        if expected==2: record['expectation_met']=record['expectation_met'] and not output.exists()
    if expected==0 and name.startswith(('normal_','updated_')):
        summary=json.loads(p.stdout)
        record['human_gold_zero']=summary['human_gold_count']==0
        record['denominator_still_null']=summary['formal_evaluation']['denominator'] is None
        record['expectation_met']=record['expectation_met'] and record['human_gold_zero'] and record['denominator_still_null']
    RECORDS.append(record)
    return p

def fresh_case(stem,split):
    case=deepcopy(base['cases'][0])
    case.update(case_id='SYN-'+stem,event_family_id='SYN-FAMILY-'+stem,family_aliases=[],split=split)
    source=case['source_refs'][0]
    source.update(uri='urn:synthetic:'+stem,document_id='SYN-DOCUMENT-'+stem,revision_id='SYN-REVISION-'+stem)
    evidence=case['evidence'][0]
    evidence.update(source_uri=source['uri'],revision_id=source['revision_id'],span_id='SYN-SPAN-'+stem,block_id='SYN-BLOCK-'+stem)
    case['input_refs'][0]['ref_id']=evidence['span_id']
    return case

def assign(case,field,identity):
    if field=='family': case['event_family_id']=identity
    elif field=='alias': case['family_aliases']=[identity]
    elif field=='document': case['source_refs'][0]['document_id']=identity
    else:
        case['source_refs'][0]['uri']=identity
        case['evidence'][0]['source_uri']=identity

for left,right in itertools.product(('family','alias','document','uri'),repeat=2):
    document=deepcopy(base)
    first,second=fresh_case('LEFT','dev'),fresh_case('RIGHT','holdout')
    identity='urn:synthetic:COMMON-EXACT-ID'
    assign(first,left,identity); assign(second,right,identity)
    document['cases']=[first,second]
    path=write('cross_'+left+'_'+right,document)
    cli('cross_field_'+left+'_'+right,['validate','--input',path],2,'FAMILY_SPLIT_LEAK')

document=deepcopy(base)
document['cases']=[fresh_case('LEFT','dev'),fresh_case('RIGHT','demo')]
cli('normal_unrelated_same_quote',['validate','--input',write('unrelated_same_quote',document)],0)
document['cases'][1]['split']='dev'
document['cases'][1]['family_aliases']=[document['cases'][0]['event_family_id']]
p=cli('normal_same_split_related_count_preserved',['validate','--input',write('same_split',document)],0)
assert json.loads(p.stdout)['candidate_count']==2

input_path=write('base_synthetic',base)
labels=json.loads((OLD/'claimed_humans_are_synthetic_only.json').read_text(encoding='utf-8'))
labels['annotators'][1]['label']['expected_status']='conflict'
records=labels['annotators']
decision={'case_id':base['cases'][0]['case_id'],'adjudicator_id':'SYN-adjudicator',
    'recorded_at':base['prepared_at'],'label_sha256s':[digest(record) for record in records],
    'reason':'Explicit synthetic review only','label':{'expected_claims':[],'expected_conditions':[],'expected_status':'unknown'}}
labels['adjudication']=[decision]
labels['identity_checks'][0]['label_sha256s']=decision['label_sha256s']
cli('normal_complete_synthetic_chain',['validate','--input',input_path,'--labels',write('valid_chain',labels)],0)
revised=deepcopy(records[0])
revised.update(revision=2,previous_sha256=digest(records[0]),change_reason='Explicit synthetic audit revision',
    affected_case_ids=[base['cases'][0]['case_id']],retest_refs=['SYN-RETEST-ONLY'])
labels['annotators'].append(revised)
cli('old_adjudication_after_current_label_revision',['validate','--input',input_path,'--labels',write('old_decision_after_revision',labels)],2,'ADJUDICATION_INVALID_OR_STALE')
current=[revised,records[1]]
labels['adjudication'][0]['label_sha256s']=[digest(record) for record in current]
cli('old_identity_after_current_label_revision',['validate','--input',input_path,'--labels',write('old_identity_after_revision',labels)],2,'IDENTITY_ATTESTATION_INVALID_OR_STALE')
labels['identity_checks'][0]['label_sha256s']=[digest(record) for record in current]
label_path=write('current_complete_chain',labels)
output=TEST/'current_chain_export.json'
cli('updated_chain_export',['export','--input',input_path,'--labels',label_path,'--output',output],0)
export=json.loads(output.read_text())
assert len(export['annotations']['annotators'])==3
assert export['annotations']==labels
cli('updated_chain_revalidate',['validate','--input',output],0)

linked=TEST/'新注册 空worktree'
created=subprocess.run(['git','worktree','add','--detach','--no-checkout',str(linked),'HEAD'],cwd=ROOT,capture_output=True,check=False)
assert created.returncode==0
junction=TEST/'junction_to_registered'
try:
    p=subprocess.run(['cmd','/c','mklink','/J',str(junction),str(linked)],capture_output=True,check=False)
    assert p.returncode==0
    holdout=deepcopy(base); holdout['cases'][0]['split']='holdout'
    holdout_path=write('explicit_synthetic_holdout',holdout)
    for target in (linked,junction):
        for kind in ('labels','holdout'):
            args=['export','--input',input_path if kind=='labels' else holdout_path,
                  '--output',target/('synthetic_'+kind+'.json')]
            if kind=='labels': args.extend(['--labels',label_path])
            cli('registered_'+target.name+'_'+kind,args,2,'HUMAN_OR_HOLDOUT_PATH_MUST_BE_EXTERNAL')
    normal_public=TEST/'public'; normal_public.mkdir()
    (normal_public/'safe.txt').write_text('Explicit safe synthetic public only',encoding='utf-8')
    cli('normal_scan_public',['scan','--input',holdout_path,'--scan-root',normal_public],0)
    try:
        os.symlink(normal_public,TEST/'native_symbolic_link',target_is_directory=True)
        cli('native_symlink_scan',['scan','--input',holdout_path,'--scan-root',TEST/'native_symbolic_link'],2,'SCAN_ROOT_MISSING')
    except OSError as error:
        RECORDS.append({'name':'native_symlink_creation','status':'blocked_environment',
            'recorded_at':now(),'winerror':getattr(error,'winerror',None),'errno':error.errno,
            'not_a_business_test_failure':True})
finally:
    assert linked.resolve().is_relative_to(TEST)
    assert junction.resolve()==linked.resolve()
    junction.rmdir()
    assert {path.name for path in linked.iterdir()}=={'.git'}
    removed=subprocess.run(['git','worktree','remove',str(linked)],cwd=ROOT,capture_output=True,check=False)
    assert removed.returncode==0

result={'recorded_at':now(),'synthetic_fixture_root':str(TEST),'actual_humans':0,
    'records':RECORDS,'mismatches':[record['name'] for record in RECORDS if record.get('expectation_met') is False]}
(RUN/'extra_probes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'cli_executed':sum('argv' in r for r in RECORDS),'mismatches':result['mismatches'],
    'fixture_root':str(TEST)},ensure_ascii=False))
raise SystemExit(1 if result['mismatches'] else 0)
