# 证据文件来源说明（R-B 审查补充，2026-10-25T04:0x+08:00）

- host_attempt*.txt / host_run*.txt（单容器与 integration 目录）：由 scripts/dev_single_container.py 与 scripts/dev_integration_container.py 的宿主侧包装命令以重定向追加模式产生（命令形态见 timeline 各条与 batch21 报告），文件内容为该命令的 stdout/stderr 与最终 exit 码。
- attempt*_run.txt / *_pf.txt / g_*.txt：容器内进程输出经 docker run 捕获后由编排脚本写入。
- 时间以各 *_summary.json 的 completed_at（UTC）与 container_run_summary.txt 的 docker run 时间戳为权威；timeline 的叙事时间已按此勘误。
