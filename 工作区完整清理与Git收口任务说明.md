# 工作区完整清理与 Git 收口任务说明

## 权威口径

- 本文档是本轮“工作区完整清理与 Git 收口”的唯一任务说明。
- 同时遵守根目录 [AGENTS.md](AGENTS.md) 与 [e7-gear-enhance-plan.md](e7-gear-enhance-plan.md)。
- 用户在 2026-07-25 提供的目标用于定义本文档；后续聊天不得静默扩大删除、忽略或外传范围。
- 实际执行由当前主 agent 监督完成；本阶段未创建子 agent。用户允许使用 `gpt-5.6-terra + high` 子 agent，但当前协作接口没有可核验的模型派发能力，因此不得虚构已派发记录。

## 目标

1. 最终 `git status --porcelain` 无输出。
2. 有价值的源码、测试、配置、文档、报告、可信快照和操作证据安全保存。
3. 应纳入版本控制的内容按来源和功能分组审阅、验证、提交并推送到 GitHub。
4. 可再生成缓存、临时日志和确认无价值的重复文件在授权范围内安全清理。
5. `.gitignore` 只增加经过逐类核验的精确生成物规则。
6. 最终无暂存残留、无未跟踪项、无未推送提交，本地分支与远程同步。

## 范围

- 当前仓库内全部已跟踪修改、未跟踪文件和目录。
- 已完成隔离目录仅作为恢复来源核验，不默认删除：
  `C:\Users\orangine\Documents\第七史诗强化装备脚本_副本隔离_20260725\`。
- `.git` 内既有异常引用只记录，不在本任务中修复或删除，除非另获明确授权。
- 当前正式策略、DP、评分、资源模型、GUI、Holdout、OCR 门槛和自动化规则只允许按其既有改动来源进行审阅、验证和保存；本任务不得借清理改变其行为。

## 禁止项

- 禁止 `git reset`、`git restore`、`git checkout` 回退、`git clean -fd`、`git clean -fdx` 或其他仓库级批量删除。
- 禁止覆盖、丢弃或静默改写无法确认来源的用户改动。
- 禁止 `git add -A`、`git add .` 或未经清单确认的批量暂存；每次只精确暂存已审阅分组。
- 禁止将全部 `reports/`、`manual_acceptance/`、截图目录或研究分片目录整体忽略。
- 禁止删除未知文件、内容分叉副本、没有权威替代品的日志/研究分片/报告。
- 禁止修复或删除 `refs/heads/main - 副本`、`refs/heads/master - 副本` 等异常引用。
- 禁止未经本轮重新明确授权，将账号信息、游戏截图、PCAP、玩家数据、可信快照或其他私人数据推送到远程。

## 输入与基线口径

- 起始分支：`codex/batch-013-plus3-verification-20260724`。
- 起始 HEAD：`0c41890d8f064c8fdd4af40c3f512cdde80e2708`。
- 远程：`origin=https://github.com/5kjpywnfh8-cmd/epic-7-auto-gear-reinforcer.git`。
- 起始本地与远程提交差：`0/0`。
- 专用分支：`codex/worktree-cleanup-20260725`。
- Git 跟踪文件：`202`。
- 已跟踪未提交修改：`31` 个文件，约新增 `3013` 行、删除 `312` 行。
- 起始暂存区：`0`。
- 前次折叠状态为 `369` 个未跟踪文件/目录；本轮须重新核验。
- 前次完整未跟踪递归扫描在 `60` 秒内超时；本轮采用目录级、限时、可续跑清单，不把超时解释为文件缺失。
- 已隔离的 SHA-256 完全一致副本：`415/415`；3 个内容分叉副本和 `.git` 内异常项未处理。

## 分类规则

每个未处理项必须归入以下一类，并记录路径、大小、哈希或判定证据、处置建议和授权状态：

1. `version_control`：应纳入版本控制的源码、测试、配置和必要文档。
2. `authoritative_evidence`：必须保存的任务说明、报告、截图、manifest、可信快照和 OCR/操作证据。
3. `local_generated`：仅本地保留且可用精确规则忽略的生成物。
4. `safe_delete_candidate`：确认可再生成或存在权威替代品的缓存、临时日志、中间文件。
5. `exact_duplicate`：名称含“副本”或疑似重复，且 SHA-256 与明确原件完全一致。
6. `divergent_duplicate`：疑似副本但大小或 SHA-256 不同，必须保留并单独审阅。
7. `unknown`：来源、价值、私人属性或权威替代关系无法确认。

补充规则：

- `__pycache__/`、`*.pyc` 等明确可再生成缓存可列为删除候选，但仍需精确清单。
- 日志、resume 分片和生成报告只有确认可再生成且存在权威替代品后才能列为删除候选。
- `.vscode` 必须逐文件区分团队配置和个人配置。
- 名称含“副本”的文件先比较大小与 SHA-256；不一致时绝不删除或覆盖。
- PCAP、游戏截图、玩家数据、账号相关快照和操作证据默认归为私人数据；提交前必须重新取得外传授权。

