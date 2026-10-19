# 文件化runner前的工具错误摘录

这些是工具/材料读取问题，不是业务测试。首次工具输出没有完整文件化receipt，精确起止未记录；只保留原始可见摘录，不编造完整原输出。均为0 primary。

1. 首次宽 ALL_TOOLS 元数据过滤输出过宽：`Warning: truncated output (original token count: 31960)`。工作树建立exit0，Ponytail review文件读取exit0；没有把截断内容当完整工具发现。
2. `rg ... docs/contracts ...` 原错误：`rg: docs/contracts: 系统找不到指定的文件。 (os error 2)`。实际合同是根contracts与docs/plan。
3. 将通配目录字面传给rg的原错误：

```text
rg: reports/reviews/recovery/G-F*: 文件名、目录名或卷标语法不正确。 (os error 123)
rg: reports/runs/recovery_r20*: 文件名、目录名或卷标语法不正确。 (os error 123)
```

4. 读取不存在的安全文件：

```text
Get-Content: 
Line |
   3 |  Get-Content -Raw docs/plan/07_security_privacy.md
     |  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
     | Cannot find path 'D:\wt\r20-early-review1\docs\plan\07_security_privacy.md' because it does not exist.
```

已改读实际05 API/工具、06测试、09运维及03/04边界，没有补造该文件。

5. 读取作者不存在的architecture命令名：

```text
Get-Content: 
Line |
   6 |  Get-Content -Raw reports/runs/recovery_r20_early_cpu_bootstrap_202610 …
     |  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
     | Cannot find path 'D:\wt\r20-early-review1\reports\runs\recovery_r20_early_cpu_bootstrap_20261016\cbm_architecture.command.json' because it does not exist.
```

本review自行建立独立CBM并取得architecture。文件化之后的CBM unknown-tool/invalid-aspect原失败有完整同名command/stdout/stderr；汇总KeyError有旧执行源及原工具stderr摘录。它们没有变成业务pass。
