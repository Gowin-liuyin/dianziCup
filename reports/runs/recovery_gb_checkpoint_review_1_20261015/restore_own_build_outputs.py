from pathlib import Path
import subprocess
import json

RUN = Path(__file__).parent
results = []
for root in [Path('D:/wt/gb-stage-review'),Path('D:/wt/gb-stage-recheck'),Path('D:/wt/gb-stage-final')]:
    target = root / 'frontend/tsconfig.tsbuildinfo'
    assert target.resolve().is_relative_to(root.resolve())
    diff = subprocess.check_output(['git','diff','--','frontend/tsconfig.tsbuildinfo'],cwd=root)
    (RUN / (root.name + '_generated_tsbuildinfo.diff')).write_bytes(diff)
    assert subprocess.check_output(['git','diff','--name-only'],cwd=root,text=True).splitlines() == ['frontend/tsconfig.tsbuildinfo']
    subprocess.run(['git','restore','--','frontend/tsconfig.tsbuildinfo'],cwd=root,check=True)
    status = subprocess.check_output(['git','status','--short'],cwd=root,text=True)
    assert not subprocess.check_output(['git','diff','--name-only'],cwd=root,text=True).strip()
    results.append({'worktree':str(root),'restored_only_own_generated_file':'frontend/tsconfig.tsbuildinfo','status':status})
(RUN / 'own_worktree_status.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False))
