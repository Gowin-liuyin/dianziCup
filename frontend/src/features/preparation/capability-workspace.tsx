import { EmptyState, StatusBadge } from "../../components/status";

const capabilitySections = {
  sources: { title: "来源登记", columns: ["来源 / 类别", "接通状态", "最近成功", "采集窗口"], dependency: "来源登记、增量游标与采集记录", explanation: "只有实际抓取记录才能说明来源已接通。发布时间未知时，采集时间不能替代发布时间。", inspector: ["来源类别与增量能力", "成功 / 失败记录", "发布、发现与入库时间", "原文修订与去重"] },
  graph: { title: "关系证据", columns: ["起点 / 关系 / 终点", "状态", "规则 / 方法", "原文依据"], dependency: "实体、关系版本与证据投影", explanation: "关系线索与确认事实分别呈现；冲突来源并列保留。图谱展示需要已有可见关系。", inspector: ["起点与终点实体", "关系类型与理由", "证据片段与规则版本", "当前 / 历史状态"] },
  questions: { title: "研究会话", columns: ["问题 / 会话", "回答状态", "引用版本", "完成时间"], dependency: "真实检索、生成与引用校验", explanation: "尚不能提交研究问题。模型或检索缺失时不会提供模板回答，也不会把任务接收解释为回答完成。", inspector: ["关键结论与支持引用", "不足、冲突与范围限制", "真实调查任务", "完整响应时间"] },
  assets: { title: "资产快照", columns: ["资产 / 快照", "完整性范围", "版本观察", "研判状态"], dependency: "授权资产快照、发布规则与研判服务", explanation: "尚不能导入或执行自查。研判保留支持适用、证据排除、证据不足和证据冲突四态。", inspector: ["快照版本与声明范围", "软件适用条件树", "外部观察与确认分栏", "证据包与过期提示"] },
  tasks: { title: "实际运行记录", columns: ["任务 / 角色", "工具与目标", "状态", "耗时 / 停止原因"], dependency: "持久化任务、调查与工具调用记录", explanation: "尚未取得任务记录。页面不会通过动画递增进度或生成 Agent 成功台词；刷新恢复依赖服务端任务标识。", inspector: ["任务与输入快照", "真实工具调用记录", "预算、失败与重试", "停止原因及结果引用"] },
  changes: { title: "变化与订阅", columns: ["事件 / 订阅", "修订原因", "旧 / 新状态", "关联证据"], dependency: "变化失效、订阅与推荐服务", explanation: "尚不能创建订阅。既有空结果与新增命中也必须被更新覆盖；不同用户的推荐按授权范围返回。", inspector: ["修订前后版本", "新增命中与旧结果失效", "本人订阅与推荐原因", "已读、退订与撤回"] },
  reports: { title: "报告清单", columns: ["报告 / 范围", "版本", "校验状态", "生成时间"], dependency: "证据报告生成与授权导出服务", explanation: "尚未取得报告记录。导出需核对证据、映射和权限；缺字段时不会生成假报告或假 OpenVEX。", inspector: ["报告版本与生成时间", "结论、引用与资产快照", "范围及未映射字段", "授权导出与限制"] },
} as const;

type PreparedPage = keyof typeof capabilitySections;

/** 业务接口未冻结时保留清晰的信息结构与缺口，不注入业务样本或发明 DTO。 */
export function CapabilityWorkspace({ page, authenticated }: { page: PreparedPage; authenticated: boolean }) {
  const section = capabilitySections[page];
  return <div className="research-grid">
    <section className="panel capability-panel" aria-labelledby="capability-title">
      <div className="panel-heading"><div><p className="eyebrow">WORKSPACE / 数据视图</p><h2 id="capability-title">{section.title}</h2></div><StatusBadge state="not_connected" /></div>
      <div className="table-scroll"><table className="intelligence-table" aria-label={section.title}><thead><tr>{section.columns.map((column) => <th scope="col" key={column}>{column}</th>)}</tr></thead><tbody /></table></div>
      <EmptyState title="本页能力待接通" description={section.explanation} />
      <div className="capability-notice"><span className="notice-mark" aria-hidden="true">!</span><p>依赖：{section.dependency}。<br />当前没有查询结果，不能据此判断为零记录或无风险。</p></div>
      <div className="panel-actions"><a className="button secondary" href="#runtime">查看运行状态</a>{!authenticated && <a className="button" href="#session">登录并核对权限</a>}</div>
    </section>
    <aside className="panel evidence-inspector" aria-labelledby="inspector-title"><div className="panel-heading"><div><p className="eyebrow">INSPECTOR / 核查</p><h2 id="inspector-title">核查上下文</h2></div><span className="inspector-symbol" aria-hidden="true">⌁</span></div><div className="inspector-body"><p className="small-note">数据接通后，在这里保留当前研究对象的依据。</p><ul className="inspection-list">{section.inspector.map((item) => <li key={item}>{item}</li>)}</ul><p className="boundary-note">未知保持未知<br /><span>事实、推断与建议分别标明</span></p></div></aside>
  </div>;
}

export function PreparedEventWorkspace({ authenticated }: { authenticated: boolean }) {
  return <div className="research-grid">
    <section className="panel capability-panel" aria-labelledby="event-feed-title">
      <div className="panel-heading"><div><p className="eyebrow">EVENTS / 事件流</p><h2 id="event-feed-title">情报列表</h2></div><StatusBadge state="not_connected" /></div>
      <form className="query-toolbar" onSubmit={(event) => event.preventDefault()} aria-label="情报筛选">
        <div className="query-input"><label htmlFor="event-query">检索关键词</label><input id="event-query" placeholder="事件标题、组件或公开标识" disabled /></div>
        <div className="query-filters"><label>产品<input aria-label="产品筛选" placeholder="全部产品" disabled /></label><label>风险类型<input aria-label="风险类型筛选" placeholder="全部类型" disabled /></label><button className="button" type="submit" disabled>检索情报</button></div>
        <p className="small-note">检索服务接通后启用筛选。列表与证据来自同一授权范围。</p>
      </form>
      <div className="table-scroll"><table className="intelligence-table" aria-label="情报事件列表"><thead><tr><th scope="col">事件 / 公开标识</th><th scope="col">来源</th><th scope="col">富化状态</th><th scope="col">版本 / 时间</th></tr></thead><tbody /></table></div>
      <EmptyState title="情报服务待接通" description="尚未取得事件查询结果。接通真实来源与事件服务后，可查看记录、修订与证据；当前不能判断为无情报。" />
      <div className="panel-actions"><a className="button secondary" href="#sources">查看来源工作区</a>{!authenticated && <a className="button" href="#session">登录并核对权限</a>}</div>
    </section>
    <aside className="panel evidence-inspector" aria-labelledby="evidence-preview-title"><div className="panel-heading"><div><p className="eyebrow">EVIDENCE / 原文依据</p><h2 id="evidence-preview-title">证据检视</h2></div><span className="inspector-symbol" aria-hidden="true">⌁</span></div><div className="inspector-body"><p className="inspector-prompt">选择事件<br />追溯每条结论</p><p className="small-note">接通后选中可见事件，查看指定原文版本、准确片段和支持关系。</p><ul className="inspection-list"><li>文档修订与来源</li><li>片段位置与核验状态</li><li>发布 / 发现 / 入库时间</li><li>冲突与证据不足</li></ul><p className="boundary-note">引文存在 ≠ 内容支持</p></div></aside>
  </div>;
}
