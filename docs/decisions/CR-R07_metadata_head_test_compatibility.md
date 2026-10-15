# CR-R07 · 前向0019后元数据测试兼容

首次创建时间：2026-10-16T06:26:27+08:00；主控/root；状态awaiting_review。
独立审查固定1b在真实forward0019运行原20元数据用例，19pass/1fail：唯一失败是原测试硬编码head0017，实际0019_aggregate_observations。原20自检确在pre0019运行，不能据原记录宣称最终SHA20通过。审查原红由reviewer保存，不改它。

仅修改test_r07_enrichment_job_metadata_pg.py的installed revision检查：要求真实PG installed等于当前冻结Alembic head，并要求0017在真实祖先链。原19约束/并发用例、输入、业务表、迁移、指标/金标/阈值均不变。这样保留必须已经迁移0017的验收，并允许已批准的0018/19前向链。不是任意revision或不存在数据库通过。

真实同原20测试于current0019重新运行20/20，原报告/manifest1b原bytes保留，新证据另run。生产业务代码与1f0522完全相同，只有测试兼容变更；无需数据库迁移，回退仅回退本测试会恢复已知false failure。需原独立reviewer检查新diff并亲复跑20，root不自签。
