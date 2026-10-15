# R05 / R17 问答前端切片

状态：awaiting_review；实现：complete（仅授权单事件问答前端切片）。基线：a1c703ad7f885767055f3a3fa1071cc8b68110dc；业务冻结：ebbdc9a3c687a1da460de78c6bf825ac6a01363d；独立分支codex/r05-question-frontend、工作树D:/dianzi-wt-r05-question-frontend。根目录后端与报告未提交修改保持不碰；未push，未自行accepted。

## 实施前审阅与设计

读取AGENTS、执行索引、恢复R05/R17、T31/T43、05API、public_api_v2及冻结question_contracts。当前源工作台已采用暗色青绿、原生React表单、公共ErrorPanel、冻结幂等请求、CSRF后代次复核及卸载取消；事件页面已有指定修订证据深链接。应用这些已有模式。

应用Ponytail 5.2 full与前端设计审阅：design-taste的营销布局不适用于此密集产品页；industrial-brutalist仅参考语义网格与终端信息层次。既有颜色、圆角、字体与AmbientBackdrop优先，不重新造设计系统。外部ui-design.md仅作待分析参考，引用布局可借鉴，假Agent轨迹与示例数据不进入产品。

信息层次：范围及当前会话模式 → 单事件UUID与问题输入 → 完整回答及真实毫秒耗时 → 来源事实/规则结论/项目建议 → 限制、时效、引用与固定修订。桌面输入与阅读双列，窄屏单列；长ID和原文可断行。无动画新增，沿用全局reduced-motion背景。

状态：认证恢复/匿名/无权限；未提问；提交中；完整回答；有限覆盖（limitations/unknown）；已过期（stale）；显式错误。网络提交未知保留同body/key；明确开始新问才换key。没有自动重试付费生成，没有假进度/在线计数。

输入：冻结library模式、恰一event UUID、1..4096 Unicode字符问题；POST同源Cookie+CSRF+Idempotency-Key。输出：严格冻结completed投影，支持ID必须属于唯一citations，分类事实要求支持。GET answers重新鉴权与校验answer_id。

拟修改：questions目录、question-client/contracts及直接测试、实际frontend/src/App.tsx路由、event-workspace.tsx最小提问入口、r05_question_workspace.spec.ts、此报告与自有raw目录。主控已确认实际共享文件所有权。六类检查：正常及引用/缺失及未知/冲突和格式拒绝/权限跨会话/重放双击未知重试/并发迟到CSRF及卸载。另验390宽、键盘、reduced-motion、恶意URL、fixture明确标识。

不做：多事件、多轮、资产、历史时间、调查轨迹、推荐、公共schema/auth/client/依赖/全局config修改。完整T31/T43/R17尚需其他恢复包；此切片不验收整卡。

## 执行与验证

所有正式检查cwd为`D:/dianzi-wt-r05-question-frontend/frontend`，时间为北京时间。`reports/runs/recovery_r05_question_frontend_20261015/*.command.json`保留完整命令参数、cwd、开始结束、真实退出码和当时HEAD。封存前检查运行在基线HEAD加未提交候选上；候选随后原样提交为业务冻结SHA，`business.diff`及`manifest.json`绑定源码，不回写原始HEAD记录。

| 检查 | 实际命令 | 开始→结束（2026-10-15 +08:00） | 退出码 / 结果 | 原始证据 |
|---|---|---|---|---|
| 全前端回归 | `npm.cmd run test -- --reporter=json --outputFile=../reports/runs/recovery_r05_question_frontend_20261015/vitest_seal.json` | 16:56:57.288→16:57:13.337 | 0；17文件249项，249passed/0failed/0skip；问答新增71项 | `full_test_seal.log`、`full_test_seal.command.json`、`vitest_seal.json` |
| 类型 | `npm.cmd run typecheck` | 16:56:57.286→16:57:00.668 | 0 | `typecheck_seal.log/.command.json` |
| lint | `npm.cmd run lint` | 16:56:57.261→16:56:59.827 | 0 | `lint_seal.log/.command.json` |
| build | `npm.cmd run build` | 16:56:57.274→16:57:01.904 | 0；45模块，228.95kB JS / 71.53kB gzip | `build_seal.log/.command.json` |
| 冻结后隔离浏览器 | `npx.cmd playwright test e2e/r05_question_workspace.spec.ts --reporter=list,json --output=../reports/runs/recovery_r05_question_frontend_20261015/e2e_frozen_artifacts` | 见`browser_fixture_frozen.command.json`精确时间 | 0；9passed/0failed/0skip；固定ebbdc9a | `browser_fixture_frozen.log/.command.json`、`e2e_fixture_frozen.json`及截图 |

依赖安装执行`npm ci --no-audit --no-fund`，exit0、299packages（未改依赖/lock）。Node v24.13.1；Playwright 1.64.1。浏览器使用既有私有cache `C:/Users/yinha/.codex/cache/dianzi/r01_playwright_1248`，隔离前端端口25185；未下载浏览器。浏览器显式路由隔离全部`/v1/**`，不连接真实问答后端、不读取真实keys。相关浏览器环境值与命令在manifest保留。

首轮缺少jsdom滚动API的unhandled错误（70断言passed但进程exit1）、误在根目录执行npm（ENOENT，检查未执行）、初次typecheck两错误（exit2）如实保留在`exploratory_failures.md`与原始`typecheck.log/.command.json`。后续真实修复后复跑，不改门槛、gold、分母或skip。

