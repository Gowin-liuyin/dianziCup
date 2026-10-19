# R06 · CNNVD 官方浏览器下载核对

记录时间：2026-10-17T02:18:56.6449890+08:00。任务切片状态：blocked；原因分类：blocked_login。整 R06 保持 in_progress / partial，本切片不登记 accepted。

## 范围与输入输出

授权输入是用户在 Codex 内置浏览器登录 CNNVD、允许取得当天官方 XML 的意图；此前未收到登录完成确认。目标入口为 `https://www.cnnvd.org.cn/frontend/childHome`，目标日期为 2026-10-17。若可见登录和下载权限成立，输出仅为一次官方 UI 下载的私有原件及净化元数据；本轮登录前置未成立，输出为阻塞收据，无下载原件。

本轮只写本报告与 `reports/runs/r06_cnnvd_browser_download_20261017/browser_receipt.json`。未修改业务代码、progress、合同、公共配置；未提交或 push。无需新增代码测试，unit / integration / API live 为 not_run；manual 可见状态核对已执行，下载验证为 blocked。

## 已读依据与仓库边界

已读 AGENTS.md、docs/plan/00_execution_map.md、docs/plan/12_recovery_task_cards_20261014.md 的 R06 卡、docs/plan/07_sources_and_resources.md、CR-R03 来源口径、CR-R06、progress/task_state.json 的 R06 记录与 CNNVD 最近交接。R06 输入输出与六项原验收条件未删改。恢复主计划规定 CNNVD 人工导入另标，不能把手工导入计为全自动；本轮更未取得导入材料。

仓库分支 `codex/full-delivery-recovery`；读到 HEAD `9726363e0d9b33467ba40a06a8bde9548b46bccf`。当前存在他人未提交修改，全部保留。Computer Use 与 Ponytail 指示已读；本轮使用 CUA 浏览器允许 UI API，不控制原生应用、不引入实现或依赖。

## 真实操作与结果

1. 初始 CUA 调用严格只执行 `cua.getTab({url: "https://www.cnnvd.org.cn/frontend/childHome"}, {browser: "iab"})`；工具返回指定 tab 不存在，并返回完整 UI API 文档。
2. `cua.listTabs({browser: "iab"})` 返回 `[]`。这仅描述本轮可控制的 IAB 会话，不推断其他浏览器或用户账号状态。
3. 新开同一个获授权 CNNVD 官方入口，页面实际重定向到 `https://www.cnnvd.org.cn/login`。工具初次创建后的变量赋值未成功，但页面已创建；随后通过工具返回的确切 tab ID `1` 重新绑定，没有重试导航或重复创建。
4. 可见页面标题为“国家信息安全漏洞库”；登录页面有“个人用户登录”“单位用户登录”和“登录”控件。未读输入框值，未读个人身份、cookies、localStorage、sessionStorage、token 或其他秘密。
5. 当前可见会话不能确认登录完成，故未进入当天下载 UI、未点击下载、未解决验证码、未登录代填或购买新服务。下载次数为 0；API 调用、付费调用、模型调用均为 0。
6. 此新建官方 tab 已 `markHandoff()`，保留登录入口供用户在当前内置浏览器继续。没有导航、关闭或修改其他用户 tab。

以上是实时 UI 观察，无 HTTP 状态或 API 授权证据。记录时间是观察完成后的本机时间，不冒充精确页面首次加载时点。未取得文件，因此 file_path / bytes / SHA256 / 文件类型 / XML 条目数均为 null，未执行 XML 内容或索引检查。

## 命令、验收与偏差

真实只读 shell 命令包括读取上述文档、`git status --porcelain --untracked-files=no`、`git branch --show-current`、`git rev-parse HEAD`；Git 读取退出码 0。一次混合文档检索引用了不存在的 `docs/plan/09_recovery_execution_plan.md` / `contracts/recovery_task_manifest.json`，退出码 1；后续通过实际 `docs/plan/11_full_delivery_recovery_20261014.md` 与 `12_recovery_task_cards_20261014.md` 找到并读取 R06 指示，该失败不是业务测试失败。

手工验收真实结果：指定旧 tab 查找失败；当前 IAB tab inventory 为空；同官方入口导航到登录；无下载。业务、合同、集成、下载完整性测试均未运行，不编造通过数量。未取得当天列表、文件大小或下载权限；更不声明官方 XML API 授权、自动增量接入或整卡 live 通过。

F1 / R1 的 CNNVD 来源准备证据只支持“官方入口可见，当前可控制会话需要登录”；P1 连续自动采集与时效没有新增证据。计划偏差只有可见登录前置阻塞，没有替代来源、规则或算法。

## 最小阻塞与后续建议

最小输入是用户在当前 Codex 内置浏览器此 CNNVD 官方 tab 完成正常登录并确认完成；无需向聊天发送账号、密码、Cookie 或 API key。之后再有界核对当天官方 XML 下载权限，并按授权最多下载一次。若 UI 要求验证码、付费或额外授权，保留明确阻塞，不绕过。本切片到此停止，其他 R06 独立工作不受影响。
