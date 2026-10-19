# 第三批冻结证据归档报告

任务：RECOVERY-EVIDENCE-ARCHIVE-FOLLOWUP-3-20261016；状态：awaiting_review。仅归档，不新编Ship评审，不签accepted。
上海开始：2026-10-16T02:43:17+08:00；结束：2026-10-16T02:46:53+08:00。

两个包共199个canonical文件、654617字节均按原bytes新建；199/199复制后及最终source/destination大小和SHA256一致，完整manifest本体匹配指定期望。0重复、0复用、0覆盖、0删除、0字节normalize、0归档/仪器失败。

| 包 | canonical报告 | 实际canonical run | 清单项 | 本体 | 单列补充 | 归档文件 |
|---|---|---|---:|---:|---:|---:|
| R05 | reports/reviews/recovery/G-B-R05-generation-predispatch-timeout-review-1.md | reports/runs/recovery_r05_generation_predispatch_timeout_review_1_20261016/ | 121 | 1 | 9 | 131 |
| R11 | reports/reviews/recovery/G-D-R11-version-ranges-review-1-recheck.md | reports/runs/recovery_r11_version_ranges_review1_fix1_20261016/ | 67 | 1 | 0 | 68 |

R05实际run名经rg确认，review与1之间有下划线；未归档同根作者fix包或其他未封存包。两manifest均为artifacts数组path/bytes/sha256。R05完整本体SHA256 6b4a9062c1aeb9fb042b58e8ead1b30c4c63798a2b5dbb79361cdd3b33b260f0；R11完整本体SHA256 4d0344b9474b6017bb06a3f1d11edc90f19c78a67de180b1c083c86b06aa0f1d。源原体、源复制后、目标本体三列均一致，没有混用filelist指纹。

R05作者code 47c47bc2b5d537166ee47a01c2ab14c035466e3d、材料 df0faafb64327be190803089f0058f9b5dc2427b；manifest中的组合实验tree b036c1b800c60405e97a7346ee6d327b00e3754a是原实验证据。R11原fix source 65838b42c0dcff863036968e39a1404aa323b3c9、最终code 71e724131daf4d03372392d58cd17c764c3e2e40、材料 8f5fe818774349b41b0b5aceb45d69ba81410678分别记录。两个review报告/run在源树未跟踪，archive_review_commit均null；不把代码/材料HEAD或实验tree冒称review提交。

作者Git blob核验依据仅按原report分列：R05原报告134–137行记录49项raw/Git blob/期望size与SHA一致，来源源码LF/checkout CRLF另外记录；R11原报告54行记录两作者manifest与固定8f blob核验0 mismatch及helper/report EOL差异。本轮不重审产品代码，不重新执行作者核验或测试。

root明确批准R05如下原封存metadata supplement，均逐source/target原bytes size/SHA核验并单列，不塞回原manifest：artifact_manifest.sha256；seal.command.json、seal.stderr.log、seal.stdout.log；seal_verify.command.json、seal_verify.py、seal_verify.request.json、seal_verify.stderr.log、seal_verify.stdout.log。摘要sidecar为89字节/SHA da1b7ffe0c01c2bc2f929479147e3aa282294cf2e64fe25dfe2d0d41550d25d3，严格绑定artifact_manifest.json及6b4a9062本体。8个metadata的逐hash见收据。

原CRLF事实共32件：R05 r09_original_red.xml为5945字节、29个CRLF、SHA f64e339dfeb1fef0fa090dfad4915c92f8176d3598173d0c43fc9e87eb780d8e；R11 31件包括原manifest。每件source/target CRLF计数与原byte hash一致，不normalize。这是源材料原事实，没有EOL漂移或内容不符。精确CRLF文件名/计数/hash全部列于新收据。

未归档：R05 9个mypy/ruff缓存文件及未冻结combo_private_index；R11一个__pycache__。仅枚举其路径，未把缓存/临时索引列为封存证据。前批4份收据/报告与7份manifest共11个保护快照原bytes不变；根.gitattributes前后26913字节/SHA d8035c60bbef1ee89d19d7831588a612ff635fbae8396cdbb9d79b7fb8ca27db一致，未编辑。

真实执行：只读rg/Git身份/status exit0；Node lstat/readFile、SHA256、fs.open(wx)/writeFile、逐文件source/target最终核验及CRLF数量核对。逐祖先拒绝链接/重解析链接、绝对路径、遍历、秘密/holdout及越限定目录。无测试/外网/付费/产品服务浏览器进程启动或已有进程探测，未运行封存脚本，未做秘密内容扫描。unit/contract/integration/security/frontend/e2e/live/manual均not_run。

共享观察HEAD cc1b1d302e22048f567475b7084bcd5490761ed2，分支codex/full-delivery-recovery。既有用户、业务、progress及报告修改原样保护；无Git写操作、push、root属性或原manifest修改。目录差别与单列补充是root明确授权的材料归档处理，无产品合同变化。
评分项证据仅E1/R1材料可追溯和原字节/红历史保全，不新增分数、性能、准确率或分母。下一步由root按精确清单复核并做窄作用Git集成，保留原review限定范围及整卡/live缺口。

收据：archive_followup_3_receipt.json；367373字节；SHA256 a45335a6e5da9447fc642d3382c757cc3a782dd6c64d8c6b99f7b136ce0ce21f。

精确清单：archive_followup_3_filelist.tsv；199行文件项；36642字节；SHA256 dd133843f5120dcfa489f82bace421464fd45de14cac3f399461d19e77beebd1。
