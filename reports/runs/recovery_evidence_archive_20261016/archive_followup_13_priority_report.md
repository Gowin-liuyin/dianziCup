# 第十三批优先P1/P2冻结归档报告

开始2026-10-16T08:38:08+08:00；结束材料核验2026-10-16T08:43:42+08:00；Asia/Shanghai。
P1/P2合计330新件、2,155,727B，复用0、覆盖0。330目标源/目标raw大小及SHA全同，原manifest本体全匹配。依主控要求仅核相关已有保护项一次：归档原收据50、原SBOM包99、P2前置R12报告和本体2，共151件无漂移；未全量重扫或复制旧5816。旧其余记录仅从第12批不可变收据继承metadata，未冒称本轮全量复验。

| 包 | manifest成员 | canonical件数 | bytes | CRLF件数 |
|---|---:|---:|---:|---:|
| R11-SBOM-inventory-recheck | 174 | 176 | 974040 | 45 |
| R11-forward-migrations-review | 152 | 154 | 1181687 | 70 |

P1实际174成员已含独立报告。加本体与root指定seal_receipt，共176；未再多算报告或猜controls。报告SHA00451e65d2001a8b916a1f2a8af5b6b4c22a891bd453ac66f4b8a92c3cac309d，本体c6de4d0ee46ba6e2f3276f337fc24c7893b9dc6dd162a84c4da59de0a0ea12b3，seal b6013d9faa15769f2c34209adb267cb63bc6c7e8dc624ecf8be36e81ee2424b6均匹配完整expected。原41 gzip同时按compressed raw与expanded_size/SHA核；19最终source快照的解压LF SHA/Git blob OID与原独立source audit一致，不新读产品树、不另建解压副本。code6942c65efd5df013c077275cbb6d8cfec3585080/material5be873ec38a41955b5a58e9762df4b866a7a9d63分列，reviewcommit=null，HEAD树无该review报告/run。

P1原27actual值扫描0match、expanded_scan172、unclassified0、classified37只按原seal证明，不重读秘密、不重跑hook。scan_diagnosis原37分类中20 whole-file raw digest与10 testcase ID/class digest亲核；7mask shape记录按明确授权作为原封存分类依据，其shape摘要没有另冒称逐pattern复验。归档scanner在两旧XML命中的2 DSN仅位于已核合成testcase名；其它fixture文件以原sealed分类及相同whole-file SHA保留，不改testID或原manifest。另1 password词法命中经当前冻结resource AST行457确认实际tuple字段username、静态前缀加uuid4，password由另一token_urlsafe产生，完整值不在source；行460是username fallback的positional调用，不猜keyword账户映射。旧第11批source哈希不同，未复用旧整源码AST结论。仅记路径/行/hash，不输出值、不执行测试源码。

P1原唯一功能547（原411+privacy/followup90+本审46）范围保留，早5红、742质量红、fixture错误、第三方warning及定向复验均不删、不累加分母。原发现1及追加Must只在库存/容量/sidecar服务及privacy修复范围闭合；不签正式App/browser、生产0022、整R11/T24/T28/阶段/live/manual或HTTP SLA。旧97封存保持原字节，局部合成SQL/容量记录不升级产品性能。

P2实际152成员已含独立报告，加本体与原review_manifest.sha256，共154。该66B sidecar严格绑定实际本体09fb958ec03460247168a8c3a11cec4f6d8f236ce7cc94aa9a6119502c55d1c9，原CRLF也保留，sidecar完整expected未给则null。报告SHA584b6828410e1e3c5e7592e775d5eaea935557bcb71629525130b017845658a1匹配。code2fe903eaff4030b64b3f5789e8027e1e11e41694/material569d8a7dc81fcea6b524b4fa172a5c7977388b93，reviewcommit=null，HEAD树无该review报告/run。

P2原实值scan记录raw673/frozen262，password/DSN/frozen三类0match、matched_paths0，归档仅读清单内原proof，不读私有连接配置、密钥、DPAPI或cache。前置0020独审报告89579f9d…及其cb27ac0e…本体为当前canonical原byte控制，均亲核；不把其limited Ship扩大整R12。P2原Ship只固定生产0021/0022及直属测试/资源适配；原helper/Ruff/format/red、初期路径仪器错误、SQL/assertions、warning和raw-LF差异保留。未签整R11/T24/T27/T28/G-D、SBOM完整产品链、App/browser/live/manual、金标、SLA/正式容量或生产运维恢复。

本批cache/私钥/DPAPI/holdout/secret reference与未freeze/WIP均未读或复制，原清单不改。未知full expected保持null；whole manifest与filelist哈希分列。CRLF原byte不规范化，LF仅内存计算或原固定blob比较；原已列run-local attrs依授权保byte复制，根attrs不改。
根main起始d31f37ff04f845d310393fd652e4e7a2647b8755，结束只读观察cd91b87556dd93453537694b5090219ae4ed9b6c，root合法变更HEAD不作review提交。根attrs fresh30806B/ce38b195bfd7c06d1a7884272e402571b56b2a614155ff52274b8f51d920ee57保持，不用第12批旧hash背书。本阶段输出raw核验后向root明确释放attrs保护，未写锁。

实际文件/hash/gzip/只读Git/标准库AST核验与wx新建，无业务unit/integration/live/manual、网络、付费、产品进程、subagent、Git写入/push、progress/accepted或新评审签字。AST旧raw匹配不足与工具临时变量错误均在P1写入前严格停止，后用当前冻结source更正；不改源、不改已有P2或旧收据。精确路径/原bytes/hash见同名priority_filelist，原身份、分类范围、检查与异常见priority_receipt。其它批次候选未读，待root合入及精确授权。
