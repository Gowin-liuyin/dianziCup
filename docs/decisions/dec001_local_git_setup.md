# DEC-001 · 本地 Git 建立（本轮决策落实记录）

决策来源：项目负责人 2026-09-30 指令（T01 续执行提示词 §4）。本文件记录实际执行结果；T00 时点的历史说明保留于 `docs/decisions/repository_mapping.md`，不重写。

## 授权边界（本轮）

- 允许：确认目录正确后首次创建本地 Git 元数据（目标分支 main）；仅在 `origin` 不存在时配置远程 `https://github.com/Gowin-liuyin/dianziCup.git`。
- 不允许：`git add`、`commit`、`push`、`fetch`、`pull`、`reset`、`clean`、强制推送、修改远程可见性、公开发布、修改全局 Git 配置。
- 远程查询成功只是一次访问观察（T00 `ls-remote` 退出码 0、0 ref），不等于拥有推送权限或发布授权。

## 实际执行（2026-09-30 20:23:48，日志 `reports/runs/t01_git_init.log`）

| 步骤 | 命令 | 退出码 | 结果 |
|---|---|---|---|
| 前置检查 | `git -C D:\dianzi rev-parse --is-inside-work-tree` | 128 | 不属于任何既有仓库，不是其他仓库子目录 |
| 前置检查 | `.git` 是否存在 | — | False，无重复初始化风险 |
| 初始化 | `git -C D:\dianzi init -b main` | 0 | `Initialized empty Git repository in D:/dianzi/.git/` |
| 远程检查 | `git -C D:\dianzi remote` | 0 | 空，origin 不存在 |
| 配置远程 | `git remote add origin https://github.com/Gowin-liuyin/dianziCup.git` | 0 | 成功（本地配置，未联网验证） |
| 校验 | `git branch --show-current` | 0 | `main` |
| 校验 | `git remote -v` | 0 | `origin → https://github.com/Gowin-liuyin/dianziCup.git (fetch/push)` |
| 校验 | `git status --porcelain`（仅计数） | 0 | 12 个未跟踪/修改条目；**未执行任何 add/commit** |

## 遗留事项

- 提交、推送、忽略规则（`.bootstrap/` 暂存目录不得入库）等待后续授权后执行；本轮工作全部以文件哈希与日志标识版本，无 commit SHA。
- 远程为空仓库；推送权限、仓库可见性与发布授权仍未确认（BLK-003/DEC-001 后续部分）。
