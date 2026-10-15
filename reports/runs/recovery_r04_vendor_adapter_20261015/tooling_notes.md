# 未持久化的早期工具错误

记录的实际错误内容，原发生时间历史未记录；不把它们作为业务失败或推算耗时。

1. run_command.py 首次以 `name --cwd path -- ...` 调用，argparse REMAINDER 捕获后续参数，报 `the following arguments are required: --cwd`。改为 `--cwd path name -- ...`，后续真实命令 receipts 均已落盘。
2. 根据旧模块名称猜测读取 vendor_blog.py，Get-Content 返回文件不存在；rg --files 随后证实现有模块为 feed.py/repository.py，已经实际读取，未新增平行 feed/repository 框架。
3. PowerShell 未引用 `HEAD^{tree}` 时把括号内容处理成额外参数，git 报 `ambiguous argument 'dAByAGUAZQA='`。仅只读命令失败；引用 `'HEAD^{tree}'` 后得到 fdbd190925d4c8a3d00282602f3c830f961339bf，源码未修改。

get_graph_schema 缺 project 的真实 exit 1 已有 cbm_schema_before.log/receipt，修正后 cbm_schema_before_corrected exit 0。测试先行缺模块和 Ruff 首轮错误分别有原始日志，未删除或覆盖失败。
