# 2026-10-14 规划审计证据

代码基线：`8e265dc039a67319140f003f6a070ea714bf7bef`。主报告：[PLAN-AUDIT-20261014](../../reviews/PLAN-AUDIT-20261014.md)。

`commands.json`记录本轮后端/前端/原计划检查的实际argv、时间、退出码和日志。`behavior_probes.json`是第一次观察；`behavior_probes_reproduced.json`为落盘复现脚本再次运行，另加持久化失败仍推进游标的观察。两者没有替代正式测试或修改应用状态。

`nvd-response.json`为本轮对官方NVD API的单次公开只读请求留档：`https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2024-34359`。响应SHA-256为`1bc5449375788cf417662cf3187bcd11c1484ed0b15026d4cf71760edd352c1f`。后续探针使用此文件，不再联网；它是审计样本，不是正式评测金标。

复现行为探针（仓库`backend`目录）：

```powershell
uv run --locked --offline python ../reports/runs/plan_audit_20261014/reproduce_probes.py
```

核对三份文档的相对链接、任务/场景/要求覆盖、状态文件重复键、独立PDF提取与Docker可连接性（仓库根目录）：

```powershell
& 'C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' reports/runs/plan_audit_20261014/verify_artifacts.py
```

此Python路径是本机bundled runtime，换机需要能导入pypdf的Python。`artifact_checks.json`中Docker exit=1是本次环境观察，不是文档检查失败。该脚本不启动/关闭容器，不运行迁移，不修改状态文件。

CBM使用官方v0.11.0 portable Linux包，SHA-256为`1f9e8293eb2bc5c05cfa27a7e8fc033da6d729ffad525ccfcdaa3fd606306683`。本机临时安装与索引可能在清理临时目录后消失，JSON证据保留在仓库；复跑先从官方release取相同版本并验证校验和。此次实际CLI形式如下：

```bash
export CBM_CACHE_DIR=/tmp/dianzi-cbm-audit-20261014/cache
CBM_BIN=/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp
"$CBM_BIN" cli index_repository --repo-path /mnt/d/dianzi --name dianzi-audit-20261014 --persistence false
"$CBM_BIN" cli get_architecture --project dianzi-audit-20261014 --path backend/src --aspects overview --format json
"$CBM_BIN" cli get_graph_schema --project dianzi-audit-20261014
"$CBM_BIN" cli trace_path --project dianzi-audit-20261014 --function-name dianzi-audit-20261014.backend.src.ai_intel.ingestion.scheduler.commit_page_persisted --direction inbound --depth 2 --include-tests false --format json
```

对应原始输出：`cbm_architecture.json`、`cbm_schema.txt`、`cbm_scheduler_production.json`。同一个trace加`--include-tests true`得到`cbm_scheduler_with_tests.json`；NVD、ClaimsLedger和应用入口的输出分别为`cbm_nvd_callers.json`、`cbm_claims_callers.json`、`cbm_application_calls.json`。

本目录没有附件密钥、私有资产明细、付费接口输出或正式holdout答案。业务源码未改动；后续若修复实现，探针输出预期会变化，应使用新的run_id保存新证据。
