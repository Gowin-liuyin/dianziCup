from pathlib import Path
import subprocess
root = Path('D:/wt/r05-pipe-review')
run = Path('D:/dianzi/reports/runs/recovery_r05_question_pipeline_review_1_20261015/frozen_tests_af73b3e')
run.mkdir(exist_ok=True)
sha = 'af73b3e66d6f984fa0071938ff302257cae09711'
for relative in ['backend/tests/integration/test_r05_question_api_pg.py', 'backend/tests/unit/test_r05_question_routes.py']:
    content = subprocess.check_output(['git', 'show', sha + ':' + relative], cwd=root)
    (run / Path(relative).name).write_bytes(content)
print(subprocess.check_output(['git', 'rev-parse', sha + '^{tree}'], cwd=root, text=True).strip())
