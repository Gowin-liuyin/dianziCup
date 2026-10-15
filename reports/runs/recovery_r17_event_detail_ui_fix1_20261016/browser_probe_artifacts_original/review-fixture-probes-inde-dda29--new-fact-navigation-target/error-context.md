# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: review-fixture-probes.spec.ts >> independent narrow screen status and new fact navigation target
- Location: ..\reports\runs\recovery_r17_event_detail_ui_fix1_20261016\review-fixture-probes.spec.ts:83:5

# Error details

```
Error: project design requires action touch targets at least 40px

expect(received).toBeGreaterThanOrEqual(expected)

Expected: >= 40
Received:    24
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - link "跳到主要内容" [ref=e4] [cursor=pointer]:
    - /url: "#main-content"
  - complementary [ref=e5]:
    - link "安全情报 DEFENSE INTELLIGENCE" [ref=e6] [cursor=pointer]:
      - /url: "#runtime"
      - generic [aria-hidden] [ref=e7]: DI
      - generic [ref=e9]:
        - text: 安全情报
        - generic [ref=e10]: DEFENSE INTELLIGENCE
    - navigation "工作台导航" [ref=e11]:
      - generic [ref=e12]:
        - link "情报列表" [ref=e13] [cursor=pointer]:
          - /url: "#events"
          - generic [aria-hidden] [ref=e14]: ≡
          - text: 情报列表
        - link "来源监测" [ref=e15] [cursor=pointer]:
          - /url: "#sources"
          - generic [aria-hidden] [ref=e16]: ◉
          - text: 来源监测
        - link "资料库" [ref=e17] [cursor=pointer]:
          - /url: "#documents"
          - generic [aria-hidden] [ref=e18]: ▤
          - text: 资料库
        - link "知识图谱" [ref=e19] [cursor=pointer]:
          - /url: "#graph"
          - generic [aria-hidden] [ref=e20]: ◇
          - text: 知识图谱
        - link "引用问答" [ref=e21] [cursor=pointer]:
          - /url: "#questions"
          - generic [aria-hidden] [ref=e22]: ">_"
          - text: 引用问答
        - link "资产自查" [ref=e23] [cursor=pointer]:
          - /url: "#assets"
          - generic [aria-hidden] [ref=e24]: ⬡
          - text: 资产自查
      - generic [ref=e25]:
        - link "任务轨迹" [ref=e26] [cursor=pointer]:
          - /url: "#tasks"
          - generic [aria-hidden] [ref=e27]: ⌘
          - text: 任务轨迹
        - link "变化与推荐" [ref=e28] [cursor=pointer]:
          - /url: "#changes"
          - generic [aria-hidden] [ref=e29]: ↗
          - text: 变化与推荐
        - link "证据报告" [ref=e30] [cursor=pointer]:
          - /url: "#reports"
          - generic [aria-hidden] [ref=e31]: ▤
          - text: 证据报告
      - generic [ref=e32]:
        - link "运行状态" [ref=e33] [cursor=pointer]:
          - /url: "#runtime"
          - generic [aria-hidden] [ref=e34]: ◫
          - text: 运行状态
        - link "会话与权限" [ref=e35] [cursor=pointer]:
          - /url: "#session"
          - generic [aria-hidden] [ref=e36]: ◎
          - text: 会话与权限
  - generic [ref=e37]:
    - banner [ref=e38]:
      - generic [ref=e39]:
        - generic [aria-hidden] [ref=e40]: ">"
        - text: 工作台
        - generic [aria-hidden] [ref=e41]: /
        - text: 情报列表
      - generic [ref=e42]:
        - text: 数据模式
        - strong [ref=e43]: 合成 / Fixture
    - main [ref=e44]:
      - generic [ref=e45]:
        - generic [ref=e46]:
          - paragraph [ref=e47]: INTELLIGENCE / FEED
          - heading "情报工作区" [level=1] [ref=e48]: 情报工作区_
          - paragraph [ref=e49]: 从事件线索进入事实、版本与原文证据。
        - button "刷新状态" [ref=e50] [cursor=pointer]:
          - generic [aria-hidden] [ref=e51]: ↻
          - text: 刷新状态
      - generic [ref=e52]:
        - generic [ref=e53]:
          - region [ref=e54]:
            - generic [ref=e55]:
              - generic [ref=e56]:
                - paragraph [ref=e57]: EVENTS / 事件流
                - heading "情报列表" [level=2] [ref=e58]
              - generic [ref=e59]: 已取得本页
            - form "情报筛选" [ref=e61]:
              - generic [ref=e62]:
                - generic [ref=e63]: 检索关键词
                - textbox "检索关键词" [ref=e64]:
                  - /placeholder: 事件标题或公开标识
              - generic [ref=e65]:
                - generic [ref=e66]:
                  - text: 产品
                  - textbox "产品筛选" [ref=e67]:
                    - /placeholder: 未支持时明确提示
                - generic [ref=e68]:
                  - text: 风险类型
                  - textbox "风险类型筛选" [ref=e69]:
                    - /placeholder: 全部类型
                - button "检索情报" [ref=e70] [cursor=pointer]
              - generic [ref=e71]:
                - text: 修订时间之后
                - textbox "修订时间之后" [ref=e72]:
                  - /placeholder: ISO 8601（含时区）
              - paragraph [ref=e73]: 时间筛选使用真实业务修订时间；本页数量不代表全部事件总数。
            - table "情报事件列表" [ref=e75]:
              - rowgroup [ref=e76]:
                - row [ref=e77]:
                  - columnheader "事件 / 公开标识" [ref=e78]
                  - columnheader "来源" [ref=e79]
                  - columnheader "状态 / 时效" [ref=e80]
                  - columnheader "首次发现" [ref=e81]
              - rowgroup [ref=e82]:
                - row [ref=e83]:
                  - rowheader [ref=e84]:
                    - link "隔离 Fixture：九维状态与历史证据" [ref=e85] [cursor=pointer]:
                      - /url: "#events/10000000-0000-4000-8000-000000000001"
                    - code [ref=e86]: FIXTURE-ONLY
                  - cell "2 个可见来源" [ref=e87]
                  - cell "active 已过期" [ref=e88]:
                    - generic [ref=e89]: active
                    - generic [ref=e90]: 已过期
                  - cell [ref=e91]:
                    - time [ref=e92]: 2026-10-15T10:00:00+08:00
            - generic [ref=e93]:
              - generic [ref=e94]: 本页 1 条 · 合成 / Fixture
              - button "下一页" [disabled] [ref=e95]
            - link "查看来源工作区" [ref=e97] [cursor=pointer]:
              - /url: "#sources"
          - region [ref=e98]:
            - generic [ref=e99]:
              - generic [ref=e100]:
                - paragraph [ref=e101]: EVENT DETAIL / 事实与修订
                - heading "事件详情" [level=2] [ref=e102]
              - link "返回列表" [ref=e103] [cursor=pointer]:
                - /url: "#events"
            - generic [ref=e104]:
              - generic [ref=e105]:
                - generic [ref=e106]:
                  - heading "隔离 Fixture：九维状态与历史证据" [level=3] [ref=e107]
                  - generic [ref=e108]: 已过期
                  - generic [ref=e109]: 合成 / Fixture
                - paragraph [ref=e110]: FIXTURE-ONLY
                - generic [ref=e111]:
                  - term [ref=e112]: 事件类型
                  - definition [ref=e113]: advisory
                  - term [ref=e114]: 保存状态
                  - definition [ref=e115]: active
                  - term [ref=e116]: 可见来源
                  - definition [ref=e117]: "2"
                  - term [ref=e118]: 首次发现
                  - definition [ref=e119]:
                    - time [ref=e120]: 2026-10-15T10:00:00+08:00
                - group [ref=e121]:
                  - generic "事件标识与关联产品" [ref=e122] [cursor=pointer]
                - paragraph [ref=e123]: 事件已标为过期；以下保留已保存的信息，不能当作当前结论。
                - link "基于此事件提问 →" [ref=e124] [cursor=pointer]:
                  - /url: "#questions/10000000-0000-4000-8000-000000000001"
              - navigation "事件详情阅读位置" [ref=e125]:
                - button "九维富化" [ref=e126] [cursor=pointer]
                - button "事实与来源断言" [ref=e127] [cursor=pointer]
                - button "原文修订时间线" [ref=e128] [cursor=pointer]
              - region [ref=e129]:
                - heading "九维富化" [level=3] [ref=e130]
                - paragraph [ref=e131]: 各维度独立记录状态。未返回的维度没有结果，不能解释为不适用或完成。显示值来自本次响应中的关联断言。
                - article "CVSS 评分" [ref=e132]:
                  - heading "CVSS 评分" [level=4] [ref=e133]
                  - generic [ref=e135]:
                    - generic [ref=e136]:
                      - generic [ref=e137]: 已取得
                      - generic [ref=e138]: 已过期
                    - paragraph [ref=e139]: 已保存此维度的引用，具体支撑关系仍以来源断言为准。
                    - generic [ref=e140]:
                      - generic [ref=e141]:
                        - generic [ref=e142]: 有证据支持
                        - generic [ref=e143]: 依据：结构化来源
                      - paragraph [ref=e144]: 9.3 · CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
                      - button "查看断言与依据" [ref=e145] [cursor=pointer]
                    - generic [ref=e146]:
                      - term [ref=e147]: 观测时刻
                      - definition [ref=e148]:
                        - time [ref=e149]: 2026-10-15T11:00:00+08:00
                      - term [ref=e150]: 来源版本
                      - definition [ref=e151]: fixture-source-revision-2
                    - generic [ref=e153]:
                      - link "查看引用：Unicode [12, 42)" [ref=e154] [cursor=pointer]:
                        - /url: "#events/10000000-0000-4000-8000-000000000001/evidence/10000000-0000-4000-8000-000000000004/revision/10000000-0000-4000-8000-000000000002"
                      - group [ref=e155]:
                        - generic "展开原文摘录" [ref=e156] [cursor=pointer]
                - article "EPSS 可能性" [ref=e157]:
                  - heading "EPSS 可能性" [level=4] [ref=e158]
                  - generic [ref=e160]:
                    - generic [ref=e161]:
                      - generic [ref=e162]: 未发现
                      - generic [ref=e163]: 当前
                    - paragraph [ref=e164]: 在已查询范围内未发现结果，不能据此排除风险。
                    - paragraph [ref=e165]: 未提供可展示的关联事实值
                    - generic [ref=e166]:
                      - term [ref=e167]: 观测时刻
                      - definition [ref=e168]:
                        - time [ref=e169]: 2026-10-15T11:00:00+08:00
                      - term [ref=e170]: 来源版本
                      - definition [ref=e171]: 未提供
                - article "KEV 目录" [ref=e172]:
                  - heading "KEV 目录" [level=4] [ref=e173]
                  - generic [ref=e175]:
                    - generic [ref=e176]:
                      - generic [ref=e177]: 不适用
                      - generic [ref=e178]: 当前
                    - paragraph [ref=e179]: 服务将此维度标为不适用，不代表其他维度没有风险。
                    - paragraph [ref=e180]: 未提供可展示的关联事实值
                    - group [ref=e181]:
                      - generic "观测时刻与来源版本" [ref=e182] [cursor=pointer]
                - article "CWE 弱点" [ref=e183]:
                  - heading "CWE 弱点" [level=4] [ref=e184]
                  - generic [ref=e186]:
                    - generic [ref=e187]:
                      - generic [ref=e188]: 有冲突
                      - generic [ref=e189]: 时效未知
                    - paragraph [ref=e190]: 来源存在冲突，保留各项断言，不在页面自动裁决。
                    - generic [ref=e191]:
                      - generic [ref=e192]:
                        - generic [ref=e193]: 有争议
                        - generic [ref=e194]: 依据：原文明示
                      - paragraph [ref=e195]: 隔离来源 A：CWE-502
                      - button "查看断言与依据" [ref=e196] [cursor=pointer]
                    - generic [ref=e197]:
                      - generic [ref=e198]:
                        - generic [ref=e199]: 有争议
                        - generic [ref=e200]: 依据：原文明示
                      - paragraph [ref=e201]: 隔离来源 B：CWE-20
                      - button "查看断言与依据" [ref=e202] [cursor=pointer]
                    - group [ref=e203]:
                      - generic "观测时刻与来源版本" [ref=e204] [cursor=pointer]
                    - generic [ref=e206]:
                      - link "查看引用：Unicode [12, 42)" [ref=e207] [cursor=pointer]:
                        - /url: "#events/10000000-0000-4000-8000-000000000001/evidence/10000000-0000-4000-8000-000000000004/revision/10000000-0000-4000-8000-000000000002"
                      - group [ref=e208]:
                        - generic "展开原文摘录" [ref=e209] [cursor=pointer]
                - article "ATLAS 映射" [ref=e210]:
                  - heading "ATLAS 映射" [level=4] [ref=e211]
                  - generic [ref=e213]:
                    - generic [ref=e214]:
                      - generic [ref=e215]: 待处理
                      - generic [ref=e216]: 时效未知
                    - paragraph [ref=e217]: 此维度尚待处理，当前没有完成结论。
                    - generic [ref=e218]:
                      - generic [ref=e219]:
                        - generic [ref=e220]: 未核验
                        - generic [ref=e221]: 依据：模型假设
                      - paragraph [ref=e222]: 隔离模型假设：关联尚未核验。
                      - button "查看断言与依据" [ref=e223] [cursor=pointer]
                    - group [ref=e224]:
                      - generic "观测时刻与来源版本" [ref=e225] [cursor=pointer]
                - article "影响版本" [ref=e226]:
                  - heading "影响版本" [level=4] [ref=e227]
                  - generic [ref=e229]:
                    - generic [ref=e230]:
                      - generic [ref=e231]: 受阻
                      - generic [ref=e232]: 已过期
                    - paragraph [ref=e233]: 此维度的处理受阻，已保存的其他信息仍可核查。
                    - generic [ref=e234]:
                      - generic [ref=e235]:
                        - generic [ref=e236]: 已撤回
                        - generic [ref=e237]: 依据：规则推导
                      - paragraph [ref=e238]: 隔离已撤回范围：>=1.0.0 <2.0.0 完整条件：仅在启用插件时适用，不能删除此条件。
                      - button "查看断言与依据" [ref=e239] [cursor=pointer]
                    - group [ref=e240]:
                      - generic "观测时刻与来源版本" [ref=e241] [cursor=pointer]
                    - paragraph [ref=e242]:
                      - text: 错误代码
                      - code [ref=e243]: fixture_scope_unavailable
                - article "论文关联" [ref=e244]:
                  - heading "论文关联" [level=4] [ref=e245]
                  - generic [ref=e247]:
                    - generic [ref=e248]:
                      - generic [ref=e249]: 失败
                      - generic [ref=e250]: 时效未知
                    - paragraph [ref=e251]: 此维度处理失败，不能把失败解释为未发现。
                    - paragraph [ref=e252]: 未提供可展示的关联事实值
                    - group [ref=e253]:
                      - generic "观测时刻与来源版本" [ref=e254] [cursor=pointer]
                    - paragraph [ref=e255]:
                      - text: 错误代码
                      - code [ref=e256]: fixture_upstream_failure
                - article "PoC 核查" [ref=e257]:
                  - heading "PoC 核查" [level=4] [ref=e258]
                  - generic [ref=e260]:
                    - generic [ref=e261]:
                      - generic [ref=e262]: 已取得
                      - generic [ref=e263]: 当前
                    - paragraph [ref=e264]: 已保存此维度的引用，具体支撑关系仍以来源断言为准。
                    - paragraph [ref=e265]: 未提供可展示的关联事实值
                    - group [ref=e266]:
                      - generic "观测时刻与来源版本" [ref=e267] [cursor=pointer]
                    - generic [ref=e269]:
                      - link "查看引用：Unicode [12, 42)" [ref=e270] [cursor=pointer]:
                        - /url: "#events/10000000-0000-4000-8000-000000000001/evidence/10000000-0000-4000-8000-000000000004/revision/10000000-0000-4000-8000-000000000002"
                      - group [ref=e271]:
                        - generic "展开原文摘录" [ref=e272] [cursor=pointer]
                - article "暴露统计" [ref=e273]:
                  - heading "暴露统计" [level=4] [ref=e274]
                  - generic [ref=e275]: 未提供该维度
              - region [ref=e276]:
                - heading "事实与来源断言" [level=3] [ref=e277]
                - paragraph [ref=e278]: 引文存在不等于内容支持。模型假设、已撤回和已被替代的断言保留各自状态。
                - paragraph [ref=e279]: 人工复核：当前只读接口未提供任务状态或确认入口。
                - article [active] [ref=e280]:
                  - generic [ref=e281]:
                    - code [ref=e282]: fixture_cvss_score
                    - generic [ref=e283]: 有证据支持
                    - generic [ref=e284]: 结构化来源
                  - paragraph [ref=e285]: 9.3 · CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
                  - paragraph [ref=e286]:
                    - text: 来源修订
                    - code [ref=e287]: 10000000-0000-4000-8000-000000000002
                  - link "原文片段 [1]" [ref=e289] [cursor=pointer]:
                    - /url: "#events/10000000-0000-4000-8000-000000000001/evidence/10000000-0000-4000-8000-000000000004/revision/10000000-0000-4000-8000-000000000002"
                - article [ref=e290]:
                  - generic [ref=e291]:
                    - code [ref=e292]: fixture_weakness
                    - generic [ref=e293]: 有争议
                    - generic [ref=e294]: 原文明示
                  - paragraph [ref=e295]: 隔离来源 A：CWE-502
                  - paragraph [ref=e296]:
                    - text: 来源修订
                    - code [ref=e297]: 10000000-0000-4000-8000-000000000002
                  - link "原文片段 [1]" [ref=e299] [cursor=pointer]:
                    - /url: "#events/10000000-0000-4000-8000-000000000001/evidence/10000000-0000-4000-8000-000000000004/revision/10000000-0000-4000-8000-000000000002"
                - article [ref=e300]:
                  - generic [ref=e301]:
                    - code [ref=e302]: fixture_weakness
                    - generic [ref=e303]: 有争议
                    - generic [ref=e304]: 原文明示
                  - paragraph [ref=e305]: 隔离来源 B：CWE-20
                  - paragraph [ref=e306]:
                    - text: 来源修订
                    - code [ref=e307]: 10000000-0000-4000-8000-000000000003
                  - link "原文片段 [1]" [ref=e309] [cursor=pointer]:
                    - /url: "#events/10000000-0000-4000-8000-000000000001/evidence/10000000-0000-4000-8000-000000000005/revision/10000000-0000-4000-8000-000000000003"
                - article [ref=e310]:
                  - generic [ref=e311]:
                    - code [ref=e312]: fixture_atlas_hypothesis
                    - generic [ref=e313]: 未核验
                    - generic [ref=e314]: 模型假设
                  - paragraph [ref=e315]: 隔离模型假设：关联尚未核验。
                  - paragraph [ref=e316]:
                    - text: 来源修订
                    - code [ref=e317]: 10000000-0000-4000-8000-000000000002
                  - paragraph [ref=e318]: 未提供可定位的原文片段。
                - article [ref=e319]:
                  - generic [ref=e320]:
                    - code [ref=e321]: fixture_versions
                    - generic [ref=e322]: 已撤回
                    - generic [ref=e323]: 规则推导
                  - paragraph [ref=e324]: 隔离已撤回范围：>=1.0.0 <2.0.0 完整条件：仅在启用插件时适用，不能删除此条件。
                  - paragraph [ref=e325]:
                    - text: 来源修订
                    - code [ref=e326]: 10000000-0000-4000-8000-000000000003
                  - link "原文片段 [1]" [ref=e328] [cursor=pointer]:
                    - /url: "#events/10000000-0000-4000-8000-000000000001/evidence/10000000-0000-4000-8000-000000000005/revision/10000000-0000-4000-8000-000000000003"
                - article [ref=e329]:
                  - generic [ref=e330]:
                    - code [ref=e331]: fixture_historical_statement
                    - generic [ref=e332]: 已被新版本替代
                    - generic [ref=e333]: 人工确认
                  - paragraph [ref=e334]: 隔离旧结论：此断言已被新版本替代。
                  - paragraph [ref=e335]:
                    - text: 来源修订
                    - code [ref=e336]: 10000000-0000-4000-8000-000000000003
                  - link "原文片段 [1]" [ref=e338] [cursor=pointer]:
                    - /url: "#events/10000000-0000-4000-8000-000000000001/evidence/10000000-0000-4000-8000-000000000005/revision/10000000-0000-4000-8000-000000000003"
              - region [ref=e339]:
                - heading "原文修订时间线" [level=3] [ref=e340]
                - paragraph [ref=e341]: 保留本次响应中的来源与修订顺序。修订号属于各自文档；这不是合并或重判的执行记录。
                - article "修订 2 10000000-0000-4000-8000-000000000002" [ref=e342]:
                  - generic [ref=e343]:
                    - strong [ref=e344]: 修订 2
                    - generic [ref=e345]: 部分解析
                  - paragraph [ref=e346]:
                    - text: 安全公告
                    - generic [ref=e347]: 事件指向的最新修订
                  - generic [ref=e348]:
                    - term [ref=e349]: 原文修订
                    - definition [ref=e350]:
                      - code [ref=e351]: 10000000-0000-4000-8000-000000000002
                    - term [ref=e352]: 文档
                    - definition [ref=e353]:
                      - code [ref=e354]: 10000000-0000-4000-8000-000000000001
                    - term [ref=e355]: 来源
                    - definition [ref=e356]:
                      - code [ref=e357]: 10000000-0000-4000-8000-000000000004
                  - generic [ref=e358]:
                    - term [ref=e359]: 源发布时间
                    - definition [ref=e360]:
                      - time [ref=e361]: 2026-10-14T08:00:00+08:00
                    - term [ref=e362]: 源修订时间
                    - definition [ref=e363]:
                      - time [ref=e364]: 2026-10-15T08:00:00+08:00
                    - term [ref=e365]: 首次观察
                    - definition [ref=e366]:
                      - time [ref=e367]: 2026-10-15T10:00:00+08:00
                    - term [ref=e368]: 入库完成
                    - definition [ref=e369]:
                      - time [ref=e370]: 2026-10-15T10:01:00+08:00
                  - link "此修订的原文片段 [1]" [ref=e372] [cursor=pointer]:
                    - /url: "#events/10000000-0000-4000-8000-000000000001/evidence/10000000-0000-4000-8000-000000000004/revision/10000000-0000-4000-8000-000000000002"
                  - link "打开留存来源地址 ↗" [ref=e373] [cursor=pointer]:
                    - /url: https://example.test/fixture-source
                  - paragraph [ref=e374]: 外部地址可能已修订；历史引用以上方保存片段为准。
                - article "修订 1 10000000-0000-4000-8000-000000000003" [ref=e375]:
                  - generic [ref=e376]:
                    - strong [ref=e377]: 修订 1
                    - generic [ref=e378]: 历史解析未核验
                  - paragraph [ref=e379]: 安全公告
                  - generic [ref=e380]:
                    - term [ref=e381]: 原文修订
                    - definition [ref=e382]:
                      - code [ref=e383]: 10000000-0000-4000-8000-000000000003
                    - term [ref=e384]: 文档
                    - definition [ref=e385]:
                      - code [ref=e386]: 10000000-0000-4000-8000-000000000001
                    - term [ref=e387]: 来源
                    - definition [ref=e388]:
                      - code [ref=e389]: 10000000-0000-4000-8000-000000000005
                  - generic [ref=e390]:
                    - term [ref=e391]: 源发布时间
                    - definition [ref=e392]: 未知 / 未留存
                    - term [ref=e393]: 源修订时间
                    - definition [ref=e394]: 未知 / 未留存
                    - term [ref=e395]: 首次观察
                    - definition [ref=e396]: 未知 / 未留存
                    - term [ref=e397]: 入库完成
                    - definition [ref=e398]: 未知 / 未留存
                  - link "此修订的原文片段 [1]" [ref=e400] [cursor=pointer]:
                    - /url: "#events/10000000-0000-4000-8000-000000000001/evidence/10000000-0000-4000-8000-000000000005/revision/10000000-0000-4000-8000-000000000003"
                  - paragraph [ref=e401]: 该历史版本原文地址未留存
        - complementary [ref=e402]:
          - generic [ref=e403]:
            - generic [ref=e404]:
              - paragraph [ref=e405]: EVIDENCE / 原文依据
              - heading "证据检视" [level=2] [ref=e406]
            - generic [aria-hidden] [ref=e407]: ⌁
          - generic [ref=e408]:
            - heading "选择原文引用" [level=3] [ref=e409]
            - paragraph [ref=e410]: 打开事件后，选择事实或维度引用，查看指定修订版本的准确片段。
      - generic [ref=e411]:
        - generic [ref=e412]: 环境未由服务端标明
        - generic [ref=e413]: 版本未由服务端标明
```

