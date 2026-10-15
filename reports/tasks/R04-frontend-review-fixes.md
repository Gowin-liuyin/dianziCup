# R04 · 前端独立审查定向修复

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T12:11:34+08:00。作者/root，状态awaiting_review、partial，只是前端切片。

独立审查固定0b983349，实际浏览器复现claim已知revision A引用却接受同span的B、新筛选403/503仍显示旧详情两项Must。复用既有hash导航和getEvidence版本校验，在claim链接加入已知revision；新筛选提交同步卸载详情/证据并清理deep link。额外修复共享HTTP边界：非JSON错误保留401/403/503，不显示原body；成功非JSON仍502。无新依赖。

新增7项必要负例：点击claim错误版本1、筛选403/503清除旧详情2、非JSON错误状态3、非JSON401清身份且不重读会话1。首次加6项在未修代码运行：108passed/6failed；首修后113passed/1failed因测试误写既有公共错误文案（独立浏览器原缺陷仍实际存在），纠正期望文案且保留所有记录；最终115passed/0fail/0skip。run目录reports/runs/recovery_r04_frontend_root_fixes_20261015，JUnit red/green/green_2不覆盖，原始开始时间在JUnit与log，首wrapper只保存结束时间，开始秒历史未记录。lint/typecheck/build三个单独recorded收据均0；临时tsbuildinfo仅恢复本轮生成已知HEADbytes。

不修改金标/阈值/分母/测试skip。原实API认证3例在前后端0b983已通过，不能直接给本新修复版背书；新代码须由原独立reviewer定向重跑浏览器负例与相关回归。尚无真实来源-PG-页面闭环，R04/R17/G-A/B未过门。
