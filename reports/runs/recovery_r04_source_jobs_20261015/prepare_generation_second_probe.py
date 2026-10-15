"""保留首轮逐字引用失败；新提示版本显式要求同一行连续引文。"""

from pathlib import Path

RUN = Path(__file__).resolve().parent
target = RUN / "probe_generation_live_single_line.py"
assert not target.exists()
source = (RUN / "probe_generation_live.py").read_text(encoding="utf-8")
source = source.replace('generation_live_31c2866"', 'generation_live_31c2866_single_line_v2"')
source = source.replace('max_length=3000)', 'max_length=160, pattern=r"^[^\\r\\n]+$")')
source = source.replace('r05-live-evidence-v1', 'r05-live-evidence-single-line-v2')
source = source.replace('r05-live-answer-v1', 'r05-live-answer-single-line-v2')
source = source.replace('用中文概括唯一证据中的事实，并逐字摘录支持摘要的一小段原文。不得添加证据未陈述的版本或修复结论。',
    '用中文简述一条证据中的事实。quoted_evidence必须从原文同一行内原样连续摘录一个支持该事实的短片段，不得换行、翻译、去除内部空格或改字；不得添加证据未陈述的版本或修复结论。')
target.write_text(source, encoding="utf-8")
wrapper = RUN / "probe_generation_live_single_line.ps1"
assert not wrapper.exists()
wrapper.write_text((RUN / "probe_generation_live.ps1").read_text(encoding="utf-8").replace(
    'probe_generation_live.py', 'probe_generation_live_single_line.py'), encoding="utf-8")
print("new bounded probe prepared; first failure unchanged")
