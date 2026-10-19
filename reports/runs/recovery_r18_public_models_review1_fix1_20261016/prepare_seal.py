"""Prepare the first-review sealing procedure for only the new fix1 evidence."""
from __future__ import annotations
import subprocess
from pathlib import Path

RUN=Path(__file__).resolve().parent
WORKTREE=Path('D:/wt/r18pm-r1f1')
raw=subprocess.run(['git','show','a7bee69be46d3b9ecc611f188723a81cb2569dd2:reports/runs/recovery_r18_public_models_review1_20261016/seal_review.py'],
                   cwd=WORKTREE,capture_output=True,check=True).stdout.decode()
raw=raw.replace('D:/wt/r18pm-r1','D:/wt/r18pm-r1f1')
raw=raw.replace('G-E-R18-public-models-review-1.md','G-E-R18-public-models-review-1-recheck.md')
raw=raw.replace('be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958','011ea225d18b7511a19d7d6056288f799bb83f20')
raw=raw.replace('codex/r18-public-models-review1-material','codex/r18-public-models-review1-fix1-material')
raw=raw.replace("'needs_changes'","'Ship limited model qualification fix'")
raw=raw.replace('R18 independent public typed model review needs changes','R18 independent public model qualification fix1 recheck')
(RUN/'seal_review.py').write_text(raw,encoding='utf-8',newline='\n')
(RUN/'.gitattributes').write_text('** -text -diff\n',encoding='utf-8',newline='\n')
print(str(RUN/'seal_review.py'))
