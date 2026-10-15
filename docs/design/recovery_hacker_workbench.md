# R17 黑客风安全研究工作台

状态：本准备切片 awaiting_review；整 R17 仍 partial。基线 b099483b4f2be3d21b3fd3e7e4327912ba75cae2；第一源码冻结 fa5787409da358ea95dbb35acfbd3a96c1fa2371（10:30，动态背景新指令之前），动效与移动说明修复冻结 00a5c990c22c6bf1e1d572fe358b086baf02d66b。作者 hacker_frontend；2026-10-15（Asia/Shanghai）。

## 真实调研与现状审计

完整读取用户提供的外部 `E:/wechatData/xwechat_files/wxid_c14weta2ez6m22_03f5/msg/file/2026-10/ui-design.md`，仅参考，不复制入仓、不覆盖合同。该文件自己的“已核对”不当成本轮证据。

本轮真实浏览并查看了 [Elastic Timeline](https://www.elastic.co/docs/solutions/security/investigate/timeline) 的“example Timeline with several events”官方截图：上部查询与时间范围、字段选择侧栏、紧凑多列事件表、行内上下文、底部分页。借鉴“查询→列表→上下文”的结构，未复制图标、截图或资产。

真实打开 [Elastic 告警详情](https://www.elastic.co/docs/solutions/security/detect-and-alert/view-detection-alert-details)：文档描述详情 flyout、Overview/Table/JSON 视图与实体互跳。本页详情图未单独放大审查，不能声称看过整张告警详情截图。借鉴保留列表上下文、明确版本与证据入口。

真实浏览并放大 [Wazuh Dashboard](https://documentation.wazuh.com/current/user-manual/wazuh-dashboard/navigating-the-wazuh-dashboard.html) 的 Dashboards 官方截图：左侧分组导航清晰，主区域按安全任务分区；官方图片突出导航而淡化其余内容。借鉴研究/任务/系统分组，未把图片中的统计当作本系统能力。

现有 React 18 / Vite 6 / TS strict / 原生 CSS；无 router/UI 库。认证使用同一次 `/v1/auth/me` 身份+CSRF 快照，Cookie 为服务端会话；token 只存内存。现界面纸白红 Swiss，仅运行概览与会话，真实接线为 auth/health。改造应保留登录、权限、会话恢复、退出失败立即清身份和撤销未确认提示，不改依赖锁或鉴权合同。

## 设计决定

近黑炭色五层：底色 #090f11、导航 #0b1214、面板 #10191c、输入 #142125、悬停 #1b2c31。绿青 #79e2ba 是唯一主强调，琥珀/红用于状态，颜色与中文标签共同表达。主文字 #e3eeec，次文 #99afab；汉字采用系统中文无衬线，数据/时间/ID 用 Consolas/SFMono 与 tabular-nums，不下载字体、不依赖 CDN。

不使用代码雨、故障闪烁、全屏终端、假 Agent 动画、3D、玻璃嵌套卡或装饰性噪声。细边框和清晰的字重/间距建立层次。桌面导航约 208px，面板紧凑，正文至少13px、说明行距1.6；关键表格内容不得只以省略号隐藏。390px 下导航改为横向可滚动，表格仅自身横向滚动；页面无整体溢出。按钮触达≥40px。焦点环、skip link、真实 aria-current；reduced-motion 降低过渡。

外部参考的宽度/五层表面/证据侧栏/任务树可采用。其 9 来源分类、额外组件库、7工具替代内部 registry、按置信度消除冲突、全部指标永久写待测均不采用：冻结合同仍是8 SourceCategory、九维 enum、来源断言冲突并列、已有真实测量应展示其窗口与分母。公开暴露只聚合；授权 tenant 资产仍按原 ACL 展示。只读回放不宣称真实 Agent。

## 信息架构与第一切片

研究：情报列表、来源监测、知识图谱、引用问答、资产自查。协作：任务轨迹、变化/推荐、报告。系统：运行状态、会话与权限。默认保持运行概览以保留 R01 连续行为；所有导航可由键盘访问、URL hash 恢复，未知 hash 有解释与返回入口。

第一切片首先完善 auth/health 整页并提供核心工作区布局与准确的待接通说明。未冻结业务 DTO 前不发送猜测请求，也不渲染伪造记录。情报页保留查询/产品/风险/时间与表头结构，未接通状态禁止提交，提供运行状态与会话入口；证据侧栏说明需要选择可见事件后才显示原文版本和定位。来源/问答/资产/图谱/任务/变化/报告分别提供合同所需信息结构与具体缺口，不拿无接口当“零条记录”。

## 分阶段 API 对齐

| 切片 | 冻结来源 | 页面行为 |
|---|---|---|
| R01 真实 auth/health | 05 + 当前 client.ts | 实际探测、重试、认证/权限、Live/Fixture 标签 |
| R04 list/detail/evidence | 03/05；最小 DTO 主控冻结中 | 200空与404未接通分别呈现；cursor分页；正确revision/quote；不可见对象无标题泄露 |
| R05/R12 问答 | public_api_v2 数值 schema_version=2 与 AskResult 判别联合 | 同步结果/真实task句柄；引用；freshness；缺模型不生成模板成功 |
| R07–R16 后续 | 原业务DTO/枚举 | 九维独立状态；四态资产；真实ToolRun；变化/推荐/报告可追溯 |

列表仅显示后端给出的本页数量，不捏造总数、实时采集/性能/准确率。503 不能解释为空；权限拒绝不显示缓存对象；stale 与待人工状态显式展示。前端不计算新业务结论。

## 验证与截图审查记录

实际执行记录见 `reports/runs/recovery_hacker_ui_20261015/commands.jsonl` 与任务报告。调研截图本轮在浏览器工具中实际查看；产品截图必须来自本工作树浏览器渲染，后续记录文件、viewport、路径、真实/隔离夹具模式与检查发现。

已执行：第一冻结60组件/认证/客户端测试；动效冻结62测试（原42完整保留+20新增）、lint/typecheck/build均退出0。主控对第一冻结实跑5browser、第二冻结实跑6browser，均0失败/跳过/flaky；认证使用真实PG默认API。详细时间和SHA见run目录两个command JSON。fixture组件检查不计产品live；业务待接通页面的browser通过也不计业务来源链通过。R04–R16业务依赖仍阻塞整R17验收。

实际查看了两个版本的desktop1280和mobile390截图。第一冻结的mobile缺口说明被table min-width区域裁切，第二冻结把空/待接通说明移出横滚表格并新增每行Range bounds断言，实际新截图全部文字换行可见。表头自身保留横滚。第二冻结的ambient-frame-a/b为实际渲染的两帧，另有computed transform变化证据；作者还在CUA实际打开25300匿名情报页，确认动态拓扑只在留白/外围、面板正文不受覆盖。图片路径见任务报告，未复制竞品素材。

## 动态背景补充（用户新明确要求）

第一源码冻结后收到用户“页面背景最后有一定的动态效果”要求，已在第二冻结交付低对比拓扑线与缓慢漂移光域，外围及留白中可见；业务面板不透明，动画不显示采集/Agent进度。CSS transform + SVG，无3D/Canvas依赖；pointer-events:none、aria-hidden。reduced-motion 浏览器实测animationName=none，390px不溢出。代码监听document.hidden暂停，单元测试已覆盖hidden/visible；实际隐藏页验证仍有下列环境缺口，不声称实际通过。

粗性能观察：60帧约999.9ms，p95帧间隔约16.70ms、最大约16.80ms，观测0 long task，装饰DOM15，主内容bounds不变。仅该设备/该约1秒窗口的粗测，不外推产品吞吐/时效/帧率保证。

隐藏页缺口：headless1248与本机已有Edge155专用headed窗口，切换页、关闭focus emulation、恢复原生后台flag、最小化后document.visibilityState仍实际visible；产品因实际visible保持running，日志准确保留。没有伪造document.hidden或DOM属性来充作live。此处停止扩大同根因探针；仍需能产生原生visibilitychange的浏览器环境验证。临时Vite25300和新开的专用浏览器均已关闭，未操作既有API/worker进程。

## R04 冻结投影与可操作证据切片

2026-10-15 后续切片直接读取主控冻结 `099c5b1af4cea9df9f6c72894ee36782b7f4c8c3` 的 CR-R04 和 knowledge_contracts.py；不复制或修改后端模型。最终前端源码 `471c54760e8fe016fcd26aca89d17a334d7b0303`，基于准备证据版本 cafbe，分支 `codex/recovery-r04-ui`。skip-link 的另支独立修复 bb3a/90da 尚不混入本批，集成须由主控协调已审版本。

| GET 入口 | 前端映射与显示规则 |
|---|---|
| `/v1/events` | schema_version 数值2；q仅标题/公开标识；product未支持时422；risk_type事件类型；updated_after业务修订时间；只显示本页条数；opaque cursor替换当前页 |
| `/v1/events/{event_id}` | 保存的标题/状态、各自独立的九维状态、来源断言origin/status、原文修订时间线；available必须有citation；缺少维度保留“未提供”，模型假设与未核验显式保留 |
| `/v1/evidence/{evidence_id}` | 引用的revision_id核对后呈现原文文本；Unicode位置原样保存；历史定位未核验；四个时间和URI为null则显示未知/未留存，不用当前来源时间填补 |

next_cursor非null且非空由主控确认并安排最小合同补记；空游标视为协议异常，不能重复取首页。URI限定http/https且无userinfo，原文/断言由React文本渲染。未知字段/枚举、错误对象或不匹配的版本都解释为合同错误。未给权限的对象不显示旧标题/数量；404列表入口与200空响应分别呈现，503不能解释为无风险。页面不重新计算支撑关系或来源等级。

引用深链使用 `#events/{event}/evidence/{evidence}/revision/{revision}`，直接回到保存的版本。桌面证据栏sticky且自身可以滚动；移动端单列呈现。引用成功后将焦点与视口移到证据检视区，避免用户需要在长详情末尾寻找片段；loading/错误不会抢焦点，定位使用instant而非平滑动画。筛选或换事件先清当前结果，错误不回填fixture。会话generation与user/tenant/permission/data_mode共同约束组件生命周期；请求开始代次不匹配时丢弃晚到200/401。401只清客户端身份并提示重登，不能宣称服务端撤销已完成。

实际浏览器校验仅在 `frontend/e2e/r04_fixture_contract.spec.ts` 中拦截所有 `/v1/**`，合成标识在数据模式、记录标题、页数和证据栏可见；产品没有fixture开关、假记录或失败替代路径。1366x900/390x844真实浏览器截图已实际查看：桌面密集表格与证据侧栏，手机元数据长ID可换行，正文不覆盖装饰。7个未提供维度、PoC失败、时效过期、模型假设、未知历史时间同时出现，避免全绿展示。390文字每行Range、文档宽度、引用后的focus/viewport均通过。最终4browser为11:37:24–11:37:31+08:00，0失败/skip/flaky；不计真实来源或R04业务live。

首轮2363 fixture 3过/1失败完整保留：401测试错误预期只有1次初始me，实际开发StrictMode为2次；后续6e42把401响应延后，记录前后me 2→2、events 2→2，断言无新增恢复请求；没有删除/skip或放宽业务要求。最后471源码追加引用焦点/可见性修复并实跑上述4browser。真实API路由、持久化事件/证据、受控真实会话回归及来源链仍待主控接通；旧00a的auth/health通过不外推为本批业务live通过。
