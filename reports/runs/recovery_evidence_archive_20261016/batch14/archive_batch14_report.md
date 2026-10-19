# 冻结证据归档第14批

任务：recovery_evidence_archive_batch14。状态 awaiting_review；本工作包归档实现 complete。未签 accepted，未评审业务实现或阶段。

实际 A 时间：2026-10-16T09:38:12.880134+08:00 至 2026-10-16T09:38:23.271824+08:00。
实际 B 成功时间：2026-10-16T09:38:57.178595+08:00 至 2026-10-16T09:39:01.620147+08:00。
本报告写入时间：2026-10-16T09:40:27.234554+08:00，Asia/Shanghai。

| 优先级/包 | 原 manifest 成员 | canonical 文件 | 新复制 | 原字节数 | 覆盖 |
|---|---:|---:|---:|---:|---:|
| A R17 作者 | 136 | 138 | 138 | 5,405,391 | 0 |
| A R17 非作者复核 | 246 | 248 | 248 | 11,723,627 | 0 |
| B R10 作者 | 55 | 58 | 58 | 298,403 | 0 |
| B R10 非作者复核 | 65 | 67 | 67 | 460,286 | 0 |
| 合计 | 502 | 511 | 511 | 17,887,707 | 0 |

A 两包各增加原 manifest 与 SHA sidecar；B 作者另有独立冻结报告，加原 manifest 和声明 ZIP，共58；B reviewer 报告已在65成员内，加 manifest/ZIP共67。没有修改任何原 manifest。

精确写集为 priority_A_filelist.tsv 的386行和 priority_B_filelist.tsv 的125行，以及本 batch14 目录内归档器、收据、失败记录和报告。canonical 原先存在0文件，hashsame复用0，冲突0。511个冻结源文件均在复制前后核 SHA/长度，canonical逐项一致；原文件没有写入。此断言分别截止各优先级收据结束时间，A释放后没有复扫A。

原 R17 reviewer ZIP e1d0e62ed01598f79601348a2e6323dc211103ea261962af271e35d1c5a4091d 的245成员，以及R10作者ZIP66804358f1a1db15ab6f7c65393c7ba9cb6a5ab93da5e3009ea079ac426d6216的55成员、reviewer ZIP35a34d967dbfe6f9d17c2b61e85c71a97797125ff62ae1e45e5ad867a658a273的65成员，均逐项对照原 manifest raw SHA/长度和源bytes；共365成员，0不匹配。ZIP原字节直接复制，无重新封包。R17作者source_change.diff.gz亦直接复制，解压SHA单列，不执行其内容。

作者196个冻结文件另以只读Git对象核验，并将源raw、Git blob、fresh reviewer checkout分别列入收据。R17作者138个Git blob均与源raw相同，但作者报告fresh checkout有120个CRLF、12830bytes/SHA5e1465dfea3f6ec4b796e70854d19614020bfee7281f39f54e06155121ceb390；LF blob与真正源raw为12710bytes/SHA6875f503aee43c40a4df9c00924f92e8f34a30add47dcf805fea47d6002e55ac。R10作者58文件中35个raw与Git LF不同，包含原CRLF manifest；其fresh checkout另有20文件与作者raw不同，均通过独立LF blob对应证明。canonical采用作者真正raw；未把fresh checkout或clean blob称为raw。crlf_count仅统计CRLF字节序列，二进制包的偶然序列不解释为文本换行。

主控明确授权精确复制原run-local属性：reports/runs/recovery_r17_sbom_workbench_fix1_20261016/.gitattributes，323bytes，SHA3f05646a4c1815dc6c7293c46ce7905a7ac83f8a45623326bd49e9de85fae2a6，0规则新增/修改。主仓.gitattributes、用户frontend/tsconfig.tsbuildinfo、batch13 priority receipt均在各优先级操作前后hash相同。本工作包没有Git index/stage/commit/push、progress、业务模块或生产状态写入。

实际命令与验证：

- `python -B reports/runs/recovery_evidence_archive_20261016/batch14/archive_batch14.py A`：exit0，386文件原manifest/raw/canonical及245 ZIP成员核验通过。
- 同入口 `B` 首轮：exit1，归档器错误地要求独立作者报告也在55成员manifest中，发生在copy阶段之前；0 canonical写入。priority_B_attempt1_failure.json保留原失败和修正，未修改源报告或清单。
- 同入口 `B` 修正后：exit0，125文件原manifest/raw/canonical及120 ZIP成员核验通过。
- 自有归档器AST parse与两份收据SHA sidecar核对：exit0。
- 读文档的一次命令因两个未带日期的路径不存在exit1；rg定位实际11/12日期文件后读取对应范围，无文件写入。

本轮unit/integration/live/manual均not_run；没有把归档检查计为业务测试。新API/进程/扫描、费用、秘密/.env/holdout/DPAPI读取、源seal/review脚本执行及递归spawn均0。没有复查batch13继承的历史6k清单，旧证据未重拷。A收据完成后已立即通知主控可以集成；B归档结果也已通知。

评分证据仅提升冻结材料可追溯性，不新增功能、准确率、性能或完整阶段验收。原R17与R10限定Ship的业务范围和live/manual缺口保留。下一步由主控依两份精确filelist执行集成、stage及独立验收；本归档工作包停止。
