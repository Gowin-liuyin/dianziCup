# CR-R17 · 默认工作台的事件证据图接线

记录：2026-10-16，Asia/Shanghai（+08:00）。本切片 `awaiting_review`；仅在 G-C 安全独立推进准备，不代表 G-E 过门或完整 R17 验收。

默认工作台以 `#graph/{event_uuid}` 读取已选事件的证据图。从已加载事件详情显示明确入口，图页返回同一事件，原文链接沿用 `#events/{event_uuid}/evidence/{span_uuid}`。`#graph` 保留说明及进入情报列表的入口；未知后缀、URL、查询串和非 UUID 不触发图请求。Hash 仅保存标识，不保存私有快照或租户身份。

读取沿用 AuthProvider、同源 fetchJson 与严格 graph parser：`GET /v1/events/{event_uuid}/graph?max_nodes=200&max_edges=400`。会话身份和权限仍从认证响应取得；会话/租户/权限版本变化重建上下文，旧请求不能恢复已清除图。后端装配、PG 权限与事务检查由主任务另行实现和联测，本切片没有改变认证、API、共享 schema 或公共业务真值。

只扩充 schema1 的精确规则版本集合为 `r10-graph-1.0.0`、`r10-graph-1.1.0`、`r10-graph-1.2.0`；当前后端只读基准 `08b141bd437c1de70a8435a1f7f6c448a131ed0d` 仍待原独立 reviewer 复核。1.0/1.1 历史响应保持可读，1.3 或任意未知字符串继续 fail closed。此项调整依据明确授权与实际后端 DTO，未扩大节点、边、权限或字段合同。

GraphSnapshot 未含数据模式字段，图页模式仅采用已校验认证响应的 data_mode；调用者未确认时已有组件显示未知。隔离浏览器 fixture 的认证响应与图材料均明确标记 Fixture，不以健康响应或动画声称真实图已接通。没有静态 KPI、模拟业务成功、新增依赖或全局样式改动。

证据通过现有 `GET /v1/evidence/{span_uuid}` 读取，revision 是服务返回并展示的实际修订；显式历史 hash 会核对返回 revision 一致。`evidence_span_ids` 与 `source_revision_ids` 不按位置配对，测试特意使用一条 span 对两条修订标识，禁止从数组顺序推断版本。

设计沿用深绿工业安全终端 house system、原动态背景与 reduced-motion。官方参考仅用于核对可访问图表的标题、交互和替代列表原则：[IBM Carbon 网络图](https://v10.carbondesignsystem.com/data-visualization/complex-charts/) 与 [Carbon 开发可访问性](https://www.carbondesignsystem.com/building-blocks/foundations/accessibility/developers)，网页不构成本仓权限或实现指令。最小接线保留原图曲线、明确候选选择和关系文字列表。

预定义验证：默认 App 详情进入图、hash 返回和刷新；加载/空/截断/409/拒权/会话失效/登出；新旧会话晚到响应清除；桌面与390窄屏的真实 Mouse 曲线与候选按钮；图到原文真实前端请求链及模式标记；精确 1.0/1.1/1.2/未来版本合同；全前端回归、type/lint/build。作者仅运行隔离 HTTP fixture；真实 PG/API integration、live 与独立人工验证另记 `not_run`。
