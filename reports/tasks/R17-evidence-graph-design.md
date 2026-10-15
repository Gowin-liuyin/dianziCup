# R17 证据图研究与设计（实现前）

记录日期：2026-10-16（Asia/Shanghai，+08:00）。基线 `8a1b04d48346d8550f0326a77f003246a0ebbab5`；独立工作树 `D:/wt/r17-graph-ui`，分支 `codex/r17-evidence-graph-ui`。该切片为 R17:T41/R10 可点击图的前端能力，完整 R17/G-E 不据此验收。

已读 AGENTS、00执行图、R17/R10恢复卡、T40/T41、03/05/06合同、当前任务状态与交接；现有事件详情、EvidenceInspector、auth-session、fetchJson、App 与暗绿 tokens。后端 DTO 以 `D:/wt/r10-pg-graph/backend/src/ai_intel/knowledge/evidence_graph.py` 为材料，路由实际位置为 `api/graph_routes.py`。后端 P1 修复尚在复核，本切片不能计为真实接通。

## 实际产品研究

1. [OpenCTI Pivot and investigate](https://docs.opencti.io/latest/usage/pivoting/)（实际读取官方页面）：实体/关系选择与右侧详情联动；扩展会使关系密集，需要明确上下文。本轮借选择和检视的布局，不实现未经合同提供的扩展、撤销、写关系或导出。
2. [Graphistry UI Guide](https://hub.graphistry.com/docs/ui/index/)（实际读取官方页面）：画布、选择工具和数据检视分工；底层表可选中相应图元素。本轮借有界工具栏、图与关系列表双向选择，不使用其 GPU/远程服务，也不冒充百万节点性能。
3. Neo4j 官方资料搜索返回 Bloom 场景、分类图例与地图的介绍；直接打开两个推测地址未成功，不将未读页面当设计依据。初始 Graphistry tutorials 地址同样不可访问，随后取得上列官方 UI Guide。共3次只读 web 调用（2 open、1 search），没有下载图像、登录或付费。

用户 `E:/wechatData/xwechat_files/wxid_c14weta2ez6m22_03f5/msg/file/2026-10/ui-design.md` 仅作为审美材料。采用微网格、类型形状、关系检视；其时间滑块、跳数、隐藏邻居、置信度、Critic、PNG/STIX 没有冻结输入，不生成对应按钮或假数值。Ponytail 5.2 full 采用现有 React/native CSS/SVG，不新增库；Industrial Brutalist UI 只取 Tactical Telemetry 网格与终端排版，沿用现有暗绿品牌，不套红色重品牌、巨大营销标题、伪随机遥测或背景重写。

## 冻结输入输出和取舍

输入：同源 GET `/v1/events/{UUID}/graph?max_nodes=200&max_edges=400`，schema1，六节点类别、六关系类别、PG业务版本、规则版本、hash、unknown gaps、truncated。严格解析所有字段、UUID、scope、端点、重复标识及数组上限。status只接受 supported/unknown，不前端推断事实。错误401/403/404/409/503独立文案；错误、换事件、换会话/权限时清除旧图，迟到响应无权恢复内容。

输出：`GraphExplorerView({eventId,onNavigateBack?,dataMode?})`；dataMode默认unknown，fixture调用者必须显式传fixture。只在 `frontend/src/features/graph/**` 新增源码与测试，外加专用 fixture e2e 与本报告/run；主控唯一注册 App/路由。

采用六列确定布局，节点每类排列，初始画布有界滚动而非随机力导向跳动。200节点/400边无需额外布局依赖；选中边突出端点，其他线低亮。六类类型用形状、文字和颜色共同表达；图内简短标签，完整原文标签留在右栏。类型筛选只改变视图，明确显示“当前视图/快照”数量，不能误称资产/风险数量。提供缩放、重置、四方向平移和原生滚动，键盘 Enter/Space 选择节点/边；关系列表提供另一条完整键盘路径。

右侧显示关系类型、方向、完整节点标题、reason、rule/model version、scope、全部 supporting_claim_ids、source_revision_ids、evidence_span_ids。现有 EvidenceInspector 私有且无图数组配对映射，复用 `#events/{event}/evidence/{span}` 固定路由，不zip猜revision，也不打开DTO提供的任意URL。证据服务返回实际revision；支持claim不是引文语义核验的替代。候选/待审状态没有提供，明确说明不在当前supported快照中，不能声称已全部审查。

unknown及truncated在图上方/侧栏单独说明，根节点无边视为“仅事件、尚无支持关系”，不显示无风险。业务版本/hash可展开核查，不将来源统计解释为受影响资产。局部动效只有边/节点短过渡，尊重prefers-reduced-motion；背景由现有shell负责。桌面1366和390窄屏控制目标至少40/44px、文字/焦点可见，窄屏画布独立水平滚动，页面自身不溢出。

## 预定义检查与边界

先写解析/client和选择/清除回归，再实现。合同/安全：六类、缺口、上限、跨ID、scope、重复/悬空端点、额外字段、非法状态/URI注入输入、错误不变空结果。组件：loading、root-only、部分gap、选边/节点、证据路由、撤权、401/403/404/409/503重试、迟到响应隔离。前端：typecheck/lint/build及现有相关回归。独有Vite25488/Edge fixture：1366/390、键盘、证据打开、reduced-motion、200/400合成数据可操作与记录耗时；禁止复用用户CNNVD tab。真实后端集成/live/manual验收保持not_run。

CBM使用官方portable actualcli，Ubuntu-22.04 root、自己的frontend/src索引、独立/tmp cache、persistence=false；读取schema/architecture/trace，TSX支持范围如实记录并以rg核对调用者。npm使用本WT锁文件离线安装；不改依赖/公共合同/认证/全站样式/进度/后端。
