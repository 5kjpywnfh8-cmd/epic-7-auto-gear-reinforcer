# Epic 非速度 +0/+3 均衡候选独立 Holdout 验证任务说明

## 状态

`validation_passed_and_released_20260720`

> 当前状态更新（2026-07-20）：已完成 64/64 隔离验证，8 个预注册闸门全部通过；用户已确认发布，正式发布任务和全量回归均已完成。下方采集状态仅保留为历史过程记录。

用户已确认选择 `output_8_13_tank_10_17`。已重铸库存权重 R50+R800 稳定研究通过绝对成本闸门，本任务进入候选冻结准备；在冻结文件写入前不得读取任何 holdout 指标或启动 Oracle。

主 agent 准备审计发现 CLI 会把任意 JSON 自行标记为完整 Fribbels，且未转换真实导出的 `export_time`。当前0/128无污染，但修复完成前暂停导入。权威修复任务：[Epic非速度Holdout完整Fribbels入口修复任务说明.md](Epic非速度Holdout完整Fribbels入口修复任务说明.md)。

入口修复已完成：CLI 现在验证完整 Fribbels 结构并将 `export_time` 转为 `+08:00` 的 `exported_at`；collection 仍为 `collecting_blind 0/128`，可继续等待新的真实导出。

入口修复验证：定向31项、语法检查、`git diff --check`及全量测试均通过，真实退出码0；真实Fribbels文件仅作只读解析预检，未导入collection。

## 稳定权重研究后的候选档位（已完成选择）

- `global_12_17`：库存主权重每10万总体力相对当前增加约`0.0878`正式百里分，top4增加约`0.0994`；开发集明确正效用误停概率质量`3.7`，效率最高、风险最高。
- `output_8_13_tank_10_17`：库存主权重增加约`0.0499`分，top4增加约`0.0566`；误停概率质量`0.3`，是当前低风险均衡档。
- `output_8_13_tank_12_17`：库存主权重增加约`0.0539`分，top4增加约`0.0611`；误停概率质量约`2.2`。相对纯坦10/17每10万体力只额外增加约`0.0040`分，却增加约`1.9`误停质量。
- 用户已接受主 agent 推荐的 `output_8_13_tank_10_17` 进入新的128件独立真实holdout：它保留约57%的全局12/17效率增益，同时把已知误停质量从3.7降到0.3。
- 权重依据：[R800稳定报告](reports/reforged_inventory_set_weight_r800_weighted_closure_audit_20260718.md)；风险依据：[Phase B/C映射修复报告](reports/epic_threshold_matrix_phase_bc_mapping_repair_20260718.md)。

## 已确认候选规则（覆盖下文历史候选）

- 候选键：`output_8_13_tank_10_17`；默认体系阈值 `+0=12 / +3=17`。
- `pure_output` 覆盖为 `+0=8 / +3=13`；`pure_tank` 覆盖为 `+0=10 / +3=17`；`bruiser`、`dual` 和其他已知正式分类使用默认 `12/17`。
- 候选仅作用于 `normal_85 Epic` 非鞋、初始速度 `<2` 的非速度早期 `+0/+3` 节点；Epic 初速速度 `>=2` 硬路线、鞋子规则、`+6` 后正式 Epic DP、Heroic M1 均不变。
- `candidate_hash`、体系映射版本、Phase B/C schema、关键动作函数、STOVE官方概率、正式DP、资源模型和评分哈希必须在冻结文件生成时计算并写入；冻结后任何规则变化都必须关闭本批次并新建任务。

## 历史候选规则（无效，不得执行）

范围固定为 `normal_85 Epic`、非鞋、初始速度 `<2`：

- 默认体系：`+0` 有效 GS 止损门槛 `12`，`+3` 门槛 `17`。
- 纯输出体系：`+0` 门槛 `8`，`+3` 门槛 `13`。
- 有效词条、终局概率、转换价值和候选体系选择继续使用 Phase B 已冻结口径。
- `category`、`current_pre_reforge_gs`、终局概率和转换价值必须来自同一个 selected candidate。
- Epic 速度 `>=2` 硬路线、`+6` 后正式 Epic DP、Heroic M1 均不变。

## 冻结要求

读取任何新 holdout 指标前，生成只写一次的候选冻结文件，至少包含：

- 规范化候选规则与 SHA-256；
- Phase B/Phase C schema、研究器和关键动作函数哈希；
- STOVE 官方 `+3` 离散概率口径及哈希；
- 正式 Epic DP、资源模型和评分规则哈希；
- holdout 纳入/排除规则；
- 固定盲收目标 `128`，manifest 固定 `64` 件 development 与 `64` 件 frozen_validation；
- 本文预注册的验证指标和闸门。

冻结文件写入后不得修改。规则或关键哈希变化时必须关闭该批次并建立新批次，禁止混合。

## Holdout 范围

固定盲收目标为 `128` 件新的真实 `+0` 快照，不在 `48/64` 件时提前查看结果，避免可选停止。

