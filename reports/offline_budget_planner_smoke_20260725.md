# 离线预算与硬上限规划结果

- 规则版本：`offline_budget_planner/v1`
- 状态：`success`
- 模式：`validated_against_hard_limits`
- 材料池：`common`
- 品质：`Epic`
- 排序：`minimum_gold -> minimum_base_experience_overflow -> minimum_material_count -> material_priority`
- 硬上限核对：`passed`

| 分段 | 需求基础经验 | 投入基础经验 | 溢出 | 材料 | 金币 |
|---|---:|---:|---:|---|---:|
| +0 -> +3 | 1969 | 2000 | 31 | lower_enhance_stone=1, powder=5 | 22400 |

- 累计预计消耗：材料 `{'lower_enhance_stone': 1, 'powder': 5}`；金币 `22400`。
- 累计建议硬上限：材料 `{'lower_enhance_stone': 1, 'powder': 5}`；金币 `22400`。
- 本结果仅为离线计算，不构成材料选择、资源消耗或实际操作授权。
