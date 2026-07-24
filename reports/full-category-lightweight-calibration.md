# +0/+3 候选体系轻量预测校准报告

- 版本：full-category-dp-calibration-v1
- 随机种子：20260711
- 精确 DP 标注样本：6
- 训练/保留集：6 / 0
- 覆盖范围：1 category/slot-stratified templates per rank shape (targeted run)
- 精确 DP 并行进程：1
- 已发布自动继续规则：0
- 分组键包含来源、品质、部位、主属性约束、体系、套装组、当前有效副属性数和可行有效副属性数。
- 未覆盖分组在产品中固定为‘待 +6 精确复核’，不回退到全局阈值。

## 保留集结果

| 分组 | 可校准样本 | 硬例外样本 | 直接决策一致率 | 复核延后率 | 误继续率 | 误停止率 | 轻量停止而 DP 继续 |
|---|---:|---:|---:|---:|---:|---:|---:|

## 速度专项

{
  "multi_roll_samples": 0,
  "multi_roll_review_dp_continue": 0,
  "speed_main_boot_samples": 0,
  "speed_main_boot_continue": 0,
  "manual_multi_roll_samples": 1,
  "manual_multi_roll_continue": 1
}

## 人工硬回归

[
  {
    "name": "07 高价值多跳速度",
    "expected_action": "continue",
    "expected_lightweight": "continue",
    "exact_action": "continue",
    "passed": true
  },
  {
    "name": "01 普通红 +0 复核边界",
    "expected_lightweight": "review",
    "exact_action": null,
    "passed": true
  },
  {
    "name": "04 异界红 +0 复核边界",
    "expected_lightweight": "review",
    "exact_action": null,
    "passed": true
  },
  {
    "name": "14 单条偏离转换候选",
    "expected_lightweight": "review",
    "exact_action": null,
    "passed": true
  }
]
