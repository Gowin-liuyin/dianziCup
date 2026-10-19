"""Append the bounded commit refresh and audit exact exited identities."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
RUN = Path(__file__).parent
sys.path.insert(0, str(RUN.parent))
import index_support as support
if os.name != 'nt':
    linux = json.loads((RUN / 'linux_resources.json').read_text())
    expected = linux['control_chain'] + linux['peak_chain'] + linux['cleanup_exact_owned_identities']
    current = support.linux_snapshot()
    left = [row for row in expected if row['pid'] in current and (current[row['pid']]['birth_clock_ticks'], current[row['pid']]['pid_namespace']) == (row['birth_clock_ticks'], row['pid_namespace'])]
    (RUN / 'postexit_linux.json').write_text(json.dumps({'recorded_at': support.now(), 'remaining_owned_identities': left}, indent=2) + '\n')
    raise SystemExit(bool(left))
sys.path.insert(0, 'D:/wt/r14-qualified-root-integration/reports/runs/r14_qualified_root_integration_20261017')
import process_metadata as metadata
sequence = json.loads((RUN / 'sequence.command.json').read_text())
left = []
for row in sequence['windows_peak_chain']:
    try:
        if metadata.identity(row['pid']) == {'pid': row['pid'], 'birth_utc': row['birth_utc']}:
            left.append(row)
    except OSError:
        pass
(RUN / 'postexit_windows.json').write_text(json.dumps({'recorded_at': support.now(), 'remaining_owned_identities': left}, indent=2) + '\n')
command = ['wsl.exe', '-d', 'Ubuntu-22.04', '--exec', '/usr/bin/python3', '/mnt/d/dianzi/reports/runs/root_batch13_index_20261017/final_bc089809/finish.py']
start = support.now()
result = subprocess.run(command, capture_output=True, timeout=10)
(RUN / 'postexit.command.json').write_text(json.dumps({'command': command, 'started_at': start, 'ended_at': support.now(), 'exit_code': result.returncode}, indent=2) + '\n')
before = json.loads((RUN / 'source_before.json').read_text())
after = json.loads((RUN.parent / 'source_final_bc089809_after.json').read_text())
old = json.loads((RUN.parent / 'source_before.json').read_text())
stable = before['files'] == after['files']
old_map = {row['path']: row['raw_sha256'] for row in old['files']}
changed = [row['path'] for row in before['files'] if old_map.get(row['path']) != row['raw_sha256']]
index = json.loads((RUN / 'index.stdout.log').read_text())['structuredContent']
commands = sorted((json.loads(path.read_text()) for path in RUN.glob('*.command.json') if path.name not in {'sequence.command.json', 'postexit.command.json'}), key=lambda row: row['started_at'])
text = f'''\n\n## 2026-10-17 · bc089809 冻结提交刷新补充\n\n输入 commit：bc089809c03472582f6256b495a6f9a2a308a5d2；实际 HEAD 与之相同。新 source_before={before['recorded_at']}，结束复算={after['recorded_at']}；224 文件 raw tree={before['tree_sha256']}；稳定={stable}。较原 3df283... 清单改变仅 {', '.join(changed)}，旧索引/日志未覆盖。\n\nCLI 实际 index_repository --help 只支持 full/moderate/fast/cross-repo-intelligence，没有 incremental；本轮按 full 刷新原独立 project=root-batch13-20261017 / cache=/tmp/dianzi-cbm-root-batch13-20261017。返回 {index['nodes']} nodes / {index['edges']} edges / parse_partial={index['parse_partial_count']} / parse_unusable={index['parse_unusable_count']}。\n\n有界序列 {sequence['started_at']}–{sequence['ended_at']}，{sequence['elapsed_seconds']:.3f}s，exit {sequence['exit_code']}；Windows{sequence['windows_peak_count']}+Linux{sequence['linux_peak_count']}={sequence['combined_peak_conservative']}/16。串行六 CLI：full refresh + consume_job、ApplicationSettings、build_graph_apply_handler、make_knowledge_change_handler、build_projection_job_handlers 的 both/depth3 trace；没有 PG/service/模型/秘密调用。每个 raw/command 使用 final_bc089809 新前缀。Windows 与 Linux exact PID/birth/namespace postexit 分别 remaining={len(left)} / Linux exit={result.returncode}。原 SessionLeader/Relay namespace PermissionError 保留，不归属其他 Docker/runc。\n\n源码交叉：workers/runtime.py:160/166/178/180 的 consume_job 从固定 EXECUTION_HANDLERS 加 enrichment/revalidation，再更新 build_projection_job_handlers；retrieval/runtime_policy.py:96/128/135/176 的 knowledge_change 仍只 HybridIndexer，明确 partial/knowledge_change_other_consumers_pending；graph_projection.py:1069 的 build_graph_apply_handler 接收 GraphProjectionStore 与 TaskScopeAuthorizer 并返回普通 JobHandler（使用调用方 Session），实际 consume_job 尚未注册 GRAPH_APPLY_JOB_TYPE。ApplicationSettings 位于 infrastructure/settings.py:34；本轮字段 rg 没有 neo4j_* 配置，不能据 class graph caller 推断具备默认 Neo4j factory。现存 driver 实现在 infrastructure/neo4j_projection.py；最初误查 knowledge/neo4j_projection.py 的 rg exit2 原 stderr 保留，正确路径查询另存 caller_config_correct.source.*。\n\n生产 caller/config/export/test 文件清单在 caller_export_test_files.source.stdout.log：workers/runtime.py、retrieval/runtime_policy.py、infrastructure/neo4j_projection.py、knowledge/graph_projection.py，以及 security/test_r10_projection_scope.py、integration/test_r10_neo4j_projection.py、integration/test_r10_projection_fix1_markers.py、integration/test_r10_projection_pg.py、unit/test_r12_default_projection_runtime.py、unit/test_r16_default_worker_registration.py。这些是后续 Root 最小注册包定位入口；没有执行这些测试，也没有把测试内容加入 CBM。完整入/出图在对应五 trace raw，class/closure 的缺边由源码补核。未进行更广的运行时动态注入、测试行为或设置回归分析，均 not_run。\n\n本补充只为此 commit/224 原始字节背书。后续 Neo4j factory/knowledge_change 代码变化需另行刷新及定向回归；不签 accepted、不改 progress、不 push。\n\n| 实际命令 | 开始 +08 | 结束 +08 | exit |\n|---|---|---|---|\n'''
for row in commands:
    text += f"| `{' '.join(row['command'])}` | {row['started_at']} | {row['ended_at']} | {row['exit_code']} |\n"
report = RUN.parents[2] / 'tasks/Root-batch13-index.md'
with report.open('a', encoding='utf-8') as output:
    output.write(text)
(RUN / 'delivery_receipt.json').write_text(json.dumps({'recorded_at': support.now(), 'commit': before['head_context_only'], 'tree_sha256': before['tree_sha256'], 'file_count': 224, 'source_stable': stable, 'changed_paths_since_prior_tree': changed, 'index_nodes': index['nodes'], 'index_edges': index['edges'], 'sequence_exit': sequence['exit_code'], 'sequence_elapsed_seconds': sequence['elapsed_seconds'], 'combined_peak': sequence['combined_peak_conservative'], 'windows_remaining': len(left), 'linux_postexit_exit': result.returncode, 'business_tests': 'not_run'}, indent=2) + '\n')
print(json.dumps({'tree': before['tree_sha256'], 'stable': stable, 'elapsed': sequence['elapsed_seconds'], 'peak': sequence['combined_peak_conservative'], 'remaining': len(left) + bool(result.returncode)}))
raise SystemExit(bool(left or result.returncode or not stable))
