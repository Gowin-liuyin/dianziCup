from pathlib import Path
import subprocess
root = Path('D:/wt/r05-pipe-recheck')
run = Path('D:/dianzi/reports/runs/recovery_r05_question_pipeline_review_1_20261015/recheck_dc014c9/frozen_tests_54bd6db')
run.mkdir(exist_ok=True)
sha = '54bd6dbb88c5aed6255b49dc485b1e327fbb7119'
relative = 'backend/tests/integration/test_r05_question_api_pg.py'
(run / Path(relative).name).write_bytes(subprocess.check_output(['git', 'show', sha + ':' + relative], cwd=root))
print(subprocess.check_output(['git', 'rev-parse', sha + '^{tree}'], cwd=root, text=True).strip())