业务封存前`git diff --cached --check`无警告。报告/raw提交的同命令报告原始npm stdout末尾空行与`business.diff`的patch空白上下文（exit2）；保留原始证据，不改日志字节或全局忽略规则来制造clean。

## 实现与文件边界

业务提交只有11个文件：`frontend/src/App.tsx`；`frontend/src/features/events/event-workspace.tsx`；`frontend/src/api/question-client.ts`、`question-contracts.ts`及两者直接测试；`frontend/src/features/questions/question-workspace.tsx`、`questions.css`、直接组件测试、明确隔离`question.fixture.ts`；`frontend/e2e/r05_question_workspace.spec.ts`。报告与此包raw为独立第二提交。build更新的已有tsbuildinfo只恢复本WT自己的生成变动，未提交它。未改公共client/auth/globals、schema、配置、进度、锁或依赖。

复用公共`fetchJson/getCsrfToken/ApiProblem/publicProblem`、`AuthProvider`代次防护、状态组件、时间显示、导航shell、AmbientBackdrop及已有事件/固定修订证据深链。必要新增为冻结DTO的严格wire解析、单事件提交/回答GET客户端、问答状态及阅读界面。没有未来调查/多轮/推荐模块和新增库。

POST只提交question/mode=library/event_ids一UUID，浏览器同源Origin自动生成，Cookie由公共client `credentials:include`传递，CSRF在内存且取得后再次检查会话/取消。body/key先序列化冻结，按钮/同步inFlight防双击和并发查询；卸载、换会话、迟到CSRF和迟到回答不会恢复私有数据。网络或格式结果未知可手动同key重试；明确开始新问题才更换key，没有自动付费重试。

响应拒绝额外/缺失/null字段、错误完成类型、未知枚举、伪造support、事实缺support、重复citation、非法时间、逆时间和负/非整数耗时。source_uri只接受无凭据HTTP(S)，只生成HTTPS外链（noopener/noreferrer）；HTTP仅提示不打开。正文与引文使用React文本，HTML不执行。data_mode必须符合当前会话，不把fixture回答贴live标签。

## 六类验收证据与状态

| 类别 | 实际可观察验证 |
|---|---|
| 正常 | POST精确body/key/CSRF、完整回答1234毫秒fixture标注、三类结论分区；键盘依据链接聚焦引用；深链打开正确evidence/revision；事件最小入口返回正确UUID |
| 缺失 | 未提问/未提供关键结论、合法证据不足和模型未配置均区别显示；limitations/unknown/stale明确可见，null和空事实支持拒绝 |
| 冲突 | 409幂等冲突/处理中/失败各有说明，恶意地址、编造supports、错误回答ID、fixture/live模式不一致都无假成功 |
| 权限 | 401清会话与冻结表单且过期提示；403权限/CSRF区分；匿名/无权限无业务请求；注销后迟到响应不恢复回答 |
| 重放 | 双击仅1POST；未知提交原body/key再次提交；只有开始新问题生成新key；GET已保存回答无CSRF/POST，刷新后可凭ID重新读取stale |
| 并发 | CSRF等待跨会话/离页不POST；请求未返回时查询与再次提交均被fence；返回内容需仍符合当前会话 |

unit/contract/security：passed（隔离fixture）；frontend：passed（静态检查及组件）；e2e：passed（9项显式fixture浏览器）。integration：not_run；live：not_run；manual：not_run（尚无人工独立验收）。本Agent实际阅读桌面1280及390截图做布局QA，不能替代独立人工验收。390无横向溢出，长文本/原文/HTML文本可读，全局reduced-motion关闭ambient动画；未新增动画。

CBM在独立/tmp cache/config、仅frontend/src索引，无秘密与holdout。基线188节点/645边；新增候选232节点/821边，0解析失败；schema与`collectSourcePage`/`submitQuestion`trace均有raw。fast模式按设计不索引测试，实际源文件/rg和测试交叉核对，图不是业务真相。

## 计划偏差、限制与评分证据

实际App位于`frontend/src/App.tsx`，事件组件位于`frontend/src/features/events/event-workspace.tsx`；主控明确追加文件所有权后才改最小路由/入口。公共合同没有改变。合法GET答案DTO没有event_id：仅同页POST已确认的answer保留内部事件绑定；重新进入页面后GET不凭输入编造绑定，仍展示引文/revision/HTTPS来源外链，并提示内部事件链接缺上下文。若要求跨刷新打开内部事件抽屉，应先通过后续合同变更给出可信event绑定。

公共fetchJson既有10秒客户端超时沿用；后端可能仍处理。超时显示提交结果未确认，手动保留原key重放，不能宣称未提交或取消服务端付费操作。未配置真实API/模型测试，本包没有实测多跳准确率、P95、来源覆盖、在线总量、Agent轨迹、真实多轮或真实持续时长。

F3：可追溯引文/固定修订、三种结论和支持ID边界有fixture交互证据；D2：桌面/移动/键盘状态有自动化截图证据；P3：只证明展示冻结完整耗时字段，不证明真实性能指标；A1：不新增或伪装Agent能力。原T31/T43/R05/R17整卡及live仍待主控后端接线、后续切片和独立评审。

建议下一步：新非作者reviewer固定业务ebbdc9a独立复跑；主控在已授权范围内接线真实单事件问答，进行真实浏览器/引用修订链与有限模型调用验收。没有accepted/推送动作。
