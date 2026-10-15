| run_id | Asia/Shanghai 开始 | 结束 | 退出码 | 命令 |
|---|---|---|---:|---|
| cbm_help | 2026-10-15T00:11:52+08:00 | 2026-10-15T00:11:52+08:00 | 0 | `wsl.exe --exec /usr/bin/env CBM_CACHE_DIR=/tmp/dianzi-cbm-r01-dependency-review-1-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --help` |
| prepare_review | 2026-10-15T00:11:52+08:00 | 2026-10-15T00:11:54+08:00 | 0 | `python D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015\prepare_review.py` |
| candidate_ci | 2026-10-15T00:12:11+08:00 | 2026-10-15T00:12:16+08:00 | 0 | `npm.cmd ci` |
| cbm_index | 2026-10-15T00:12:11+08:00 | 2026-10-15T00:12:16+08:00 | 0 | `wsl.exe --exec /usr/bin/env CBM_CACHE_DIR=/tmp/dianzi-cbm-r01-dependency-review-1-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/c/Users/yinha/.codex/worktrees/recovery-r01-vitest-candidate/dianzi/frontend/src --name dianzi-r01-dependency-review-1 --mode fast --persistence false` |
| baseline_ci | 2026-10-15T00:12:41+08:00 | 2026-10-15T00:12:47+08:00 | 0 | `npm.cmd ci` |
| candidate_audit | 2026-10-15T00:12:41+08:00 | 2026-10-15T00:12:43+08:00 | 0 | `npm.cmd audit --json` |
| candidate_lint | 2026-10-15T00:12:41+08:00 | 2026-10-15T00:12:47+08:00 | 0 | `npm.cmd run lint` |
| candidate_typecheck | 2026-10-15T00:12:41+08:00 | 2026-10-15T00:12:43+08:00 | 0 | `npm.cmd run typecheck` |
| cbm_schema | 2026-10-15T00:12:41+08:00 | 2026-10-15T00:12:45+08:00 | 0 | `wsl.exe --exec /usr/bin/env CBM_CACHE_DIR=/tmp/dianzi-cbm-r01-dependency-review-1-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_graph_schema --project dianzi-r01-dependency-review-1 --format json` |
| baseline_audit | 2026-10-15T00:13:08+08:00 | 2026-10-15T00:13:11+08:00 | 1 | `npm.cmd audit --json` |
| baseline_json | 2026-10-15T00:13:08+08:00 | 2026-10-15T00:13:14+08:00 | 0 | `npm.cmd run test -- --reporter=json --outputFile=D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015\baseline_vitest.json` |
| candidate_junit | 2026-10-15T00:13:08+08:00 | 2026-10-15T00:13:14+08:00 | 0 | `npm.cmd run test -- --reporter=junit --outputFile=D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015\candidate_junit.xml` |
| candidate_registry | 2026-10-15T00:13:08+08:00 | 2026-10-15T00:13:11+08:00 | 0 | `npm.cmd view vitest@4.1.11 version engines peerDependencies dependencies --json` |
| cbm_trace | 2026-10-15T00:13:08+08:00 | 2026-10-15T00:13:12+08:00 | 0 | `wsl.exe --exec /usr/bin/env CBM_CACHE_DIR=/tmp/dianzi-cbm-r01-dependency-review-1-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project dianzi-r01-dependency-review-1 --function-name getCurrentUser --direction both --include-tests true --format json` |
| baseline_versions | 2026-10-15T00:13:35+08:00 | 2026-10-15T00:13:37+08:00 | 0 | `npm.cmd ls --depth=0 --json` |
| candidate_json | 2026-10-15T00:13:35+08:00 | 2026-10-15T00:13:40+08:00 | 0 | `npm.cmd run test -- --reporter=json --outputFile=D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015\candidate_vitest.json` |
| candidate_versions | 2026-10-15T00:13:35+08:00 | 2026-10-15T00:13:37+08:00 | 0 | `npm.cmd ls --depth=0 --json` |
| candidate_build | 2026-10-15T00:14:26+08:00 | 2026-10-15T00:14:28+08:00 | 0 | `npm.cmd run build` |
| source_crosscheck | 2026-10-15T00:14:26+08:00 | 2026-10-15T00:14:26+08:00 | 0 | `rg -n getCurrentUser\|vi\.\|vitest\|coverage\|threshold\|poolOptions\|minWorkers\|singleFork\|singleThread\|projects\|browser frontend/src frontend/tests frontend/vite.config.ts frontend/package.json` |
| quality_frontend_inherited | 2026-10-15T00:14:55+08:00 | 2026-10-15T00:15:06+08:00 | 1 | `python D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015\candidate_replay\scripts\dev.py check --scope frontend --timeout-seconds 90` |
| quality_frontend_utf8 | 2026-10-15T00:15:15+08:00 | 2026-10-15T00:15:25+08:00 | 0 | `python D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015\candidate_replay\scripts\dev.py check --scope frontend --timeout-seconds 90` |
| candidate_diff_check | 2026-10-15T00:17:12+08:00 | 2026-10-15T00:17:12+08:00 | 0 | `git diff --check d0a179eeb3621cdf21a4cba94a6b5bd4e8a2a120 497740a771e7cb2d719ab22ebad34bd30539e20d` |
| runner_config | 2026-10-15T00:17:12+08:00 | 2026-10-15T00:17:13+08:00 | 0 | `node D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015\inspect_runner.mjs` |
| check_evidence | 2026-10-15T00:17:23+08:00 | 2026-10-15T00:17:24+08:00 | 1 | `python D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015\check_evidence.py` |
| check_evidence_recheck | 2026-10-15T00:17:51+08:00 | 2026-10-15T00:17:51+08:00 | 0 | `python D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015\check_evidence.py` |
| runtime_node | 2026-10-15T00:17:51+08:00 | 2026-10-15T00:17:51+08:00 | 0 | `node --version` |
| runtime_npm | 2026-10-15T00:17:51+08:00 | 2026-10-15T00:17:51+08:00 | 0 | `npm.cmd --version` |
| runtime_python | 2026-10-15T00:17:51+08:00 | 2026-10-15T00:17:51+08:00 | 0 | `python --version` |
| no_test_negative | 2026-10-15T00:18:53+08:00 | 2026-10-15T00:18:54+08:00 | 1 | `npm.cmd run test -- __r01_independent_review_no_matching_case__` |
| rollback_pair_quality_utf8 | 2026-10-15T00:18:53+08:00 | 2026-10-15T00:19:05+08:00 | 0 | `python -c import importlib.util, pathlib, sys; p=pathlib.Path("dev_frozen_quality.py"); s=importlib.util.spec_from_file_location("rollback_quality",p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.PROJECT_ROOT=pathlib.Path.cwd(); m.BACKEND_DIR=m.PROJECT_ROOT/"backend"; sys.exit(m.run_scope_checks("frontend",90))` |
| final_candidate_identity | 2026-10-15T00:23:09+08:00 | 2026-10-15T00:23:09+08:00 | 0 | `git rev-parse HEAD HEAD^{tree}` |
| final_candidate_status | 2026-10-15T00:23:09+08:00 | 2026-10-15T00:23:09+08:00 | 0 | `git status --porcelain` |
| final_evidence_check | 2026-10-15T00:23:09+08:00 | 2026-10-15T00:23:09+08:00 | 0 | `python D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015\check_evidence.py` |
