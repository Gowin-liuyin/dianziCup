# R18 · MCP 未预期异常边界修复 1

文档首次创建/本次写作开始：2026-10-16T10:21:05+08:00
写作结束/更新时间/证据截止：见文末真实时点。
作者：/root/r18_protocol_sdk_contract_preparation；主控：/root。
状态awaiting_review；当前修复片complete，整R18仍partial；未push/accepted。
WT D:/wt/r18-mcp-output-budget-fix1；分支codex/r18-mcp-output-budget-fix1。
基线f246815bd678c624a11f784de5dc2b3c83981cde；已测/冻结source c691a0d5d0e06a4cc52567e1e816cd49cb0b1e7f
source tree9980da61338eb7b2b9202f98aa0c1055af1f9f70；已审修复待定向复核。
产品编码逐编辑时间未单独记录，不由mtime/test duration推算。

## 1. 具体触发与范围

R18/G-E，T04/T32/T35/T51切片，A1/E1/X1。公开DianziClient的MockTransport
注入RuntimeError合成credential marker。原legacy initialize将异常文本放wire
及stderr；modern discover的wire为generic错误但stderr仍泄漏marker。
这是当前边界Must1，0实际秘密；不把合成故障叫实际产品凭据泄漏。
原非作者报告G-E-R18-mcp-output-budget-review-1.md，SHA
5b2f13314c2b595a193b20b96f50a0d186d95a3017b0898af0f3995c5fe317d4。
review manifest e8b75e1...86成员逐raw核验，非作者needs_changes保留。

## 2. 修复、复用与调用关系

仅mcp_adapter.py共享工具callback末尾增加2行catch Exception，返回既有
_tool_error固定backend_internal_error。无str/repr/trace/headers/query/key/cookie
或异常日志；官方SDK收到合法isError=true结果，无须处理/打印该异常。
先保留ClientInputError/ApiError/TransportError/ResponseContractError/native
tokenizer分类；输入ValidationError原边界不动。不catch BaseException，不吞
KeyboardInterrupt/SystemExit/CancelledError，不假成功或悄悄重试。
复用现错误构造和serverInfo meta；两个实际结果均60tokens/229UTF8B，完整
正式r18-output-budget-1预算通过。无新依赖/抽象/DTO或另一套业务事实。
图project dianzi_r18_mcp_output_budget_fix1_20261016，仅sdk/python，首次改前
index/architecture/rg0；冻结后刷新和trace0，源码交叉核实共用ask/check路径。
真实链：官方ClientSession→stdio→shared callback→DianziClient DI故障
→固定安全ToolResult→官方transport。PG/model/live不在该测试链。

## 3. 原输入、原红与独立复核

same2 final probeff45fa3f...、fixture8c448aa9...逐字复制，输入/断言未改。
reviewer封存前修正原pytest.raises诊断形式以允许合法ToolResult，安全条件
不放宽：wire/stderr markerFalse且固定backend_internal_error；旧仪器在review保留。
本WT修改前亲跑2fail/exit1，6个wire/stderr/observation先逐bytes复制before_fix_*，
之后原命名观察由同测试生成新绿，不覆盖redcopies。修改后逐字same2 2pass。
cancelc7ab01e0...与independentc2902104...也逐字复制，immutable4文件SHA见
same2_frozen_input_hashes.json/independent_regression_input_hashes.json。
本作者未替自己签accepted；原非作者在新冻结版本定向复核，由root登记。

## 4. 实际验证与时间/资源限度

冻结296/296，0fail/error/skip；原280+same2两+cancel两+独立protocol12去重。
10:14:15–10:14:44+08，XML26.262s；mypy7/style/format/staged check各0。
实际ClientSession旧握手/现代discover、ASCII/中文/emoji、7999/8000/8001、
完整meta/reference、cache/no implicit download/native边界及HTTP拒绝仍绿。
实际queue cancel未调度backend；4已执行IO继续占worker，late result未返取消者。
queue cancellation0.125s；slowstream question IOtimeout0.1s，实际0.312s完成。
完整wall deadline和中止已发IO仍缺口，root指定后续SDK/runtime修，不在本批扩补丁。
unit/contract/security本片passed；integration仅合成stdio/loopback/ASGI passed；
frontend/e2e/live/manual not_run。PG0/产品模型0/测绘0/外部付费调用0，编码费用unknown。

