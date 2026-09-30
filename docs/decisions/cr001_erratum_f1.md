# CR-001 勘误（F-1）· BASELINE_SOURCE_HASH_MISSING 措辞更正

日期：2026-09-30（Goal 第 30 轮）｜性质：**追加勘误文件**，不改写 `docs/decisions/cr001_t06_mapping_and_baseline_hash.md` 原文（该文件已被 RV-FIX 报告以 SHA-256 绑定，改写会使审查版本绑定失效）。
来源：独立复查报告 `reports/reviews/RV-FIX.md` 建议级意见 F-1（非阻断）。
落盘者：主控工程 Agent（文档勘误，不涉及代码、合同、测试与任何批准）。

## 1. 原表述（保留，不修改）

cr001 §3「最小变更与备选 · 逐项旧 → 新」第 3 项与 `reports/tasks/T01.md` 修复附录「P-2 修复」段落称：

> 缺失条目或文件不可读输出 `BASELINE_SOURCE_HASH_MISSING`

## 2. 实测行为（RV-FIX 复查确认）

- 文件**不可读**（无法读取内容计算哈希）时，实际输出为 `INPUT_ERROR`，退出码 **2**，并非 `BASELINE_SOURCE_HASH_MISSING`。
- `BASELINE_SOURCE_HASH_MISSING` 实际覆盖两种情形：
  1. 基线 `source_hashes` 中**缺失**当前被检查文件的条目；
  2. 基线冻结的相对路径**当前不存在**（基线含未知路径）。

即：原表述把"文件不可读"误归入 MISSING 码；正确口径是"条目缺失/路径未知 → BASELINE_SOURCE_HASH_MISSING，读取失败 → INPUT_ERROR exit 2"。

## 3. 影响评估

- 不影响 P-2 修复的有效性结论：N10 篡改场景拦截走 `BASELINE_SOURCE_HASH_CHANGED`（RV-FIX 实测 exit 1）；未改动副本 PLAN_OK；删基线条目报 MISSING；均与实测一致。
- 不影响 cr001 的旧→新值、基线哈希、五项冻结内容未变等核心声明（RV-FIX 已逐项核实属实）。
- 级别：建议级（非阻断），仅措辞精确性问题。

## 4. 处置

- 本文档作为 cr001 与 T01 修复附录的正式勘误引用；后续文档批次引用 P-2 行为时以本勘误为准。
- cr001 与 T01.md 原文保留（历史记录原则）；如未来 CR-001 经人工追认批准后统一修订文档，须一并吸收本勘误并记录修订。