纳入条件：

- `normal_85 Epic`；
- 非鞋；
- `+0`；
- 初始速度不存在或 `<2`；
- 四条完整副属性；
- 来源于冻结时点后的完整 Fribbels 导出；
- 有稳定 `instanceId`，并能生成规范化状态指纹。

排除条件：

- 任一 Phase A/B/C 开发、冻结验证、旧 Oracle、旧盲测或旧前瞻批次使用过的实例 ID 或指纹；
- Heroic、rift_85、鞋子、速度硬路线、已强化装备；
- 手工表单、模拟样本、条件合成样本或缺少可信来源的 JSON；
- 重复实例或重复指纹。

只需要真实 `+0` 快照；不要求实际强化到 `+3`。快照成功写入后装备可以出售。`+3` 使用 STOVE 官方概率精确枚举并按概率加权。

## 采集与隔离

- 建立独立样本文件，不复用旧 `+0/+3` 成对采集器或其 `128` 件 manifest。
- 状态机固定为 `collecting_blind -> ready_for_frozen_validation -> validation_complete`。
- `0--63` 件期间只允许显示总进度、排除计数和原因，不得计算 Oracle、候选动作、误停或效率。
- 达到 `128` 件后才原子写入不可变 manifest，固定记录 `64/64` 分组、样本 ID、实例 ID、指纹、来源时间、规则哈希、数据哈希和排除项；达到64件只显示进度，不得冻结或读取。
- 采集失败不得影响正式建议或 GUI 主流程；不得接入 OCR、ADB、Airtest 或自动点击。

## 验证方法

对冻结的 `development` 64 件统一执行：

1. `+0` 精确 DP Oracle 与候选动作审计。
2. 对实际进入 `+3` 的状态枚举全部官方合法分支，并按概率加权运行 `+3` Oracle。
3. `+6` 后复用正式 Epic DP，不改变后续策略。
4. 使用 Phase B formal `runs=10`、五个 seed、Heroic M1 和显式维度裂缝/圣女 3-7 联合资源池复核候选相对当前策略的效率。
5. 分别报告总体、纯输出、纯坦、半肉、双效的样本数和风险；稀疏分组只报告，不另调门槛。

## 预注册验证闸门

全部满足才允许进入人工发布确认：

- `+0` 明确正效用召回 `>=95%`；
- `+3` 概率加权明确正效用召回 `>=99%`；
- 纯输出 `+0` 明确正效用误停为 `0`；
- 候选总 regret 不高于当前正式策略；
- 不出现单件或单分支 `continue_utility - stop_utility >=0.01` 的高损失误停；
- 候选相对当前正式策略的五 seed 正式价值率成对 95% 区间下界 `>0`；
- Heroic 产出 `-20%/+20%` 两个敏感性场景下区间下界仍 `>0`；
- 数据隔离、哈希和 64/64 件 manifest 全部有效。

未通过时不得用 holdout 调参。只能维持当前正式策略，或在用户明确批准后建立全新的研究和验证批次。

## 产物

- 候选冻结 JSON；
- 独立 holdout 采集 JSON 与不可变 manifest；
- 人类可读验证报告与逐件/逐分支原始 JSON；
- 采集器、验证器和回归测试；
- 更新后的 `e7-gear-enhance-plan.md`。

报告必须使用每 100,000 总体力口径，拆分正式百里分、22 速、75+、维度裂缝体力、圣女 3-7 体力和循环数。绝对值若仍条件于 holdout 分布，必须明确标注，不能解释为账号自然掉落产量。

## 禁止修改

- 正式 Epic/Heroic 强化策略；
- DP lambda 与资源模型默认值；
- 评分、跳值表、转换规则；
- GUI 业务逻辑、OCR、ADB、Airtest 和自动点击；
- Phase A/B/C 历史报告、JSON 和 resume。

## 验证要求

- 先增加冻结、盲收隔离、去重和闸门失败回归测试。
- 运行相关定向测试、语法检查和 `git diff --check`。
- 候选冻结与采集实现完成后运行 `tools/run_all_tests.py`，报告真实退出码。
- 未收满 128 件时，只能报告盲收进度，不能生成 manifest、读取开发/验证标签或声称 holdout 验证完成；下文旧的64件表述由本节覆盖。

## 正式验证运行记录（2026-07-20）

