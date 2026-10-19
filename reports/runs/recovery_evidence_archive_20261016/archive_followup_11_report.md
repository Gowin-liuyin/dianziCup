# 第十一批冻结证据归档报告

开始：2026-10-16T07:03:14+08:00；结束核验：2026-10-16T07:21:05+08:00；时区 Asia/Shanghai。
仅归档冻结 reports 原字节；新建 285 件，共 15764224 字节，复用 0 件，覆盖 0 件。旧材料及既有收据 5025 件、本批优先收据 2 件，合计 5027 件均未漂移；285 件新目标重新核验源/目标大小及 raw SHA256 全匹配。

| 包 | 原 manifest 成员 | canonical 件数 | 字节数 | CRLF 文件数 | 原结论范围 |
|---|---:|---:|---:|---:|---|
| R17-assets-recheck | 100 | 104 | 14852304 | 66 | Ship：frontend assets workbench code slice; M01 closed only |
| R11-SBOM-inventory-original-review | 97 | 99 | 485426 | 60 | needs_changes：original SBOM inventory implementation review; original finding 1 remains |
| R11-PG-assessments-recheck | 79 | 82 | 426494 | 39 | Ship：internal PostgreSQL/CAS fix1 review only |

R17 原 manifest 为 100 成员；原 work/index 封存证明为 103 件，原报告、本体及 checksum 包含在该计数内；另归档已指定的 sealed_byte_proof.json，canonical 合计 104 件。103 件源暂存 blob 原字节标识逐件亲核一致；这是只读 index 证据，review_commit=null，不把作者材料 HEAD 当新审查提交。PNG 等 32 件仅核原字节哈希。优先收据和清单保持原 SHA。

SBOM 原 97 成员已含独立报告和 report_raw.md.gz；加本体及原 seal_receipt.json，合计 99 件。报告 gzip SHA60f3f65887a5cbff7688432e2688b725f6d4a8aaf02bac42b8a544d5d600089f，解压字节与原报告匹配；24 个 gzip 解压 raw 与派生 LF 摘要分别记录，18 个原源码快照解压 raw SHA及 Git blob OID 与原封存 audit 标识一致。未新读产品源码或另建解压副本。seal_receipt 根仅给短前缀 479ccc，完整 expected=null，observed=479ccca6d12deba50ac1c520e1179131a2886fb725d088996d8eb92276fecf7f。needs_changes 原隐私边界问题与容量/SLA缺口均保留。

PG 原 79 成员加独立报告及本体，再单列复制原绑定 delivery_receipt.json，共 82 件；未塞回原 manifest。sourceproof SHA3cb5385c7516e1348797ad97c96a40e36b73faa8e8758418f614f403e9187750 的原作者55 raw、旧作者118 raw、旧独立80 raw及7源码 blob 核验事实保持原依据，归档人未重新审业务源码。原作者 fix 任务报告 observed=990a30455df74651a750296066c244907d10acbcd456435d62fc45caacc23c39，expected=null；它与此次独立 reviewer 报告 a7143362… 属于不同文件。原12 probe 的11 pass/1 diagnostic fail完整保留，诊断用例期望旧漏洞可提交而修复拒绝，不改为 skip，也不列为新 Must；14 Lock 证明与2/33/15/354/12测试组不重复累计。

敏感限定扫描：仅授权材料文本与 gzip 内存解压；未读取秘密、缓存、holdout 或新 live 输入。SBOM 原封存实值 hook 记录 4 个动态值检查、0 实值命中、0 blocked shape；归档人未重跑 hook。归档模式识别的33处私有字段标记有明确合成用例 AST 字面量用途证据，8处 DSN 为掩码；另2处 password 词法匹配经元组 AST 映射实际属于 username/account 字段的静态前缀与 UUID 拼接，不是完整密码或环境值。仅记路径、函数、行、哈希，未输出值。PG 新封存 secret_scan 记录4个实值注册、0匹配、regex_only=false、连接前加载hook；这是本包原证明，和旧包 hook 分列。R17 限定文本模式扫描无待定形状，图片仅哈希不宣称图像敏感语义检查。

每个原 manifest 本体 SHA 单列，未用 filelist SHA 代替。三个 reviewer 材料未有新提交，review_commit 均为 null；代码/作者材料 SHA 分列。CRLF 原字节未规范化，LF 仅内存计算用于区分。原清单内 run-local .gitattributes 按先前明确授权原字节复制，哈希见精确清单；根 .gitattributes 未修改。
根 main 起止只读观察均为 b502b7ea4a2ffdeca24b8edc7fa8a33cc0980457。根 .gitattributes 30056B / 4e4dd89bd2d70e9488186ccfeec276b85f91697806888eacc25f4010d44aec08，前后保持。

实际执行：文件读取/原字节新建/哈希、只读 rg/Git 元数据、标准库 gzip 解码及 AST 分析。业务 unit/integration/live/manual 均 not_run；未联网、付费、开启产品进程、spawn、Git 写入、push、progress/accepted 变更或验收签字。Git 非ASCII路径引用、工具包装语法、AST 元组定位的中间失败均在写入前更正并单列；不计业务测试失败。

精确路径、大小、raw/LF摘要见 archive_followup_11_filelist.tsv；全部前后核验及分包原身份、异常、限制见 archive_followup_11_receipt.json。
