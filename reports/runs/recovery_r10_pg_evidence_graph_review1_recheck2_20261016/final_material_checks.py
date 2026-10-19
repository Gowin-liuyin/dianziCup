"""Capture final diff exits and version-specific original subset denominators."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import subprocess
from review_runner import ROOT,RUN,run

FINAL='ff5aa737f37c7a591bee6758485e745a0e83b086'
PREFIX='reports/runs/recovery_r10_graph_fix2_20261016/'
run('final_material_diff',['git','diff','--check','29e1ebddca5cbadffc8c6533bdeeb08b8d63e469',FINAL],ROOT)
run('final_source_diff',['git','diff','--check','29e1ebddca5cbadffc8c6533bdeeb08b8d63e469',FINAL,'--','backend','docs/decisions/CR-R10_graph_fix2.md'],ROOT)
def blob(path):
    return subprocess.check_output(['git','show',FINAL+':'+path],cwd=ROOT)
def names(raw):
    return sorted(case.attrib['name'] for case in ET.fromstring(raw).iter('testcase'))
original=Path('D:/dianzi/reports/runs/recovery_r10_pg_evidence_graph_review1_20261016/r10_pg_independent.xml').read_bytes()
author=blob(PREFIX+'frozen_original_probe20_subset.xml')
result={'original_20_case_ids':names(original),'author_20_subset_case_ids':names(author),
        'same_case_ids':names(original)==names(author),'author_subset_only':[name for name in names(author) if name not in names(original)],
        'original_only':[name for name in names(original) if name not in names(author)]}
reviewer=ET.parse(RUN/'legacy33.xml').getroot()
selected=[case for case in reviewer.iter('testcase') if case.attrib['name'] in names(original)]
assert len(selected)==20
result['reviewer20_within_legacy33']={'tests':len(selected),'failures':sum(case.find('failure') is not None for case in selected),
                                    'errors':sum(case.find('error') is not None for case in selected),
                                    'skipped':sum(case.find('skipped') is not None for case in selected)}
assert sorted(case.attrib['name'] for case in selected if case.find('failure') is not None)==sorted(case.attrib['name'] for case in ET.fromstring(author).iter('testcase') if case.find('failure') is not None)
(RUN/'original20_subset_comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
dec=Path('D:/dianzi/docs/decisions/CR-R10_graph_fix2_review_scope.md')
body=dec.read_bytes()
(RUN/'scope_clarification_identity.json').write_text(json.dumps({'path':str(dec),'raw_bytes':len(body),'raw_sha256':hashlib.sha256(body).hexdigest(),
                                                              'authority':'root explicit scope clarification only; preserve original CR and denominator'},indent=2),encoding='utf-8')
print(json.dumps({'original20_equals_author_subset':result['same_case_ids'],'clarification_bytes':len(body),'clarification_sha256':hashlib.sha256(body).hexdigest()},indent=2))