- `128/128` 与不可变 `64/64` manifest 已确认，验证器已按冻结候选开始正式计算。
- 已完成并保存 development 分区 `64 × 5 = 320` 个流量分片；冻结验证分区尚未完成，因此当前不得输出通过/失败结论。
- 原验证器在等待整批 `ProcessPoolExecutor.map` 返回后才写分片，两个长跑在外层时限结束，最终 JSON/Markdown 尚未生成。该状态不是预注册闸门失败。
- 仅允许将逐件状态和流量作业改为“完成一个、校验哈希、原子写一个”并支持续跑；不得读取验证结果后调参，不得修改正式策略或候选冻结内容。
- Phase B formal 共享 Heroic 分片的历史代码哈希与当前源码不同，但 5 seed 共 400 片齐全；验证器必须读取 formal 报告保存的历史哈希进行严格 `input_hash` 兼容校验，禁止直接忽略哈希或修改缓存。
- 联合资源汇总字段已核对：使用资源模型返回的 `expected_lower_stone_units`；字段修正不改变资源模型、批次成本或预注册闸门。
- 首份报告的绝对百里分列误使用每100体力率，且未列出22速/75+；修复仅作用于人类可读报告，JSON 与闸门结果保持原样。

## Holdout 完成记录（2026-07-20）

- 状态：`validation_passed_pending_user_release`。候选仍冻结为 `output_8_13_tank_10_17`，未修改正式策略。
- `development=64`、`frozen_validation=64`；逐件 JSON 包含 128 件、全部官方 `+3` 概率分支、Oracle、当前动作和候选动作。冻结组分支概率逐件和为 1。
- 冻结组预注册闸门全部通过：`+0` 召回 `100%`、`+3` 加权召回 `100%`、纯输出 `+0` 误停 `0`、regret 不高于当前、无高损失误停、联合价值及 Heroic 产出敏感性区间下界均大于 0。
- 正式产物：[报告](reports/epic_output_8_13_tank_10_17_holdout_validation_20260719.md)、[逐件 JSON](reports/epic_output_8_13_tank_10_17_holdout_validation_20260719.json)。

### 正式发布记录（2026-07-20）

- 用户明确确认发布 `output_8_13_tank_10_17`；独立发布任务已完成。
- 正式策略版本为 `baili-formal-dp-v1-epic-balanced`，生产规则与 4,610 个冻结状态动作逐条一致。
- 发布报告：[epic_output_8_13_tank_10_17_release_20260720.md](reports/epic_output_8_13_tank_10_17_release_20260720.md)；发布任务：[Epic非速度均衡候选正式发布任务说明.md](Epic非速度均衡候选正式发布任务说明.md)。
- 完成后不自动发布；必须等待用户确认，并以新的发布任务说明执行正式策略哈希/回归冻结。

## 用户确认记录（2026-07-18）

- 用户确认 `output_8_13_tank_10_17` 进入本轮独立 holdout。
- 确认依据：库存主权重每10万总体力相对当前增加约`0.0499`正式百里分，top4增加约`0.0566`；已知误停质量`0.3`，相比纯坦12/17仅少约`0.0040`分但少约`1.9`误停质量。
- 本记录只确认候选，不代表正式策略已发布；冻结和盲收仍须按本文件的128件隔离协议执行。

## 准备完成记录（2026-07-18）

- 已先新增失败测试，再创建独立 `src/e7_enhance/epic_balanced_holdout.py` 与 `tools/collect_epic_balanced_holdout.py`。新实现不导入旧 `+0/+3` 成对采集器、不读取旧 manifest，也不计算候选动作、Oracle、误停、regret 或效率。
- 只写一次的候选冻结文件已生成：`samples/epic_output_8_13_tank_10_17_holdout_freeze_20260718.json`。它冻结 `output_8_13_tank_10_17` 的默认12/17、纯输出8/13、纯坦10/17，以及 Phase B/C、官方+3概率、正式DP、资源模型和评分哈希与预注册闸门。
- 独立 collection 已生成：`samples/epic_output_8_13_tank_10_17_holdout_collection_20260718.json`，状态 `collecting_blind`、进度 `0/128`。达到64件仍只显示进度；当前没有 manifest、没有开发/冻结验证读取、没有验证报告或效率结果。
- 采集 CLI 仅接受由其附加 `full_fribbels_export` 与文件 SHA-256 的导入，使用实例 ID 与规范化指纹同时排除历史和批内重复。128件时才原子写入 `samples/epic_output_8_13_tank_10_17_holdout_manifest_20260718.json` 并固定64/64分组。

## 准备验证（2026-07-18）

- 冻结、盲收隔离、历史/批内去重、64件提前读取拒绝、128件64/64 manifest 与来源标记的失败回归均已转绿；相关定向测试共13项通过。
- `python -B -m py_compile src/e7_enhance/epic_balanced_holdout.py tools/collect_epic_balanced_holdout.py tests/test_epic_balanced_holdout.py` 退出码 `0`；`tools/run_all_tests.py` 真实退出码 `0`、输出 `ALL TEST FILES PASSED`。
- 当前 CLI 进度：`accepted=0`、`target=128`、`remaining=128`、`status=collecting_blind`。在达到128前不运行 Oracle、动作审计、联合资源池或任何验证报告。
- 上述0/128进度已被首次可信player snapshot导入覆盖：当前`accepted=6`、`remaining=122`、`status=collecting_blind`。仅更新盲收进度，仍未运行Oracle、动作审计、联合资源池或验证报告。