## 5. 文件、合同与回滚

唯一product文件adapter；必要probe快照/newrun helper和精确run-local binary attrs。
SDK core4、词表/token/byte阈值、oldv2/publicschema/HTTP未绑定策略、包装/locks/
backend/progress/根attrs全部未改。原91、368、review86=545材料记录raw未改。
无评分/金标/分母/阈值/失败skip变化，无新增重大决策。回滚只回退该2行，保留
全部历史/raw；无DDL/drop/downgrade。没有用安全修复冒充6tools/分页/PG鉴权/live。

## 6. 问题台账、评分与下一步

Must1：未预期IO异常交给SDK通用异常处理，rootcause缺安全收口；2行修复，
same2与完整296绿，待原非作者复核。没有新增首红业务问题；原2红完整保留。
A1/E1/X1边界证据在run和probe；正式P1/P2/P3指标not_run。下一步root安排
原非作者新WT审fixed source/material；整体deadline/正式PG身份/6tools/分页另批。

## 7. 实际命令

| 标签 | argv | cwd | 开始 / 结束(+08) | exit | 日志 |
|---|---|---|---|---|---|
| copy_independent_regressions | D:/dianzi/backend/.venv/Scripts/python.exe -c from pathlib import Path; import hashlib,json; source=Path('D:/wt/r18-mcp-output-budget-review1/reports/runs/recovery_r18_mcp_output_budget_review1_20261016'); target=Path('reports/runs/recovery_r18_mcp_output_budget_fix1_20261016'); pairs=[('test_cancellation.py','c7ab01e0d116cd7c146cd872e7432b99ab9b8f170884b1b8656ae696a9009021'),('test_independent_mcp.py','c29021042cbaf0e6b956cf7c0789519d527675151fbace493b86710a1f6c1659')]; rows=[];
for name,expected in pairs:
 raw=(source/name).read_bytes(); assert hashlib.sha256(raw).hexdigest()==expected; assert not (target/name).exists(); (target/name).write_bytes(raw); rows.append({'path':name,'raw_sha256':expected,'inputs_and_asserts_unchanged':True})
(target/'independent_regression_input_hashes.json').write_bytes(json.dumps(rows,indent=2).encode()+b'\n'); print('2 independent regression files copied exact bytes') | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:13:54+08:00 / 2026-10-16T10:13:55+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/copy_independent_regressions.log |
| copy_same2_frozen_probe | D:/dianzi/backend/.venv/Scripts/python.exe -c from pathlib import Path; import json,hashlib; source=Path('D:/wt/r18-mcp-output-budget-review1/reports/runs/recovery_r18_mcp_output_budget_review1_20261016'); target=Path('reports/runs/recovery_r18_mcp_output_budget_fix1_20261016'); pairs=[('test_unexpected_error_diagnosis.py','ff45fa3f78dc3a6cd845f86a34abd68576e746e7458392001a233feb1630a4f3'),('unexpected_error_stdio_fixture.py','8c448aa919d723a1c0810ecc7cc3322f5665bde9931a1ac327d6d09a445a4d2e')]; records=[];
for name,digest in pairs:
 raw=(source/name).read_bytes(); assert hashlib.sha256(raw).hexdigest()==digest; assert not (target/name).exists(); (target/name).write_bytes(raw); records.append({'path':name,'sha256':digest,'unchanged_input_and_assertions':True})