## 备份与恢复

- 已跟踪修改由当前工作树、专用分支基线和精确 diff 清单共同保护；不得通过回退处理。
- 删除候选在删除前必须输出精确路径、数量、总大小、理由和恢复方式。
- 对未知或有价值但不应提交的内容，优先提出工作区外可恢复隔离方案；目标目录、manifest、哈希和恢复命令须在执行前明确授权。
- 已有副本隔离目录保持只读恢复来源，不在本任务中清空。

## 执行步骤

### 阶段一：建立安全基线

1. 记录当前分支、HEAD、远程、本地/远程差异、跟踪文件数、已跟踪修改、暂存区、未跟踪项、文件数量和大小。
2. 创建并切换专用分支 `codex/worktree-cleanup-20260725`。
3. 输出可复核基线报告；任何扫描超时必须明确记录扫描边界。

### 阶段二：处理已跟踪修改

1. 对 31 个已跟踪修改按任务来源和功能分组，审阅 diff、关联任务说明、报告和测试。
2. 每组源码必须与测试配套验证；文档同步任务说明和总计划。
3. 每组通过后精确暂存、独立提交并推送；不得混入无关文件。
4. 无法确认来源的修改列入待确认清单，不回退、不覆盖。

### 阶段三：处理未跟踪内容

1. 按目录分批、限时、可续跑枚举全部未跟踪项。
2. 应提交内容完成审阅、验证和分组提交。
3. 私人数据在远程提交前停在精确外传清单并向用户取得新授权。
4. 可忽略、可隔离、可删除和无法判断项分别形成精确清单。

### 阶段四：安全清理

1. 每次只处理一个明确分类。
2. 删除、隔离或新增忽略规则前先报告路径、数量、大小、理由、恢复方式和授权状态。
3. 无法判断项暂停并向用户确认。
4. 每批处理后重新检查 Git 状态和文件哈希。

### 阶段五：最终收口

1. 更新本文档、总计划和最终清理报告。
2. 运行分组定向测试、必要的全量测试和 `git diff --check`。
3. 提交并推送任务说明、分类清单、验证报告及经核验的 `.gitignore` 修改。
4. 验证本地分支与远程同步，暂存区为空。
5. 运行并保存 `git status --porcelain`；只有输出为空才可标记完成。

## 产物

- 本任务说明。
- `reports/worktree_cleanup_baseline_20260725.md` 与对应 JSON。
- `reports/worktree_cleanup_tracked_groups_20260725.md` 与对应 JSON。
- `reports/worktree_cleanup_untracked_inventory_20260725.md` 与对应 JSON。
- 经授权时的精确删除/隔离/外传 manifest。
- `reports/worktree_cleanup_closure_20260725.md` 与对应 JSON。
- 分组 Git 提交和远程分支记录。

## 验证要求

- 所有清单路径必须存在性可核对；需要哈希的文件使用 SHA-256。
- 每个源码分组运行与风险相称的定向测试，必要时运行 `tools/run_all_tests.py` 并记录真实退出码。
- 每次提交前运行 `git diff --cached --check`；最终运行 `git diff --check`。
- 每次推送后核对本地/远程 ahead/behind 为 `0/0`。
- 最终 `git status --porcelain` 必须无输出，且不得以宽泛忽略规则掩盖权威证据。

## 停止条件

- 发现未知文件、内容分叉副本或无法证明有权威替代品的日志/报告，停止对应处置并列清单。
- 发现私人数据拟上传但没有本轮新授权，停止对应提交/推送并列外传清单。
- 发现哈希变化、目标冲突、权限异常、扫描边界不完整或多个任务修改同一文件，立即 fail closed。
- 测试失败时停止该提交分组，不用删除或回退掩盖失败。
- `.git` 异常引用继续只记录，不修复；若它阻止必要提交/推送，先报告精确阻断再请求授权。

## 当前状态

`phase_1_complete_phase_2_tracked_review_in_progress_no_cleanup_performed`

