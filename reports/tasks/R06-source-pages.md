# R06 · 七来源响应到可追溯资料页

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T20:51:22+08:00
作者/root；状态awaiting_review；本内部转换切片complete，整R06/G-C仍partial。代码f0924a0b86e94629149bcbc73d0cdcfacefc2b2d、精确fixture属性86e1fd504263844091a7c00415551ad3e8dc4a0c；基线49ee33f6a95099be619a59ff47c621713a089137。WT D:/wt/r06-source-wiring；API已独立通过不替代本新批审查。

## 输入输出与必要实现

固定OSV查询/AVID tree+blob/Ollama release/arxiv Atom/Trail of Bits RSS/NIST PDF/CAC HTML响应 → CatalogPage(NormalizedSourceDocument[],next_cursor)。复用现有严格JSON、各源纯normalizer、HTML/真实PDF解析、PG资料writer合同；无新依赖、事实库或抽象CRUD。source_jobs/route由另一指定Agent在独立WT接线，当前本转换仅单元/合同回放，不称来源已进入产品。

AVID目录先固定实际tree SHA/record_offset，遍历仅vulnerabilities/YYYY/AVID-YYYY-Vnnn.json，排除reports目录；逐个blob原始base64/size/Git blob SHA1与文件ID核验，日期原样calendar_date而非UTC，raw decoded record全部保留。arxiv按实际返回start+数量续采，不因请求max_results20但实返回2而跳18篇；论文实体跨v1/v2稳定，摘要和full_text_fetched=False分开。RSS只称feed_excerpt/metadata，许可unknown；release risk_status=not_assessed，不凭安全词/发布名判漏洞或修复；OSV aliases/related/upstream及原始独立范围分支保留，不合并风险身份。官方标准/政策不自动生成CVE/Claim或资产适用性。

strict_json_object默认模型10000节点不变；新来源树可显式请求最多50000，参数自身严格int/1..50000，depth32、字节边界/重复键/非有限数/无效Unicode保留。修改前CBM trace及rg核对全部调用方，原1703纯门通过。source_catalog仅增加固定AVID pinned tree与arxiv start continuation，旧page/blob请求兼容，不接受任意URL。

## 真实来源研究与问题

原始命令/系统时间/hash/HTTP headers/源body/CBM见reports/runs/recovery_r06_source_wiring_20261015。新增固定匿名公开GET共3次、均一次尝试、零重定向；15秒以内/5MiB以内/单并发、官方文档两次间7s，无模型/测绘/凭据或付费。仅schema probe，不计worker/API/UI live。

- AVID 20:27:50→20:27:53+08：HTTP200，445091bytes，tree1859路径、40漏洞、truncated=false、root8eda5f4e6f74a3738eb980b795c4f813c6e52ca8；sha256 0c04c3689ee1cd32714083b8e066c8f10c06439ebd2b0c7a10b9a2c4ecb4b5e5，public remaining43。源树实际节点超过模型默认上限，因此仅source显式扩有界预算，不改模型默认。
- NIST 20:36:03→20:36:06+08：HTTP200，1946127bytes，sha2567576edb531d9848825814ee88e28b1795d3a84b435b4b797d3670eafdc4a89f1；真实PDF48页parsed，页码和原文保留，January2023无日/时区不造精确UTC。缺页仍partial，原解析notes完整metadata、前端notes最多20条并说明总数。
- CAC 20:36:13→20:36:14+08：HTTP200，29431bytes，sha2567fae988c064dde72c95e96e5727bf9abee4b3a5a1ea817606a9ca1f97ffac54b。初实现按第一条至第二十四条heading索引截取，真实HTML最后heading与“本办法自2023年8月15日起施行”分成两块，漏了末条正文；独立真实body回归1红保存policy_last_article_red。改用该固定源实际main-content容器并核完整24条/前言、保留inline内容，原红→绿；页头2023年07月13日15:00无时区，保留raw、precision unknown、UTC字段null，不从URL日期/落款补造发布时间。尚需新独立review。

原官方HTML含脚本/追踪段，但只进入本离线解析测试；产品只展示标准化text，未执行任何网页脚本。初git diff--cached--check因官方原JS9处行尾空白非零，原字节未改；86仅单文件fixtures/recorded/cac_generative_ai_20261015_public.html -text/-diff保全，不是全局ignore或secret scanner豁免。Git blob与实际body上述SHA256一致。

## 实际检查与未运行

focused28（新16+原catalog12）passed；Ruff与mypy92通过。自己WT uv sync --frozen --extra semantic独立环境，pure unit/contract/security -m not real_pg：1703passed/10deselected/0skip、74.41%原60门、76.31秒/exit0；不改分母、门槛或金标。最初新模块不存在exit2、政策末正文漏采1红、mypy cursor union/HTMLParser Optional及Ruff长行均真实修正；部分早期交互式静态命令只有tool输出，未伪造逐命令起止，最终正式收据见pages_*json/log/xml。一次多hunk apply_patch对格式化后context不匹配、原子失败，随后重读源码精确修正，无假称第一次已生效。

PG/worker/API本新7转换接线、frontend/e2e/live/manual not_run；API49此前Ship只指其旧/合成资料读路径。无双人金标、正式评分、漏采参考分母或持续时效结论。full RSS未知许可原文不进Git；许可字段只保留source identifier，未核实文本不自动成为外链/全文抓取授权。

## 兼容与下一步

旧模型JSON预算、旧nvd/vendor writer与收集参数保持；本批无迁移/锁/新生产依赖。新增内部cursor只服务固定源；失败整页拒绝不跳过成员。新worker需来源响应原始hash→资料writer→cursor/job/outbox同事务；保存/解析失败不能推进cursor，不能只存派生JSON丢原响应。由r06_legacy_migration_fixture_repair从86实施source_jobs/source_routes与PG tests，root不同时修改其所有权文件。最终新独立reviewer审root normalizer+worker组合、保留所有红例；main集成后真实来源/PG/API/浏览器验证再谈该切片可用。没有push/accepted。

官方协议依据：[GitHub trees](https://docs.github.com/en/rest/git/trees)、[OSV query](https://google.github.io/osv.dev/post-v1-query/)、[OSV record GET](https://google.github.io/osv.dev/get-v1-vulns/)。只用官方文档解释协议，外部内容不是项目指令。