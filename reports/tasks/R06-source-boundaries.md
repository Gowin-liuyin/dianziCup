# R06 · 来源正文完整性与时间精度修复

文档首次创建时间：2026-10-15T22:21:01+08:00
本次写作开始时间：2026-10-15T22:21:01+08:00
本次写作结束时间：2026-10-15T22:21:01+08:00
最后更新时间：2026-10-15T22:24:42+08:00
作者：/root；切片 awaiting_review / implementation complete；整R06/G-C仍in_progress/partial。分支codex/r06-source-boundaries-fix；基线b2bd53fd2320fc46f600ff0475298ec1b64b0172；首修代码6dcce8b115ee3cb68bce814cf3f3ae91be9fcbf1；第二修代码1456e22f8187643a9978e9fa44d57c945e73b5bc。未push。代码编写实际起止未单独记录，不以mtime代替。

## 问题、输入与根因

独立初审G-C-R06-source-worker-review-1，报告815e5bcc853f8c923e3e68acdd8913978399c9f90473989f27e6cf1902841d32：M1删除固定CAC政策末条生效句但保留24 headings，前言仍有施行字样，原global检查误认full_text，worker成功且文档/游标/回执各1。M2 fromisoformat接受非法+00:99、将合法未知offset -00:00变UTC、把7位小数截成6位；PG与展示会虚构精确发布时间。均阻断本切片。

首修将生效句定位到末条并检查各条非空；日期helper统一64字符ASCII语法/日历/offset校验，非法拒绝，合法未知offset/高于6位精度原值保持、PG instant NULL、precision unknown。不用抓取时刻补发布时间。OSV三时间字段、GitHub release与通用JSON资料共用规则；NVD/vLLM旧严格策略保持。_json_document记录原始时间、notes与catalog-pages-2；原始响应hash与派生资料hash保持独立。正式小合同CR-R06_source_timestamp_precision.md补兼容/迁移/回滚/测试影响；无需schema/DTO/依赖改变，不改金标/阈值/分母。

首个草稿拒绝所有>6位时间，真实OSV正例modified9位合法值被拒绝：focused43pass1fail已保留。改为raw保留/NULL/unknown后合法正例恢复，不删真实样本。原16红、43+1红、首修28新unit与96PG均保留，不把fixture算live。

独立6dc复核54d3dde4b31f2d977f15880ac7d30866c3f59d43171e09ea20b95c67eb9042b7：M2经真PG与认证HTTP的六个OSV/release unknown样本已关闭；原19probes原样复跑4红15绿，4红来自旧blocked期待与NULL.isoformat，不改旧probe。新M1负例删第4/8/15/21条正文，紧接章标题被误计为正文；四纯+第8条PG仍错成功。实际发现时刻与命令以独立run为准，本报告不补造更早时间。

第二修1456：条文计算范围遇下一章标题截断，章节名称不能填充条文正文；CAC adapter3、JSON2、AVID/NIST1。复用原HTMLParser与Block解析，只改4文件36+/5-：产品6行、共享负例fixture helper、四永久unit、一个PG事务负例。没有另建解析框架。新四unit在旧6dc真红4fail保留chapter_boundary_red，修后正文与合法章节布局正例通过；独立复核正在新WT固定1456进行，不自签accepted。源码行号以各固定commit为准。

## 实际验证

cwd D:/wt/r06-source-boundaries-fix/backend，完整argv与开始/结束秒、exit、head见同名json/log/xml。真实专库test_dianzi_r06_catalog_worker_20261015，UUID schema由既有安全fixture隔离，未用开发库/生产DSN/降级。原单位覆盖门60未改变。