(target/'same2_frozen_input_hashes.json').write_bytes(json.dumps({'source':str(source),'files':records},indent=2).encode()+b'\n'); print('same2 final probe and fixture copied byte for byte') | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:11:43+08:00 / 2026-10-16T10:11:43+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/copy_same2_frozen_probe.log |
| evidence_helper_format | D:/dianzi/backend/.venv/Scripts/ruff.exe format --config backend/pyproject.toml reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/seal_fix1_materials.py | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:20:38+08:00 / 2026-10-16T10:20:38+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/evidence_helper_format.log |
| evidence_helper_lint | D:/dianzi/backend/.venv/Scripts/ruff.exe check --config backend/pyproject.toml reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/seal_fix1_materials.py | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:20:44+08:00 / 2026-10-16T10:20:44+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/evidence_helper_lint.log |
| fixed_format | D:/dianzi/backend/.venv/Scripts/ruff.exe format --check --config backend/pyproject.toml sdk/python/ai_intel_client/mcp_adapter.py | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:12:42+08:00 / 2026-10-16T10:12:42+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/fixed_format.log |
| fixed_style | D:/dianzi/backend/.venv/Scripts/ruff.exe check --config backend/pyproject.toml sdk/python/ai_intel_client/mcp_adapter.py | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:12:42+08:00 / 2026-10-16T10:12:42+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/fixed_style.log |
| fixed_type | D:/dianzi/backend/.venv/Scripts/mypy.exe --strict sdk/python/ai_intel_client | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:12:42+08:00 / 2026-10-16T10:12:50+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/fixed_type.log |
| frozen_index | wsl.exe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r18-mcp-output-budget-fix1/sdk/python --name dianzi_r18_mcp_output_budget_fix1_20261016 --mode fast | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:17:54+08:00 / 2026-10-16T10:17:59+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/frozen_index.log |
| frozen_trace | wsl.exe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project dianzi_r18_mcp_output_budget_fix1_20261016 --function-name dianzi_r18_mcp_output_budget_fix1_20261016.ai_intel_client.mcp_adapter.create_current_read_tool_server --direction both --depth 2 --max-output-tokens 1800 --format json | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:18:46+08:00 / 2026-10-16T10:18:49+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/frozen_trace.log |
| full_original_and_independent | D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -q sdk/python/tests tests/plan/test_public_api_v2.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_independent_boundaries.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_cli_fix1_regressions.py reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/test_unexpected_error_diagnosis.py reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/test_cancellation.py reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/test_independent_mcp.py -o addopts= --junitxml=reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/full_original_and_independent.xml | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:14:15+08:00 / 2026-10-16T10:14:44+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/full_original_and_independent.log |
| prechange_architecture | wsl.exe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_architecture --project dianzi_r18_mcp_output_budget_fix1_20261016 --format json | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:11:51+08:00 / 2026-10-16T10:11:56+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/prechange_architecture.log |
| prechange_exception_callers | rg -n create_current_read_tool_server\|_tool_error\|Exception\|CancelledError\|call_tool\|OutputBudgetTokenizationError sdk/python/ai_intel_client sdk/python/tests | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:11:20+08:00 / 2026-10-16T10:11:20+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/prechange_exception_callers.log |
| prechange_index | wsl.exe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r18-mcp-output-budget-fix1/sdk/python --name dianzi_r18_mcp_output_budget_fix1_20261016 --mode fast | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:11:20+08:00 / 2026-10-16T10:11:26+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/prechange_index.log |
| preserve_same2_red | D:/dianzi/backend/.venv/Scripts/python.exe -c from pathlib import Path; import json,hashlib; r=Path('reports/runs/recovery_r18_mcp_output_budget_fix1_20261016'); names=[f'unexpected_{p}_{s}' for p in ['handshake','modern'] for s in ['stderr.log','wire.json','observation.json']]; rows=[];
for name in names:
 raw=(r/name).read_bytes(); target=r/('before_fix_'+name); assert not target.exists(); target.write_bytes(raw); rows.append({'source_name':name,'preserved_name':target.name,'sha256':hashlib.sha256(raw).hexdigest()})
