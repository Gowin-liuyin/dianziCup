# CR-R17 · 证据图重叠关系的真实指针选择

记录：2026-10-16，Asia/Shanghai（+08:00）。当前授权为主控下达的R17 UI fix1，目标冻结370f873，独立工作树`D:/wt/r17-graph-ui-fix1`；状态`awaiting_review`，不由实现者签accepted。

问题：原图曲线由`index % 4`偏移，完整六类合法图中边2中点约(407,682.671875)的真实鼠标点击选中边6；移去逆边后仍被后绘论文边的透明22px stroke抢占。独立初审`D:/wt/r17-graph-review1/reports/reviews/recovery/G-E-R17-evidence-graph-review-1.md`已封存；本fix新红测同样2fail/1单边positive，原review/probe/raw/hash不修改。

选择：保留现有有界曲线与六列布局；真实指针转换为SVG坐标，对所有可见曲线计算距离，独立于DOM绘制顺序。最近曲线在22 CSS px内且无近似并列时精确选中；在最近距离4 CSS px内存在多条关系时展示明确的候选列表，让用户选择有序号、类型、方向、完整端点和标识的一条，不默选最后绘制项。22px半径与44px non-scaling透明stroke保持触控面积，按钮桌面≥40px/窄屏≥44px。几何采样有固定上限，最多400边；密集图不生成额外业务节点或虚构关系。

键盘/辅助技术按已聚焦的关系ID直接激活；关系列表继续按ID选择。候选区进入后焦点到首项，可Escape/取消；节点选择、筛选、缩放、平移与重置清除旧候选。既有证据hash路由、1.0/1.1精确规则元数据、schema1、supported/unknown状态、认证隔离、动态背景与reduced-motion保持。

替代方案：仅缩小透明hit会降低可触控性，并不能解决交点；只重新排六条线会漏掉20+/平行/逆向/400边；加graph库/力布局扩大依赖与视觉变化。本fix不采用这些方案。

预定义验证：先真实mouse同根因red，再同场景green；完整六类每条边、20+不同端点与平行逆边、390/1366、缩放80%–180%和原生滚动/平移的真实坐标点击；候选mouse/键盘、cancel、过滤清除；200/400有界操作与渲染、原e2e10项、全前端回归、type/lint/build。不能用locator直接dispatch到被遮挡path替代指针命中。人工/live/真实API仍not_run。

只改graph feature及专属新tests/e2e、本CR与自有报告/run，不改App/shared API/backend/全局CSS/锁/progress；不改指标/金标，不push，不完整R17/G-E签字。此记录只说明已授权的UI选择改动，不更改公共业务DTO。