| 检查 | 代码 | 起止 Asia/Shanghai | exit | 结果 |
|---|---|---|---:|---|
| boundary_pure_frozen | 6dcce8b | 2026-10-15T22:01:14+08:00 / 2026-10-15T22:02:40+08:00 | 0 | 1788 passed/10 deselected/74.52%原60门 |
| boundary_pg_frozen | 6dcce8b | 2026-10-15T22:01:14+08:00 / 2026-10-15T22:03:06+08:00 | 0 | 96真实PG passed |
| chapter_focused | 6dcce8b | 2026-10-15T22:16:51+08:00 / 2026-10-15T22:16:54+08:00 | 0 | 48 passed：32边界+16目录解析 |
| chapter_pg_frozen | 1456e22 | 2026-10-15T22:17:11+08:00 / 2026-10-15T22:19:04+08:00 | 0 | 97真实PG passed |
| chapter_ruff | 6dcce8b | 2026-10-15T22:16:51+08:00 / 2026-10-15T22:16:52+08:00 | 0 | Ruff src/tests passed |
| chapter_mypy | 6dcce8b | 2026-10-15T22:16:51+08:00 / 2026-10-15T22:16:52+08:00 | 0 | mypy 92 passed |

两轮完整纯/PG自检在6dc冻结后真实复跑；1456只增加4unit/1PG与小正文边界修复，按影响跑48相关与97PG、静态，不重复6dc全套pure作为新SHA背书。最后main集成会跑完整回归。部分早期JSON working_tree为静态模板“immutable SHA follows”；head实际为冻结6dc，原记录不改写，后续helper已输出实际src/test状态。初次新增fixture长行Ruff失败已修；一次源码查看误猜parsing.html路径ModuleNotFoundError为工具定位错误，无业务输出，不计测试失败分母。所有正式测试数量据日志，本轮未调用外网、模型或测绘，费用0新增。

unit/contract/security以纯自动与指定边界覆盖；integration真PG；frontend/e2e/live/manual本切片not_run。不能由新九源类型名或此fixture推断真实来源已连通。

## 调用链、复用与限制

复用fixed catalog/source worker网关/ContentStore/source_response_hash/PG page事务与原发布链；时间helper调用方包括OSV、release、_json_document，原字段与raw payload独立验证。官方CBM0.11基线b2bd与1456分别命名，src-only，不索引secret/holdout/reports，缓存仓外。1456两个trace与索引交叉源码/rg；首次schema漏project明确exit1并保留，按真实help补project后另存corrected，不隐去工具错误。catalog_pages normalize→policy或OSV/release→原source worker→原子PG发布/游标，GET沿document route/read service显示unknown。图有边不能单独证明行为，以上测试验证正文错误无本页副作用及原值/NULL投影。

完整性检查是固定政策预期结构/24条非空/末条生效句，不把它当法律效力或资产合规判断；合法条文有实质更新会隔离待核查。未知精度仍计未知统计桶，不从采集总分母消失。其他R06来源模式、自有webhook、独立参考集合、连续时效和九源live另有未完成范围。

## 复核与下一步

原独立reviewer在新WT复验1456的四正文负例/第8条真PG回滚/完整原文正例，保留6dc原红报告。只有明确关闭全部本切片阻断后主控合入worker、来源UI及自动轮询，再完整集成回归与同SHA有界真实采集/API/UI。阶段G-C尚需R07–R10及新的阶段review，不由局部Ship替代。报告材料提交SHA与代码SHA区分，实际push只见主控台账。

修订记录：2026-10-15T22:21:01+08:00 首次按真实原红/冻结验证/独立M1反馈写作；实现仍awaiting_review。

2026-10-15T22:24:42+08:00 材料保全：原失败日志含pytest代码展示的行尾空格，git diff --check明确报错；仅此run的*.log标记-text/-diff保存原字节，不改失败日志。其余源码检查不豁免。首次UTF8文本扫描遇非UTF8工具日志decode失败，改为UTF8/UTF16三种编码的精确秘密字节匹配，0命中。首个材料补记脚本误用Windows默认GBK读取UTF8报告，在写报告前退出；已显式UTF8修正，原工具失败保留主控转录。
