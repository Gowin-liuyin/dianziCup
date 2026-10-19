# 0023–0026 正式 CR 文档补核

What this change does: 本附录只核对 root 后补的完整性加强 CR 是否准确描述已经审查的 0023–0026 迁移。原冻结代码结论仍为限定 Ship，原报告和 manifest/raw 均未修改。

被审文档：`D:/dianzi/docs/decisions/CR-recovery_0023_0026_integrity_guards.md`，当前未提交；读取时 root HEAD=`17ab90e0a6b100530a3078dd525f9086813c9728`。文档 raw/LF-view SHA256=`eea6e883397f8f42383fd35807ed403896b6de0e4c6d403d9432aca48c50424e`。本补核不把该 root 工作区或未测 draft 解释为已审 source。

核对仍固定迁移 source=`16484eaca45791ed2ec403471561faa10ab6d036`、材料 `2a833225bc5f2dfc720219d6765b034bd6bd6288` 与九项 approved_guards。脚本只读 Git 对象/文档，不连接数据库、不运行 pytest。实际命令 `D:/dianzi/backend/.venv/Scripts/python.exe reports/runs/recovery_forward_migrations_review1_20261016/cr_appendix/audit.py`，cwd=`D:/wt/recovery-forward-migrations-review1`；2026-10-16T10:28:23.824271+08:00 开始，10:28:24.402446+08:00 结束，exit 0；测试数 0，PG 连接 0。原文 raw 和 zip、精确 guard SHA、metadata Git 字节及收据在 `cr_appendix` 子目录，不追溯纳入原 manifest。

文档应修 1 项：**第 10 行“当前与作者1e210090 metadata guard已对齐”范围过宽。** 实际 `1e210090d74d1444101330f0c8b8637ad1dd50a3` 的 conversation_models 第 124–137 行包含完整 turn 不可变 function/trigger，规范化 SQL 与迁移一致；该文件没有固定 search_path 的 DDL。固定迁移 `0024_conversation_context.py:109` 则包含 `ALTER FUNCTION qa_validate_turn_ownership() SET search_path FROM CURRENT`，这仍是 migration 相对于作者 metadata 的额外加强。若保持当前笼统说法，会让后续 metadata-only 建表/反射被误认为具有完整相同 guard。

最小修订：将该句改为“完整 turn 不可变函数/触发器已与作者1e210090 metadata 对齐；查询函数 search_path 固定仍为生产迁移的显式加强差异”。这只是文档限定，不要求改历史 metadata、迁移或原 tests。复核标准是修改后第 10 行明确区分这两项，不再声称全部 guard 对齐。

其余内容匹配已审事实：九个 guard 的精确 statement/hash 全匹配；0023 nullable/旧行及有 receipt 的 DELETE 禁止、0024 deferred owner/NULL tenant 与合法 conversation/answer 更新、0025 batch 实核 SHA256/不可变但 state 可变、0026 保持冻结 key/rate schema、前向顺序/旧数据保留/拒绝 downgrade 和应用关闭入口回滚一致。CR 如实声明正式记录晚于实施，保留旧 head 红、材料 whitespace 红和首轮子日志复用缺口，也没有把 IO 前限流、current-auth/async ActorRef 等后续接线义务登记为本次产品验证。

文档结论：**修订第 10 行后可登记描述匹配；原迁移限定 Ship 不受影响。** Not checked: root main 集成、1e210090 完整应用行为、任何新 PG/live/客户端测试均未检查。资源此前已释放，本补核未重新占用 PG slot；未提交、push 或修改 accepted/progress。
