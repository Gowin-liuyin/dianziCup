# CR-R11 · 精确生态版本比较的成熟依赖

状态：awaiting_review；主控批准准备实现，独立审查未发生，不代表R11/G-D放行。
建设依据：已批准CR-R01–CR-R09与R11/T26要求复用成熟生态比较，不新增评分/盲测变化。

## 变更与必要性

packaging 26.3原已锁定为传递依赖，新增直接声明>=26.3,<27；新增semver>=3,<4并锁3.1.0。
只新增semver一个包，现有包版本不变。PyPI精确PEP440与严格SemVer需要不同语义，避免自制排序；
不提供任意npm范围解释或git提交祖先工具。无凭据、无付费API或大模型下载。
官方依据：[SemVer精确比较](https://python-semver.readthedocs.io/en/latest/usage/compare-versions.html)、
[packaging版本处理](https://packaging.pypa.io/en/stable/version.html)，2026-10-16读取。

## 兼容性、迁移与回滚

Python3.12与现有依赖主版本不变；只更新backend/pyproject.toml和uv.lock，安装按uv sync --locked。
无数据库或旧事实迁移，现有公开VersionAssertionValue/VersionInterval不变。
回滚需撤销本依赖声明并同步撤下直接使用semver的新比较模块；不能留下运行时缺包。
历史研判与证据不删除；后续规则版本变化保留历史，未知/回补/git不转为确定安全。

## 任务与测试影响

R11/T26内部比较器先准备，正式依赖R07/R10接线与资产快照不越门。
函数必须要求package_key/ecosystem/scheme一致；完整性默认未知，fixed右开/last_affected闭、
预发布、多分支、回补、部分范围、非法版本与缺版本全部有正负例。原分母与阈值不改。
此提交只提供依赖，规则/PG/资产API/frontend/live/manual均not_run，由新独立reviewer审核完整批次。

首次创建时间：2026-10-16T01:30:32+08:00
记录人：/root
