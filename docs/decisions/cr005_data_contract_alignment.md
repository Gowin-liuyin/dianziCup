# CR-005 · 03 数据合同字段对齐（T05 审查 M4 处置）

日期：2026-09-30（Goal 第 78 轮）｜性质：合同偏差处置记录｜来源：R-T05 审查 M4（reports/reviews/R-T05.md）。

## 已完成对齐（迁移 0002）

| 原实现 | 合同 03 §3 | 状态 |
|---|---|---|
| document_revisions.revision_index | revision_number | 已改名 |
| document_revisions.supersedes_id | previous_revision_id | 已改名 |
| 缺 TextBlock | TextBlock（块/哈希/区间） | 已建表 text_blocks |
| evidence 缺 block_id/quote_sha256/verified_at | 引文一致性字段 | 已加列并在 attach 校验 |

## 分期对齐（本单保留现结构, 后续任务补齐）

| 偏差 | 合同要求 | 归属 |
|---|---|---|
| 单一 content_hash | raw_object_key/raw_sha256/normalized_* 分离 | T07+ 随规范化管线 |
| evidence.supports_claim bool | ClaimEvidence.support_kind(supports/refutes/context)+validation_status | T08 论断管线（三态语义, 消除布尔化削弱未知≠否定） |
| 缺 parser_version/parse_status/is_synthetic/material_change | 解析元数据 | T09 解析任务 |
| 缺 documents.source_record_id 与 source+source_record 唯一键 | 03 §4 | T08 抓取管线 |
| fetch_attempts.new_event_count | 合同无此字段 | T08 收敛为 contract 字段或删除 |

## 理由

R-T05 认可两条路径：向 03 靠拢或走变更单留痕。命名与结构性问题已即刻对齐；其余字段与业务管线（规范化/解析/论断）强耦合，属对应任务范围，提前批量建列会违反「不创建与本任务无关的未来模块」。本单明确偏差清单、归属与验收口径：对应任务落地前，相关评分证据不计入，未知≠否定。