# Epic 非速度 +0/+3 门槛矩阵 Phase C 组合收口任务说明

## 状态

`superseded_by_mapping_repair_pending_user_confirmation`

本任务曾完成离线比较，用户于 2026-07-18 确认选择 `balanced_output_m4`。随后复核发现“输出(必爆)”被错误映射到 `unknown`，体系组合结论已失效。映射修复与纯坦9组复核现已完成，但本文件中的候选规则、结果和推荐仍仅保留为失效审计记录；不得冻结、发布或采集。新结果见[修正报告](reports/epic_threshold_matrix_phase_bc_mapping_repair_20260718.md)。

## 目标

在 Phase B 已完成的候选体系一致口径和 `runs=10` 公共基础分片上，比较少量预注册组合，收口 Epic 非速度 `+0/+3` 的保守、均衡和激进风险档位。

## 范围

- 仅研究 `normal_85 Epic`、非鞋、初始速度 `<2` 的 `+0/+3` 早期止损。
- 复用 Phase B formal `runs=10` 基础缓存，不重新模拟 `+3` 后正式路径。
- Heroic M1、正式 Epic `+6` 后路线、官方跳值概率和联合资源池口径保持不变。
- 不修改正式策略、DP、资源模型、评分、GUI、OCR 或自动化。
- 不读取新的 holdout，不自动选择候选。

## 冻结候选集合

- `current_formal`
- `global_10_14`
- `global_12_17`
- `global_14_18`
- `balanced_output_m2`：默认 `12/17`，纯输出使用 `10/15`
- `balanced_output_m4`：默认 `12/17`，纯输出使用 `8/13`
- `balanced_high_priority_m2`：默认 `12/17`，纯输出与纯坦使用 `10/15`

## 统一指标

- 每 100 体力正式价值增量及五 seed 成对区间。
- 保留 `global_12_17` 收益的比例。
- `+0` 真实误停、`+3` 误停分支与概率质量。
- utility loss、regret、节省体力。
- 每 100,000 总体力的正式百里分、22 速、75+、维度裂缝体力、圣女 3-7 体力和循环数。

离线排序与发布闸门必须分开。零误停只限制发布，不得删除离线风险对照。

## 已完成结果

| 候选 | 每100体力价值增量 | 保留12/17收益 | 正效用误停概率质量 |
|---|---:|---:|---:|
| `global_10_14` | 0.000425 | 52.52% | 0.8 |
| `global_12_17` | 0.000810 | 100.00% | 3.7 |
| `global_14_18` | 0.001165 | 143.91% | 8.0 |
| `balanced_output_m2` | 0.000681 | 84.14% | 3.7 |
| `balanced_output_m4` | 0.000515 | 63.58% | 2.2 |
| `balanced_high_priority_m2` | 0.000541 | 66.80% | 1.8 |

`balanced_output_m4` 显著降低了 `+3` 误停概率质量；`balanced_high_priority_m2` 消除了 `+0` 明确正效用误停，但 `+3` 风险仍需人工取舍。当前没有候选自动通过发布。

## 主 agent 复核

- `balanced_output_m2` 与全局 `12/17` 的明确正效用误停概率质量和 utility loss 相同，但效率更低、regret 更高，不再作为首选。
- `balanced_high_priority_m2` 相比 `balanced_output_m4` 每 100,000 总体力只多约 `0.026` 正式百里分，但 utility loss 为 `0.042477`，约为后者 `0.005320` 的 8 倍，且 regret 更高。
- 当前推荐 `balanced_output_m4` 进入新的独立 holdout：默认门槛 `12/17`，纯输出使用 `8/13`。该推荐尚未获得用户确认，不冻结哈希、不开始验证。
- 用户已确认上述推荐。后续唯一权威任务为 [Epic非速度+0+3均衡候选独立Holdout验证任务说明.md](Epic非速度+0+3均衡候选独立Holdout验证任务说明.md)。

上述确认已因体系映射错误暂停。修正任务以 [Epic非速度PhaseB-C体系映射修复与坦克门槛复核任务说明.md](Epic非速度PhaseB-C体系映射修复与坦克门槛复核任务说明.md) 为当前唯一权威入口；旧 Phase C 报告保留为失效审计证据。

## 产物

- [Phase C 报告](reports/epic_threshold_matrix_phase_c_20260718.md)
- [Phase C 原始结果](reports/epic_threshold_matrix_phase_c_20260718.json)
- [Phase C 研究器](tools/research_epic_threshold_matrix_phase_c.py)
- [Phase B 正式报告](reports/epic_threshold_matrix_phase_b_formal_r10_20260718.md)
- [Phase B 正式结果](reports/epic_threshold_matrix_phase_b_formal_r10_20260718.json)

## 验证

- Phase C 复跑通过。
- 语法检查和 `git diff --check` 通过。
- `tools/run_all_tests.py` 全量通过，真实退出码 `0`。

## 下一步与停止条件

- 暂停 `balanced_output_m4` 冻结与 holdout。先修复体系映射、重聚合输出组合，并完成纯坦独立门槛复核。
- 修正候选重新获得用户确认前，不得读取新 holdout 指标或修改正式策略。
- 不再新增 Phase D 或扩大矩阵；若现有候选均不可接受，则维持当前正式策略并关闭本研究线。
