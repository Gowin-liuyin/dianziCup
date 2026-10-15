# CR-R11 · SBOM 私有快照 sidecar 冻结提案

首次创建时间：2026-10-16T06:12:23+08:00
写作开始/结束时间：2026-10-16T06:12:23+08:00 / 2026-10-16T06:12:23+08:00
主控：/root；状态：awaiting_review，仅内部合同，生产迁移 not_run。

依据：用户已批准真实 SBOM、完整资产历史与变化重判。独立纯 adapter 审查确认 projection hash 无法单独代表 dependency/composition 等关系变化；本变更保留这些已要求语义，不增加评分要求。

唯一新增表：asset_snapshot_sbom_sidecars，snapshot_id 为主键；asset_id/tenant_id/snapshot_id 三列外键约束已有私有快照；adapter_version、spec_version、sidecar_sha256、combined_semantic_sha256、canonical_payload JSONB 全必填。两个 hash 固定64位小写hex，版本/租户1–200字符，payload必须object。UPDATE/DELETE触发器拒绝改写，原资产 raw_input BYTEA 仍为唯一原文；不建立新的事实或任务状态。

兼容：既有 snapshot DTO 与 manifest_sha256 保持原 projection 语义，JSON/CSV历史不回填、不重新解析或改hash。新 SBOM current判等使用combined hash，sidecar-only变化必须新增快照、scope epoch和change/outbox；outbox保留 manifest_sha256 并新增 combined_semantic_sha256 与 sidecar_sha256。安全 sidecar 读取用独立接口，不将raw/opaque字段加到旧严格前端DTO。

迁移：生产0022由主控统一，依赖0020/0021后再正式冻结。当前只新增metadata模块，应用不自动create_all，既有0019库不因此声称已迁移。实现者在独占test库forward0019后创建这一局部表，仅计服务集成验证；正式空库/旧资料升级另验收。

回滚：未生产迁移可回退本metadata及依赖它的调用方；生产有历史后不得删除sidecar，仅关闭新增导入，保留读兼容或前向修复。不能只退表而留下调用方查询失败。

任务与测试：R11/T24导入、历史、原文与依赖变化重判；需新增PG真实外键/跨租户/immutable/rollback/replay/sidecar-only变化用例及新独立审查。现静态Ruff/format/mypy单文件通过与DDL/字段/FK assert smoke通过；PG、frontend、e2e、live、manual尚not_run，不签任务或阶段。

定位：修改前实际CBM main5f-assets-sbom-seam 198nodes/823edges，schema/trace与源码rg核对；图未呈现入口调用边，源码inventory_routes直接调用import_manifest已确认，不能据无边推无路径。工具原始输出在本次tool运行记录，未补造未保存的磁盘日志或时间。
