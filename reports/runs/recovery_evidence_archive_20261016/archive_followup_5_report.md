# 第五批冻结证据归档报告

任务：RECOVERY-EVIDENCE-ARCHIVE-FOLLOWUP-5-20261016；状态：awaiting_review。只封存归档，不新编Ship，不写accepted或阶段放行。

上海开始：2026-10-16T03:50:04+08:00；收据截止：2026-10-16T03:59:27+08:00。首先核对第四批收据d5da1062afe9827f3aae87097ae95b0fe77f3cca6dbecf50148d986a4ee143ec及报告1c8d07e0331d0febe85d9f4493c771d7b016c2ea8ec946e69c22debce104003e，仍为原SHA。

本批新建512文件，核验84个既有canonical文件，共596个批准范围文件/13989370字节均最终大小、SHA匹配；0覆盖、0删除、0字节normalize、0归档失败。R20两个原清单缓存成员policy_excluded/not_verified，不纳入596核验数。

| 包 | 原清单成员 | 实际成员核验 | 本体 | identity补充 | 新复制 | 既有核验 |
|---|---:|---:|---:|---:|---:|---:|
| R06 observer复核 | 248 | 248 | 1 | 1 checksum | 250 | 0 |
| R07 single model维度 | 126 | 126 | 1 | 1 checksum | 128 | 0 |
| R20 8a CPU诊断 | 134 | 132 | 1 | 1 identity | 134 | 0 |
| R10 PG evidence graph | 83 | 83 canonical-only | 1 | 0 | 0 | 84 |

前三包root预先给定的manifest本体SHA分别为：da7d1090392741d42d56ab49435ad53865f70dc197d07da9c728cc9c33313f31；28da9eb51fb412477224ca21947b2774d322dbdcb51eb0dd70a3e13c87d02741；d561bcb845a5f3e9d1436846e6ff21f1388e21df9236ead06872c26cab689a1d。源原/源后/目标整本体均匹配，不混filelist指纹。实际manifest名依次artifact_manifest.json、review_manifest.json、artifact_manifest.json。

R10 expected wholeSHA未提供，保持null；此次canonical reviewer_artifact_manifest.json观测本体90d05a36b159830e8a19fba3f88d9d5647a64238066e7dbd1bf00952ca0ab5dd前后稳定。报告raw SHA0f662aa4c2b21e74749668a0eeb740b25a7af70e2cbe3072eea67bb7bfd6dbe7严格匹配root给值。不能把观察值冒称事先冻结expected。

R10指定外部D:/wt/r10-graph-review1的report/run实际不存在；其HEAD b0b7a5b856cc38862f64c01565309564d67c34c0的限定Git树也无报告/run。root明确确认原review作者canonical交付并授权只核现有canonical，自身83成员+本体84原raw全匹配；0复制，不冒称双源或Gitcommit封存。原报告提及作者raw/blob37项的依据只作为原report引用，此次外部source/raw/Git blob核验未执行。没有缺失的canonical manifest成员或外部exploratory条目需要补造。

R20 manifest134原项含__pycache__/diagnose.cpython-312.pyc与observe_processes.cpython-312.pyc，和本批排缓存范围冲突。root明确裁决两项policy_excluded/not_verified，不读不复制；声明大小7827/13149及原声明SHA只记录，actual size/hash=null。原manifest完整保留，未删除这两行，不伪称134/134成员通过。实际132成员含独立报告，再加manifest和manifest_identity为134个归档文件。

封存identity单列：R06 artifact_manifest.sha25690字节/SHA ef5ac1fa337991e2b6110636317fd21b52c8e5c9bb74fd02e54f9dfc35ca9349；R07 review_manifest.sha25688字节/SHA a47b4aaa1cbcc27aa9bea2af05b7ca28145185077328e798f622b8ad01f1c6ec；R20 manifest_identity.json303字节/SHA 369696ba97ecbce6b9caf4b84cc84c8939a2fa278b20e6f72aa1a00e2360bedf。都严格绑定本体，未塞回原manifest。

敏感限定扫描只在批准596文件内存中进行：590文本/非binary文件查四类ASCII模式，6已知binary仅hash。private key header/provider token/literal secret assignment均0；R10八个原日志/XML共52个DSN形状，52个密码均为掩码，0未掩码/未分类；匹配值不输出、不写入新材料。前次口述54已按工具逐项结果更正52。未读provider、DPAPI、秘密配置或已排缓存；模式扫描不等于完整秘密审计。

R06身份：code1c4cce9770bfa29d08728a0131f7fc7fe714f9bc / material521b740612b2d0465f2be50cd58b5028f1c820b7 / supplement与观察HEAD b08824f738ca185776916ae02689d8507f956c5c；R07 code d8a3189bb7bc1cfde24825f5478920e37eac9556 / material b05e63462f1b513eabc183d0a8d42b03196696d2；R20诊断固定产品8a1b04d48346d8550f0326a77f003246a0ebbab5；R10原manifest声明code b0b7a5b856cc38862f64c01565309564d67c34c0/material16803ce6be9ad6adb6d89f46c594cfa420190c24。四包archive_review_commit均null，不把source/material/supplement HEAD冒称review提交。

原错误/红记录及限定结论保持：R06 Ship仅离线observer、新live秒0，不是新6小时证明；R07 single Ship未证明worker/runtime/PG/API整链；R20 Fix1和2 first、不签Ship、产品CPU红未修；R10 needs_changes和原独立PG红保留。原报告及日志的source/destination原byte SHA未改，TSV记录raw_0d0a_count为原字节序列，binary序列不冒称文本EOL；所有计数前后相同。

前四批26个收据/报告/清单/manifest保护文件前后不变，且均匹配原冻结SHA。根.gitattributes前后27526字节/SHA519cdc875fa739a7c1c534d89e4b2d7b11f6ff23bc9860e523aec05dfca13792一致，未编辑。runtime venv/cache目录只枚举到边界，不读不复制其内容；原CBM source副本仅按明确manifest成员复制，不递归复制作者backend/源树。

真实执行：初次rg批命令exit1因最后R10无匹配；后续独立源identity和Git树检查exit0确认缺失。Node lstat/安全路径映射、readFile/SHA256、fs.open(wx)及最终raw核验；R10仅读现存文件。0业务测试/网络/模型/测绘/付费/产品服务浏览器进程启动或探测/源修改/Git写操作/push/progress修改。业务八层verification均not_run；缓存两项未核验和R10外部源缺失明确保留。

共享观察HEAD8a1b04d48346d8550f0326a77f003246a0ebbab5、分支codex/full-delivery-recovery；已有用户和状态修改原样保护。评分项仅E1/R1可追溯/原红保全，不新增评分、性能、准确率或分母。下一步root按动作TSV应用窄attributes和Git集成，保留两缓存未核验、R10 canonical-only边界及各片live缺口。

收据archive_followup_5_receipt.json；1091746字节；SHA256 f293b9597c45c6b00e028219c531d3dd2a6ec6f2d5caa9c318ce3822db3ecab5。

精确动作清单archive_followup_5_filelist.tsv；596行；138832字节；SHA256 fb752f88a5c87dc6ddce7e2ebfa07c49824f34ef041e7b77c773ca21bcdc1fa0。两policy_excluded缓存另列收据，TSV不列为已核验文件。
