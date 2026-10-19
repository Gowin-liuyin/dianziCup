"""Write the narrow read-only classification review with actual clock times."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
report = RUN.parents[1] / "reviews/recovery/G-C-R06-fixture-classification-review-1.md"
assert not report.exists()
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")
audit = json.loads((RUN / "fixture_origin_audit.json").read_text())
command = json.loads((RUN / "fixture_independent_tests.json").read_text(encoding="utf-8-sig"))
content = f"""# G-C · R06 前端 CSRF 测试字面量独立分类审查

文档首次创建时间：{started}
本次写作开始时间：{started}
最后更新时间：{started}
审查者：/root/r06_integrated_live_validation，未参与来源 UI 或分类表实现。
固定代码：1156b2ed6616e3a4297215c2893d2cbe633f5215；干净 detached WT D:/wt/r06-integrated-live-1156。

What this change does: 本轮只确认两份已冻结前端测试文件中的三个原正则命中是否为隔离 CSRF 夹具。没有修改分类表、scanner 模式/扫描根/阈值、业务代码或全局状态。

结论：Ship，限于下列三项精确 hash/offset 的 verified_synthetic_fixture 分类依据。由主控填写正式分类记录并重新执行原安全门；本结论不代表该门已过、整 R06 或 G-C 已验收。

## 来源、位置和作用

| 文件 | 原字节 SHA256 | 模式 / LF 规范文本 start:end | 行号 |
|---|---|---|---|
| frontend/src/api/source-catalog.test.ts | 54b175df5285f96cab764b96c8dd2989963a884a74613a2d651559915da28309 | original_secret_value_pattern / 2504:2526 | 28 |
| frontend/src/features/sources/source-admin-catalog.test.tsx | 118e1ec9471caddab3b68fb9275d836531534fb3f1370ba8b3d700d05e2e86ac | original_secret_pattern / 610:640 | 9 |
| 同上 | 同上 | original_secret_value_pattern / 610:640 | 9 |

源 git blob 分别 ab24b7e50119fa12e2792f0687176600c457bedf 与 83179db3353cb61d562317c61c40edd355e7556b。匹配原值不在本报告/消息输出；value hash、pattern hash 和定位在 [fixture_origin_audit.json](../../runs/{RUN.name}/fixture_origin_audit.json)。独立脚本确认工作目录文件与固定 SHA 的 git show 内容相同（只允许 CRLF/LF 差异）。

source-catalog.test.ts:25–34 通过 vi.stubGlobal(fetch) 返回本地合成的 csrf response，并断言 collectSourcePage 按原 body、固定路径、Cookie credentials 和 CSRF header 发送；source-admin-catalog.test.tsx:9/17–29 的 admin 明确 data_mode fixture，installFixture 同样只返回合成 auth/me、auth/csrf、collect 和 job 对象。afterEach 恢复 stub/cleanup；没有从进程、DPAPI、HTTP 或资产资料读取这些常量。它们并非产品默认口令、真实 session 或运行配置。

实际 production source-client.ts 仍调用共享请求客户端，CSRF 从真实 auth/csrf 得到；source-workspace 由真实会话代次/身份约束接入 App。源码/rg 与独立 CBM frontend/src 图交叉核实（442 nodes/1662 edges、0 skipped/partial；collectSourcePage both trace 在同 run），图仅辅助证明调用关系。已有独立 UI 报告 G-C-R06-source-admin-ui-review-1.md 的 SHA256 291703a3fceec671341db3963545c8917a1b9827cc44c7495b75b8a1fbe2cd03 再核对一致，该审查明确 Edge fixture 隔离与实际 live 未运行；本轮没有把该 fixture 审查当作产品在线事实。

## 实际验证

- 只读 origin 脚本 audit_fixtures.py/ps1：exit0，三个匹配与原安全门位置一致，原值未回显；与已授权 runtime、MinIO 和 DPAPI 登录秘密精确比较，碰撞 0。未读取模型/测绘 vault，故此项秘密集合不扩大声称。
- {command['started_at']} → {command['ended_at']}，cwd {command['cwd']}：{command['command']}，exit {command['exit_code']}，34 passed / 2 files / 0 failed / 0 skip。原日志 fixture_independent_tests.log 和命令 JSON 保留。均为显式 unit fixture，不计 live。
- 读取 AGENTS、R06、数据/API/测试合同和新版 Ponytail review；未参与分类实现；无业务/金标/分母/阈值、旧报告修改或 push。

没有发现此范围内的阻断项。网站 CAC 原 HTML 的公开脚本 query token 不在本轮三项分类中，不能称 synthetic；其仓外保留和脱敏迁移由主控另行取证，本轮没有修改原 raw manifest。

Verdict: Ship（仅上述三项固定 fixture 分类依据）。
Not checked: 未复跑全仓秘密门、真实 API/外源/browser 或整阶段；全仓门须主控新增精确分类后重跑。
"""
ended = datetime.now(clock).isoformat(timespec="seconds")
content += f"\n本次写作结束时间：{ended}\n"
report.write_text(content, encoding="utf-8")
print(json.dumps({"report": str(report), "sha256": hashlib.sha256(report.read_bytes()).hexdigest(), "written_at": ended}))
