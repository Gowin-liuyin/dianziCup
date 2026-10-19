第六批冻结证据归档报告；归档验证完成，业务状态及验收状态不变。

真实时间（Asia/Shanghai）：开始 2026-10-16T04:34:06+08:00，逐项验证及收据封装结束 2026-10-16T04:57:03+08:00。限定目标为 D:/dianzi 对应 reports 路径及本归档run；仅按原bytes新建，不覆盖、不删改、不归一化原材料。

本批六包共 525 个新文件、6600357 B，源与canonical目标逐文件raw SHA256/size全部匹配；整manifest本体再核一致。复用0、覆盖0、重复0、raw核验失败0。精确525项路径/size/SHA/action/0D0A数见 archive_followup_6_filelist.tsv，SHA256=c12e3b626f8249f2ee0627868d7c685479f12d6b5acc20a7463b9d0761bb9088。

| 包 | 原manifest声明数 | 实际归档数 | 字节数 | 提交/固定材料核验 |
| --- | ---: | ---: | ---: | --- |
| R07-publication-recheck | 76 | 78 | 386313 | review_commit=null |
| R06-large-release-diagnosis | 81 | 82 | 897181 | review_commit=null |
| R17-graph-review | 89 | 91 | 3263431 | review_commit=null |
| R08-persistence-review | 68 | 69 | 673331 | review_commit=null |
| R07-acl-lock-author | 112 | 114 | 670304 | 114/114 raw Git blob |
| R07-cvss-author | 97 | 91 | 709797 | 91/91 raw Git blob |

R07 publication复核为76成员+本体+绑定checksum；R06诊断81成员+本体；R17为89成员+本体+绑定checksum；R08为68成员+本体；ACL原作者112 run成员+本体+独立任务报告；CVSS原97声明中90件reports成员+本体，另7项业务/测试/合同仅manifest引用，不复制到产品位置。没有把filelist SHA当本体SHA。

| 包 | root预期本体SHA | 源及目标观测本体SHA |
| --- | --- | --- |
| R07-publication-recheck | e82dd5f4898b6db229933631871ef04b783ea30c505e9dd61e53d2838e098cb1 | e82dd5f4898b6db229933631871ef04b783ea30c505e9dd61e53d2838e098cb1 |
| R06-large-release-diagnosis | null（未提供） | d223c872a6844f6419521e7164da2b6fdc9ae0427a5b4085dd2f2bf58048d1cc |
| R17-graph-review | 812970796a9d0325ce1011876525b3aa5bfccbdda7454ff7101f430c9b21874e | 812970796a9d0325ce1011876525b3aa5bfccbdda7454ff7101f430c9b21874e |
| R08-persistence-review | 28d5eacb9c6ff36eb18981926f87d8afd63761345cbc2cc821e0ce0a2248fcfd | 28d5eacb9c6ff36eb18981926f87d8afd63761345cbc2cc821e0ce0a2248fcfd |
| R07-acl-lock-author | null（未提供） | 34aed164803763a0486366478b1856e6119a9104015398310b5b671d9b98f745 |
| R07-cvss-author | null（未提供） | 471616bf0d46c3a8bb386101c919ab322e380d12f0968f7df84abc98ab2d39a1 |

R06诊断和两原作者包未给预期本体SHA，expected=null；观测值不冒充预先封存期望。CVSS filelist_sha256=5bd5fb7da0d2244f144cb41e1e702ee906da05695df7d7aca1e21861a7c14973，与本体471616…分别记录。原manifest全部未改。

本批根基线为 136fbaef337036d95229aa4976c1ba49b2e6b04c，最终read-only rev-parse HEAD相同（exit0）。root合法merge后的 .gitattributes 为29645 B、SHA256=5e34449531d262e56ef2edb57549e36dfea815e6036b2de4260f99fc4771c77a；与本批起点相同。此前五批收据、报告、清单及各原manifest共33项全部复核，原SHA均不变；新基线不是沿用第五批旧attrs。Git index/commit/push、progress、业务源码和根attrs无修改。

两个run-local .gitattributes 是已获root授权的原manifest成员原bytes复制，各8 B、SHA256=705fd4d6451a31d36b3df7de96f83f30ac976c9b4a6d1e51671d8e2f33e2d0da。它们不表示归档者编辑规则或获得根attrs权限。

6包review_commit均为null；四review/诊断材料没有独立review提交，两原作者固定材料提交b0a5b64014f89a689b6b1efcdd21e791b454c12f/fde252955fd88f537b844b0414d08967d0b2d67a分别完成reports/run原raw Git blob 114/114、91/91核验。code/material/review身份在收据分列。其他作者产品blob核验依据原报告声明分列，不杜撰新产品code hash审查。

R07 publication原结论仅service slice Ship及三Must闭合；R17原pointer Must1 needs_changes、R08原TTL Must1 needs_changes不变；R06诊断原live失败不变，离线真实原文PG重放不是livePassed。两原作者7/2红、旧fixture/old-test和其他失败原bytes保留。本归档不编新review结论、不签accepted。

限定敏感扫描：503 文本件、22 二进制仅hash；70 DSN形状password均已mask；6 literal赋值形状经root授权固定dc04源码AST与XML捕获在内存等值分类为synthetic参数化字符串判别输入。依据为backend/tests/security/test_t06_authentication_and_scope.py第168/169/170行纯字符串参数，test_secret_scan_distinguishes_public_failure_check_from_credential_literal仅向176行判别函数传入，无env/cfg/模型来源。源码blob SHA256=e6df1bc8d71bdd9416cbeaac28cca5d9742368671f9d5068bb603d639e29d237，Git OID=fddf4e84363f4b38c54232eadb285293e736f41e；dc04和b0相同。匹配值未输出；没有读取新的modelvault/DPAPI/provider秘密或实际运行该测试。该有限模式检查不宣称全秘密认证。

CRLF保真：320 件存在raw 0D0A，共26759序列，源/目标计数一致；二进制也可含0D0A，清单不猜编码。没有normalize。R17四个原自引用seal日志按明确授权不复制（not_copied，收据列具体路径）；__pycache__等缓存目录不枚举/不读/不拷。R07复核248代码blob只归档其manifest文件，0代码/cache复制；CVSS7产品/合同引用不复制。仓外原大正文、cache/venv/node_modules、作者.git、schema/code未递归复制。

归档检查采用Node标准fs/crypto原bytes读写/路径边界+lstat拒绝链接和越界、read-only rg定位、固定Git树object核对、root明确允许的Python标准AST字面量检查。真实业务unit/contract/integration/security/frontend/e2e/live/manual本轮均not_run；网络、模型、付费和产品服务进程0。read-only shell/Git/AST检查确有执行，不把它们写成0 OS进程。一次工具包装SyntaxError发生在执行前、文件变更0，已保留；初始AST保守未分类后完成参数tuple解析才定性，不计业务测试失败。

本收据只证明限定冻结材料原bytes归档与核验。评分、正式6h/live、整卡和最终验收须由有权owner依据各原报告继续，归档者不更新progress。
