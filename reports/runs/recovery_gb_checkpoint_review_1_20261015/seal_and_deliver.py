from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil

RUN = Path(__file__).parent
REPORT = RUN.parents[1] / 'reviews/recovery/G-B-checkpoint-review-1.md'
DEST_RUN = Path('D:/dianzi/reports/runs/recovery_gb_checkpoint_review_1_20261015')
DEST_REPORT = Path('D:/dianzi/reports/reviews/recovery/G-B-checkpoint-review-1.md')
started = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert DEST_RUN.resolve().is_relative_to(Path('D:/dianzi/reports/runs').resolve())
assert DEST_REPORT.resolve().parent == Path('D:/dianzi/reports/reviews/recovery').resolve()
assert not DEST_REPORT.exists() and not DEST_RUN.exists()
report = REPORT.read_text(encoding='utf-8')
report = report.replace('后两源套件继续本人数据库bba59f55','新增来源3/7/11、25原文与41知识API继续本人数据库bba59f55')
failure_paths = json.loads((RUN / 'initial_byte_failures.json').read_text(encoding='utf-8'))
extra = '\n\n初审全部字节差异补核：12条checkout hash拒绝及13条Git blob hash差异涉及9个唯一path，均已亲测CRLF/LF归一后字节完全相同；initial_byte_failures.json逐条保留原manifest/checkout/blob SHA、拒绝数和原因（2026-10-15T18:58:47+08:00至18:58:48+08:00，exit0）。不是9个实际秘密。下列列表为全部差异路径：\n\n'
extra += '\n'.join('- `' + item['path'] + '`：WT拒绝记录=' + str(item['raw_rejected_records']) + '，blob差异记录=' + str(item['blob_mismatch_records']) for item in failure_paths)
extra += '\n\n资源通知（核对主控消息，非本reviewer续期）：MinIO段3在2026-10-15T18:57:02+08:00结束，段4在18:57:49+08:00启动，47秒中断，新硬截止20:57:49+08:00。本人114对象亲测属于段3；不拼持续时长，也没有因资源续期重复验证既有对象。产品候选仍1927。\n'
ended_write = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
report = re.sub(r'\n最终报告写作实际起止：.*?审核停止于本G-B阶段。\n',extra + f'\n最终报告补核封存实际起止：{started} → {ended_write}；证据截止包含final_metadata_seal 18:59:31+08:00；封存时刻{ended_write}。审核停止于本G-B阶段。\n',report)
REPORT.write_text(report,encoding='utf-8')
(RUN / 'report_final_seal.json').write_text(json.dumps({'started_at':started,'ended_at':ended_write,'sha':'1927eeb00a7e0c1335f76340b0382f46102f08f2','report_sha256':digest(REPORT),'verdict':'Ship limited R04/R05 stage','history_failures_preserved':True,'business_files_modified':False,'shared_state_accepted_push':False},ensure_ascii=False,indent=2),encoding='utf-8')
files = [path for path in RUN.rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.name not in {'artifact_manifest.json','delivery_receipt.json'}]
manifest = {'sha':'1927eeb00a7e0c1335f76340b0382f46102f08f2','report_path':str(DEST_REPORT),'report_sha256':digest(REPORT),'files':[{'path':path.relative_to(RUN).as_posix(),'bytes':path.stat().st_size,'sha256':digest(path)} for path in sorted(files)],'excluded':'Only reviewer-generated __pycache__; self-manifest/delivery receipt separately sealed'}
(RUN / 'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
DEST_REPORT.parent.mkdir(parents=True,exist_ok=True)
shutil.copyfile(REPORT,DEST_REPORT)
DEST_RUN.mkdir(parents=True)
for path in [*files,RUN / 'artifact_manifest.json']:
    destination = DEST_RUN / path.relative_to(RUN)
    assert destination.resolve().is_relative_to(DEST_RUN.resolve())
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(path,destination)
    assert digest(path) == digest(destination)
assert digest(REPORT) == digest(DEST_REPORT)
ended = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
delivery = {'started_at':started,'ended_at':ended,'report_path':str(DEST_REPORT),'report_sha256':digest(DEST_REPORT),'files_verified':len(files)+1,'run_destination':str(DEST_RUN),'copies_hash_equal':True,'only_authorized_destinations':True,'accepted_push_business_edits':False}
(RUN / 'delivery_receipt.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copyfile(RUN / 'delivery_receipt.json',DEST_RUN / 'delivery_receipt.json')
assert digest(RUN / 'delivery_receipt.json') == digest(DEST_RUN / 'delivery_receipt.json')
print(json.dumps(delivery,ensure_ascii=False))
