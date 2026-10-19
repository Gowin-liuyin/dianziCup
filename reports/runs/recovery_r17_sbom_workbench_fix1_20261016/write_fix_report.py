"""Write measured fix evidence without replacing the original failed review or claiming live acceptance."""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/tasks/R17-sbom-workbench-fix1.md"
SOURCE = "18d05f1c5842ed7a57f3be9f0351ede4af0b018a"
now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
if REPORT.exists():
    raise RuntimeError("do not overwrite first report creation")
commands = sorted([json.loads(path.read_text(encoding="utf-8")) for path in RUN.glob("*.command.json")], key=lambda item: item["started_at"])
rows = ["| " + item["log"] + " | " + item["started_at"] + " → " + item["finished_at"] + " | " + str(item["exit_code"]) + " |" for item in commands]
text = f"""# R17 · SBOM PURL 展示防线 fix1

文档首次创建时间：{now}
本次写作开始时间：{now}
本次写作结束时间：WRITE_END
最后更新时间：WRITE_END
本报告证据截止时间：2026-10-16T08:44:17+08:00
实际实施开始：初始化完整时间历史未记录；最早结构化命令为2026-10-16T08:30:18+08:00。
作者：/root/r17_sbom_workbench_frontend_integration
独立审查：原非作者 /root/r17_sbom_workbench_first_independent_review 待定向复核。
任务状态：awaiting_review（fix实现 complete；整R17/T42及G-E仍partial/未过门）。
工作分支：codex/r17-sbom-workbench-fix1
工作目录：D:/wt/r17-sbom-workbench-fix1
原基线：7a653880af12e4160ca8edf26fccbaf5d1e6f0f0；原业务源码406187742a72655bc5f8825f42bc0f1a440af218。
本次已测源码：{SOURCE}；冻结于2026-10-16T08:39:29+08:00。
材料提交/推送：写作时尚未发生；此任务不push、不改progress、不自签accepted。
验证：unit/contract passed（isolated）；security/frontend/e2e passed（synthetic）；真实PG/0022/defaultAPI integration not_run；live blocked；manual not_run。

## 1. 问题与验收边界

新独立初审 needs_changes 报告 SHA-256 214d8367cde4614e45d765c8326504db18ea9da4fe19859e49a1b3f457ee9ecb、run manifest d7f22390774e910a685c6db24d66beb2b63176e24b31fae7c4f7e09e7731aeb7。唯一Must1：SBOM snapshot purl与sidecar target_ref共享isSafeSbomPurl将版本中的percent编码slash误作解码后的包路径分隔，encoded at也未拒绝。原三值在两个调用方被接受，Edge中显示本应隐藏的合成位置；不是生产泄漏证明。

三个固定输入为原独审的encoded绝对版本、encoded at与二次encoded slash，见reviewer原脚本与专属test；未读取任何.env文件，字符串均为明确synthetic测试值。验收必须使两个产品调用路径均拒绝，在原M01同步撤销机制中清除私有DOM和迟到恢复路径；合法npm @scope继续可读。

## 2. 最小修复、复用与调用方

只改frontend/src/features/assets/asset-contracts.ts的共享helper，并加两个专属测试文件（sbom-purl-fix1.test.ts、r17_purl_profile_cases.ts）。App、导航、CSS、认证、sidecar合同/marker、业务DTO、后端、迁移、锁、global属性与原测试均不改。

成熟Python PackageURL0.17.6源码的处理顺序为：npm原始@scope先分离，原path对@做rpartition，再decode字段。复用这一明确边界：原始版本分隔在percent解码之前固定；namespace/packagePath/version分别一次decode；version的decoded slash或at、字段中的残余percent/URI/控制码都拒绝。双层编码第一轮留下percent即拒绝，不无限解码，不再按最后slash猜有无version。纯展示安全子集不构造组件身份、生态适用、版本真值，不平行重写完整PackageURL业务解析器。无新依赖。

原parseSnapshot及sbom-contracts.safeReference仍调用同一helper，ScopeMismatch沿现onFailure/isCurrent撤销路径。JSON/CSV、raw File上传、CSRF/Origin/幂等、历史绑定、普通503、安全链接与redaction markers未改变。URI/package PURL只是声明，未增加URL fetch或服务器文件读取。

CBM在业务修改前建立独立frontend/src full索引，冻结18d05后刷新，733 nodes/2960 edges，parse_partial/unusable/skipped 0；原/新trace与rg核14个入向调用者及App真实路径。缓存不提交。57个原test/spec文件相对7a LF逐字不变，包括原518及原18。

## 3. 原诊断与正确验收的区别

原独审两个MUST Edge先断言bug的危险值“可见”、截两张图，再断言应撤销。修对后该bug-presence诊断必然在“泄漏可见”处失败，不能称它原样绿，也不能删掉这条原断言。已把原完整spec字节封存（SHA eb72ec82f8c962002c0695634a1053344d3c04d8191cbad9d289663990801155）；资源adapter只将26173改26373，原断言原样，未改原作者/独审目录。

在未改业务源码前，原3 unit按同输入复现0/3，原2 Edge按同断言复现0/2，危险原值可见的PNG、JSON及两份error-context完整保留于edge_red_artifacts。fix另加6个正确验收（3输入×snapshot/ref）：断言工作区已撤销、原值没有DOM、snapshot路径尚未发sidecar请求；4个合法npmscope同时验证snapshot与ref可读。旧诊断不作为正确验收分母；新验收10/10。

## 4. 固定后端校准与问题台账

手写36种原始/一次/二次percent、Unicode、控制、伪URI、npmscope和版本样例，expected不是由新UI计算生成。固定Git5be真实服务display profile校准：34种直接相等。两种原始tab/newline在PackageURL底层URLsplit会被剥除，纯profile返回true；真实同Git的SBOM适配入口则以invalid_sbom_string拒绝，客户端既有string边界也拒绝。保留首次差异红，不将36说成纯profile全等；对这两种额外执行实际adapter负例，两次均拒绝。没有更改手写false期待。

| 问题 | 发现/复验事实 | 状态 |
|---|---|---|
| Must1 | 原3 unit 08:31:49→08:31:52退出1；原2 Edge 08:32:25→08:32:46退出1；helper改后37首轮过；冻结后557/66全过 | 作者修复，待原非作者复核 |
| 后端source guard工具误判 | 08:35:54以raw==Git LF比较reviewer导出的CRLF，退出1；没有代码变更。保留两hash并核LF相等 | 工具修复，原红留档 |
| 两个原始控制码校准差异 | 08:36:29纯profile34样例发现tab/newline两差异，退出1；08:37:20实际adapter拒绝，08:39:23最终36例保持34profile相等+2adapter拒绝 | 已解释/证明，不伪称全等 |

一次functions脚本quote语法错误发生在tool调用解析，未运行测试或写业务文件，随后纠正参数；不伪算业务失败/通过。本轮没有第二个产品Must。没有修改金标、阈值、分母、skip或原失败断言。

## 5. 实际验证

原目录和完整argv/开始结束/exit位于每个command.json；下表时间均实际Asia/Shanghai到秒，原Edge JSON startTime为UTC明确保留。不同轮通过数不累加。

| 原日志 | 开始 → 结束 | exit |
|---|---|---|
{chr(10).join(rows)}

冻结源码unit_frozen.json：557总/557pass/0fail/0pending/0todo=原518+新增39个测试（36种PURL输入，原Must三值另有精确Scope类型断言）。不是557种独立输入。原518的所有函数与期待未改。原8个跨语言真实serializer synthetic样本继续在原518中，不重复加分。

冻结dist Edge：66 expected/0unexpected/0skip/0flaky=原18+原独审一般38+新正确验收10；仍是fixture，不算PG/live。两条原“先证明bug”诊断只在红阶段运行，按上述理由单列。新同原输入的六条DOM撤销和四条npm正例是真实Edge/dist操作，原一般38覆盖权限/迟到/503/URI/历史/390/动效等回归。

Typecheck/lint/build在18d05后重新运行均0；Python业务未修改，不宣称mypy/Ruff已运行。后端校准只纯profile/adapter，不装配API，不连PG。所用node_modules通过junction复用，未设置只读ACL，可能生成Vite缓存；不安装或改依赖/锁，缓存/dist/tsbuildinfo不提交。

最后检查26373 listener0与本任务preview node0，未全局kill。原author118 members+两冻结Gitcontrols共120以及独审272 members，前后实际hash/长度漂移0；reviewer另一个checksum控制文件首轮未单独记录rawhash，未假称其前后字节比较。原canonical manifest hash前后均匹配给定值。

## 6. 计划/合同与材料

没有新增公共协议或批准决策变更。修复仅落实已冻结CR-R11的安全展示和R17权限/无秘密边界，代码helper安全子集按原始分隔与成熟解码语义处理；成熟组件仍在后端权威链中。

本专属run .gitattributes复用root许可的精确规则：* -text保raw，log/xml保原空白，json只允许CR-at-eol仍检查真实空格/tab。未改root/global或原run。红/绿浏览器使用独立outputDir，原PNG/error-context不覆盖。raw与Git LF分别记录；材料manifest与提交后blob逐个核，控制receipt不循环嵌自身SHA。

## 7. 评分与场景

D2/E1/X1：已证实私有DOM撤销负例、合法scope、实际独立反馈闭环及原材料/测试保护。F2/F3/U04/U05/U08仍仅输入与历史声明展示切片，不把purl安全展示当生态版本研判/资产真值/更新重判，也不提升优秀档评分。

## 8. 交接与限制

交原非作者对冻结18d05及最终材料定向复核：原三输入、对应两产品路径、raw版本边界与npmscope、36固定后端校准、原518/18与scope/迟到回归、code/raw/GitLF与392原材料不漂移。作者状态awaiting_review，Must关闭由独审报告决定；原needs_changes报告保持不变。

生产0022/defaultAPI/真实授权SBOM/browser live、完整R17/T42/G-E、研判/导出、manual/录像仍未证明。实际秘密读取0、模型/测绘/付费provider调用0，费用unknown。main用户tsbuildinfo不触碰；本WT构建生成的tsbuildinfo不提交。没有push或对外发送消息。

## 9. 文档修订记录

{now} 首次成稿，由本实现Agent根据真实红绿/源码冻结/控资源记录写入；first创建时间不据mtime推测。首次实现初始化未记录时间保持未知，后续仅以结构化命令时间证明。
"""
finished = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
REPORT.write_text(text.replace("WRITE_END", finished), encoding="utf-8", newline="\n")
print(json.dumps({"created_at": now, "written_at": finished, "report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest()}))
