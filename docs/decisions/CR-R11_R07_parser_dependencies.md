# CR-R11/R07 · SBOM 与分类目录必要依赖

首次创建时间：2026-10-16T05:54:42+08:00
写作开始/结束时间：2026-10-16T05:54:35+08:00 / 2026-10-16T05:54:42+08:00
主控：/root
状态：awaiting_review；不代表任务或阶段验收

目标与依据：用户已批准真实 SBOM、九维富化和成熟依赖。复用 Package URL 官方 Python 实现解析 purl，复用 PyYAML SafeLoader 读取 MITRE ATLAS 的固定版本 YAML；不实现自制编码或 YAML 解析器。类型 stub 用于严格 mypy 检查，不全局忽略第三方类型。

变更：生产直接依赖 packageurl-python==0.17.6（原未安装）、PyYAML==6.0.3（原为 semantic 间接依赖，现提升直接）；开发直接依赖 types-PyYAML==6.0.12.20260906。本次锁文件原 93 包版本全部保留，仅新增上述 purl 与 stub，现 95 包。仅修改 backend/pyproject.toml、backend/uv.lock，业务调用方由各任务独立实现和审查。

兼容：Python 3.12；原环境配置、数据库 schema、API、指标分母和金标无改变。基础生产安装可读 YAML，不再依赖 semantic extra 恰巧安装它。Package URL 与 YAML 使用输入大小、深度、重复键和类型边界由相应业务模块负责。

迁移：uv sync --project backend --frozen --all-extras；生产按现有部署方式安装冻结依赖，不执行数据库迁移、不下载新模型。现有 PyYAML 版本没有升级。

回滚：只回退本变更的 manifest/lock 并按旧 lock sync；在 SBOM/taxonomy 调用方集成后，需连同依赖该库的调用方回退，不能留下导入失败入口。无业务数据删除。

任务影响：R11/T24 SBOM adapter 与 R07 分类目录输入需要本依赖；不减少任何验收范围。尚未接线的模块和高密度组件容量缺口不因此通过。

验证：四条命令 exit 0，真实 purl/SafeLoader/安装版本 smoke 通过；业务测试未运行。本机最初 purl add/sync 已执行但未记录完整起止，历史未记录；本次记录从 2026-10-16T05:54:35+08:00 起算，不补写旧时间。详见 reports/runs/recovery_r06_integration_20261015/sbom_taxonomy_dependency_receipt.json。

官方依据：[Package URL 0.17.6](https://pypi.org/project/packageurl-python/0.17.6/)、[PyYAML 6.0.3](https://pypi.org/project/PyYAML/6.0.3/)、[types-PyYAML](https://pypi.org/project/types-PyYAML/)（6.0.* 类型）。包下载费用 unknown，无产品模型或测绘调用。待各切片的新独立 reviewer 核对实际调用与边界。
