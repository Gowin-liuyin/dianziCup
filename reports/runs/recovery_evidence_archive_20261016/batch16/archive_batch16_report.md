# 第16批有限冻结证据归档

任务 recovery_evidence_archive_batch16，状态 awaiting_review，归档实现 complete。仅报告与raw归档；不签整T、R卡、阶段或accepted。
报告生成时间：2026-10-16T11:55:16.331090+08:00，Asia/Shanghai。

| 包 | canonical新文件 | 原字节数 | 覆盖 | 最终错误 |
|---|---:|---:|---:|---:|
| A R07 audit | 216 | 5,064,106 | 0 | 0 |
| B R12 context | 192 | 839,986 | 0 | 0 |
| C production0023–26与文档补核 | 321 | 1,186,195 | 0 | 0 |
| D R18 key fix2 | 147 | 594,647 | 0 | 0 |
| E MCP预算 | 147 | 404,276 | 0 | 0 |
| F R17真实浏览器与freshmain | 575 | 73,549,692 | 0 | 0 |
| 合计 | 1,598 | 81,638,902 | 0 | 0 |

精确改动文件为六份最终group filelist TSV（F使用group_F_recheck_filelist.tsv）的1598个不同canonical路径，以及本batch16目录文件。同字节skip0，真实canonical冲突0。全部源raw在复制前后hash/长度一致；canonical复制完成时逐一相同，不复扫已经分段释放的包。公共CR、progress、模型、源/配置/缓存文件均不拷贝；11个非reports业务/测试成员只读证明。run-local attrs仅复制原冻结清单列出的字节、0规则变更，主attrs未写。各收据独立保存操作前后主attrs/用户tsbuildinfo SHA。

报告canonical链接：

- A [作者](D:/dianzi/reports/tasks/R07-input-audit-fix1.md)；[非作者](D:/dianzi/reports/reviews/recovery/G-C-R07-input-audit-review-1-recheck.md)。
- B [作者](D:/dianzi/reports/tasks/R12-conversation-context-fix1.md)；[非作者](D:/dianzi/reports/reviews/recovery/G-D-R12-conversation-context-review-1-recheck.md)。
- C [作者](D:/dianzi/reports/tasks/R07-R12-R10-R18-forward-migrations.md)；[非作者](D:/dianzi/reports/reviews/recovery/G-D-recovery-forward-migrations-review-1.md)；[CR补核](D:/dianzi/reports/reviews/recovery/G-D-recovery-forward-migrations-review-1-cr-appendix.md)。
- D [作者](D:/dianzi/reports/tasks/R18-api-key-expiry-fix2.md)；[非作者](D:/dianzi/reports/reviews/recovery/G-E-R18-api-key-credential-review-1-recheck2.md)。
- E [作者](D:/dianzi/reports/tasks/R18-mcp-output-budget-fix1.md)；[非作者](D:/dianzi/reports/reviews/recovery/G-E-R18-mcp-output-budget-review-1-recheck.md)。
- F [作者terminal](D:/dianzi/reports/tasks/R17-integrated-sbom-browser.md)；[非作者](D:/dianzi/reports/reviews/recovery/G-E-R17-integrated-sbom-browser-review-1.md)；[freshmain](D:/dianzi/reports/reviews/recovery/G-E-R17-integrated-sbom-browser-review-1-fresh-main.md)。

实际清单与来源：A作者真实raw_manifest.json包含103 materials+2 changed_source，连manifest106输入；2源只读排除，canonical104，review111+manifest112。B作者104+manifest105，review86+manifest87。C作者171artifacts+manifest172，6 source排除；review141+manifest142；appendix5个run artifact+独立报告+manifest7，不修改现行CR。D作者85成员内3业务路径排除，canonical83；review63+manifest64。E作者76+manifest77，review69+manifest70。F作者使用最终固定Git tree内完整own run与terminal报告380，review170+manifest/tar/report173，fresh19+manifest/tar/report22。各缩写SHA仅作输入匹配前缀；收据保存真实完整manifest SHA，作者与已提交review实际Git blob独立核1214项，不把LF view称raw。未提交review与post材料字节明确标记，不从作者HEAD伪推review commit。

F材料历史分层：原active289、历史v2 282、review170、fresh19共760个tar成员分别匹配各自原manifest及archive SHA；26张actual_edge_7_stale最终PNG实际在380冻结作者文件中归档。完整material相关commit/tree/parents见F_material_lineage_proof.json，未只取最后receipt。原fixture82c402及其run attrs不在写集；只核root6be固定Git对象，不覆盖当前fixture。

原始失败与更正：metadata发现仪器首次遇到list-root manifest时AttributeError，exit1，发生在任何canonical写入前；随后兼容真实schema。F第一轮命令exit0但收据明确blocked/2 errors/0 copies，原因是归档器将历史v2 tar的seal.py/source_proof.json与active当前文件比较。没有原raw漂移。保留group_F_receipt.json与其blocked filelist；按两份各自原manifest实核active289/v2 282均0 mismatch，修正归档器后用新F_recheck收据，不覆盖旧记录。原作者历史红、资料whitespace、早期失败、pg_1 fixture复用限制均按原字节保留，不trim或修改计数。

实际命令：`python -B reports/runs/recovery_evidence_archive_20261016/batch16/archive_batch16.py A/B/C/D/E`逐包运行，均exit0/错误0；F首轮exit0/错误2/0复制；`... F --attempt recheck` exit0/错误0。收据SHA sidecar、脚本AST parse、原fixture固定blob证明exit0。每个包真实+08起止在其receipt，摘要索引逐项引用。

unit/integration/live/manual/full-repo测试均not_run；没有执行作者/reviewer/seal脚本，没有网络/付费请求、新进程业务或Git index/stage/commit/push/进度写入。没有全仓扫描或复核历史6k，也未重扫批14/15成员。

敏感边界：未加载.env/DPAPI/holdout或运行时秘密。该0计数只说明归档器访问边界，不等于原始材料通用安全扫描0；原作者/独立review显式扫描范围、合成fixture分类与sealed原件一起保留，未用空泛全0替换这些证明，也未打印明文值。本任务不新增产品性能、准确率或完整验收证据；评分意义仅为F2/E1/D1/X1材料追溯。六包均已分段通知主控，下一步只由主控集成/验收；本包停止。
