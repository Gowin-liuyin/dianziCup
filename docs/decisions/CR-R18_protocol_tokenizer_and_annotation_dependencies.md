# CR-R18/R19 · 协议、明确输出预算与标注类型依赖

文档首次创建时间：2026-10-16T08:20:09+08:00
本次写作开始时间：2026-10-16T08:20:09+08:00
本次写作结束时间：2026-10-16T08:20:09+08:00
最后更新时间：2026-10-16T08:20:09+08:00
主控：/root。状态：批准建设目标内依赖 checkpoint；不签 R18/R19/阶段验收。
基线：5b29b3e8c6ea1d10ca50cf2d2006f8460b53253c；独立提案 bd1e07ce2aa328e7408d9cf42c5dc9d66e0719ff/100bf16dfc9d77a722ba7933521261d2c1677b95。

复用官方 MCP SDK==2.3.0，两 transport 后续使用同共享 REST/PG 权限能力；不手写协议或改用旧 v1 FastMCP。CLI 用现 httpx、Pydantic 与 argparse，不加 SDK cli/rich extra。tiktoken==0.14.0 用 o200k_base 的指定 8000 tokens 输出预算；它不是 DeepSeek/Claude 计费 token 数。运行前必须准备官方编码 bytes/hash，没有数据必须 not_configured，不按字符数假报 tokens。现只安装库，未初始化编码/模型/服务器，尚无客户工具实调用。

官方类型 stubs types-jsonschema==4.26.0.20261006 对应既有 jsonschema4.26.0，支持 R19 独立标注工具 strict 类型检查，避免 Any/cast/global ignore。原 97 个包版本未变，新锁 113 个包；新增 16 个（含 httpx2/httpcore2/mcp-types/PyJWT/cryptography/multipart/pywin32/regex/requests/stubs 等，精确清单见 dependency_install_receipt.json）。旧 httpx/httpcore 留用业务，不用同名假替换。不是旧依赖主版本升级。

来源及许可：[MCP 2.3.0](https://pypi.org/project/mcp/2.3.0/) MIT，wheel dd0c44c089d16453e8ae31a3877a0054d7a2314caaa81f5e0541b9b1734b2377；[tiktoken 0.14.0](https://pypi.org/project/tiktoken/0.14.0/) MIT；[types-jsonschema](https://pypi.org/project/types-jsonschema/4.26.0.20261006/) Apache-2.0，wheel29301f4e65e3928540cdf5e23ad716e38bb0c0b416a48dada213edd3d70206ec。最终发布物保留原许可证，不把本库许可扩张为第三方数据库许可。

兼容/迁移：只新增必要依赖，原八公开对象、cookie Origin/CSRF、PG facts/job authority、200同步/10MiB异步/10000组件、评分分母/阈值/金标均未变；无数据库迁移。API Key/schema/SDK package 与沙箱后续各自冻结并新独审。semantic optional runtime 按既有批准锁安装 ONNX1.24.4/tokenizers0.22.2/numpy2.4.2，08:15同步前主venv这些未安装；不冒称下载过权重或完整语义产品已运行。

真实验证：08:15:36–51 三命令 exit0：uv add --no-sync 两库、dev stubs、uv sync --locked --extra semantic，详 commands.json。最初同进程 import smoke exit1，安装后原 interpreter 没重处理新 pywin32 .pth；新 child 实际导入与 MCPServer 离线构造 exit0，具体起止见 receipt/fresh_interpreter_smoke.log。原工具异常保留于实际调用记录，不把它说成协议不兼容，也不覆盖失败计数。模型/测绘调用0，包网络请求数/费用 unknown。

回滚：先关闭新 MCP/SDK output_budget/标注类型路径，再回退本依赖 checkpoint 三文件并按需要 uv sync --locked --extra semantic；保留 PG、标注 sidecars/历史与缓存，不 destructive downgrade/drop，不删用户数据。读取原调用者/锁与类型测试后审。任务影响 R18/R19，以及 R12 的现语义运行环境，真实MCP HTTP/stdio、8k预算、安装 wheel、客户调用/权限撤销、人工双人裁决仍待实际验证；库安装不替代这些门。