- 已完整读取 `AGENTS.md`、`e7-gear-enhance-plan.md` 和 `cultivation-skills:dev`。
- 已创建并切换专用分支 `codex/worktree-cleanup-20260725`。
- 安全基线已完成：[Markdown](reports/worktree_cleanup_baseline_20260725.md) / [JSON](reports/worktree_cleanup_baseline_20260725.json)。
- 完整未跟踪枚举成功：`255840` 个文件；工作区排除 `.git` 后为 `256449` 个文件、`2379545803` 字节。
- `reports` 是主要卡顿来源：`255347` 个文件、`1972226214` 字节，主体是研究 resume 分片；`manual_acceptance` 含私人游戏截图和操作证据，未经本轮外传授权不得推送。
- 现有 `reports/*.md` 忽略规则过宽，已列为必须替换项；当前尚未修改 `.gitignore`。
- 尚未删除、忽略、移动、暂存、提交或上传任何待分类内容。
- 深层副本盘点完成：[报告](reports/worktree_cleanup_deep_duplicate_inventory_20260725.md)、[SHA-256 manifest](reports/worktree_cleanup_deep_duplicate_manifest_20260725.csv)、[JSON 汇总](reports/worktree_cleanup_deep_duplicate_summary_20260725.json)。
- 工作区外 `127759` 个 exact-match 候选的目标冲突为 `0`，3 个内容分叉副本已排除；当前状态 `exact_duplicate_isolation_preflight_passed_move_pending`。
- `127759/127759` 个 exact-match 候选已按 manifest 可恢复移动并逐项验证；结果 manifest 位于工作区外隔离目录。工作区现只剩 3 个内容分叉副本。
- 深层副本曾使历史审计读到 Heroic `160` 个 shard 而非权威 `80`；隔离后回归 `test_historical_bridge_keeps_v3_v4_baseline_and_resource_conservation` 为 `1/1` 通过，未修改审计器或测试。
- 当前状态：`phase_2_generated_resume_noise_ignored_tracked_review_pending`。
- 已将过宽的 `reports/*.md` 替换为精确规则：仅忽略 `reports/*_resume_*/`、`reports/test_logs_*/`、`reports/epic_threshold_matrix_single_debug/`、`reports/visual/`、`runtime_cache/` 和本地 `.vscode/`；未删除任何文件，顶层权威报告继续可见。
- 重新分类结果：`reports/` 共 `127855` 个文件、`1100733173` 字节，其中 `60` 个生成/调试目录是主要扫描噪声；顶层报告仍有 `316` 个文件、`176552041` 字节待逐份审阅。源码/测试/工具未跟踪文件共 `98` 个，`manual_acceptance` 未跟踪入口共 `276` 个，其中 `190` 个为截图、PCAP、日志或 PID 等私人/操作证据。
- 校准组已通过 `32` 项定向测试并提交 `fc4e2e9`；策略/DP/资源组已通过 `92` 项定向测试并提交 `ede8e5e`；GUI 组已通过 `33` 项定向测试并提交 `77baf88`，三次均已推送到 `origin/codex/worktree-cleanup-20260725`。
- 已补齐运行时依赖并提交 `04bb9af`，只读 OCR/MuMu/离线汇总工具提交 `4cad58d`，可复现研究工具提交 `cef92cc`；均已推送，未包含 `reports/`、`samples/` 或 `manual_acceptance/` 私人证据。
- 统一全量测试 `tools/run_all_tests.py` 真实退出码 `0`，耗时 `292.8` 秒，输出 `ALL TEST FILES PASSED`；2 个 Qt 用例各自动重试一次后通过。
- 根目录未跟踪文档共 `68` 个：3 个内容分叉副本继续保留；2 个历史任务文档含具体本地连接标识，当前不推送、不静默改写；其余 63 个文档通过 UTF-8 读取检查，进入项目文档提交候选。
- 安全根目录文档已形成本地提交 `aa00b55`；首次推送被外传闸门拒绝，因为总计划历史段落仍保留 4 处具体本地端点。未绕过拒绝，也未推送该提交。
- 已将总计划中 4 处历史端点机械替换为 `<local-adb-endpoint-redacted>`；复核结果为具体端点命中 `0`、占位符 `4`、UTF-8 可读、`git diff --check` 通过，文件 SHA-256 为 `763affa2bafa27f223e01326a7ec79077db4b2b9548c679e188ed25043fb3503`。
- 当前状态：`phase_3_endpoint_redaction_verified_safe_docs_push_pending`。未删除、移动、回退或混入私人证据；下一步独立提交并推送脱敏，再审核顶层报告、样本和私人 `manual_acceptance` 证据。

### 未跟踪内容复核与 smoke 分片精确忽略（2026-07-25）

- 脱敏文档提交已改写为 `3b44695` 并成功推送到 `origin/codex/worktree-cleanup-20260725`；本地与远程同步，已跟踪修改和暂存项均为 `0`。
- 推送后精确枚举得到 `2166` 个未跟踪且未忽略文件：`reports` 1876、`manual_acceptance` 276、`samples` 9、根目录 5。IDE 显示的一万多个项目不等于一万多个代码改动。
- 只读分类确认 5 个 smoke 分片目录共 `1651` 个文件、`5194317` 字节，均为可再生成中间结果；已按精确目录加入 `.gitignore`，文件原位保留，未删除或移动。
- 清单见 [Markdown](reports/worktree_cleanup_untracked_inventory_20260725.md) 与 [JSON](reports/worktree_cleanup_untracked_inventory_20260725.json)。规则与清单提交后仍有 `515` 个待决文件：顶层研究/生成报告 189、顶层私人/真实报告 36、`manual_acceptance` 私人证据 276、样本 9、根目录分叉副本 3、含具体本地连接标识的历史文档 2。
- 当前状态：`phase_3_inventory_recorded_generated_smoke_ignored_private_decision_pending`。下一步先审阅 189 个顶层研究/生成报告；私人证据和 7 个命中真实/实例/Fribbels 标记的样本不得在未取得精确新授权时推送，3 个分叉副本继续保留原位。
