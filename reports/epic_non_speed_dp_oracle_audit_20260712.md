# Epic 非速度早期策略精确 DP 审计（2026-07-12）

## 结论

- 人工标签是玩家资源偏好与风险验收，不是单件边际强化效用的唯一真值；本报告以精确 DP utility margin 判定资源动作，并把人工作为第二套对照。
- 目标 46 件中纳入 45 件，按规则单列排除 1 件速度硬路线、非法或无法唯一关联记录；另有 7 件同源历史审核记录不属于 Epic +0/+3 目标集合。
- Oracle 为 normal_85 Epic 独立跳值表的精确离散枚举；没有使用 Monte Carlo、人工标签或装备获取成本。
- 已发布成本系数：799.2 体力/百里分，lambda=0.0012512513。
- `continue` 和 `cautious_continue` 在资源动作上都表示强化至下一节点；只有数值零点容差内的 Oracle 才标为人工复核。
- 发布结论：不建立正式策略修改任务。

## 稳定关联与排除

- 主关联：源文件 `ingameId/id`；盲测导入后缺失实例 ID 的记录，用规范化装备状态指纹关联。
- 指纹包含套装、部位、主属性、强化等级、装备等级、品质与排序后的副属性值/跳数；排除 code 与实例 ID。重复指纹直接报告并排除。
- 已纳入：old holdout 21 件；blind 24 件。

## 候选与 Oracle

| 策略 | 二元动作一致 | 总 regret | P90 regret | 误强化/浪费体力 | 误停/损失终局价值 | Oracle 正效用召回 | 终局价值/100体力 | 人工三分类一致 | 人工复核 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 当前正式策略 | 51.11% | 0.0746 | 0.0040 | 22/84.83 | 0/0.00 | 100.00% | 1.172 | 46.67% | 100.00% |
| A 当前全部谨慎继续 | 51.11% | 0.0746 | 0.0040 | 22/84.83 | 0/0.00 | 100.00% | 1.172 | 46.67% | 100.00% |
| B 全局当前有效 GS 分层（对照） | 80.00% | 12.9089 | 0.1777 | 2/23.47 | 7/13.53 | 69.57% | 0.721 | 62.22% | 40.00% |
| C 分类终局达标概率 | 66.67% | 0.0778 | 0.0040 | 14/58.02 | 1/0.08 | 95.65% | 1.201 | 37.78% | 17.78% |
| D 分类×部位低档 GS | 73.33% | 14.7322 | 0.2672 | 2/23.47 | 10/15.75 | 56.52% | 0.720 | 55.56% | 33.33% |
| E 分类×部位×主属性限制 | 73.33% | 14.7322 | 0.2672 | 2/23.47 | 10/15.75 | 56.52% | 0.720 | 55.56% | 33.33% |
| F 分类低档 GS 加当前目标 GS | 73.33% | 14.7322 | 0.2672 | 2/23.47 | 10/15.75 | 56.52% | 0.720 | 55.56% | 33.33% |
| G 分类×部位 GS 与终局概率混合 | 71.11% | 14.7623 | 0.2672 | 2/23.47 | 11/15.83 | 52.17% | 0.733 | 57.78% | 31.11% |
| H 预期终局 GS/下一节点体力 | 66.67% | 0.0778 | 0.0040 | 14/58.02 | 1/0.08 | 95.65% | 1.201 | 37.78% | 11.11% |
| I 高召回约束下 GS 效率 | 66.67% | 0.0778 | 0.0040 | 14/58.02 | 1/0.08 | 95.65% | 1.201 | 37.78% | 11.11% |
| J 可行词条与合法转换 | 62.22% | 0.4266 | 0.0040 | 14/58.02 | 3/0.49 | 86.96% | 1.213 | 66.67% | 71.11% |

## 人工与 Oracle 分歧

- 人工偏保守但 DP 正效用：6 件
- 人工偏激进但 DP 负效用：9 件
- DP 边界不确定：0 件
- 人工与 DP 资源动作一致：30 件

## 发布闸门

- B 的人工动作一致率为 73.33%，但有 7 件 Oracle 正效用误停，total regret=12.9089。
- C 的 total regret=0.0778，仅比当前策略 0.0746 高，但仍有 1 件误停。
- 46 件均已读取人工标签，只能用于审计，不能作为候选调整后的独立发布验证。
- 后续要求：从剩余真实 normal_85 Epic 冻结至少 48 件新独立验证批次，再读取人工标签。

## 逐件结果

