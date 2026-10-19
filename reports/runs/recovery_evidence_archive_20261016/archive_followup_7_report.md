第七批冻结独立审查材料归档报告。归档验证完成；未修改产品、Git、progress或accepted。

真实Asia/Shanghai时间：2026-10-16T05:03:48+08:00 → 2026-10-16T05:08:22+08:00。目标仅为D:/dianzi对应reports路径和本归档run，原bytes wx新建；0覆盖、0归一化、0重复。

四包共368件、3,192,545 B，368项source/canonical raw SHA256及size全部匹配，4个manifest本体再核匹配给定预期。R06为174成员+本体=175件；R17为75成员+本体+绑定checksum=77件；R11为66成员+本体+绑定seal receipt=68件；R08为47成员+本体=48件。原manifest不改。

| 包 | canonical manifest本体SHA256 | 报告观测SHA256 |
| --- | --- | --- |
| R06-bulk-review | e6e016ec9f6144feaf95141caf34489e7449e6114b206425c2f8a951402c41e8 | e4597009d1fc7e11468c2f37ad97605a3f6f402431ea2cd2bf7e97f96148b233 |
| R17-graph-recheck | 184e38e78839ebc53cac484d3681b5c59e68b54d4b2d2a948433fe6c58dc0b73 | b42b4e97640c8599ec97691bc47ba9e42750dbbf385282d514c75773feec2d9f |
| R11-inventory-review | 3c604d1e969c40d6ca37e207729ea1f7650ef61b2448f7baa87700b94c0413fb | 730fafd134f26cbedcc30a454700b8b7f3a1052fe2b12357515b6c29ed6bda92 |
| R08-persistence-recheck | f066d69eff865e71e4baa74147f6f361d2c0ef2989e5a6675bff9417742c6d27 | 8906a531923a1bad45b8996d9a02d3333ef6c46a0200e6bf5b3b40d6ed879502 |

R11报告root预期为null，观测730fafd134f26cbedcc30a454700b8b7f3a1052fe2b12357515b6c29ed6bda92与manifest成员一致；没有把观测改写为已提供预期。R11 seal_receipt.json原bytes306 B、SHA256=a969cc03e5995280b793408e9b4a9b4b7608c88ea85b9ce0baee7ef8f19bcdb0，绑定本体3c604d…/报告730f…/66成员，按原封存metadata授权补充，未塞回manifest。

精确逐项列表：archive_followup_7_filelist.tsv，368 rows、SHA256=c860bdfd97387a66e022c581b1c57442be8b9577f8f3ec6e75a3fb2709c2d34d；raw SHA、本体SHA与派生LF各列分开。R17共59个declared LF/crlf字段源核验通过，目标派生LF59/59匹配；其余Git blob字段作为原manifest或原报告身份依据。四包新review材料Git ls-tree均0行，review_commit全部null，实际source HEAD不是review提交；没有杜撰untracked材料Git LF或新产品code hash审查。

归档前后前六批共2,316项冻结canonical/自有收据报告清单逐raw核验无漂移：其中2,297份原canonical材料及19份此前自有收据/报告/清单。根HEAD read-only前后为136fbaef337036d95229aa4976c1ba49b2e6b04c，根 .gitattributes 前后29645 B、SHA256=5e34449531d262e56ef2edb57549e36dfea815e6036b2de4260f99fc4771c77a，未修改。R08 run-local .gitattributes为原已列8 B、SHA256=705fd4d6451a31d36b3df7de96f83f30ac976c9b4a6d1e51671d8e2f33e2d0da，仅按root原授权复制bytes。

原独立结论保真：R06 Ship仅批量保存服务/所列固定版本，真实分页、MinIO/API/Celery/browser、来源八类live、持续运行和≤6h未证；R17 Ship仅pointer修复切片，原Must1闭合，生产App/backend/真实整合/live等未证；R11 Ship仅资产PG/独立router切片，P3历史raw投影债务及覆盖门/未接线限制保留；R08 Ship仅PG repository/service/cache TTL切片，原Must1闭合，生产0019/Redis IO/API/worker/UI/live等未证。原red、instrument失败、分母与原not_run全部原bytes保留，本归档不新编评审结论、不验收整卡。

限定扫描352文本、16二进制仅hash，匹配0、未分类0；不输出secret值、不读vault/model/provider/DPAPI。有限ASCII模式不称全秘密认证。源数据外部大正文只有原声明hash/大小，不读取/复制。R17六产品引用只metadata不复制；原original_probe等已列材料原bytes保存；2个实际自引用seal log明确not_copied。R11 tmp/cbm-src、pycache及R08 pycache均不读/不复制；不复制作者.git、cache/venv/node_modules、holdout或业务source。

raw 0D0A存在于187件、共13855序列，源目标计数相同；包括binary可能的0D0A，不猜编码、无normalize。

真实归档操作：read-only rg定位（exit0）、Git rev-parse HEAD/ls-tree固定身份（均exit0）、Node标准fs/crypto逐bytes size/hash/path边界+lstat链接拒绝、wx新建与copy后复核。初次rg文件名输出含R11 tmp/cbm-src路径并被截断，未读其内容，随后的精确manifest搜索和严格归档边界排除了tmp；该工具过程如实记入收据，不计业务失败。

本轮业务unit/contract/integration/security/frontend/e2e/live/manual均not_run，网络/模型/付费/新产品进程/spawn均0；只进行实际read-only shell/Git和归档Node操作，不冒称0 OS进程。评分和最终accepted由root及有权评审负责，归档者不更新状态。
