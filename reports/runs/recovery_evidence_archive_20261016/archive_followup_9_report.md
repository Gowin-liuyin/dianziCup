第九批冻结证据canonical归档报告。仅原bytes归档，不变更业务、Git、progress、根attrs或accepted。

真实Asia/Shanghai时间：2026-10-16T06:13:34+08:00 → 2026-10-16T06:22:44+08:00；两核心包优先收据于2026-10-16T06:19:47+08:00落盘后保持原bytes。四包共493新raw文件、1,801,922 B，复用0、覆盖0、normalize0、重复0、原bytes核验失败0。先前4,189项canonical及收据/报告/清单前后全部原SHA不变，优先两项也不变。

| 包 | 实际canonical文件 | 字节数 | 预期manifest本体raw SHA | 观测source/canonical本体raw SHA |
| --- | ---: | ---: | --- | --- |
| R11-SBOM-review | 216 | 685161 | ea25028a5f945e2c7c4efc66d7eb69d7cf8ef71ca44966b122ed58bac574b0e1 | ea25028a5f945e2c7c4efc66d7eb69d7cf8ef71ca44966b122ed58bac574b0e1 |
| R11-condition-review | 88 | 393328 | null（未提供） | 4317611410e3c667ccca08b958e6a1fa313f03dd9ea5626fd81f5f6b807d4104 |
| R12-hybrid-review | 84 | 274686 | 47acc1c2e549cea6fcf7ebadf3e31ab5fcc06d86fee3b7a1c29cb0889b3f591f | 47acc1c2e549cea6fcf7ebadf3e31ab5fcc06d86fee3b7a1c29cb0889b3f591f |
| R06-restart-guard-review | 105 | 448747 | ef4d82602040c7fda44d01d0049ae717669f44ce95f3b4a3dbad40fe9918a2f1 | ef4d82602040c7fda44d01d0049ae717669f44ce95f3b4a3dbad40fe9918a2f1 |

SBOM采用原封存表示：211 sealed/*.gz + 原独立报告 + report_frozen.md.gz + artifact_manifest.json + 其原gzip + 绑定review_seal_receipt.json =216件。211原artifact逐gzip size/SHA核验，内存gunzip后逐原raw size/SHA一致，不新建211份重复解压raw。manifest gzip rawSHA=97d097e048ff6b5e86bc715bd48f8755f4c912e48b536c91028baddc97411b0f，解压与本体ea250…原bytes相等；report gzip同原报告相等。报告rawSHA=4ffa43d4d1d3a02773340cd37ed6c99efb90b8ce1f040c95817861e90084d5d3。所有原manifest均不改。

条件规则88件全部列于review_filelist。root未提供report/filelist whole expected，因此expected均null：报告观测dd8da52a460656e3a9a9f5a938129ee14860954a4eca9c6cf92592771ac0a7a5，本体观测4317611410e3c667ccca08b958e6a1fa313f03dd9ea5626fd81f5f6b807d4104；观测不冒充预先期望。辅助review_manifest原body3ab06d78925938f5ef305207d4db7e3075a7ce0f7f8c2f587fcb65ec70b701db与filelist声明一致。

raw_evidence.zip原whole SHA=a0ff83fbc7dfd348f8470296cfb457f3625e9102bca0b3d8d86d516ef8b05b8f；含85个原raw条目及exact review_manifest额外metadata。85原raw逐size/SHA匹配，再按获准同canonical路径wx新建原bytes；源checkout不改。其中50原raw不同于Git表示，均仅CRLF→LF；固定review提交f1e2f760cb96e3b8faa9c69f0336f38f1a6f6140的88真实Git对象分别36 raw-exact、52 LF-only（另2为manifest/filelist）。没有把GitLF替代原raw，也没有对现存目标normalize。

R12为83成员+本体=84件；R06为103成员+本体+绑定checksum=105件。各报告和本体匹配给定raw SHA；R12 source code f316a7…/material a43d25…仍为原needs_changes及四合法writer红，不给任何新修复SHA背书。R06仅固定tool44c9415/product e310准备切片，旧bae46 raw mismatch、两个Must红、最终31green和root live gate缺失原记录全部保留，不计6h。

精确493项清单：archive_followup_9_filelist.tsv，SHA256=649da8431ba435e30c33ccd6096ce9bd00c548e6eb8378c065d969988b044666，每项action/size/raw SHA/source_kind/0D0A及fixedGit representation。priority receipt SHA=2272aef22d2324409bc50a916ac65fb34276ba90436190dd299772b442827a74，priority filelist SHA=20863d077dcb85df075c6cca7c2682818c1a5d45cbc6410ae403ce7b626f1cad，本批不改写这两文件。

本批root HEAD前后均0532c4f58611e068fc7d5b03da984bc57dbad9f2（最终实际观察0532c4f58611e068fc7d5b03da984bc57dbad9f2）。root graphApp精确whitespace后的合法新attrs为30,056 B、SHA=4e4dd89bd2d70e9488186ccfeec276b85f91697806888eacc25f4010d44aec08，前后不变；不沿用第八批4df6。只原manifest列run-local attrs原bytes复制，具体hash见收据；根attrs、锁、Git index/commit/push/progress无写入。

review/source/material身份分列。条件review固定f1e有真实88对象raw/LF核验；SBOM Bea是combined source HEAD，原review_commit=null且该source树0本review材料，不能当review提交。R12/R06新报告无review提交，review_commit均null；tool44c只依原冻结manifest身份和证据，不抓工具whole tree或active live。产品作者Gitblob证明按原报告basis分列，本归档不新编产品审查。

原结论保真：SBOM Ship仅pure adapters及唯一依赖checkpoint，10000公共parser容量与完整SBOM/PG/整卡缺口保留；条件Ship仅纯条件规则，whole unit 2214=2208 passed+6 failed、原native严格CPU红与73.96%门原记录保留；R12 needs_changes及四合法writer红保留；R06 Ship仅重启部署守卫准备，root live gate缺失、不启动，不转6h/整卡通过。无新Ship签署、金标或分母变动。

限定扫描覆盖194个物理文本source、85 ZIP原raw文本及205 gzip解压原文本，共484文本表示；6 gzip解压binary原件仅hash。原report/manifest双gzip与已扫描对应plain完全相同，ZIP metadata与已扫描review_manifest相同。敏感形状匹配0、未分类0，无值输出，没有实际秘密/provider/vault/model环境读取；本批没有需要新AST分类的命中。有限ASCII扫描不声称全秘密认证。

canonical raw 0D0A存在于138件、共11094序列，原source/目标相同；压缩binary也可能偶含序列，不称全为文本行尾。SBOM解压原raw计数另列，原CRLF保真。

真实操作：read-only rg定位、Git rev-parse/ls-tree（exit0）；Node标准fs/crypto/zlib逐gzip/ZIP SHA/size、内存原raw、路径边界及lstat链接拒绝、wx新建与逐目标核验。ZIP仅store/deflate、禁止encrypted/link/duplicate/ZIP64并校验授权path；没有extract到源或临时cache，没有执行ZIP/gzip/脚本内容。初始将raw_archive误作JSON，PK格式拒绝0文件写；初始85-only ZIP断言额外遇1个已获准exact review_manifest，核明86=85+metadata后继续。这两个工具过程如实记入receipt，不计业务测试失败。

本轮业务unit/contract/integration/security/frontend/e2e/live/manual全部not_run；新网络/模型/费用/产品服务进程/subspawn为0。read-only shell/Git与Node归档实际执行，不冒称0 OS进程。评分、正式6h/live、整卡/阶段/accepted继续由有权root/评审办理。
