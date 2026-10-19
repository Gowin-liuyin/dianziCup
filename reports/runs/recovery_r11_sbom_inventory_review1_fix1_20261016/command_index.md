# 本复核实际命令索引

所有时间为Asia/Shanghai；argv精确内容见commands.jsonl。backend表示独立WT/backend，WT表示独立WT根。

|编号|命令标识|cwd|上海起止|exit|用例/检查数|raw路径|
|---:|---|---|---|---:|---|---|
|1|cbm_src_index|WT|2026-10-16T07:10:28+08:00 → 2026-10-16T07:10:34+08:00|0|非功能用例命令|cbm_src_index.log|
|2|cbm_src_get_graph_schema|WT|2026-10-16T07:10:34+08:00 → 2026-10-16T07:10:38+08:00|0|非功能用例命令|cbm_src_get_graph_schema.log|
|3|cbm_src_get_architecture|WT|2026-10-16T07:10:38+08:00 → 2026-10-16T07:10:41+08:00|0|非功能用例命令|cbm_src_get_architecture.log|
|4|cbm_assets_index|WT|2026-10-16T07:10:41+08:00 → 2026-10-16T07:10:46+08:00|0|非功能用例命令|cbm_assets_index.log|
|5|cbm_assets_get_graph_schema|WT|2026-10-16T07:10:46+08:00 → 2026-10-16T07:10:49+08:00|0|非功能用例命令|cbm_assets_get_graph_schema.log|
|6|cbm_assets_get_architecture|WT|2026-10-16T07:10:49+08:00 → 2026-10-16T07:10:52+08:00|0|非功能用例命令|cbm_assets_get_architecture.log|
|7|pg_sbom|backend|2026-10-16T07:10:31+08:00 → 2026-10-16T07:10:53+08:00|0|50例/50过/0败/0错/0skip|pg_sbom.log|
|8|cbm_trace_get_snapshot|WT|2026-10-16T07:10:52+08:00 → 2026-10-16T07:10:55+08:00|0|非功能用例命令|cbm_trace_get_snapshot.log|
|9|cbm_trace_read_asset|WT|2026-10-16T07:10:55+08:00 → 2026-10-16T07:10:56+08:00|0|非功能用例命令|cbm_trace_read_asset.log|
|10|cbm_trace_list_assets|WT|2026-10-16T07:10:56+08:00 → 2026-10-16T07:10:57+08:00|0|非功能用例命令|cbm_trace_list_assets.log|
|11|cbm_trace_list_snapshots|WT|2026-10-16T07:10:57+08:00 → 2026-10-16T07:11:01+08:00|0|非功能用例命令|cbm_trace_list_snapshots.log|
|12|pg_legacy|backend|2026-10-16T07:10:55+08:00 → 2026-10-16T07:11:01+08:00|0|46例/46过/0败/0错/0skip|pg_legacy.log|
|13|cbm_trace_get_snapshot_sbom|WT|2026-10-16T07:11:01+08:00 → 2026-10-16T07:11:02+08:00|0|非功能用例命令|cbm_trace_get_snapshot_sbom.log|
|14|cbm_trace_import_manifest|WT|2026-10-16T07:11:02+08:00 → 2026-10-16T07:11:05+08:00|0|非功能用例命令|cbm_trace_import_manifest.log|
|15|cbm_trace_safe_sbom_sidecar|WT|2026-10-16T07:11:05+08:00 → 2026-10-16T07:11:09+08:00|0|非功能用例命令|cbm_trace_safe_sbom_sidecar.log|
|16|cbm_trace_safe_sbom_snapshot|WT|2026-10-16T07:11:09+08:00 → 2026-10-16T07:11:12+08:00|0|非功能用例命令|cbm_trace_safe_sbom_snapshot.log|
|17|pure|backend|2026-10-16T07:09:46+08:00 → 2026-10-16T07:11:56+08:00|0|369例/369过/0败/0错/0skip|pure.log|
|18|pg_new|backend|2026-10-16T07:12:06+08:00 → 2026-10-16T07:12:14+08:00|1|11例/7过/4败/0错/0skip|pg_new.log|
|19|pg_corrected|backend|2026-10-16T07:13:09+08:00 → 2026-10-16T07:13:11+08:00|0|1例/1过/0败/0错/0skip|pg_corrected.log|
|20|mypy|backend|2026-10-16T07:13:12+08:00 → 2026-10-16T07:13:30+08:00|0|非功能用例命令|mypy.log|
|21|changed_ruff|backend|2026-10-16T07:13:30+08:00 → 2026-10-16T07:13:30+08:00|0|非功能用例命令|changed_ruff.log|
|22|changed_format|backend|2026-10-16T07:13:30+08:00 → 2026-10-16T07:13:30+08:00|0|非功能用例命令|changed_format.log|
|23|pg_nullmeta|backend|2026-10-16T07:14:22+08:00 → 2026-10-16T07:14:24+08:00|1|2例/0过/2败/0错/0skip|pg_nullmeta.log|
|24|pg_old|backend|2026-10-16T07:12:06+08:00 → 2026-10-16T07:15:39+08:00|0|24例/24过/0败/0错/0skip|pg_old.log|
|25|review_materials_import_fix|backend|2026-10-16T07:17:09+08:00 → 2026-10-16T07:17:09+08:00|0|非功能用例命令|review_materials_import_fix.log|
|26|review_materials_format|backend|2026-10-16T07:17:09+08:00 → 2026-10-16T07:17:10+08:00|0|非功能用例命令|review_materials_format.log|
|27|review_materials_ruff|backend|2026-10-16T07:17:10+08:00 → 2026-10-16T07:17:10+08:00|1|非功能用例命令|review_materials_ruff.log|
|28|review_materials_ruff_final|backend|2026-10-16T07:17:31+08:00 → 2026-10-16T07:17:31+08:00|0|非功能用例命令|review_materials_ruff_final.log|
|29|source_audit|backend|2026-10-16T07:18:17+08:00 → 2026-10-16T07:18:21+08:00|0|非功能用例命令|source_audit.log|
|30|cbm_final_src_index|WT|2026-10-16T07:31:18+08:00 → 2026-10-16T07:31:24+08:00|0|非功能用例命令|cbm_final_src_index.log|
|31|pg_newfinal|backend|2026-10-16T07:31:20+08:00 → 2026-10-16T07:31:26+08:00|0|13例/13过/0败/0错/0skip|pg_newfinal.log|
|32|cbm_final_src_get_graph_schema|WT|2026-10-16T07:31:24+08:00 → 2026-10-16T07:31:28+08:00|0|非功能用例命令|cbm_final_src_get_graph_schema.log|
|33|cbm_final_src_get_architecture|WT|2026-10-16T07:31:28+08:00 → 2026-10-16T07:31:31+08:00|0|非功能用例命令|cbm_final_src_get_architecture.log|
|34|cbm_final_assets_index|WT|2026-10-16T07:31:31+08:00 → 2026-10-16T07:31:36+08:00|0|非功能用例命令|cbm_final_assets_index.log|
|35|cbm_final_assets_get_graph_schema|WT|2026-10-16T07:31:36+08:00 → 2026-10-16T07:31:40+08:00|0|非功能用例命令|cbm_final_assets_get_graph_schema.log|
|36|cbm_final_assets_get_architecture|WT|2026-10-16T07:31:40+08:00 → 2026-10-16T07:31:43+08:00|0|非功能用例命令|cbm_final_assets_get_architecture.log|
|37|cbm_final_trace_get_snapshot|WT|2026-10-16T07:31:43+08:00 → 2026-10-16T07:31:46+08:00|0|非功能用例命令|cbm_final_trace_get_snapshot.log|
|38|cbm_final_trace_read_asset|WT|2026-10-16T07:31:46+08:00 → 2026-10-16T07:31:50+08:00|0|非功能用例命令|cbm_final_trace_read_asset.log|
|39|cbm_final_trace_list_assets|WT|2026-10-16T07:31:50+08:00 → 2026-10-16T07:31:53+08:00|0|非功能用例命令|cbm_final_trace_list_assets.log|
|40|pg_legacyfinal|backend|2026-10-16T07:31:49+08:00 → 2026-10-16T07:31:56+08:00|0|46例/46过/0败/0错/0skip|pg_legacyfinal.log|
|41|cbm_final_trace_list_snapshots|WT|2026-10-16T07:31:53+08:00 → 2026-10-16T07:31:56+08:00|0|非功能用例命令|cbm_final_trace_list_snapshots.log|
|42|cbm_final_trace_get_snapshot_sbom|WT|2026-10-16T07:31:56+08:00 → 2026-10-16T07:32:00+08:00|0|非功能用例命令|cbm_final_trace_get_snapshot_sbom.log|
|43|cbm_final_trace_import_manifest|WT|2026-10-16T07:32:00+08:00 → 2026-10-16T07:32:03+08:00|0|非功能用例命令|cbm_final_trace_import_manifest.log|
|44|cbm_final_trace_safe_sbom_sidecar|WT|2026-10-16T07:32:03+08:00 → 2026-10-16T07:32:06+08:00|0|非功能用例命令|cbm_final_trace_safe_sbom_sidecar.log|
|45|cbm_final_trace_safe_sbom_snapshot|WT|2026-10-16T07:32:06+08:00 → 2026-10-16T07:32:10+08:00|0|非功能用例命令|cbm_final_trace_safe_sbom_snapshot.log|
|46|pg_sbomfinal|backend|2026-10-16T07:31:49+08:00 → 2026-10-16T07:32:11+08:00|0|59例/59过/0败/0错/0skip|pg_sbomfinal.log|
|47|pg_edgesfinal|backend|2026-10-16T07:32:51+08:00 → 2026-10-16T07:32:55+08:00|1|9例/8过/1败/0错/0skip|pg_edgesfinal.log|
|48|pure_final|backend|2026-10-16T07:31:18+08:00 → 2026-10-16T07:33:05+08:00|0|396例/396过/0败/0错/0skip|pure_final.log|
|49|pg_edgescorrected|backend|2026-10-16T07:33:29+08:00 → 2026-10-16T07:33:32+08:00|0|1例/1过/0败/0错/0skip|pg_edgescorrected.log|
|50|mypy_final|backend|2026-10-16T07:34:09+08:00 → 2026-10-16T07:34:10+08:00|0|非功能用例命令|mypy_final.log|
|51|ruff_final|backend|2026-10-16T07:34:10+08:00 → 2026-10-16T07:34:11+08:00|0|非功能用例命令|ruff_final.log|
|52|format_final|backend|2026-10-16T07:34:11+08:00 → 2026-10-16T07:34:11+08:00|0|非功能用例命令|format_final.log|
|53|callers_final_rg|WT|2026-10-16T07:34:11+08:00 → 2026-10-16T07:34:11+08:00|0|非功能用例命令|callers_final_rg.log|
|54|pg_oldfinal|backend|2026-10-16T07:31:20+08:00 → 2026-10-16T07:34:11+08:00|0|24例/24过/0败/0错/0skip|pg_oldfinal.log|
|55|cbm_qualified_final_get_snapshot|WT|2026-10-16T07:34:11+08:00 → 2026-10-16T07:34:14+08:00|0|非功能用例命令|cbm_qualified_final_get_snapshot.log|
|56|cbm_qualified_final_read_asset|WT|2026-10-16T07:34:14+08:00 → 2026-10-16T07:34:17+08:00|0|非功能用例命令|cbm_qualified_final_read_asset.log|
|57|cbm_qualified_final_list_assets|WT|2026-10-16T07:34:17+08:00 → 2026-10-16T07:34:20+08:00|0|非功能用例命令|cbm_qualified_final_list_assets.log|
|58|cbm_qualified_final_list_snapshots|WT|2026-10-16T07:34:20+08:00 → 2026-10-16T07:34:23+08:00|0|非功能用例命令|cbm_qualified_final_list_snapshots.log|
|59|cbm_qualified_final_get_snapshot_sbom|WT|2026-10-16T07:34:23+08:00 → 2026-10-16T07:34:26+08:00|0|非功能用例命令|cbm_qualified_final_get_snapshot_sbom.log|
|60|cbm_qualified_final_import_manifest|WT|2026-10-16T07:34:26+08:00 → 2026-10-16T07:34:29+08:00|0|非功能用例命令|cbm_qualified_final_import_manifest.log|
|61|cbm_qualified_final_safe_sbom_sidecar|WT|2026-10-16T07:34:29+08:00 → 2026-10-16T07:34:32+08:00|0|非功能用例命令|cbm_qualified_final_safe_sbom_sidecar.log|
|62|cbm_qualified_final_safe_sbom_snapshot|WT|2026-10-16T07:34:32+08:00 → 2026-10-16T07:34:35+08:00|0|非功能用例命令|cbm_qualified_final_safe_sbom_snapshot.log|
|63|audit_final|WT|2026-10-16T07:35:03+08:00 → 2026-10-16T07:35:07+08:00|0|非功能用例命令|audit_final.log|

未进入command()的准备与读取不补造收据：uv_sync_receipt.json有独立真实起止/exit0；prepare_final.py的最终校验start/end见final_material_verification.json，工具exit0、135清单项/214原test blobs。legacyfinal首次数据库标识65字符被PG截短，前置guard异常exit1、0测试执行，完整栈见legacyfinal_runner_error.log，没有磁盘完整起止收据；仅缩短自有mode并用fresh DB复跑。git FF与源码/doc读取为会话工具记录，未虚构原stdout日志。