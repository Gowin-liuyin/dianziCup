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

1. 负责人先登记事件家族。译文、转载、修订、题目和资产组合使用同一 event_family_id；填入稳定 family_aliases。家族主标识、alias、document_id 和来源 URI 使用同一精确标识键域，同一案例中的标识关联到同一 split；通过其他案例形成的传递/循环关联也不能跨 split，改放另一个字段不能绕过。未声明或采用不同字符串的语义关系仍需人工回看。
2. 将真实标注与 holdout 放在主库、所有工作树及任何产品挂载之外。标注文件的 `data_mode=human`；实际产品挂载由 `--product-root` 逐个传入。不能以忽略文件、另一个 Git 分支或仓内目录作为隔离。身份核验证据也留在受控仓外目录，仅记录 evidence_ref。
3. 负责人核对两位实际人员身份、独立提交安排及利益冲突；先分别交付候选原文，第一份标签不要提供给第二人。不同字符串 ID 不证明不同人员。两人各自核对原文固定版本、必要证据、版本/条件/unknown/conflict 与许可，再填 `annotators`；模型不能代填最终标签或作为唯一裁判。
4. 校验两份标签。有分歧时保持 awaiting_adjudication，负责人安排第三人依据原文裁决，记录 reason、所裁两份完整记录的 hash、最终 label。裁决人不能与任一标注 ID 相同。无分歧也仍需真实独立身份核验。零/一份标签不能带裁决或身份记录；孤儿、同 case 重复、过期 hash、自我裁决/核验或缺理由的记录一律拒绝，不会因 awaiting_human_label/awaiting_adjudication 被忽略后导出。
5. 完成人工身份/独立提交检查后，负责人填写 identity_checks：两人 ID、当前两份记录 hash、verified_by/verified_at、method、evidence_ref 和 independent_submission_confirmed。这个文件记录人工声明，不证明声明真实；工具最多标 ready_for_manual_review，仍需独立审查者验收。
6. 任何标签修订追加 revision；填写前一完整记录的 previous_sha256、change_reason、affected_case_ids 和 retest_refs，保留原记录及旧导出 artifact hash。禁止覆写旧标注包。正式修改金标还需按原合同批准变更并统一复测所有对照；此工具不授权该变更。

人工文件采用 `candidate_case_v1.json` 的 `annotation_bundle` 定义。初始骨架为 schema_version=1、data_mode=human、candidate_cases_sha256、annotators=[]、adjudication=[]、identity_checks=[]。candidate_cases_sha256 是候选 cases 数组按 UTF-8、ensure_ascii=false、sort_keys=true、separators=(",",":") 序列化后的 SHA-256；每条 label 使用 expected_claims、expected_conditions、expected_status，不预填正确答案。可在仓外编辑 JSON；字段定义与允许枚举见 schema，合成填表示例只存在测试文件中。

```powershell
& $python scripts/annotation/prepare.py validate --input benchmarks/manifests/r19_public_dev_candidate_v1.json --labels D:/controlled-evaluation/labels_r19_v1.json --product-root D:/actual-product-mount
& $python scripts/annotation/prepare.py export --input benchmarks/manifests/r19_public_dev_candidate_v1.json --labels D:/controlled-evaluation/labels_r19_v1.json --output D:/controlled-evaluation/review_r19_v1.json --purpose annotation --product-root D:/actual-product-mount
& $python scripts/annotation/prepare.py validate --input D:/controlled-evaluation/review_r19_v1.json --product-root D:/actual-product-mount
```

这些路径是操作说明，未创建真人文件或完成身份核验。每次调用从 `git worktree list --porcelain -z` 读取当前仓库的全部注册工作树（含空工作树/后来新增工作树），并解析实际路径和显式产品挂载；不扫描用户其他目录。标签或 holdout 不能经 symlink/junction 别名绕过。Git/注册信息不可用时以 REPOSITORY_WORKTREE_REGISTRY_UNAVAILABLE 非零拒绝。工具拒绝将任何标签导出到 prompt/index/image/fixture；annotation 导出包含完整历史与独立 annotation_sha256，必须在受控仓外。导出的 hash 可检测未同步改 hash 的编辑，但不是签名或可信身份系统；保留外部不可变旧包和第三方复核记录是人工责任。

## 家族隔离与漏入检查

holdout 候选和任何带 annotations 的输入/输出必须仓外。holdout 只能作 annotation 导出，不能导出到 prompt/index/image/fixture。

```powershell
& $python scripts/annotation/prepare.py scan --input D:/controlled-evaluation/holdout_candidates_v1.json --scan-root D:/public-build/prompts --scan-root D:/public-build/image-manifests --scan-root D:/public-build/index-manifests
```

这里只读取操作者明确选择的公开树。不要把秘密、真人身份、真实答案目录或整台机器作为 scan-root。检查候选 ID/家族/alias/URI/短证据在公开文件中出现；如果显式提供仓外 --labels，还检查 holdout expected_claims 的原文泄漏，stdout 不打印答案。二进制文件也按字节检查；符号链接和超过 10 MB 文件报错。该检查不解压压缩镜像、不查询外部索引，也不能证明语义/编码变换后的内容没有泄漏。只有 unknown/conflict 等短状态且没有可识别论断时仍需人工检查。正式冻结前必须核对实际镜像与索引输入清单，不能用这个局部检查代替原 T46 验收。

