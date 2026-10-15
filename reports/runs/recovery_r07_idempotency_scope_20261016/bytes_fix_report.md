# 原始材料字节归档修正

本修正由主代理明确授权，只在本 run 增加局部 `.gitattributes`：`* -text` 保留原材料字节；pytest `.log/.xml` 仅关闭数据尾空格判断；`nvd_regression_observation.json whitespace=cr-at-eol` 只认可该原始 CRLF 文件的 CR 行尾。未改根/全局 attrs、其它 run、业务 source、原始日志/JUnit、既有 manifest SHA 或原红计数。

代码仍冻结 `ba69d6cbc2bc4828a56bdc8c7d2f2c95c4dda5ce`。材料提交 `a92cc7c64592a06a00317e0ae2887124d3c51141` 可能在 Git core.autocrlf=true 下存入 LF 转换后的 blob；本提交从未转换的本工作树原 bytes 重新 stage 明确列于原 manifest 的本 run 文件。baseline_job_service.py 必须保持原 e61 Git raw blob SHA256 `13dd4cfe22ab590bcf74483656d7ef1c9eb745f0bc02909d0876029b5a1daa5e`，不能 trim 红日志来规避检查。

原 `raw_manifest.json` 路径和 SHA256 保持 `reports/runs/recovery_r07_idempotency_scope_20261016/raw_manifest.json` / `2dbdad200695ea322ab104548f068c2fdd86f42d2abc80fb76139d6c3ab1826a`。新增 bytes_fix_manifest 单独记录 stage blob/raw-byte 比对、局部 attrs、命令真实起止秒与 exit；未知历史 bootstrap 时钟为 null，不能推定通过。原 manifest 不自引用本新增材料。

原 manifest 的 53 个材料行含 5 个未入 Git 的生成 `.pyc` 缓存；它们的历史行及 SHA 保留，当前归档明确为 `excluded / not_Git_verified`，不读取、复制或强制提交缓存。其余 48 个原路径逐项检查 Git blob 与原 raw SHA，其中本 run 46 项按原 manifest 的明确文件列表重新 stage；任务报告和 CR 的 2 项只核验，不改字节。代码与测试证据不依赖缓存。不能将 60 行（含 7 个源文件）全部表述为 Git raw-byte 一致。

原业务源文件在 Windows 工作树包含 CRLF，代码 blob 以原 manifest 的 `lf_sha256` 与冻结 `ba69` 核验，不能用材料归档规则重 stage 业务源。新增材料、旧 manifest 和 fingerprint 另列实际 Git blob/raw-byte 比对。`source_diff`、`source_unchanged`、`material_staged_diff` 的真实退出码见新 receipt；本轮实际敏感值扫描另写新 JSON，不覆盖旧扫描结果。测试计数仍为 unit6、contract2、PG16、security8、regression33；baseline red30pass/2fail，早期29pass/3fail仍保留。live/e2e/manual 未运行，外网/付费调用0、费用unknown。
