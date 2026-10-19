第十批canonical冻结证据归档报告。仅对应新reports及本归档run，未修改业务/progress/根attrs/锁/Git或accepted。

真实Asia/Shanghai时间：2026-10-16T06:45:24+08:00 → 2026-10-16T06:58:24+08:00；R12优先单包于2026-10-16T06:47:13+08:00交付，优先收据/清单保留原bytes。四包330新文件、12,237,214 B，0复用、0覆盖、0normalize、0重复、0 raw hash/size核验失败；旧4,687项及本批优先2项均前后原SHA不变。

| 包 | 原成员 | 实际归档 | 报告观测raw SHA | manifest本体观测raw SHA |
| --- | ---: | ---: | --- | --- |
| R12-hybrid-recheck | 72 | 73 | fdd7e85122b79c02cd4afc4b0f9a44fbec51322e7761d783920930d9dfb066d8 | a66ff50b93bd0763f0b80ae1414655c14a0d31de2393f422da7c1240352dc767 |
| R07-default-entry-original-review | 90 | 92 | 47e76630f5979244e050b6b046c40720b2fb09f38886d1a1808027f2328fcd63 | c4e29433d17105e9d5d8976e5bf805bfc7d951c9ef834c518ec2aebf6a62c8a2 |
| R17-assets-original-review | 80 | 83 | f5f7a0282deab873b959ce669a1960112e5f77a741db3e8b85bea9715f66342a | 4d691147aab160db8ba79dc3185c09ec98e799e97a236625d1e197c8085ad6e7 |
| R11-PG-assessments-original-review | 80 | 82 | f92ba375d415b5af55252f7bcac016e227318fa2ac56dcf911436d10ed2e1643 | 0ae2caf7d9b34f0511bf5b6e4d6e5017ee895f7381dbcf644b912a350e37ff0b |

R12=72成员+本体73；R07=90成员+本体+原postseal receipt92；R17=80run成员+独立report+本体+原checksum83；R11PG=80run成员+独立report+本体82。原schema分别entries.size_bytes、entries.size、files.bytes、root-array.bytes，按实际schema核验，不改原manifest。

R12与R11PG报告/本体的完整root expected SHA均逐raw匹配。R07/R17用户只给SHA前缀，完整expected保持null，另保存给定前缀47e76630/c4e29433与f5f7a028/4d691147及实际完整观测；前缀匹配不是完整预期SHA验证，观测不会冒充root预先提供的全值。raw/GitLF/manifest body/filelist身份分列。

R12 code ba1548d591d2b341e61a230f1cdd5bd387f3235b/material d3f55300c34760bd97d9a85c710fc23b4a480b66；新review无Git提交，原初审needs_changes及四个合法writer红包保持原SHA不变。新原结论仅固定内部retrieval服务/Fix1当前性围栏限定Ship，不签完整R12/G-D、迁移/worker/API/UI、多跳/SLA/真人gold。

R07、R17、R11PG原needs_changes分别原样保留：R07 default durable entry fix1 first；R17 assets M01先修；R11PG finding1先修。不以新修复或root其他集成替它们涂绿，不签整卡、阶段或accepted。

R07安全封存闭合：原actual_value_scan.json 438 B/rawSHA=12bc5ce9ab24dbfca818dace1477db3f72884b2d13f070550e85a97ba8ef829f，记录原reviewer以现有WSL connection实值在内存检查238件、actual_value_matches=0、matched_paths空、secret_values_written=false/external_requests=0；本postseal receipt绑定90成员、本体c4e…及report47e…。归档者没有重新读取该秘密connection或执行hook，证据依据明确为原sealed hook记录及hash闭合。

原probe_harness_redaction.json绑定两个当前安全修订文件：independent_forward_asset_pg.log旧unsafe rawSHA=24bf7e7ee95fd54c9c091975fee94b564c7afd7c005e8ac028a967ea6d5d3884，修订safeSHA=a02448b18580e696f55931265459f0eb2d7ee1e184bfb569a0968e2737c4a70e；XML旧unsafe rawSHA=b421b098085089b2fdead25a4f85b5287001a14639d70c942338b30eecc5b015，修订safeSHA=03c19afdc5667a582ad131f5649bf0e1ca4efc5591bbde5705f3ae45babf720a。只复制这两份manifest绑定的修订bytes，旧未脱敏版本0读取/0复制，保留旧hash及2份计数，shared_redaction_hook_now_loaded=true原记录与扫描/脱敏脚本hash一并保存。

归档者另做310文本件限定模式检查、20原render image binary仅hash；6处DSN形状密码均mask，未分类0、无匹配值输出，本轮没有需要新AST分类的literal命中。hook scripts只作原材料byte核验，不执行，也不读private cache/vault/holdout；有限模式检查不宣称新实值扫描或全秘密认证。

四包Git ls-tree在各源HEAD下own report/run均0记录，review_commit全null；source HEAD与code/material SHA分列，不杜撰untracked reviewer GitLF。作者产品blob依据原独立报告与source proofs分列，归档者没有新实现或产品code审查；目标rawSHA/size每项再核，CRLF不normalize。

root开始HEAD=acfe244e93662119b9d4b86033f8903bd4b43ec6，最终read-only观察HEAD=b502b7ea4a2ffdeca24b8edc7fa8a33cc0980457；本批root只锁attrs，HEAD变化如实记录，归档者无Git写。根attrs前后30,056 B/SHA=4e4dd89bd2d70e9488186ccfeec276b85f91697806888eacc25f4010d44aec08。R12 run-local .gitattributes86 B/a3568863bf9880736cc27133f8e87c8a9c2f13b4707a41173fb21b54c6fa1e3f；R11PG run-local14 B/85e48d232edc7b02f6cecf8fbbf905f3b126c467b594d8dd16c4f8fa283a8320，均原已列bytes复制，不是修改规则。

逐包收据：R12采用本批immutable priority receipt，另三包独立receipt路径/SHA见总收据per_package_receipts。总精确清单archive_followup_10_filelist.tsv为330行，SHA=b61d5bee2c0a1c1d51b7171e00ee5917fd2270743d0333fda37e611d0db28123。原所有manifest/postseal/checksum不改，priority receipt SHA=c682fd5e71be0207935489d6868a148b35a576634b065f63511320378f00eff9原bytes保留。

原raw 0D0A序列存在于185件、共16205，源目标相同；binary也可能含0D0A，不猜编码。

真实操作：read-only rg实际定位、Git rev-parse/ls-tree（exit0）、Node fs/crypto/zlib原bytes hash/size/path边界+lstat拒绝链接、wx新建及copy后全部复核。初次剩余包文件名rg筛选误匹配WT根名前缀，列出额外文件名并截断，未读那些内容，改精确reports相对路径筛选后只核本授权包；此工具过程如实保留。没有抓正在active live、新cache或toolwhole tree。

本轮业务unit/contract/integration/security/frontend/e2e/live/manual全部not_run；新增网络/模型/费用/产品服务进程/spawn均0。read-only shell/Git与Node归档确有执行，不写成0 OS进程。评分、正式持续窗口、完整验收由有权root/评审处理，归档不签accepted。
