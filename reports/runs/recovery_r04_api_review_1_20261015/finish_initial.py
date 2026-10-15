"""Complete the initial independent review report and freeze byte hashes without a commit."""

import hashlib
import json
import shutil
import subprocess
from datetime import datetime,timedelta,timezone
from pathlib import Path

run = Path(__file__).resolve().parent
report = run.parents[1]/'reviews/recovery/G-B-R04-api-review-1.md'
cache = Path('C:/Users/yinha/.codex/review-cache/r04-api-review-1-20261015')
cache.mkdir(parents=True,exist_ok=True)
movements = []
for source in run.glob('*.coverage.sqlite'):
    destination = cache/source.name
    assert not destination.exists()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    shutil.move(source,destination)
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == digest
    movements.append({'original_path':str(source),'cache_path':str(destination),'sha256':digest,
        'bytes_unchanged':True})
(run/'coverage_cache_relocation.json').write_text(json.dumps(movements,indent=2))
created = datetime.fromtimestamp(report.stat().st_ctime,timezone(timedelta(hours=8))).isoformat(timespec='seconds')
now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
contents = report.read_text(encoding='utf-8')
contents = contents.replace('首次创建、写作开始与初审证据截止：2026-10-15T13:47:09+08:00。',
    f'首次创建：{created}；写作开始与初审证据截止：2026-10-15T13:47:09+08:00；本次附录写作结束：{now}。')
contents += f'''

## 初审收尾附录 · {now}

主控要求的同根补测 `reviewer_extra_boundaries` 实际13:49:08–13:49:17，exit1，9项中3passed/6failed/0skip：三个surrogate模型输入已被Pydantic拒绝，这三项通过；三个NUL模型输入未被拒绝，这三项失败。没有把surrogate臆测为已确认HTTP缺陷。另三项分别将source_scope/claim_ids/reference_ids写为数组[{{}}]，现有PG数组约束接受；实际HTTP500纯文本Internal Server Error，不是RFC9457固定503。此为Must2的成员类型损坏补证，原8探针未改。

cursor unit实际13:49:55–13:49:57，exit0，24passed/0fail/skip；完整相关auth/security/contract在私密env连接本人DB实际13:49:55–13:50:46，exit0，36passed/0fail/skip，原30pass/6setup errors保留。新增字段/阈值/分母没有改。

作者证据提交完整SHA `d97703a98593a625214dcdf3edcb744a26c7ab65` 和 `bd16aa3d81062148a5441e3b55bdec79cffaaf63` 实际解析；最终manifest的68项，每项捕获文件SHA256/大小与Git blob SHA256/大小均实校验0不符（13:52:13–13:52:17，exit0）。manifest Git blob SHA256为2970ecf9bb23728e19dad9590027263996593241d6f16f6cfd5f617bc04d665c；四个新增业务/测试文件在作者6e7c与本人4934的Git blob字节相同，app4行挂载diff另按d8f9248核对。首次证据核验误将manifest中五个已授权源码路径当越界而退出1；只扩为准确五路径白名单后核验，不读取其他路径。完整结果见author_evidence_verification.json，不把作者329unit/24PG计为本人结果。

为了实际扫描动态认证值，对原24和原8探针增加仅审查conftest的根0600秘密登记后再执行；13:52:20–13:52:56，exit1，27passed/5failed/0skip，与初始相同的五个业务失败。原探针哈希e8fd5f80663779f323fbbf9ac35f28a7333db44478c1c62c081ee9a9daf6b69b不变；业务源码/原测试没有改。原24copy的断言未改；conftest仅路径绑定、注册秘密并保留原失败脱敏钩子。

实际秘密扫描13:53:26–13:53:27，exit0：70个动态密码/会话值、测试DSN全文/连接密码全文及2577个8字符片段，86个本人证据/报告文件，0命中。最终扫描应在本附录落盘后再次执行；结果不含DSN/password/token值。原始首次8探针与24执行未保存已退出进程的动态秘密；后一次同输入执行以实际登记值补证，没有声称回溯取得旧进程密码。root0600文件只含本测试资源，未读产品keys/.env/KEYS/holdout。模型、测绘、PoC与第三方资产调用0。

初期Windows原始coverage SQLite位于本人raw目录，已按字节哈希不变移至本人仓外cache；后续每次COVERAGE_FILE直接使用仓外独立文件。JSON与日志仍原样，没有跨OS同名coverage冲突。移动清单见coverage_cache_relocation.json。Linux在线pip等待后仅终止本人pip PID25136，包装器GBK解码失败，未取得该子进程完整stdout，不将它列为测试结果；Linux离线uv第一次-r用法退出2、修正后本源缓存索引缺包退出1，原收据/日志保留。改用逐项核对锁版本的物理复制，独立venv完整unit已经实过。最早argparse顺序、相对exe路径两项执行前失败仅有工具消息，没有完整秒级收据，明示缺证，不补造时段。

本轮产物只为报告/raw证据，未改业务/schema/锁/progress，不commit/push，不整卡accepted。资源释放记录见resource_release.json/receipt；结论仍needs_changes，建议主控修三项后交新固定目标定向复核。F1/D2/R1仅有保存情报的三GET读取证据，F2仅逐维保存状态与引用投影；不证明来源持续采集、全部富化或任何评分满分。
'''
report.write_text(contents,encoding='utf-8')
paths = [path for path in run.rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.name != 'manifest_initial.json']
paths.append(report)
entries = [{'path':str(path.relative_to(Path('D:/dianzi'))).replace('\\','/'),
    'captured_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'size_bytes':path.stat().st_size}
    for path in sorted(paths)]
manifest = {'recorded_at':now,'code_sha':'4934de35a02c1b8841a9e364d31fa281cf3c0f5d',
    'tree_sha':'eecdd8d361898f550795555d3ffd58b8f630dfe7','status':'needs_changes',
    'source_tree_clean':not subprocess.check_output(['git','-C','C:/Users/yinha/.codex/worktrees/recovery-r04-api-review-1/dianzi','status','--porcelain'],text=True).strip(),
    'original_eight_probe_sha256':hashlib.sha256((run/'independent_tests/test_review_api_boundaries.py').read_bytes()).hexdigest(),
    'note':'captured byte hashes; append-only follow-up artifacts may have their own manifests; no acceptance recorded',
    'files':entries}
(run/'manifest_initial.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'report':str(report),'recorded_at':now,'manifest_file_count':len(entries),
    'source_tree_clean':manifest['source_tree_clean'],'original_eight_probe_sha256':manifest['original_eight_probe_sha256']}))
