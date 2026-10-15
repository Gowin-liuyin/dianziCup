探索记录（不计为业务测试）：
- 初次主目录rg目标docs/recovery与contracts/api/v2不存在，实际返回exit1。冻结仓库使用docs/plan/12_recovery_task_cards_20261014.md与contracts/schemas/public_api_v2.json，不猜另一份合同。
- 首次PowerShell未引用HEAD^{tree}被解释为-encodedCommand参数，git显示ambiguous argument。随后始终单引号引用该参数，原/最终tree均实际取得。
- CBM cli --help实际exit0；cli help实际exit1 unknown tool。依据主控已验证工具名执行index_repository/get_graph_schema/trace_path，raw分别保留。不由错误命令推论CBM功能不存在。
- rg命令两个Windows未展开的question*、R05*路径glob报错；随后使用目录及-g文件筛选、git show读取。一次寻找既有backend/auth路径不存在；未将其当业务失败。
- 独立WT npm ci --ignore-scripts --no-audit --no-fund实际exit0，added299，已有锁未改。Node v24.13.1，npm11.8.0。此探索安装的原始输出在工具记录；未冒称它有独立command.json。
- 尝试DTO只读辅助子Agent返回agent thread limit reached；未启动或参与本审查。随后主控明确槽位分配，全部审查由本reviewer执行。
- npm build生成已有受跟踪frontend/tsconfig.tsbuildinfo。本reviewer仅还原自己由build造成的生成变动：git restore --source=<当时被审SHA> -- frontend/tsconfig.tsbuildinfo；最后worktree clean。未恢复作者/主目录任何用户修改。
- 初审确证红例NEG01保留e2e_negative.log/json/error-context；不改断言、不改阈值、未skip。新SHA通过原样NEG01，另保存e2e_recheck。
