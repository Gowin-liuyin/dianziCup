# Root · 批次17部署资源、身份审计与真实PG验证

文档首次创建时间：2026-10-17T10:20:24+08:00
本次写作开始时间：2026-10-17T10:20:24+08:00
本次写作结束时间：2026-10-17T10:20:24+08:00
最后更新时间/证据截止时间：2026-10-17T10:20:24+08:00
阶段G-C：in_progress/partial；G-E独立准备，当前checkpoint awaiting_review
工作分支：codex/full-delivery-recovery
基线已测/已审代码SHA：9d8b222cd6cfcc87e618867c918a1b8fcdafa32f
本批fixed WIP字节：root_batch17_code_freeze.json；新代码独审尚未完成
提交/push：写作时尚未发生；不是阶段通过。

## 行为、复用与必要改动

独立9d审查复现默认App Docker/wheel缺外置contracts文件导致导入失败，公开Ask身份字段拒绝漏记审计。Root用标准库importlib.resources与精确冻结AskRequest package JSON修部署；不引入依赖、不改公共合同。新的request_audit只记录拒绝的字段名不记录值，由旧RequestValidation和新严格JSON路由共用；PG audit失败明确503/no-store/no回答。原body/credential/CSRF/idempotency/size/depth错误继续原语义。新原输入复验在新冻结源上仍待原独审，不能旧版本背书。

导入f316经独立275+3离线/17真实PG的八typed绑定文件与0031前向迁移；Root90直属离线通过，默认getter/publisher尚未接通，整R18仍partial。七原integration head期望仅0030→0031八处输入跟进，source912数据库/运行WT保持0030；7组实际Root新head PG未运行，不能拿f316或9d证明。精确替换原hash/新hash在root_batch17_forward_head_expectations.json。

## 实际检查与独立证据

Root工作目录D:/dianzi/backend，现82公开Ask/新包资源/审计+90绑定=172不同offline通过，0fail/error/skip；mypy4 normalfollowimports与Ruff/format6通过。原style首次exit1(4长行/1import由Ruff修)，原红保留后仅新test linewrap与imports修正；所有命令/NativeJob收据/stdout/stderr/XML在reports/runs/recovery_reviewed_integration_20261016/reviewed_slices_batch17_*。每命令60s、512MiB/process1GiB/job、2CPU(rate833/24)、Win峰4–5、own残留0。

Root对独立固定9d实际六PG窗于2026-10-17T10:11:31.434152+08:00至10:13:19.608499+08:00共21例全部exit0（生命周期2、默认App1、公开18）；真实PG/默认build_engine/auth/quota，模型/semantic显式fixture，不计live。原新增audit同输入真实PG于10:09:52.756839至10:10:03.555879为1fail，原old route audit1/newAsk漏审计0的缺陷证实，原9d needs_changes未洗绿。精确收据在D:/dz16r1/reports/runs/root_batch16_review1_20261017/pg_support及pg_audit_support；Root两固定single-label PS在本run。新Root资源/审计源的actualPG/wheel导入待冻结定向复核。原首PS错误pg_support路径被hashguard拒绝，未注入启动PG；六窗第一次多层PWSH字符串变量提前展开ParserError，未启动PG，直接同shell foreach修正后原6窗全部执行。工具原红保留，未更改任何业务oracle。

9aa风险生产真实5窗13不同为12pass/1setupfail（expired输入违反expires>issued）。唯一作者8125只合法expired timestamp input+直属AST守卫，生产6blob/原Grade/ACL/oracle不变；Root原single target10:15:34.918852至10:15:41.852588 exit0。此前互锁与输入红不删；独审封存最后意见中，不把12+复验1叫同fixture版本14/14。Risk生产尚未导入Root。

新reader b46独审338旧回归passed但原3独立负例failed（critic未绑当次请求/声明；旁边context误拒）；19PG仅collect且新fixture complete_job签名输入问题已发现，未实际执行。Root另派fixer与publisher，不把单测绿当可信reader。

## Source真实状态与问题

actualCORE6b86/OPSf418/helper5e39/bindingbae在09:35门通过后第三次启动；worker12212 birth134366745620895099/beat45736 birth134366745620891064（100ns原整数），authorization各8.251/8.188秒，进入product_import未完成，09:36:17.463555 guardian source_owner_exit，ready timeout。12phase原记录保留，formal6h=false，服务不在运行；guardian第三次报告CPU=18.15625秒，先两次37.6875秒，完整第三次kernel closure仍待新版strict诊断audit，不擅自reset预算。旧preliminary JS snapshot17位birth数字失精度已明确非authoritative，third_launch_precise_identity_addendum.json保存原raw SHA与十进制字符串显示，原core文件/文件名仍身份依据，补充不是ready/closure证明。

新唯一Source诊断实现batch Git23对象29→7进程、严格bounded known pre_ready与owned归档，未装actual；15s/6h/450日志/CPU资源门不改。历史3次失败不是同版本稳定窗口。

## 并行、合同与评分缺口

本时间真实8active包含Root：Source唯一fix、R16 HTTP、R17变化UI、R18插件ports、QA reader新fix、风险原独审、QA publication唯一作者。root独占App/schema/migration/状态/Git/资源秘密；plugin唯一tool_gateway/workflow两shared seam；R16唯一read_adapters；readerfix唯一新generation_requests helper与reader，Runtime委托由workflow唯一owner实施。各WT/固定baseline、PG Root逐窗注入、CBM独占固定cache，Agent slots不等于CPU或物理连接数。

CR-R16_change_history_http、CR-R18_plugin_production_ledger、CR-R18_risk_expired_fixture_interval、CR-R18_task_qa_publication_transaction及原receipt已登记；准确落实仍awaiting independent review。复用PG事实/shared reads/immutable ops/model grounding/同事务，不抬预算、不改Gold/分母/门。新变化UI首summary不能代old/new/detail/双时间；插件真实session/quota/docker/default、任务atomic publisher/default getter、完整多轮多跳/9职责/图谱/重判/后段评测文档仍有内部工作。人工gold0/授权资产范围/CNNVD数据仍外部缺口。G-C未过門，最后已核远端G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7；本批付费模型/测绘调用0，费用unknown。

复用既有服务、stdlib package资源与同一审计端口必要新增；没有新依赖/平行真相库。用户tsbuildinfo原SHA3c587e/push台账/Root-batch13-index和未知文件继续保护。实现写作总时长未单独计；上述测试窗口不称持续采集。下一冻结本checkpoint供原default reviewer真实新wheel/audit/PG定向复验，再接Source修复与风险/变化/插件/任务链路。

修订记录：2026-10-17T10:20:24+08:00首次据实际收据落盘。

修订记录：2026-10-17T10:23:42+08:00 精确替换次数校正为8；新增model purebuilder共享seam CR。
