第八批冻结材料canonical归档报告。归档验证完成，不改变业务、Git、progress或accepted。

真实Asia/Shanghai时间：2026-10-16T05:53:25+08:00 → 2026-10-16T06:02:10+08:00；前三组于2026-10-16T05:58:28+08:00交付不可改优先收据。共五组1,497件：新增raw归档1,219件、17,698,558 B；R10仅验证既有canonical278件、1,024,152 B，0复制。合计18,722,710 B。0覆盖、0normalize、0重复、0 raw hash/size核验失败。

| 包 | 原manifest成员数 | 实际归档/核验数 | 新增数 | 本体SHA256 |
| --- | ---: | ---: | ---: | --- |
| R17-graph-app-review | 95 | 98 | 98 | bc9548f04afcdd9d11d2c21079819d4fd1841bb25474ba3a78d8dc7862c44c9b |
| R11-R08-migrations-review | 127 | 129 | 129 | 2ead6acce350e583b9818c1491a395de487b50a248b1b4df252d542b36e97d80 |
| GC-e310-validation | 858 | 854 | 854 | 9cecc31bc8b628995156a4005e1066e99ed424a104ce046d94d67d40f293b879 |
| R20-early-review | 136 | 138 | 138 | 2138c79fee70d550482d0dae4cded4f91bc4cd34db177a25b41626e3d80c37f1 |
| R10-final-canonical | 277 | 278 | 0 | 8df36e1fb15f3b9c21b6912c1a6031a28fd9eca8635e4909aa6e6e4e0212f3cd |

R17为95 run成员+独立报告+本体+绑定checksum=98；迁移127成员+本体+原freeze receipt=129；GC原858成员中6缓存明确排除，852成员+本体+绑定checksum=854；R20为136成员+本体+manifest identity=138；R10原277成员（已含精确scope CR）+本体=278。原manifest本体全部保持原bytes并匹配给定预期；任何声明filelist/LF不是本体raw SHA。

GC六项policy_excluded/not_verified（不读、不复制）：__pycache__/run_command.cpython-312.pyc、cpython-313.pyc；mypy_cache/.gitignore、3.12/cache.db、CACHEDIR.TAG、missing_stubs。原858 manifest不改，也不冒称858成员全部已归档。其他cache/venv/node_modules/.git/holdout/vault无bytes读取或复制。R20十一*_cache/*_temp目录只曾枚举文件名，内容未读未拷，已从归档范围剔除并如实记录工具过程。

最终精确清单archive_followup_8_filelist.tsv包含1,497项实际action/size/raw SHA/0D0A/declared LF/目标派生LF，SHA256=1a7fe301f636b4d79b68bad19b481773a687ec1a86980c73cf147a6456766723。前三组不可改优先receipt SHA=8a0b00d0763307594ce8e7ffd353efeae63869faae7e3a320813672db2ef53a7；priority filelist SHA=459793d897bb30e25b1ad1485bebcbd8b4832c022b767620d9f0aeb0f73f9f9f，本次落盘前再核原bytes相同。

root新基线：开始HEAD=e310f7735bd499c4d9fbcefe8a644e2309a16a62；最终read-only观察HEAD=48b56033cf5daf3ce8cfaa710c0acbda7cc2356e。此批root只锁attrs，没有锁HEAD；归档者未执行任何Git变更，真实记录该HEAD差异。合法五次merge后根attrs为30,207 B、SHA256=4df656bc18f4d4bc5fdb044bf8179671b370b555d3dfb0a9c90dff72b10d9e4a，本批前后相同，不沿用第七批5e。前七批2,687项canonical/自有收据报告清单原SHA全部前后复核不变；优先2项收据清单也不变。

三个原run-local .gitattributes按既有root明确授权仅复制原bytes：R17 8 B/705fd4d6451a31d36b3df7de96f83f30ac976c9b4a6d1e51671d8e2f33e2d0da；迁移169 B/6f7e4ea344e79b48627f301bd30487ca1027ea003c97f2dac2aa044a53cbe971；R20 32 B/f06666f6fe21c046b1c0c2485093329932741239f67e2d0561a95e356df9c412。根规则未编辑。

raw/LF/Git分列：321项原声明LF源及目标分别匹配；迁移固定review材料提交b8fe1171eb2f67dc58805d41354764398417dd40的129项归档raw均与真实Git对象相等（0仅LF替代）；R20原136声明raw_git_blob_sha1仅为派生raw身份，逐项计算匹配，不能据此声称存在review提交。其余review_commit为null；R10本批为canonical-only，没有外部source双源或独立review提交证据，e310 tree查询其report/run/CR为0行，未用HEAD冒充review commit。作者产品code/blob证明只按原报告声明分列，不复制或重新审查产品source。

R10报告raw SHA=cdbfdb9c3a85a327169718f7e4d8ce9b70aa18fcefd8b5ceb01f9ca48028d143；精确CR raw SHA=7b8cea169d444dc6ca95057723114db86b1bde9587ca128ea536ef8fa0bc5fe4，3206 B。两者与277原成员/本体分别核验，128个已封存合成CAS fixture对象仅canonical bytes核验，0复制；它们不是缓存抓取或外部原文读入。

限定敏感扫描1,493文本+4 binary仅hash；190处DSN形状password均mask，12处literal赋值形状均为固定e310 AST证明的synthetic参数化用例node IDs。backend/tests/security/test_t06_authentication_and_scope.py原blob SHA256=e6df1bc8d71bdd9416cbeaac28cca5d9742368671f9d5068bb603d639e29d237、Git OID=fddf4e84363f4b38c54232eadb285293e736f41e，168/169/170行纯字符串参数，仅在176行进入is_public_authentication_failure_comparison；XML与三roster字符串仅该synthetic case node IDs中的捕获赋值，内存匹配12/12。无env/cfg/模型输入，未执行测试，匹配值未输出。没有实际凭据读取或未分类文件；有限模式扫描不称全秘密认证。

原范围和红记录保真：R17 Ship仅默认App前端图接线，真实默认后端/API/PG/live未证；迁移Ship仅0018/0019生产DDL前向迁移，覆盖门/整卡/真实产品/live未证；GC组合限定Ship可作为受控采集基线，原pure首扫红及继承CPU/default60完整门仍未闭合；R20仅早期资源/生命周期安全改善，Windows<1硬界、原3秒热点wall门及全CPU验收保留；R10仅固定PG read service/router工厂及Fix2，old red/noepoch注入边界与scope CR保留。没有新Ship结论、分母/金标变化或全绿宣称。

raw 0D0A序列存在于380件、共277913；源/目标一致，包括binary中的可能序列，不猜编码，不normalize。

真实命令与操作：read-only rg定位（exit0）；Git rev-parse HEAD/ls-tree（exit0），迁移固定b8fe及GC固定e310；Python标准AST读取固定测试源码与XML/JSON node ID内存等值分类（exit0）；Node标准fs/crypto路径边界/lstat拒绝链接、逐hash/size、wx原bytes新建及copy后复核。Node旧绑定过期在首个fs操作前报fs is not defined，已恢复，文件变更0；R20初次缓存目录名字枚举及后缀过滤修正已记录，0缓存内容读拷。

本轮业务unit/contract/integration/security/frontend/e2e/live/manual全部not_run；新增外网/模型/费用/产品服务进程/spawn为0。read-only shell/Git/stdlib AST与Node归档确有执行，不写成0 OS进程。完整评分/正式6h/live/整卡/阶段与accepted仍由有权owner处理。
