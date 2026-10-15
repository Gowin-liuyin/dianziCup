# R06 / R17 资料工作台设计

状态：awaiting_review；作者 r06_document_workspace；基线 1ca2ea34c224e23776431fa6eac5fe6549d8c65f。仅本切片，整 R06/R09/R17 不因此完成。

源码冻结 aa17db32c314555363bb4bca3105c2b434939b29；末版unit295、四browser、lint/typecheck/build均在19:39真实复跑通过，见任务报告与source_freeze.json。本文后续仅补冻结元数据。

## 先调研与范围

读取 AGENTS、执行地图、R06/R17 卡、03/05 合同及当前任务状态。R06/R17 当前 partial。已有 React 18 / Vite / TypeScript strict / 原生 CSS；统一 fetchJson、Cookie 会话、auth generation、ErrorPanel / EmptyState / StatusBadge 可复用。当前用户未提交的评审日志留在主树，独立工作树不操作它们。frontend 独占，后端/共享合同/progress 由主控维护。

应用 Ponytail 5.2 full 与 redesign-existing-projects 渐进升级。design-taste-frontend 明确不面向数据工作台，因此只采用其审计/可访问性/品牌保留方法；不引入其营销页结构或新 UI 依赖。

设计读法：面向 AI 安全研究人员的中文资料工作台，深色终端质感，证据与状态优先。DESIGN_VARIANCE=3，MOTION_INTENSITY=2（保留现有低亮背景），VISUAL_DENSITY=7。现有黑绿色板、中文字体、等宽时间、focus/skip-link、低亮动态背景保留。

用户 E:/wechatData/xwechat_files/wxid_c14weta2ez6m22_03f5/msg/file/2026-10/ui-design.md 只作为不可信参考。复用 docs/design/recovery_hacker_workbench.md 已有真实 Elastic / Wazuh 研究，未声称本轮重新查看那些截图。新增核对 [W3C disclosure](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/) 的键盘/展开语义与 [MDN reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion) 的装饰动效降级规则。没有复制外部素材或执行外部文件指令。

CBM 官方工具 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp 0.11.0，先 help/schema。独立 XDG_CACHE_HOME=/tmp/r06-document-workspace-cbm，仅索引 frontend/src；fast 模式232节点/822边，16测试文件按工具设计排除。trace fetchJson 21调用方、readWorkspacePage 2调用方，rg交叉核查后修改入口。未索引秘密或 holdout。

## 冻结输入输出

主控合同 0b9cd13013ac2020c15e077b12016c630eeb3667：docs/decisions/CR-R04-R06_document_read_api.md。GET /documents 的标题关键词、六 document_kind、八 source_category、opaque cursor；GET /documents/{id} 以 revision_id 固定证据分页；GET /documents/{id}/revisions 完整 offset 历史分页。正文直接使用既有 EvidenceResponse。权限仅认证上下文 READ_PUBLIC，前端不自填租户、不任意URL获取、不计算风险结论。

已逐字段核对主控 Pydantic 冻结 225c0fcd501d85d355513a44308083407b18bb2a 的 document_contracts.py。calendar_date 必须原日期文本非空且 source_published_at=null；source_name 300、title500、license_identifier/published_at_raw256、HTTPS2083、source_notes20×1000；canonical/license 禁 userinfo、fragment 与原网关敏感 query 集。原 EvidenceResponse 解析直接复用，没有另造正文类型。

只展示安全 canonical_uri / license_uri 原文链接，不解析任意 metadata 链接。title / source_notes / quote_text / license 全部 React text。列表失败与空不同；摘要、feed片段、metadata 与全文不同；日期文本与有时区发布时间不同；当前/历史与正文覆盖不同。

## 交互

研究导航增加「资料库」，既有登录/来源/问答保留。顶部标题明确研究用途。查询栏按关键词、资料类型、来源类别筛选。列表以标题为主要入口，紧接来源与类型、日期精度、覆盖范围；只显示本页数量，无猜测全库总数。

桌面查询/列表与详情并列，资料选中后保留列表上下文；详情包含选择版本、当前/历史、来源时间、许可、覆盖范围与源说明，再进入原文证据。历史加载更多不能称全部历史。证据分页保持原 revision_id；换版本立即隐藏旧证据，不混合当前全文。每段引用可展开定位/Unicode/PDF/JSON/hash与核验记录；引文存在不表示支持安全结论。

