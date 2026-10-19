"""Report actual case rosters without adding overlapping executions."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from run_command import ROOT,RUN

summary={}
for path in sorted(RUN.glob('*.xml')):
    suites=ET.fromstring(path.read_bytes())
    cases=suites.findall('.//testcase')
    groups={}
    for case in cases:
        kind='failed' if case.find('failure') is not None else 'error' if case.find('error') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
        group=groups.setdefault(case.get('classname'),dict(tests=0,passed=0,failed=0,error=0,skipped=0))
        group['tests']+=1
        group[kind]+=1
    counts={key:sum(g[key] for g in groups.values()) for key in ['tests','passed','failed','error','skipped']}
    summary[path.name]=dict(**counts,groups=groups,roster=[dict(classname=c.get('classname'),name=c.get('name'),outcome='failed' if c.find('failure') is not None else 'error' if c.find('error') is not None else 'skipped' if c.find('skipped') is not None else 'passed') for c in cases],junit_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
(RUN/'test_rosters.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
commands=[json.loads(p.read_text()) for p in sorted(RUN.glob('*.command.json'))]
(RUN/'command_index.json').write_text(json.dumps(commands,indent=2),encoding='utf-8')
print(json.dumps({name:{key:value for key,value in item.items() if key not in {'roster','groups'}} for name,item in summary.items()},indent=2))
print(json.dumps({'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'tree':subprocess.check_output(['git','show','-s','--format=%T','HEAD'],cwd=ROOT,text=True).strip(),
    'tracked_diff':subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines(),
    'command_count':len(commands)},indent=2))
