# 冻结证据归档报告

任务：RECOVERY-EVIDENCE-ARCHIVE-20261016；状态：awaiting_review。归档校验通过，未签产品验收。
上海开始：2026-10-16T01:25:28+08:00；结束：2026-10-16T01:34:57+08:00。

五个冻结包共395个canonical文件、3,876,003字节按原bytes新建；0复用、0覆盖、0删除、0normalize。两轮复制后/最终source与destination的size和SHA256均一致，归档失败0。新增自有文件只有本报告和archive_receipt.json。

| 包 | 原清单项 | 含manifest本体/补充的归档文件 | manifest本体SHA256 |
|---|---:|---:|---|
| A | 65 | 66 | 0335139ea03d70663765522da0dab7169a737cf016758c6f7d2aab1dfed338c9 |
| R08 | 66 | 67 | 415f9aadf911f2310a9a5f78a92306cf93a3fe6092e12eb82ae3afd256e9c02b |
| R20 | 110 | 111 | 7cbb0b5689f3f7cb5d02bda3d165adbe2fb1fd6a18b147ea4f6508598db65085 |
| R06 | 81 | 83 | f68ec664eec62451af1e75f947f45c59d8c8977c88127703c5a8ab55330e1f45 |
| R17 | 66 | 68 | 5a523731899150c000db763a5716dd77a35b50a0f6f8e545c4427bd8e3f987d9 |

原manifest schema分别为artifacts数组(path/size_bytes)、entries数组、artifacts数组(relative_path/bytes)、artifacts对象键以及evidence_files数组(path/bytes)。R17 sha256_lf仅记录，不代替原raw哈希。全体manifest本体原样复制，源/目标本体复算均与上表一致。

源code/material/frozen SHA、canonical报告/run范围、逐文件校验及作者Git blob核验依据完整分列在archive_receipt.json。A/R08/R20/R17 review原材料未跟踪，archive_review_commit为null，不将产品HEAD冒称review材料提交。R06固定review提交dcfcab9a39157b08f12567b7008fd4e88a1ac71c的83项由只读ls-tree object ID与本地raw Git-blob SHA1逐项匹配。

A作者manifest本体91125322b8fa70d7c5dd9c40af8f84ad1afcd56c6070316af8dddb32094885dd和filelist a3ea1549f82c7dd714418046703b20424445ca5ac79265b287d85d4c081bee06分列；原strict exit1的467字节日志SHA dc569e84cd9af3ffdf6d8d94552688438adb815bca1014416b616caa92f43c86保全。
R06 needs_changes保持；原legacy exit1记录33 tests/6 failures/0 errors/0 skipped仅为原记录。9176字节pg_legacy.log（SHA 97400545db29c77fe2c965d81ae00bdc782c3866d5509c61949884ff2e1a73d8）和19853字节XML（SHA 4932fbad296ecc28cef5425ed38412ab47cbfc7fe9c56a3db86f129a298c598f）原bytes保全。

root已批准A/R08原manifest列出的run内.gitattributes按原bytes新建；原file hash见收据。根.gitattributes未编辑，归档前后13675字节/SHA 12a3f0625c04b203d572bc28d390ef5fa3414047390281a00cdbf960ecaff1f1一致。
补充单列：R06 staged_bytes_audit.json按固定dcfcab9的codeCommit-source归档；R17 artifact_manifest.sha256按sidecar-source归档，值和绑定artifact_manifest.json严格匹配。两项均经root明确授权，未塞回原manifest。A四个/R06一个__pycache__未列封存清单，未归档。

归档仪器有两次失败尝试，均保存于收据而未掩盖：预复制侧录解析曾误把sha256sum的摘要和文件名整行当纯摘要；随后按摘要及绑定文件名解析。首次长收据JavaScript包装语法失败Expected ')'，未执行写入；随后改为序列化静态payload生成收据。这些是归档仪器失败，不是产品测试；工具未捕获精确秒，不回填mtime。

真实执行：Node fs.lstat/readFile、crypto SHA256/Git blob SHA1、fs.open(wx)/writeFile与逐文件复核；只读Git rev-parse/branch/status/ls-tree exit0。业务测试0、网络0、模型0、测绘0、付费0、产品/服务/浏览器进程启动0、已有进程探测0。unit/contract/integration/security/frontend/e2e/live/manual均not_run，未执行秘密内容扫描。

合同/计划偏差：无产品合同变更；root从四包明确扩充为五包并批准上述原属性和两补充。共享HEAD与指定349c5e3ec27196257b98cdfcb63c75fb50157978一致；实际分支是codex/full-delivery-recovery，而非口头main。已有未提交文件未修改。
评分项证据仅E1/R1材料可追溯和原失败保全；不生成任何评分、准确率、性能或持续运行时长。下一步由root按收据复核，统一窄作用Git attrs/add/renormalize与提交；保持原review限定范围、R06 needs_changes及外部缺口。

收据：archive_receipt.json；591326字节；SHA256 c5a5d13eb2b2a0fa7e6cf9cedf26471ae78082f005ef9676c871a6f2b7d2f80d。
