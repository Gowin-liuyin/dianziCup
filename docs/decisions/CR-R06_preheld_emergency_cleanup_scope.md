# CR-R06 · 采集辅助进程故障收尾范围

文档首次创建时间：2026-10-16T12:25:25+08:00
本次写作开始时间：2026-10-16T12:25:25+08:00
状态：approved_for_implementation；kernel fix1仍needs_changes，真实采集未激活。

独立真WSL复现：后代pidfd_open OSError逃逸，关闭已有句柄后child/leaf遗留；只扩大catch仍残留leaf，永久pin失败不能用现有接口安全整树清零。批准原minio_segment.py及新增minio_controller.py两个operations文件：复用现有controller fork一个有界helper，不新增常驻服务。nonce envelope及owner/target sibling共享原512MiB、swap0、1CPU、128pids；额外1controller PID计入原cap，不翻倍。

启动前校验activation、prepared controller hash、boot/nonce/inode/helper birth及独立SID。controller最多16预持句柄，helper预留128pin+4IO FD，RLIMIT/open预检失败不得Popen。所有kill/procs/events能力在资源故障前建立；freeze后只对已证明同nonce/ancestry且无陌生成员的target发group kill，events0和held helper ACK必须实测。未知成员拒绝group kill，不伪造ACK、不移动他人PID。parent死亡helper仅将自己PID移到owner sibling，在scope外完成预持能力收尾。

OSError路径保留已证明句柄，先安全TERM/KILL/ACK再关闭；释放reserve后最多一次重试，共同15秒清理及22500秒硬截止保持，普通IO TERM10/KILL5不放宽。原sourcejobs450/HTTP35100/6小时21600秒/CPU20%及1200CPU/总2GiB上限均不变。私有旧8operations/10core bundle不覆盖，新prepared初始ready=false，独立review和rootfreshgate通过才激活。此授权不启动实际collector、MinIO或付费API。

兼容：原所有正常启动/退出/暂停及Windows/Linux路径复跑；增加永久pin、真实EMFILE、parentdeath、未知成员、入口失败无child、FD泄漏负例。迁移仅新prepared manifest/hash；回滚停止自有nonce进程、恢复旧未激活prepared，保留故障日志，不能杀共享资源。整阶段持续采集仍未通过，旧1670.46秒观察不得拼接为6小时。

本次写作结束时间：2026-10-16T12:28:28+08:00
最后更新时间：2026-10-16T12:28:28+08:00
