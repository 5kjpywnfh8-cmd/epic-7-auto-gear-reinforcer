# Heroic 紫装速度门槛研究基准修正 v2

状态：`smoke_only_not_for_release`。

## 已修正

- 第一版把“谨慎继续”视作所有后续节点继续；现在 H4 与正式基准逐节点一致。
- normal Epic 保持已发布 DP；没有再传入 `enable_dp_assist=False`。
- normal Heroic 在未发布资源 lambda 时，从 +6 开始使用明确的 `baili_marginal_low` 基础回退，且 `dp_enabled=false`。
- H2/H3 仅覆盖授权套装、Heroic、非鞋、+0、初始 2/3 速；H4 与未覆盖装备完全交由同一正式基准。
- 终局输出分离原生正式 GS、合法满值转换可达 GS、实际策略承担转换成本的 GS；未知分类不再改写为半肉。

## Smoke 结果

v2 smoke（`set_speed`、2 seed、每 seed 12 个完整联合批次）已出现 +6 与 +9 止损，不再发生第一版“+3 后全部到 +15”。H4 每循环的圣女经验补充约为 137 体力；第一版约 594 的结果来自错误的后续强化路径，不能比较或复用。

## 研究闸门

尚未达到每个主候选、每种初始值口径至少 200 个模拟 Heroic 22+ 有效终局。完整结果必须使用 Heroic 初始 2/3 速的自然概率分层与公共轨迹，并同报告条件成功率、自然权重和加权后贡献；在此之前不得建立速度前瞻批次或修改 Heroic 正式门槛。

第一版报告 `heroic_speed_threshold_100k_20260713.md` 已标记 `superseded_due_to_followup_baseline_error`。v2 smoke 原始数据为 `heroic_speed_threshold_100k_baseline_v2_smoke_20260713.json`。