# Test source

```ts
  4   | import { eventDetailFixture, fixtureEventId, fixtureOldEvidenceId, fixtureOldRevisionId, fixtureRevisionId, historicalEvidenceFixture } from "../../../frontend/src/features/events/event-detail.fixture";
  5   | 
  6   | async function fixtureRoutes(page: Page, options: { empty?: boolean; holdDetail?: Promise<void>; evidenceMismatch?: boolean } = {}) {
  7   |   const requests: string[] = [];
  8   |   await page.route("**/v1/**", async (route) => {
  9   |     const path = new URL(route.request().url()).pathname;
  10  |     requests.push(`${route.request().method()} ${path}`);
  11  |     let body: unknown;
  12  |     if (path === "/v1/auth/me") body = { user_id: "independent-r17-fixture-user", tenant_id: "independent-r17-fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") };
  13  |     else if (path === "/v1/health/live") body = { status: "live" };
  14  |     else if (path === "/v1/health/ready") body = { status: "ready", reason: "independent isolated fixture", dependencies: {} };
  15  |     else if (path === "/v1/events") body = { schema_version: 2, items: [eventDetailFixture.event], next_cursor: null, data_mode: "fixture" };
  16  |     else if (path === `/v1/events/${fixtureEventId}`) {
  17  |       await options.holdDetail;
  18  |       body = options.empty ? { ...eventDetailFixture, dimensions: [], claims: [], revisions: [], event: { ...eventDetailFixture.event, freshness: "unknown" } } : eventDetailFixture;
  19  |     } else if (path === `/v1/evidence/${fixtureOldEvidenceId}`) body = options.evidenceMismatch ? { ...historicalEvidenceFixture, revision_id: fixtureRevisionId } : historicalEvidenceFixture;
  20  |     else throw new Error(`Unexpected independent fixture request ${path}`);
  21  |     await route.fulfill({ status: 200, json: body });
  22  |   });
  23  |   return requests;
  24  | }
  25  | 
  26  | test("independent loading then empty schema2 detail remains unknown", async ({ page }, info) => {
  27  |   await page.setViewportSize({ width: 390, height: 844 });
  28  |   let release: () => void = () => { throw new Error("detail gate not set"); };
  29  |   const gate = new Promise<void>((resolve) => { release = resolve; });
  30  |   const requests = await fixtureRoutes(page, { empty: true, holdDetail: gate });
  31  |   await page.goto(`/#events/${fixtureEventId}`);
  32  |   await expect(page.locator(".event-detail-loading")).toHaveAttribute("aria-busy", "true");
  33  |   await expect(page.locator(".dimension-value")).toHaveCount(0);
  34  |   await expect(page.getByRole("region", { name: "事件详情", exact: true })).not.toBeFocused();
  35  |   await page.getByRole("region", { name: "事件详情", exact: true }).scrollIntoViewIfNeeded();
  36  |   await page.screenshot({ path: info.outputPath("loading-fixture-390.png") });
  37  |   release();
  38  |   await expect(page.getByRole("region", { name: "事件详情", exact: true })).toBeFocused();
  39  |   await expect(page.getByText("未提供该维度", { exact: true })).toHaveCount(9);
  40  |   await expect(page.getByRole("heading", { name: "尚未取得事实记录", exact: true })).toBeVisible();
  41  |   await expect(page.getByRole("heading", { name: "尚未取得修订记录", exact: true })).toBeVisible();
  42  |   await expect(page.getByText("事件时效未知；请结合来源版本与观测时间核查。", { exact: true })).toBeVisible();
  43  |   await expect(page.locator(".dimension-value")).toHaveCount(0);
  44  |   await expect(page.getByText("真实 / Live", { exact: true })).toHaveCount(0);
  45  |   await page.screenshot({ path: info.outputPath("empty-fixture-390.png"), fullPage: true });
  46  |   await writeFile(info.outputPath("get-caller-requests.json"), JSON.stringify(requests, null, 2));
  47  | });
  48  | 
  49  | for (const width of [1366, 390]) {
  50  |   test(`independent readable saved assertions and revisions ${width}px`, async ({ page }, info) => {
  51  |     await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
  52  |     await page.emulateMedia({ reducedMotion: "reduce" });
  53  |     await fixtureRoutes(page);
  54  |     await page.goto(`/#events/${fixtureEventId}`);
  55  |     await expect(page.getByRole("region", { name: "事件详情", exact: true })).toBeFocused();
  56  |     await page.getByRole("article", { name: "CWE 弱点", exact: true }).evaluate((element) => element.scrollIntoView({ block: "start", behavior: "instant" }));
  57  |     await page.screenshot({ path: info.outputPath(`conflict-hypothesis-fixture-${width}.png`) });
  58  |     const claims = page.getByRole("region", { name: "事实与来源断言", exact: true });
  59  |     await page.getByRole("button", { name: "事实与来源断言", exact: true }).focus();
  60  |     await page.keyboard.press("Enter");
  61  |     await expect(claims).toBeFocused();
  62  |     await page.screenshot({ path: info.outputPath(`saved-assertions-fixture-${width}.png`) });
  63  |     await page.locator("#claim-10000000-0000-4000-8000-000000000009").evaluate((element) => element.scrollIntoView({ block: "start", behavior: "instant" }));
  64  |     await expect(page.getByText("完整条件：仅在启用插件时适用，不能删除此条件。", { exact: false }).first()).toBeVisible();
  65  |     await page.screenshot({ path: info.outputPath(`hypothesis-withdrawn-fixture-${width}.png`) });
  66  |     await page.getByRole("button", { name: "原文修订时间线", exact: true }).focus();
  67  |     await page.keyboard.press("Enter");
  68  |     await expect(page.getByRole("region", { name: "原文修订时间线", exact: true })).toBeFocused();
  69  |     await page.screenshot({ path: info.outputPath(`saved-revisions-fixture-${width}.png`) });
  70  |   });
  71  | }
  72  | 
  73  | test("independent revision mismatch keeps evidence error and no quote", async ({ page }, info) => {
  74  |   await page.setViewportSize({ width: 1366, height: 900 });
  75  |   const requests = await fixtureRoutes(page, { evidenceMismatch: true });
  76  |   await page.goto(`/#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}/revision/${fixtureOldRevisionId}`);
  77  |   await expect(page.getByRole("complementary", { name: "证据检视", exact: true }).getByRole("alert")).toBeVisible();
  78  |   await expect(page.locator("blockquote")).toHaveCount(0);
  79  |   await expect(page.getByRole("article", { name: "CVSS 评分", exact: true })).toBeVisible();
  80  |   await writeFile(info.outputPath("revision-mismatch-get-caller.json"), JSON.stringify(requests, null, 2));
  81  | });
  82  | 
  83  | test("independent narrow screen status and new fact navigation target", async ({ page }, info) => {
  84  |   await page.setViewportSize({ width: 390, height: 844 });
  85  |   await page.emulateMedia({ reducedMotion: "reduce" });
  86  |   const requests = await fixtureRoutes(page);
  87  |   await page.goto(`/#events/${fixtureEventId}`);
  88  |   await expect(page.getByRole("region", { name: "事件详情", exact: true })).toBeFocused();
  89  |   for (const state of ["已取得", "未发现", "不适用", "有冲突", "受阻", "失败", "待处理"]) expect(await page.getByText(state, { exact: true }).count()).toBeGreaterThan(0);
  90  |   const hypothesis = page.getByRole("article", { name: "ATLAS 映射", exact: true });
  91  |   await expect(hypothesis.getByText("依据：模型假设", { exact: true })).toBeVisible();
  92  |   await expect(hypothesis.getByText("未核验", { exact: true })).toBeVisible();
  93  |   await expect(page.getByRole("article", { name: "CWE 弱点", exact: true }).getByText("隔离来源 B：CWE-20", { exact: true })).toBeVisible();
  94  |   await expect(page.getByText("事件已标为过期；以下保留已保存的信息，不能当作当前结论。", { exact: true })).toBeVisible();
  95  |   const factButton = page.getByRole("article", { name: "CVSS 评分", exact: true }).getByRole("button", { name: "查看断言与依据", exact: true });
  96  |   await factButton.scrollIntoViewIfNeeded();
  97  |   await factButton.focus();
  98  |   const metrics = await factButton.evaluate((element) => ({ text: element.textContent, bounds: element.getBoundingClientRect().toJSON(), fontSize: getComputedStyle(element).fontSize, lineHeight: getComputedStyle(element).lineHeight, minHeight: getComputedStyle(element).minHeight, outline: getComputedStyle(element).outline, viewport: { width: window.innerWidth, height: window.innerHeight } }));
  99  |   await writeFile(info.outputPath("new-fact-target-metrics.json"), JSON.stringify({ metrics, requests }, null, 2));
  100 |   await page.screenshot({ path: info.outputPath("fact-button-focus-fixture-390.png") });
  101 |   await page.keyboard.press("Enter");
  102 |   await expect(page.locator("#claim-10000000-0000-4000-8000-000000000006")).toBeFocused();
  103 |   expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}`);
> 104 |   expect(metrics.bounds.height, "project design requires action touch targets at least 40px").toBeGreaterThanOrEqual(40);
      |                                                                                               ^ Error: project design requires action touch targets at least 40px
  105 | });
  106 | 
```