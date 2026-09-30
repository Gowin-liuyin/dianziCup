# RV-T10 · T10 独立快审

结论：**T10 = accepted**

## 1. 复跑命令与退出码

| 命令 | 结果 | 退出码 |
|---|---|---|
| `uv run pytest tests/contract -q --cov-fail-under=0`（backend） | 13 passed（13/13，0.19s） | 0 |
| `uv run mypy src`（backend） | Success: no issues found in 27 source files | 0 |

## 2. 三断言抽查

① **CVE/NVD 分立实现且多来源评分并列保留（非只留最高分）——通过。**
- 分立：`cve.py` 与 `nvd.py` 为独立模块，各自 dataclass（CveRecord/NvdRecord）、独立 schema 版本常量（cve-schema-1 / nvd-schema-1）与连接器名/版本，normalize 逻辑互不共用。
- 并列保留：CveRecord.scores 为 `tuple[tuple[str, float], ...]`，逐条追加所有 metric 的 baseScore（cve.py:52-61），无 max/取最高分逻辑；NVD 同理遍历 metrics 字典全部条目（nvd.py:52-59）。C01 断言两侧同时保留 {"cvssV3_1": 10.0, "cvssV2_0": 9.3} 与 {"cvssMetricV31": 10.0, "cvssMetricV2": 9.3}，且 weaknesses 一并保留。

② **rejected 独立、缺字段记 missing 不编造、429 有限重试后明确失败——通过。**
- rejected：state 从 cveMetadata 如实透传（cve.py:40），C05 断言 REJECTED ≠ PUBLISHED，不折叠为活动漏洞。
- 不编造：缺容器/描述/评分/日期分别记入 missing_fields（containers、containers.cna、description、metrics、datePublished、dateUpdated），published_at 取 None 而非空串/默认时间（cve.py:69-78）；C04 断言 scores==()、published_at is None、missing 含三项。缺 state 时为 "UNKNOWN" 哨兵（未知≠否定），不冒充 PUBLISHED。
- 429/假成功：fetch_with_rate_limit_guard 恰好 3 次尝试（MAX_RETRY_AFTER_429=2 重试）后抛 NvdUnavailableError（nvd.py:82-93），非 200 亦抛错；discover_cve_pages 遇 429 直接 ConnectorContractError，超页数上限报契约错误（cve.py:91-110）。C06 断言 attempts==3 且异常明确，任何路径不返回假成功。

③ **fixture 明示脱敏合成、live blocked 如实登记——通过。**
- fixture 顶层 `fixture_kind: "recorded_desensitized_synthetic"` + note「合成脱敏样本, 非真实响应副本; 真实接口字段核验因环境 DNS 阻断记 blocked」。
- reports/tasks/T10.md §3/§5 如实登记 live=blocked（DNS 解析为非公网地址）、真实接口字段/分页核验=not_run，未以 fixture 冒充 live。

## 3. 边界说明（不影响结论）

- 真实 CVE/NVD 接口字段、真实分页规模、真实 429 重试均 not_run（live blocked 如实登记），结论仅覆盖离线合同语义。
- 多来源评分为元组并列保留；测试用 dict() 比对仅取断言视角，实现本身不折叠重复来源键。

## 4. 未查项

- unit/integration/security 全量回归、ruff、真实语料 live：本次快审范围外，not_run。
