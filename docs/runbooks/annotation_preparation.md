# R19 候选标注准备

本地工具仅准备候选、检查人工记录并导出审查包。它不会冻结金标、核验真实人身份或计算准确率。R04 真实原文链已独立限定通过，因此这个准备切片可提前实施；R19 最终冻结仍需要 R07–R16、完整题型覆盖、两位独立人工和裁决/冻结签字。

当前公开候选在 `benchmarks/manifests/r19_public_dev_candidate_v1.json`：1 个 real/dev 候选，0 人工标签。原公告标题、URI、文档/修订 ID 与精确的包名字段证据可供人工回看；4 字符证据只能支持包名字段核查，不能确认漏洞版本、修复版本或资产适用条件。许可为 unknown、转载权限 unverified。没有复制整个未知许可原文。

工具复用 `scripts.verify_plan.load_json` 的重复键拒绝方式，以及项目已锁定的 jsonschema Draft202012Validator；其余使用 Python 标准库。不修改公共 schema、依赖锁、产品 API、数据库、索引、原始 fixtures 或指标。

```powershell
$python = 'D:\dianzi\backend\.venv\Scripts\python.exe'
& $python scripts/annotation/prepare.py validate --input benchmarks/manifests/r19_public_dev_candidate_v1.json
& $python scripts/annotation/prepare.py import --input benchmarks/manifests/r19_public_dev_candidate_v1.json --output benchmarks/manifests/local_import_v1.json
& $python scripts/annotation/prepare.py export --input benchmarks/manifests/local_import_v1.json --output benchmarks/manifests/local_prompt_candidates_v1.json --purpose prompt
```

输出文件必须尚不存在。默认 stdout 只有各类候选数量、人工准备状态和 `human_gold_count=0`；错误非零且只输出固定错误码。导入和再次导出都保留 case ID、家族 ID、来源、时间、许可、短证据和候选类型；candidate_sha256 绑定候选 payload。`input_refs.path` 仅是校验后的相对引用，不会自动读取文件；来源 URI 也不会被此工具访问。

## 人工最短核验清单

1. 负责人先登记事件家族。译文、转载、修订、题目和资产组合使用同一 event_family_id；填入稳定 family_aliases。校验器还核对来源 URI 和 document_id 跨 split 重叠，但无法识别未声明的语义关系，人工必须回看。
2. 将真实标注与 holdout 放在主库、所有工作树及任何产品挂载之外。标注文件的 `data_mode=human`；实际产品挂载由 `--product-root` 逐个传入。不能以忽略文件、另一个 Git 分支或仓内目录作为隔离。身份核验证据也留在受控仓外目录，仅记录 evidence_ref。
3. 负责人核对两位实际人员身份、独立提交安排及利益冲突；先分别交付候选原文，第一份标签不要提供给第二人。不同字符串 ID 不证明不同人员。两人各自核对原文固定版本、必要证据、版本/条件/unknown/conflict 与许可，再填 `annotators`；模型不能代填最终标签或作为唯一裁判。
4. 校验两份标签。有分歧时保持 awaiting_adjudication，负责人安排第三人依据原文裁决，记录 reason、所裁两份完整记录的 hash、最终 label。裁决人不能与任一标注 ID 相同。无分歧也仍需真实独立身份核验。
5. 完成人工身份/独立提交检查后，负责人填写 identity_checks：两人 ID、当前两份记录 hash、verified_by/verified_at、method、evidence_ref 和 independent_submission_confirmed。这个文件记录人工声明，不证明声明真实；工具最多标 ready_for_manual_review，仍需独立审查者验收。
6. 任何标签修订追加 revision；填写前一完整记录的 previous_sha256、change_reason、affected_case_ids 和 retest_refs，保留原记录及旧导出 artifact hash。禁止覆写旧标注包。正式修改金标还需按原合同批准变更并统一复测所有对照；此工具不授权该变更。

人工文件采用 `candidate_case_v1.json` 的 `annotation_bundle` 定义。初始骨架为 schema_version=1、data_mode=human、candidate_cases_sha256、annotators=[]、adjudication=[]、identity_checks=[]。candidate_cases_sha256 是候选 cases 数组按 UTF-8、ensure_ascii=false、sort_keys=true、separators=(",",":") 序列化后的 SHA-256；每条 label 使用 expected_claims、expected_conditions、expected_status，不预填正确答案。可在仓外编辑 JSON；字段定义与允许枚举见 schema，合成填表示例只存在测试文件中。

```powershell
& $python scripts/annotation/prepare.py validate --input benchmarks/manifests/r19_public_dev_candidate_v1.json --labels D:/controlled-evaluation/labels_r19_v1.json --product-root D:/actual-product-mount
& $python scripts/annotation/prepare.py export --input benchmarks/manifests/r19_public_dev_candidate_v1.json --labels D:/controlled-evaluation/labels_r19_v1.json --output D:/controlled-evaluation/review_r19_v1.json --purpose annotation --product-root D:/actual-product-mount
& $python scripts/annotation/prepare.py validate --input D:/controlled-evaluation/review_r19_v1.json --product-root D:/actual-product-mount
```

这些路径是操作说明，未创建真人文件或完成身份核验。工具拒绝将任何标签导出到 prompt/index/image/fixture；annotation 导出包含完整历史与独立 annotation_sha256，必须在受控仓外。导出的 hash 可检测未同步改 hash 的编辑，但不是签名或可信身份系统；保留外部不可变旧包和第三方复核记录是人工责任。

## 家族隔离与漏入检查

holdout 候选和任何带 annotations 的输入/输出必须仓外。holdout 只能作 annotation 导出，不能导出到 prompt/index/image/fixture。

```powershell
& $python scripts/annotation/prepare.py scan --input D:/controlled-evaluation/holdout_candidates_v1.json --scan-root D:/public-build/prompts --scan-root D:/public-build/image-manifests --scan-root D:/public-build/index-manifests
```

这里只读取操作者明确选择的公开树。不要把秘密、真人身份、真实答案目录或整台机器作为 scan-root。检查候选 ID/家族/alias/URI/短证据在公开文件中出现；如果显式提供仓外 --labels，还检查 holdout expected_claims 的原文泄漏，stdout 不打印答案。二进制文件也按字节检查；符号链接和超过 10 MB 文件报错。该检查不解压压缩镜像、不查询外部索引，也不能证明语义/编码变换后的内容没有泄漏。只有 unknown/conflict 等短状态且没有可识别论断时仍需人工检查。正式冻结前必须核对实际镜像与索引输入清单，不能用这个局部检查代替原 T46 验收。

## 已执行和未执行

原 T46-C01–C06 的工具行为由 `scripts/annotation/tests/test_prepare.py` 对显式 synthetic fixture 实测，含双填表→分歧→裁决→身份记录→CLI 外部导出。actual real/dev 包仅做本地来源/证据字段校验，仍 awaiting_human_label。测试里的 identity 和 label 不能计为真人或金标。

frontend/e2e/live/manual、正式性能与准确率均 not_run。工具不调用付费模型、DB/API、来源网络或秘密存储。正式 R19/T46/T01 完成与 G-F 放行未发生；此准备包提交非作者独立 review。
