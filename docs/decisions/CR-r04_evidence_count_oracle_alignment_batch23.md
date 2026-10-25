# CR-r04_evidence_count_oracle_alignment_batch23

- 文档首次创建时间：2026-10-25T09:46:00+08:00
- 本次写作开始时间：2026-10-25T09:46:00+08:00
- 最后更新时间：2026-10-25T09:46:00+08:00
- 状态：awaiting_review（裁决执行件，依据 progress/DECISIONS_pending.md 裁决②建议项；GOAL 指令授权方式B）
- 关联：`df214c664`（测试冻结时点）；`cb868896c`、`8d48c95ec`、`f3c2e41e3`（CVSS qualifier evidence 链合同演化）；批次21 oracle 对齐先例（codec -1→-2、迁移 head 0026→0031）

## 裁决（引用简报证据）

`test_r04_source_documents.py::test_a_b_a_creates_three_revisions_and_preserves_old_evidence` 对 revision 1 的 evidence 期望由 2 更新为现行已评审合同的确定性输出 4，并按 locator 构成锁定。

- 失败证据：`reports/runs/batch21_integration_unlocked/test_r04_source_documents_pf.txt:13-26`，`AssertionError: assert 4 == 2`，断言点 `test_r04_source_documents.py:254-261`。
- 根因：测试冻结于 2026-10-15；此后产品合同演化使每个 source fact 附带 identifier qualifier 独立 evidence 行。**实测构成**（`reports/runs/batch23_decisions/run2/test_r04_source_documents_pf.txt` 断言消息）：revision 1 = `['/description', '/ghsa_id', '/ghsa_id', '/vulnerabilities/0/package/name']`——2 条主事实 + 2 条 /ghsa_id qualifier。triage 报告"CVSS authority+vectorString"归因经执行核实不成立（vendor 路径无 ScoreValue fact），以实测为准。
- 选项 A（保持 2）被否：需回退已评审的证据粒度合同（逆向变更单，不可逆性高）。
- 选项 B（本 CR）：期望值跟随已入库合同；排序等值断言（4 个 locator 全集）比纯数字更强。该计数是单 revision 的 evidence 行数，不是任何指标分母。

## 改动

1. `backend/tests/integration/test_r04_source_documents.py`：:254-261 的标量计数断言替换为 locator 集合排序等值断言（`/description`、`/ghsa_id`×2、`/vulnerabilities/0/package/name`）。
2. 不改：产品代码、其它断言、该文件其余 24 个用例。

## 验证

- 容器逐文件：`tests/integration/test_r04_source_documents.py`（钉定 run_id=`r04_source_documents_20261015`，port 5432，与 batch21 pf 证据同条件）——1 例从失败清单消失，24 例无回归。
- 宿主定向：`uv run python -m pytest tests/unit tests/contract -q --no-cov -k "source_documents or evidence"`。
- 全量回归：backend 离线全量 failed 仍为 0。

本次写作结束时间：2026-10-25T09:46:00+08:00