## 已执行和未执行

原 T46-C01–C06 的工具行为由 `scripts/annotation/tests/test_prepare.py` 对显式 synthetic fixture 实测，含双填表→分歧→裁决→身份记录→CLI 外部导出。actual real/dev 包仅做本地来源/证据字段校验，仍 awaiting_human_label。测试里的 identity 和 label 不能计为真人或金标。

frontend/e2e/live/manual、正式性能与准确率均 not_run。工具不调用付费模型、DB/API、来源网络或秘密存储。正式 R19/T46/T01 完成与 G-F 放行未发生；此准备包提交非作者独立 review。

## 开发集装配（批次21 C5.3 新增）

在已有候选准备工具之上，本仓库另有两条本地装配命令（不修改 prepare.py 与 candidate_case_v1）：

```powershell
$python = 'D:\dianzi\backend\.venv\Scripts\python.exe'
# 1) 把 T01 合成 pilot 案例适配为 candidate_case_v1 种子 bundle（20 例，全部 synthetic/dev，独占新建）
& $python scripts/annotation/build_synthetic_seed.py --input fixtures/synthetic/pilot_cases.json --output benchmarks/manifests/r19_synthetic_dev_seed_v1.json
# 2) 合并 1 个 real bundle 与 20 例 synthetic 种子为 dev-set manifest（21 例，独占新建）
& $python scripts/annotation/assemble_dev_set.py --bundle benchmarks/manifests/r19_public_dev_candidate_v1.json --bundle benchmarks/manifests/r19_synthetic_dev_seed_v1.json --dev-set-id r19_dev_set_assembly_v1 --output benchmarks/manifests/r19_dev_set_assembly_v1.json
# 3) 两个产物都必须能被既有工具复检（exit 0）
& $python scripts/annotation/prepare.py validate --input benchmarks/manifests/r19_synthetic_dev_seed_v1.json
& $python scripts/annotation/prepare.py validate --input benchmarks/manifests/r19_dev_set_assembly_v1.json
```

实测命令在宿主以 `VIRTUAL_ENV=D:\dianzi\backend\.venv` 前缀下的 `uv run python -m unittest discover -s scripts/annotation/tests -p "test_dev_set_assembly.py" -v` 覆盖（10 例），证据在 `reports/runs/batch21_r19_implementation/`。

0 gold 声明（多层一致，本节新增两层）：装配器拒绝任何 `label_status != awaiting_human_label` 的 case（LABEL_STATUS_NOT_AWAITING）；dev-set manifest 的 `summary.gold` 机读块恒为 `human_gold_count=0`、`gold_status=none_no_human_labels`、`formal_evaluation not_run/null`，并由 `benchmarks/schemas/dev_set_manifest_v1.json` 的 const 固定。`scale_statement` 是固定字符串：本 dev-set 为 awaiting_human_label 候选装配物，仅用于标注规则验证与人工准备，不是金标，不参与任何正式指标计算。

种子溯源与降级说明：`build_synthetic_seed.py` 只读 `fixtures/synthetic/pilot_cases.json`；T01 旧值域 `data_kind`（revision/version_range 等）统一登记为 `synthetic`，原值写入 limitations 可追溯；每个候选在 limitations 指回原 case_id。pilot_cases 的 `expected_result`/`expected_basis` 是规则推导的待复核提案，绝不复制到任何候选字段或标签；`candidate_task` 只写场景任务并明确提案仅作复核参照。evidence span 取该案例 `input` 对象规范化 JSON 文本的前缀（≤240 字符，offset 从 0 起，json_pointer 指根），hash/offset 全部离线可验。许可按 unknown/unverified 登记，待人工核验。

装配行为与边界：`assemble_dev_set.py` 逐 bundle 复用 `validate_candidates`（含 candidate_sha256 绑定），随后把全部 cases 合并再跑一次同规则校验，使跨 bundle 的重复 case_id（DUPLICATE_CASE）与家族/alias/document_id/URI 键域跨 split（FAMILY_SPLIT_LEAK）被拒绝；含 holdout split 的 bundle 直接拒绝（HOLDOUT_SPLIT_REFUSED），holdout 候选继续走 prepare.py 的仓外通道，永不进仓内 dev-set manifest。manifest 信封与 candidate_bundle 兼容（schema_version/prepared_at/cases/candidate_sha256/summary），装配元数据在 summary（dev_set_id、assembled_at、source_bundles 含逐 bundle path/hash/计数、counts 按 data_kind 与 split 分列、label_status_counts、gold、dev_set_sha256、scale_statement）；`dev_set_sha256` 只绑定 cases+counts+label_status_counts，同输入重复装配结果确定。输出独占新建（OUTPUT_EXISTS），`--scan-root` 可选复用 scan_leaks 对合并后内容复扫（当前装配物无 holdout，needle 集为空，属边界内检查而非镜像/索引审计）。schema 的 id/hash/time/source/evidence/candidate_case 定义在校验时从 candidate_case_v1.json 合并提供，公共合同文件未被复制或修改。真实双人标注、裁决、身份核验、真实 holdout 集与冻结签字仍未发生；装配物规模为 1 real + 20 synthetic 种子，不是完整开发集，也不是指标分母。
