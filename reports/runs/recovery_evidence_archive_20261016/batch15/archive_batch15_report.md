# 冻结证据归档第15批

任务 recovery_evidence_archive_batch15；状态 awaiting_review；本归档实现 complete。角色只有冻结字节归档，未签 accepted、业务或阶段验收。

C 实际执行：2026-10-16T09:43:49.916120+08:00 至 2026-10-16T09:44:03.997893+08:00。
D 实际执行：2026-10-16T09:44:14.759726+08:00 至 2026-10-16T09:44:24.986842+08:00。
报告生成时间：2026-10-16T09:45:47.796898+08:00；Asia/Shanghai。

| 包 | 原manifest成员 | canonical文件 | 新复制 | bytes | 覆盖 |
|---|---:|---:|---:|---:|---:|
| C R11作者 | 188 | 187 | 187 | 2,895,730 | 0 |
| C R11非作者复核 | 122 | 124 | 124 | 644,940 | 0 |
| D R18作者active修订 | 144 | 146 | 146 | 846,874 | 0 |
| D R18非作者复核 | 57 | 58 | 58 | 441,668 | 0 |
| 合计 | 511 | 515 | 515 | 4,829,212 | 0 |

改动文件精确见 priority_C_filelist.tsv 311行、priority_D_filelist.tsv 204行；其余新文件只在本batch15目录。hashsame复用0、canonical冲突0、原manifest/成员SHA不匹配0。每个冻结源在操作前后hash/长度相同；canonical全部直接原bytes复制，没有改原日志、报告、manifest或压缩格式。

C作者报告在原188成员中。其两个业务成员 backend/src/ai_intel/assets/sbom_inventory.py、backend/tests/unit/test_r11_sbom_locator_privacy.py只做源raw/冻结Git/fresh checkout/原tar验证，明确policy_excluded，不写主仓业务路径。186个reports成员加原manifest成为187 canonical。原tar SHA37f993007648b6bdebe436aee68ed5e0a2239821d1f181194f3fe7e5a5f2873c直接保存；187成员逐字节匹配，包括被排除的两份业务源码，未重新封包或改原188 manifest。C reviewer报告不在122个run成员内，明确另加冻结报告和manifest，所以124 canonical。C源189文件（188成员+manifest）对应Git对象另核，94个raw与Git LF不同、fresh checkout有76个换行不同；真正raw与Git/fresh分别存档。

D作者active144成员包含旧报告与active材料修订报告；另加active manifest与主控明确指定的post-final fresh_material_checkout_byte_proof.json成为146 canonical。原71 exact_raw逐source/Git/fresh原字节一致；73 LF逐raw、CRLF归一结果、Git blob、fresh checkout分别核验。145个已提交文件（144成员+manifest）中15个Git LF与作者raw不同，fresh checkout59个raw不同，均保留独立身份，不将clean blob冒称原raw。

active manifest原raw SHA33c4f94a47e771408f5bf724d67135810a72a09857b89722502ae2118b78ff81与Git LF SHA86f2ef7091b87f3173a80c85797f66ba95e4dc082596954a92aed54562e3a189分别实核。post-final附件 SHA9d7db9b1996596ee96fc414aa5d23c4f1a0b9b3e9b7dfcd39de5b5555fb34c92只作为主控授权附件；不属于0601冻结commit，未递归引用新的docs或其他材料。其144行原raw/Git/mode声明与本轮实核逐项相等。D reviewer报告在57成员内，仅另加manifest成为58 canonical。

精确原run-local attrs复制只有 reports/runs/recovery_r18_sdk_client_fix1_20261016/.gitattributes，39bytes，SHA0f852240c3160bbd3d232b2b78eacd3d4d713f48878c428f27274985d6c357f7，0规则新增/修改。主仓.gitattributes、用户frontend/tsconfig.tsbuildinfo、batch14索引在C/D操作前后hash均相同。本工作包没有index/stage/commit/push、progress、生产数据库或业务状态写入。

实际命令与结果：

- `python -B reports/runs/recovery_evidence_archive_20261016/batch15/archive_batch15.py C`：exit0；311 canonical、2只读业务成员及187原tar成员核验通过。
- 同入口 `D`：exit0；204 canonical、71exact_raw/73LF声明、原manifest与明确附件核验通过。
- 自有两份收据SHA sidecar、归档器AST parse、334作者已提交文件raw或CRLF归一与Git身份检查：exit0。
- `git -C <明确source WT> rev-parse <固定commit>^{tree}` 和 `cat-file -t <固定commit>`：exit0，旧A/B只核不可变commit/tree对象，0个旧136/246/55/65成员重读/重拷；详见immutable_commit_proof.json。

本轮归档命令无失败/skip；unit/integration/live/manual均not_run。未执行源runner/seal/review脚本，未访问网络、付费API、秘密/.env/holdout/DPAPI，未spawn。未复扫历史6k；batch14文件字节未修改，C释放后没有重扫C源或canonical。

合同无变更；原188 manifest内两业务成员的只读排除已向主控单列，不修改原清单。归档只提供F2/E1/D1/X1相关冻结证据的追溯，不新增功能通过、评分、准确率、性能或完整阶段结论。C完成即通知主控可集成后端fix，D完成也已通知。下一步由主控依精确filelist集成和独立验收；本归档包停止。
