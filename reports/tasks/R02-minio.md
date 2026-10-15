# R02 · MinIO原文存储冻结切片

文档首次创建时间：2026-10-15T11:24:08+08:00
本次写作开始/结束/最后更新时间：2026-10-15T11:24:08+08:00 / 2026-10-15T11:24:08+08:00 / 2026-10-15T11:24:08+08:00
主控实现：/root；状态awaiting_review；实现partial；整R02/G-A未验收。代码冻结60fe4c311f98a0692e2207b884d83b676f5fb9c2，前置9a696b7；没有push。

## 范围与实现

R02/T05的对象适配切片，复用现有PG内容对象/修订/父行锁/事务、SHA256接口和官方MinIO SDK7.2.20；新增最小ContentStorage协议、可信配置工厂与远端实现确有两种IO语义，未重写知识层或建立第二事实库。原StoredObject内部Path接口保留，远端只返回hash/size。固定bucket、哈希键、限64MiB和超时、TLS默认严格、无SDK重试、先读验hash/再写/写后验证才登记PG，缺失与拒绝/网络/服务错误分开。settings选minio配置不全就启动失败，不能悄悄回退本地。工厂已在真实PG修订测试调用；默认API/worker业务仍未接入，R03/R04继续完成，不能以测试路径冒称产品闭环。

## 实际问题和验证

- 初次unit SDK错误样本用了不符真实S3Error签名的fixture，124passed/1failed；按真实SDK签名修fixture，125passed/cov62.70%。原unit_first/unit_sdk_error_fixed日志和XML保留，未把失败skip。
- 加配置工厂后纯unit135passed/cov63.21%，原60门未降；该命令起止未单独捕获，JUnit原始工具时间保留，不能拿文件mtime编造。mypy57源exit0；Ruff首轮6项、格式后3项已修到exit0，静态完整记录待冻结复跑。
- 真实隔离PG r02_knowledge_20261015+MinIO测试bucket：11:19:13–11:19:34，`uv run --locked pytest tests/unit tests/integration/test_r02_minio_persistence.py tests/integration/test_r02_knowledge_revisions.py tests/integration/test_r02_relation_identity_regressions.py --junitxml=<private temp> -q`，172passed/0failed/0error/0skip，cov74.13%，1warning保留。包含独立进程新客户端、A→B→A三版、新PG连接、rollback不发布、真实对象损坏拒绝覆盖、真实拒绝与missing分别、存储断线不提交、两线程同版。cwd D:/dianzi/backend；实际参数和原始计数见real_first.command.json/log/xml。原始JUnit暂存仓外指定秘密目录；在内存精确脱敏后只把脱敏副本写reports，临时原件已删除。
- 自有原文服务实际重启11:20:29–11:20:31，PID4244→18956，同hash读取字节一致，见restart_verification.json与两个service_segment收据；不是mock、不是全系统备份恢复，也不是正式性能数字。

## 资源和限制

官方Go下载checksum、构建固定模块/Go sums、真实二进制hash均见本run。实际server源码v0.0.0-20251015172955-9e49d5e7a648，Go1.27.2构建二进制自报DEVELOPMENT.GOGET，不能冒称发行包；官方仓库归档维护限制保留。SDK新增pycryptodome/urllib3用于真实S3签名/HTTP，未替换整栈。测试只有root身份、明文loopback、独立bucket；产品TLS/最小权限/部署镜像与备份、旧本地对象迁移尚未验证，不能称production可用。resource上限、7200秒截止、实际启停时间见service收据；无付费API，模型费用unknown。

## 验证分层与下一步

unit=passed（本切片135）；contract=not_run（新配置边界在unit）；integration=passed（真实资源172混合范围）；security=not_run（专门审查尚未发生，含部分边界不替代全层）；frontend/e2e/live/manual=not_run。新独立review应冻结60fe4c3并复跑关键7个MinIO/PG案例、坏凭据/损坏/回滚；顺带核对已集成33423b4/8015ac0/9a696b7的初审Must修复和原生失败隐私，不能只读作者日志。整R02仍需维度持久化、发布幂等/重放与最终独立结论。

本报告结束：2026-10-15T11:24:08+08:00。真实未来审查、提交、push时间必须另记，不回填此时尚未发生的结果。