| 实例 ID | 批次 | 关联 | + | Oracle 动作 | margin | 下一节点体力 | 终局价值 | 当前 | B | C | 人工 | 对照 |
|---|---|---|---:|---|---:|---:|---:|---|---|---|---|---|
| 3885723080 | blind | canonical_fingerprint | 0 | continue | 1.085588 | 2.46 | 1.273 | cautious_continue | cautious_continue | continue | cautious_continue | 人工与 DP 资源动作一致 |
| 3977486440 | blind | canonical_fingerprint | 0 | continue | 0.264225 | 2.46 | 0.373 | cautious_continue | cautious_continue | continue | cautious_continue | 人工与 DP 资源动作一致 |
| 3977489886 | blind | canonical_fingerprint | 0 | stop | -0.004001 | 3.20 | 0.000 | cautious_continue | stop | stop | stop | 人工与 DP 资源动作一致 |
| 3996850773 | blind | canonical_fingerprint | 0 | stop | -0.002689 | 3.20 | 0.011 | cautious_continue | stop | stop | cautious_continue | 人工偏激进但 DP 负效用 |
| 3996864533 | blind | canonical_fingerprint | 0 | continue | 0.887596 | 2.46 | 1.035 | cautious_continue | cautious_continue | continue | continue | 人工与 DP 资源动作一致 |
| 4017335618 | blind | canonical_fingerprint | 0 | stop | -0.004001 | 3.20 | 0.000 | cautious_continue | stop | stop | stop | 人工与 DP 资源动作一致 |
| 4019991959 | blind | canonical_fingerprint | 0 | continue | 0.851204 | 3.20 | 1.020 | cautious_continue | cautious_continue | continue | cautious_continue | 人工与 DP 资源动作一致 |
| 4029023301 | blind | canonical_fingerprint | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | stop | continue | stop | 人工与 DP 资源动作一致 |
| 4040490328 | blind | canonical_fingerprint | 0 | continue | 0.267229 | 2.46 | 0.333 | cautious_continue | stop | continue | stop | 人工偏保守但 DP 正效用 |
| 4040493561 | blind | canonical_fingerprint | 0 | continue | 1.008043 | 2.46 | 1.102 | cautious_continue | stop | continue | stop | 人工偏保守但 DP 正效用 |
| 4042159299 | blind | canonical_fingerprint | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | stop | stop | stop | 人工与 DP 资源动作一致 |
| 4042186802 | blind | canonical_fingerprint | 0 | continue | 0.113437 | 2.46 | 0.181 | cautious_continue | cautious_continue | continue | continue | 人工与 DP 资源动作一致 |
| 4042198699 | blind | canonical_fingerprint | 0 | stop | -0.004001 | 3.20 | 0.000 | cautious_continue | stop | continue | cautious_continue | 人工偏激进但 DP 负效用 |
| 4072930137 | blind | canonical_fingerprint | 0 | continue | 0.314979 | 3.20 | 0.462 | cautious_continue | cautious_continue | continue | cautious_continue | 人工与 DP 资源动作一致 |
| 4085710815 | blind | canonical_fingerprint | 0 | stop | -0.004001 | 3.20 | 0.000 | cautious_continue | stop | continue | stop | 人工与 DP 资源动作一致 |
| 4085715095 | blind | canonical_fingerprint | 0 | continue | 1.346232 | 2.46 | 1.530 | cautious_continue | cautious_continue | continue | cautious_continue | 人工与 DP 资源动作一致 |
| 4088641847 | blind | canonical_fingerprint | 0 | stop | -0.004001 | 3.20 | 0.000 | cautious_continue | stop | stop | stop | 人工与 DP 资源动作一致 |
| 4097405678 | blind | canonical_fingerprint | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | stop | continue | stop | 人工与 DP 资源动作一致 |
| 4109728696 | blind | canonical_fingerprint | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | stop | stop | stop | 人工与 DP 资源动作一致 |
| 4109762500 | blind | canonical_fingerprint | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | stop | continue | stop | 人工与 DP 资源动作一致 |
| 4119234423 | blind | canonical_fingerprint | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | stop | continue | stop | 人工与 DP 资源动作一致 |
| 4119234426 | blind | canonical_fingerprint | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | stop | stop | stop | 人工与 DP 资源动作一致 |
| 4119234427 | blind | canonical_fingerprint | 0 | continue | 0.521295 | 2.46 | 0.542 | cautious_continue | stop | continue | cautious_continue | 人工与 DP 资源动作一致 |
| 4121274132 | blind | canonical_fingerprint | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | stop | cautious_continue | stop | 人工与 DP 资源动作一致 |
| 3539404044 | old_holdout | instance_id | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | stop | continue | cautious_continue | 人工偏激进但 DP 负效用 |
| 3599441551 | old_holdout | instance_id | 0 | continue | 0.475036 | 2.46 | 0.620 | cautious_continue | cautious_continue | continue | cautious_continue | 人工与 DP 资源动作一致 |
| 3617586848 | old_holdout | instance_id | 0 | stop | -0.004001 | 3.20 | 0.000 | cautious_continue | stop | continue | cautious_continue | 人工偏激进但 DP 负效用 |
| 3625975934 | old_holdout | instance_id | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | cautious_continue | continue | cautious_continue | 人工偏激进但 DP 负效用 |
| 3662448880 | old_holdout | instance_id | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | stop | cautious_continue | cautious_continue | 人工偏激进但 DP 负效用 |
| 3672372006 | old_holdout | instance_id | 0 | continue | 0.058242 | 2.46 | 0.133 | cautious_continue | stop | cautious_continue | cautious_continue | 人工与 DP 资源动作一致 |
| 3674239640 | old_holdout | instance_id | 0 | continue | 0.212857 | 2.46 | 0.320 | cautious_continue | cautious_continue | continue | cautious_continue | 人工与 DP 资源动作一致 |
| 3674456008 | old_holdout | instance_id | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | stop | stop | stop | 人工与 DP 资源动作一致 |
| 3674576379 | old_holdout | instance_id | 0 | continue | 1.028811 | 2.46 | 1.205 | cautious_continue | cautious_continue | continue | continue | 人工与 DP 资源动作一致 |
| 3697224036 | old_holdout | instance_id | 0 | stop | -0.001841 | 2.46 | 0.000 | cautious_continue | stop | cautious_continue | cautious_continue | 人工偏激进但 DP 负效用 |
| 3710537727 | old_holdout | instance_id | 0 | continue | 0.410639 | 2.46 | 0.535 | cautious_continue | cautious_continue | continue | continue | 人工与 DP 资源动作一致 |
| 3739360444 | old_holdout | instance_id | 0 | stop | -0.003078 | 2.46 | 0.000 | cautious_continue | stop | cautious_continue | cautious_continue | 人工偏激进但 DP 负效用 |
| 3759152938 | old_holdout | instance_id | 0 | continue | 0.193524 | 2.46 | 0.292 | cautious_continue | cautious_continue | cautious_continue | continue | 人工与 DP 资源动作一致 |
| 3958076815 | old_holdout | instance_id | 3 | continue | 0.106032 | 10.70 | 0.138 | cautious_continue | cautious_continue | cautious_continue | cautious_continue | 人工与 DP 资源动作一致 |
| 3960938570 | old_holdout | instance_id | 3 | continue | 10.696114 | 13.91 | 11.008 | cautious_continue | stop | continue | stop | 人工偏保守但 DP 正效用 |
| 3965269321 | old_holdout | instance_id | 3 | stop | -0.006065 | 10.70 | 0.015 | cautious_continue | cautious_continue | continue | cautious_continue | 人工偏激进但 DP 负效用 |
| 3996852173 | old_holdout | instance_id | 3 | continue | 1.403283 | 10.70 | 1.608 | cautious_continue | cautious_continue | cautious_continue | stop | 人工偏保守但 DP 正效用 |
| 4010616628 | old_holdout | instance_id | 3 | continue | 0.030143 | 10.70 | 0.080 | cautious_continue | cautious_continue | stop | stop | 人工偏保守但 DP 正效用 |
| 4015856793 | old_holdout | instance_id | 3 | continue | 0.851701 | 10.70 | 1.016 | cautious_continue | cautious_continue | continue | cautious_continue | 人工与 DP 资源动作一致 |
| 4040486219 | old_holdout | instance_id | 3 | continue | 0.177706 | 13.91 | 0.213 | cautious_continue | stop | continue | cautious_continue | 人工与 DP 资源动作一致 |
| 4095491577 | old_holdout | instance_id | 3 | continue | 0.171097 | 13.91 | 0.200 | cautious_continue | stop | continue | stop | 人工偏保守但 DP 正效用 |

## 口径

- 即时停止 utility 规范化为 0；当前出售/回收值是两条路径共同的沉没状态，不在差值中重复扣除。继续路径的节点净成本已包含之后停止时的出售/回收差额。
- `forced_continue_stamina` 是“候选要求强化到下一节点、其后回到 Oracle”的端到端期望增量体力；它用于误强化成本与 regret 统计。
- 终局正式价值、速度潜力和合法满值转换价值均来自 Oracle 终局枚举；转换成本为一次 100,000 金币并已折算进入 utility。
- 这 46 件均已有人看过，不能再作为调整候选后的独立发布验证。若要改变任何候选门槛，须先从剩余真实 normal_85 Epic 冻结至少 48 件新验证样本。
