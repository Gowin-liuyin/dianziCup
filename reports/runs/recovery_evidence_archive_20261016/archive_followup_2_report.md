# 第二批冻结证据归档报告

任务：RECOVERY-EVIDENCE-ARCHIVE-FOLLOWUP-2-20261016；状态：awaiting_review。仅完成归档核验，不新编Ship结论，不登记accepted。
上海开始：2026-10-16T01:51:40+08:00；结束：2026-10-16T01:55:03+08:00。

两个包139个canonical文件、626415字节按原bytes新建；0复用、0覆盖、0删除、0字节normalize。复制后及最终source/destination全部139/139大小、SHA256匹配，归档失败0、仪器失败0。

| 包 | 清单项 | 加manifest本体 | 单列补充 | 归档文件 | 原/源后/目标manifest本体SHA256 |
|---|---:|---:|---:|---:|---|
| R06失败留证复核 | 59 | 60 | 1 staged-byte侧录 | 61 | 451c07a17037e2d950bc09f85b1aa83c54bde19d22e6e1af71079b925ed76720 |
| R07模型字段复核 | 77 | 78 | 0 | 78 | 09343f91e797bfef674b317a61e3ba427c71b4ab69674c4db9d2c354eddc8f21 |

改动范围仅下列新canonical报告、对应run内封存文件和自有followup收据/报告：
- reports/reviews/recovery/G-C-R06-failed-response-review-1-recheck.md；reports/runs/recovery_r06_failed_response_review_1_recheck_20261016/。
- reports/reviews/recovery/G-C-R07-model-fields-review-1-recheck.md；reports/runs/recovery_r07_model_fields_review_1_recheck_20261016/。
- reports/runs/recovery_evidence_archive_20261016/archive_followup_2_receipt.json 与 archive_followup_2_report.md。

R06 manifest为artifacts对象键/size_bytes；R07为artifacts数组path/bytes。R07原path使用Windows反斜杠，在拒绝绝对路径、空段、点/父段、盘符后只映射路径分隔符；没有重写原manifest或任何文件bytes。逐祖先lstat验证限定路径及普通文件，拒绝链接/重解析链接、秘密与holdout路径；fs.open(wx)确保只新建。

R06作者修复code e1bae9db650df7946417cf42ec3817484514483a、作者完整材料 b7817239022caed52ba6b8912b2d827c58a60181，与冻结review提交63523d0cd3c8e3207229871c7c1581c5789f722a分列。此固定review树61/61 Git object ID与源raw Git blob SHA1一致。59清单项加manifest本体为60；staged_bytes_audit.json为codeCommit-source补充，不塞回原manifest：20092字节/SHA256 63903fe758146263d0954c130ba77e215131d2ab8108a6d249897f2e3a7da4fc。
R07作者code 696b1d88045ee862db1af3aaf569574ad361feaf、材料 ef24758bd8e9e3e1e8e24760d330a9ffe62af341分列。review材料在源worktree未跟踪，archive_review_commit=null；不把源HEAD写成review提交。

作者Git blob核验依据只引用原报告并分列于收据：R06原报告51–53行记录旧87/new33原bytes与固定blob一致及checkout换行差异；R07原报告39、59–61行记录新103/103精确及旧73件raw/LF差异。作者manifest本体R06 cf585ab7063ffda419532951e903259d6bb1a2fca579b41edd0bda0e108dd1d4、R07 1d57ce725de521581cd3798ead71f47d17975430ab42747d2f1afce9606e5943不是上表review manifest本体。此次不重审产品代码或复跑作者测试。

前批archive_receipt.json/archive_report.md及五份manifest共7个保护快照前后字节一致。根.gitattributes未编辑，前后13675字节/SHA256 12a3f0625c04b203d572bc28d390ef5fa3414047390281a00cdbf960ecaff1f1一致。本批manifest未列run内属性，没有新增属性文件。R06一个/R07三个未列__pycache__均未归档。

真实执行：Node fs.lstat/readFile/crypto SHA256与Git blob SHA1/fs.open(wx)/writeFile逐文件核验；只读Git身份/status/固定ls-tree exit0。0业务测试/网络/模型/测绘/付费/产品服务浏览器进程启动/已有进程探测，0秘密文件与holdout读取。unit/contract/integration/security/frontend/e2e/live/manual均not_run；未执行秘密内容扫描。完整逐canonical文件预期、source、target大小及SHA见新收据。

共享HEAD真实为595a13197a2c1bba6ad79957f8fde3750ba2a6c6，实际分支codex/full-delivery-recovery；已有用户/progress/报告修改原样保留。无Git写操作、业务/progress/根属性修改、push或accepted登记。无产品合同偏差；范围和staged-byte补充依据root本批授权。
评分项证据仅E1/R1字节完整性、可追溯和前批历史保全，不新增评分/准确率/性能/分母。下一步由root复核收据并统一窄范围Git集成，保留原review限定范围与整卡/live缺口。

收据244789字节，SHA256 5de57db2d96be9a3b0a29167b6f3cb07d3983abe98aeaa6570820d372edd4519。
