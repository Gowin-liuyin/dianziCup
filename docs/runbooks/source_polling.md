# 固定公开来源自动轮询

自动轮询复用已有PG权威任务与Celery beat/worker；没有独立游标文件或内存事实库。首次启用前需完成数据库前向迁移、真实网关/原文存储配置和来源可用性核对，环境中不要写任何下载材料提供的凭据样例。

在可信运行环境显式设置`SOURCE_POLLING_ENABLED=true`后启动worker和scheduler。compose通过同名变量透传，默认false；配置false后重启worker/beat，停止创建新轮次，已入队任务继续依原请求/页数上限完成，历史及游标保留。直接调用disabled任务不会连接数据库。不要用重置游标、删除任务或切换fixture模式代替停机/恢复。

beat每60秒安排一次`ai_intel.sources.poll_due`；它只在单个PG事务中安排九个固定source key。vllm_vendor每30分钟，其余每60分钟，UTC桶固定window_end。每源每轮最多5页，原worker每页3次attempt上限/7秒间隔/有界HTTP超时保持。AVID一页最多目录+blob两次GET，不能把page数叫HTTP数。API仍可显式提交1–20页backfill/live任务；手动与自动共享源租约和游标，不互建真值。

重复tick、多beat或重启不会为同源同桶重复创建root任务。包括continuation在内的活跃来源工作先续接，不叠加新轮次。若旧窗口未完成，worker按原窗口继续，partial只表示本次页数预算耗尽；不能据此宣称所有数据已采完。单次poll最多新建9个root jobs，source队列活跃总数>500或source payload非法/超4096字节时明确报错并不创建更多任务；现有来源请求远小于该界，防止积压时放大负载。

网关保持固定域/路径、DNS/IP/TLS/MIME/大小/超时限制，不跟随任意redirect；签名webhook、CNNVD认证API、EPSS/KEV更新不由这九固定来源poller冒充。无新增模型或测绘付费调用。供应商额度、HTTP429、来源结构变动和网络失败分别保留在PG任务/attempt；polling间隔只是策略，不能证明时效或覆盖率。

运行时记录代码SHA、SOURCE_POLLING_ENABLED、启动/结束、队列/专库/端口、每来源窗口及HTTP attempt。只读`GET /v1/jobs/{job_id}`（或/api/v1）沿用当前系统管理员鉴权；任务ID来自PG/outbox权威记录。结果succeeded/partial/failed/blocked分别解释，禁止把错误显示成0条。普通资料/问答用户不能开启来源管理；部署配置不接受请求体租户、任意URL、query或shell。

采集停止后重启同专库与broker即可处理原任务，原页回执和租约generation防止旧worker覆盖。是否满足≤6h或无漏采，需独立参考集及真实观察日志验证；当前小批调度实现不替代R06/R22正式验收。故障恢复/指标告警整套验收仍归R20，相关报告必须注明尚未证明的范围。