(r/'before_fix_output_manifest.json').write_bytes(json.dumps({'original_labels_preserved':True,'files':rows},indent=2).encode()+b'\n'); print('6 original red protocol outputs preserved byte for byte') | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:12:07+08:00 / 2026-10-16T10:12:07+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/preserve_same2_red.log |
| same2_after_fix | D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -q reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/test_unexpected_error_diagnosis.py -o addopts= --junitxml=reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/same2_after_fix.xml | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:12:42+08:00 / 2026-10-16T10:12:47+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/same2_after_fix.log |
| same2_before_fix | D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -q reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/test_unexpected_error_diagnosis.py -o addopts= --junitxml=reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/same2_before_fix.xml | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:11:51+08:00 / 2026-10-16T10:11:57+08:00 | 1 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/same2_before_fix.log |
| source_commit | git commit -m R18 contain unexpected backend errors within safe MCP tool results | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:17:32+08:00 / 2026-10-16T10:17:32+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/source_commit.log |
| source_preflight | D:/dianzi/backend/.venv/Scripts/python.exe -c from pathlib import Path; import subprocess,json,hashlib; r=Path('reports/runs/recovery_r18_mcp_output_budget_fix1_20261016'); assert subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()=='f246815bd678c624a11f784de5dc2b3c83981cde'; assert not subprocess.check_output(['git','diff','--cached','--name-only']).strip(); changed=subprocess.check_output(['git','diff','--name-only','--','sdk/python']).decode().splitlines(); assert changed==['sdk/python/ai_intel_client/mcp_adapter.py']; inputs=json.loads((r/'same2_frozen_input_hashes.json').read_bytes())['files']; others=json.loads((r/'independent_regression_input_hashes.json').read_bytes());
for e in inputs: assert hashlib.sha256((r/e['path']).read_bytes()).hexdigest()==e['sha256']
for e in others: assert hashlib.sha256((r/e['path']).read_bytes()).hexdigest()==e['raw_sha256']
for e in json.loads((r/'before_fix_output_manifest.json').read_bytes())['files']: assert hashlib.sha256((r/e['preserved_name']).read_bytes()).hexdigest()==e['sha256']
print('source only adapter2lines; 4 frozen probes and6 original redcopies unchanged') | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:17:04+08:00 / 2026-10-16T10:17:05+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/source_preflight.log |
| source_staged_check | D:/dianzi/backend/.venv/Scripts/python.exe -c import subprocess; names=subprocess.check_output(['git','diff','--cached','--name-only']).decode().splitlines(); assert len(names)==7; assert all(p=='sdk/python/ai_intel_client/mcp_adapter.py' or p.startswith('reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/') for p in names); r=subprocess.run(['git','diff','--cached','--check'],check=False); raise SystemExit(r.returncode) | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:17:26+08:00 / 2026-10-16T10:17:26+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/source_staged_check.log |
| stage_source | git add -- sdk/python/ai_intel_client/mcp_adapter.py reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/run_check.py reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/.gitattributes reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/test_unexpected_error_diagnosis.py reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/unexpected_error_stdio_fixture.py reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/test_cancellation.py reports/runs/recovery_r18_mcp_output_budget_fix1_20261016/test_independent_mcp.py | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:17:11+08:00 / 2026-10-16T10:17:11+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/stage_source.log |
| verify_fixed_error_budget | D:/dianzi/backend/.venv/Scripts/python.exe -c from pathlib import Path; import json; from mcp_types import CallToolResult,SERVER_INFO_META_KEY; from ai_intel_client.output_budget import McpOutputBudget; r=Path('reports/runs/recovery_r18_mcp_output_budget_fix1_20261016'); b=McpOutputBudget(Path('D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/fb374d419588a4632f3f557e76b4b70aebbca790')); rows=[];
for p in ['handshake','modern']:
 result=CallToolResult.model_validate_json((r/('unexpected_'+p+'_wire.json')).read_bytes()); assert result.is_error; assert SERVER_INFO_META_KEY in result.meta; assert b.fits(result); serial=result.model_dump_json(by_alias=True,exclude_none=True); rows.append({'protocol':p,'tokens':len(b.encoding.encode_ordinary(serial)),'utf8_bytes':len(serial.encode()),'complete_result_with_server_info_fits':True})
(r/'fixed_error_budget_proof.json').write_bytes(json.dumps(rows,indent=2).encode()+b'\n'); print('both actual fixed errors fit formal complete budget with serverInfo') | D:\wt\r18-mcp-output-budget-fix1 | 2026-10-16T10:16:27+08:00 / 2026-10-16T10:16:28+08:00 | 0 | ../runs/recovery_r18_mcp_output_budget_fix1_20261016/verify_fixed_error_budget.log |

## 8. 文档修订

首次完整写作结束/更新时间/证据截止：2026-10-16T10:21:05+08:00。
