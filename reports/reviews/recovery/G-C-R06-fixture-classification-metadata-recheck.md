# G-C · R06 fixture 分类元数据定向复核

文档首次创建/本次写作开始/结束/最后更新时间：2026-10-15T23:11:00+08:00
独立审查者：/root/r06_integrated_live_validation，未实现此分类表。

What this change does: 核对主控 415ee580258ce55b8771c4fc4d070c3a8e78aea0 的三条精确分类是否准确落实 d3e175… 独立意见，并保留原 1156 的 51 条历史记录。首轮独立报告原字节/hash 未改。

结论：Ship（仅 classification 元数据）。strict duplicate-key JSON 读取通过；原 51 条记录逐对象完整相同；新增 3 条 path/raw SHA256/pattern SHA256/LF start:end/value SHA256 均与 fixture_origin_audit.json 相同；source commit 对应 blob、fixture source path 和 review_ref 真实存在且一致。未修改分类、scanner、业务、阈值或状态。完整脱敏 receipt 见 ../../runs/recovery_r06_integrated_live_20261015/classification_commit_audit.json，脚本 audit_classification_commit.py 可复跑。

实际命令：D:/wt/r06-integrated-live-1156/backend/.venv/Scripts/python.exe -B reports/runs/recovery_r06_integrated_live_20261015/audit_classification_commit.py；cwd D:/dianzi；exit0（本脚本所有断言通过才写本结论）。未重跑 34 fixture/全纯测试；主控已保存的原安全 42 passed 是其执行证据，不冒称本审查实际重跑。后续 1a52e17 的原 log -text/-diff 保全不在本次分类逻辑范围；实际 source/browser live 仍固定 1156。

Verdict: Ship（仅上述元数据一致性）。Not checked: 全阶段、秘密全集和后续产品变化。
