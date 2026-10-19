# 第四批冻结证据归档报告

任务：RECOVERY-EVIDENCE-ARCHIVE-FOLLOWUP-4-20261016；状态：awaiting_review。仅归档，不新编Ship、不写accepted或G-C放行。

上海开始：2026-10-16T03:11:22+08:00；归档收据截止：2026-10-16T03:15:31+08:00。

四包443个canonical文件、4754336字节按原bytes新建；443/443复制后及最终source/target大小、SHA256一致，四份manifest本体和两份指定报告SHA均匹配。0重复、0复用、0覆盖、0删除、0字节normalize、0归档失败。

| 包 | 原清单项 | 加本体 | 补充 | 归档文件 | 本体SHA256 |
|---|---:|---:|---:|---:|---|
| R11 manifest parser复核 | 87 | 1 | 0 | 88 | bfed9a57ffe30d34e432f7624f5d7f99967755088d53b66f046d3b98c60f1606 |
| R09 knowledge cards复核 | 92 | 1 | 7 | 100 | 4501d0367e881fb6cc3e9ec71acad5687ff9655cd852b511c81befce0d572f95 |
| R07 publication首次评审 | 66 | 1 | 0 | 67 | f8e7c54f3ccae19244c44932adc359d11c1061c44028e3243d548b352984050d |
| G-C integrated 8a | 185 | 1 | 2 | 188 | d57bba88253b5822f72ea6076767f9ea10b6d9c2aa70bb128937033bf5adce6d |

R11交接“87含本体”与实际schema差1：files数组87项不含自身，因此全部原项加本体为88。未删除文件或改manifest。R09经rg确认实际run为recovery_r09_knowledge_cards_review_1_recheck_20261016；集成manifest实际为artifact_manifest.json。

canonical报告为G-D-R11-manifest-parser-review-1-recheck.md、G-C-R09-knowledge-cards-review-1-recheck.md、G-C-R07-publication-review-1.md，位于reports/reviews/recovery；集成报告精确例外为reports/tasks/G-C-integrated-8a-validation.md。各run和每一文件精确列表见下表TSV及收据。

前三包schema为files数组path/size_bytes/sha256；集成为artifacts数组path/bytes/raw_sha256。源原、源复制后、目标manifest整本体SHA分别记录，不混filelist。R07报告SHA 6b8bf321f34986dfddac1f02b0c3e713f35abb60bad6d1b5c03d61279eb0100d；集成报告SHA 2a464b82b6b779bb80a0a558992b87157283734ea910f25d4fe013e83ecd4c2f严格匹配。

版本身份分列：R11 code64dcd946601cd0e0f7435f59019ee709e3738a35 / material37e492b4e26fc5b6197b60d2494926d4181a21c3；R09 code dd36cf78c3d15138683d09c12ea867c0055b9674 / material b5ca278d739feac5dba9ca3e693d538a5a8d475e；R07固定产品71e594cb958bd93d21fb7ed66574b3cba4cc47e1；集成固定产品8a1b04d48346d8550f0326a77f003246a0ebbab5。后两包没有另给author material提交，不猜。四份新review/validation文件均untracked，archive_review_commit全null，不把产品HEAD当新review提交。作者Git blob依据只引用原report行号/原文，本轮未重新执行产品核验。

原结论保全：R07仍needs_changes，三项Must未关闭，不能写Ship。GC完整回归仍failed，原完整11红及JUnit未覆盖；四产品CPU红未关闭。原七环境节点复核7/7仅属后续环境复核，不写原全套绿或重算分母。R11原探针37 passed/1 failed的CSV探索红例与R09限定组合意见也原样保留。

R09单列artifact_manifest.sha256及seal_review/verify_review各command/stdout/stderr，共7件；六回执在原manifest.excluded逐名列出，stdout和摘要绑定本体。GC单列摘要与显式绑定本体的seal.json，共2件。依据root本批封存metadata授权逐源/目标大小、SHA核验，未塞回原manifest。

GC已列external_temporary_manifest.json清单自身115242字节/SHA 66e4bee50bdd4dcf0e47e95a5b88962ced23ac87688fb212485fe365a31cd3fd，files数组420项。只复制清单本身，0仓外tmp目标读取/复制。六个runtime目录仅记路径、不枚举读内容：R11 __pycache__、R09 .venv/mypy_cache/ruff_cache、R07 __pycache__、GC mypy_cache。node_modules和仓外tmp不归档。

换行字段说明：收据/TSV crlf_count计原0D0A字节序列，201件有该序列；实际191个文本文件含CRLF（R11 37、R09 15、R07 57、GC 82），另10个GC二进制文件（9 PNG、1 SQLite coverage）也含0D0A。GC backend_full_pure_actual.stdout.log不能完整按UTF8解码，编码未猜，原raw SHA及952个0D0A序列保全。源/目标计数和哈希一致，没有EOL转换。

前三批7个收据/报告/清单和9份manifest共16个保护文件前后相同，且全部匹配此前原冻结SHA。根.gitattributes前后27526字节/SHA 519cdc875fa739a7c1c534d89e4b2d7b11f6ff23bc9860e523aec05dfca13792一致，未编辑。本批没有已列run/.gitattributes；raw_attributes.txt仅原封存建议，未应用。

实际执行为只读rg/Git身份/status exit0；Node lstat/readFile、SHA256、fs.open(wx)/writeFile与source/target最终核验。拒绝绝对路径、盘符、遍历、秘密/holdout、链接/重解析及范围外文件；GC tasks只该精确报告例外。0业务测试/网络/模型/测绘/付费/产品服务浏览器启动/已有进程探测/外部tmp读取。未运行封存脚本或秘密内容扫描；八层业务验证均not_run。

收据截止时归档仪器失败0。收据之后的报告生成工具包装有一次SyntaxError: Invalid or unexpected token，在functions.exec解析阶段失败，未调用文件写入工具、未创建报告；随后改用序列化短payload生成本报告。失败精确秒未捕获，不回填。它不影响443件原bytes与收据；此失败明确保留在报告。

共享观察HEAD8a1b04d48346d8550f0326a77f003246a0ebbab5、分支codex/full-delivery-recovery；已有用户/业务/progress修改原样保留，无Git写操作、push、业务/progress/根属性修改或accepted。评分项证据仅E1/R1可追溯和原红保全；不新增分数、性能、准确率或分母。下一步由root按分包清单做窄作用Git集成，保留R07 needs_changes、GC完整failed和整卡/live缺口。

收据archive_followup_4_receipt.json；911163字节；SHA256 d5da1062afe9827f3aae87097ae95b0fe77f3cca6dbecf50148d986a4ee143ec。

| 分包精确清单 | 文件项 | SHA256 |
|---|---:|---|
| archive_followup_4_r11_manifest_recheck.tsv | 88 | 6f306c8e7ff3aca3d4450f0d524d7edc2a65df9ea864bec04c302a168dc32c72 |
| archive_followup_4_r09_cards_recheck.tsv | 100 | 14da220e4d96549910147b1d75d780d8c098ca3c8dbc7443c13dfea4252be9e8 |
| archive_followup_4_r07_publication_first.tsv | 67 | 06cff2a141da4e51e2320ae3e46292fdca5cd0b3cb769eb4f40f3b2d51283c9a |
| archive_followup_4_gc_integrated_8a.tsv | 188 | 7e1719aeaa3cbb605971273a540ecd32342620679d6872d32063d3ca761394f6 |