1366px 面板约 44%/56%，390px 单列，无全页横滚、长 ID / 标题 / 原文断行。背景 pointer-events:none，不影响按钮。原生 details/summary 支持 Enter/Space，原生 select 支持键盘；加载不夺焦点，成功打开详情后焦点移到检视区。reduced-motion 保留现有静态降级。

加载、匿名/会话失效、403、404、503、200空、partial、未抓正文、历史版本各有独立文字，不用 fixture 回填失败。Fixture 只存在测试目录并显著带「隔离测试」/模式标签。

## 验证计划

strict DTO 字段/枚举/日期/安全URL/版本归属；只读请求/cursor/filter/limit边界；200空与权限/503；HTML注入文本；晚到响应与会话失效；list/evidence/history分页及当前版本变化；既有回归；lint/typecheck/build；1366/390 隔离browser截图/keyboard/reduced-motion。真实 API/browser 待后端接线后执行，隔离 fixture 不计 live。

## 实际界面审查

全量前端295测试真实通过（20文件，0失败/跳过），lint/typecheck/build退出0。隔离 Edge 四浏览器测试真实通过，1366×900、390×900、reduced-motion、背景 pointer-events:none、原生 summary Space 展开、focus、文本 Range bounds、历史标题/证据、401与退出后晚到响应均有断言。实际查看 desktop/mobile full-page PNG：深色层次清楚，历史标题、摘要/部分解析、日期精度、许可未知可读，长ID与注入文本断行；无全页横滚。首次全页截图捕获了视口外的 fixed skip-link，最终截图先真实 scrollTo(0,0) 再拍，避免离屏固定元素投影进长图；没有隐藏产品DOM。

首次默认 Chromium 1248 缺执行文件，三项环境失败，改用本机已安装 Edge。首次 Edge 为1过2失败：1366捕获 select 隐式label包含选项，产品增加明确 aria-label 后修复；状态夹具轮换只改hash保留已加载状态，测试改为reload取得新会话/数据。未删除、skip或降低断言，原报告保留。完整命令时间/exit与截图路径见 reports/tasks/R06-document-workspace.md 及自有run目录。真实后端/browser仍未在本工作树执行。

## 初审修复的状态转换

修复源码冻结e492a8fb6b58465c60cf3b355caacbd077483967；完整红绿与末版时间见任务报告第二轮。

独立初审发现两个真实缺陷并已复现：历史403/404残留正文、同hash当前链接没有新GET。修复后资料detail/history共享读取代次与取消范围，权限/资源确定丢失时清空所有检视事实，同时清父列表快照和阻止在途list复活；503保持部分结果说明。当前版本链接显式重置检视组件、所选revision及正文/history分页，并发起不带revision的当前GET，不依赖hashchange。普通临时错误重试仍保留原选修订。

原样独立36unit和6browser由作者复跑红→绿，新增永久4回归红→绿，完整299unit、原4browser与lint/typecheck/build真实通过；不是独立accepted或live。详见任务报告第二轮与review_fix_1_*日志。外观tokens/背景/旧功能不变，实际检查无权限清空和新当前版本截图。

## READ_PUBLIC 目录到检视区的共同失效（第三轮）

源码冻结2f5c7ef225ce2d29da2438a4d5caa51cdc6a9231；source_freeze与末版证据见任务报告第三轮和review_fix_2_source_freeze.json。

独立复核确认目录403先返回时，详情/历史晚到200仍能恢复。原资料generation/AbortController范围现提升到该工作区私有scope，让目录、详情和历史共用；目录403/401取消全部资料请求并卸载Inspector，其他资料确定失效保持原清缓存行为。搜索/上下页/回首页/重试均先取消旧scope再换查询，503与入口404继续保留明确不同语义。

305unit、8Edge（原4+新4）、原36/6和新增独立7/1有效单元均真实通过；独立新增Edge有矛盾可见性前置，原样结果完整保留并由主控确认由原reviewer修probe，作者未改断言。所有限定证据和仪器修正说明见任务报告第三轮。实看403清空截图，外观与动效未改，当前仍awaiting_review / live not_run。
