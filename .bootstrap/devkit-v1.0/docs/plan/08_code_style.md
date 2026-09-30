
# 08 · 代码风格与可维护性

这是用户明确要求，不是可选美化：代码自然、见名知意、说明性注释只用文档注释、简洁并适度复用。

## 1. 命名规则

| 不采用 | 应采用 | 理由 |
|---|---|---|
| `data`, `data2`, `tmp` | `source_document`, `normalized_document`, `evidence_span` | 说清对象 |
| `process`, `handle` | `normalize_advisory`, `publish_document_revision` | 说清动作与结果 |
| `flag`, `ok` | `has_conflicting_evidence`, `is_snapshot_current` | 布尔含义明确 |
| `time`, `size` | `request_timeout_seconds`, `response_size_bytes` | 单位明确 |
| `get_all` | `list_current_asset_snapshots` | 说明范围与版本 |
| `Manager`, `BaseService` | `VersionRangeEvaluator`, `SourceConnector` | 只在确有接口职责时建类型 |

允许领域标准缩写，如 `CVE`、`CVSS`、`URL`、`HTTP`、`SQL`；不把普通单词压成 `cfg`、`res`、`mgr`。循环索引可以短，但遍历业务对象使用实际名称。

读函数名应知道是否联网、是否持久化、是否仅计算。`find_...`返回可选结果，`require_...`找不到则抛特定异常；同一项目保持一致。

## 2. 文档注释

Python模块/类/公开函数使用docstring说明必要语义。TypeScript公开接口和非显然的hook使用TSDoc。禁止“先获取、然后循环、最后返回”等逐段叙述性行内注释。

推荐风格示意（依赖类型由对应任务提供，不是可独立运行的实现）：

```python
def find_affected_assessments(
    change_event: ChangeEvent,
    dependency_index: DependencyIndex,
) -> set[AssessmentId]:
    """返回因证据修订或候选范围变化而需要重新验证的研判标识。"""
    dependent_ids = dependency_index.find_dependents(change_event.changed_ids)
    candidate_ids = dependency_index.find_matching_watchers(change_event.scope)
    return dependent_ids | candidate_ids
```

参数与返回类型已经清楚时不重复一页说明；版本区间开闭、租户范围、事务责任等非显然限制应写进docstring。

不要求每个简单getter、私有纯函数、测试函数都有长注释。测试名称与夹具命名要表达行为，不用 `# Arrange / Act / Assert`段落注释。

许可证、机器生成标记、shebang和必要工具指令保留；新加 `noqa`、`type: ignore`或eslint关闭须局部、带审查记录，不能作为类型设计替代。

## 3. 复用与抽象

先找已有实现。相同的范围判断、时间转换、重试分类、权限校验、错误编码只能有一个权威入口。

同一逻辑出现两处且含义相同，可以抽函数；稳定的外部变动点用Protocol，例如来源、模型、存储和时钟。不要因为未来可能有第三种实现就构造五层工厂。

正确抽象例子：多个连接器共享HTTP超时、限流分类和原文保存；各自保留源特有分页和解析逻辑。

错误抽象例子：把公告、论文、资产和政策都塞进 `GenericEntityService[T]`；通过大量字符串开关决定不同业务；为三行代码建四个类。

不复制三套条件引擎给问答、推荐和资产页面。它们应使用同一个 `AssessmentResult`。

## 4. 简洁不等于压缩

函数优先单一职责、清楚的早返回和少层嵌套。建议普通业务函数控制在约60行内、普通模块约400行内，但这是审查提示，不是强制机械拆分；复杂度或语义更重要。

不得把可读逻辑压成嵌套三元表达式、复杂lambda或超长链式表达式。一个明确循环优于难懂的“高级写法”。

不要为“复用”隐藏业务差异。论文前提匹配与软件漏洞版本判定可以共享证据对象，但不得共享会把前提匹配写成已利用的结果语义。

## 5. 类型与边界

API/模型响应使用严格Pydantic模型，未知字段是否允许逐合同声明；模型输出默认禁止多余字段。内部稳定记录用dataclass或明确类型，不到处传 `dict[str, Any]`。

外部原始JSON可以使用受限JsonValue类型，进入业务前必须解析。类型错误不能以cast强压；宽泛异常只允许在最外层转换并保存上下文，不吞掉根因。

一个请求一个数据库Session；事务边界在应用服务，不由每个repository随意commit。时钟和ID生成在基础设施边界注入，测试不依赖睡眠和真实当前时间。

## 6. 测试与前端

测试名如 `test_expanded_version_range_invalidates_empty_result_cache`。只mock外部边界，不mock被测核心判断。期望值由人工审定或独立参考计算，不调用同一被测函数生成。

React按功能模块组织。拆分证据卡片、状态标记、任务进度等真实复用组件；不做万能动态页面渲染器。空态、加载态、失败态、过期态、无权限态与正常结果同样实现。

不使用Any、忽略lint、关闭strict或禁用测试作为“修复”。无实际用途的依赖、空壳类、未调用的工具函数和演示硬编码删除或不创建。

## 7. 审查顺序

先检查业务正确与安全，再检查合同与测试，最后看命名、重复和文档注释。不要在有严重逻辑错误时把一轮时间都用来格式化；但通过任务验收前风格要求同样必须满足。

代码审查至少检查：含糊命名；多余叙述性注释；重复业务规则；过度抽象；不必要配置项；宽泛异常；隐式网络调用；混合租户数据；未运行测试；模型输出被直接当事实。
