# 22速研究口径修正报告

日期：2026-07-13

## 根因与修正

- 旧研究把`speed_current`的+0门槛统一设为2，错误覆盖了normal_85 Heroic正式门槛4。现已冻结`speed_current_exact`：normal/rift Epic为2，normal Heroic为4；+3仅命中速度时到+6，之后交回正式后续策略。
- 旧联合汇总按相同候选名组合Epic/Heroic，强制同门槛。现已改为显式品质组合，例如`current_epic2_reachable_heroic4`和`reachable_epic2_heroic3`。
- 旧研究将已筛选的速度胚子直接记为每个85体力批次必得装备。现已拆分口径：条件速度胚子只计算增量强化资源；完整装备池因缺少自然初始速度/掉落权重及固定非速度分支，明确标记`not_estimated`，不再输出副本每100体力产量。
- 新研究使用STOVE Epic速度概率及用户确认的Heroic速度概率；旧0.7%尾部分片未读取。normal/rift分布继续独立。

## 条件结果

以下均为“已获得、非鞋且带速度胚子”的每100增量体力22速效率，不是副本产量。

| 来源 | 官方主分布较真实当前 | 结论 | 主要代价（每胚子） |
|---|---:|---|---|
| normal Epic 可达性Epic2 | `-0.000632`，95% `[-0.001029,-0.000235]` | 低于当前 | 正式价值`-0.106678`、原生75+`-0.003022`、输出60`-0.007451` |
| normal Epic 命中链Epic2 | `+0.005758`，95% `[0.004855,0.006661]` | 速度更高 | 正式价值`-0.164055`、原生75+`-0.005397`、输出60`-0.009128` |
| normal Heroic 可达性Heroic4 | `+0.001051`，95% `[0.000962,0.001139]` | 速度更高 | 正式价值`-0.022295`、转换75+`-0.000002`、输出60`-0.000130` |
| rift Epic 可达性Epic2 | `+0.012438`，95% `[0.011884,0.012991]` | 速度更高 | 正式价值`-0.235983`、原生75+`-0.017653`、输出60`-0.009945` |
| rift Epic 命中链Epic2 | `+0.018160`，95% `[0.015828,0.020492]` | 速度更高 | 正式价值`-0.467567`、原生75+`-0.036458`、输出60`-0.013223` |

normal Epic可达性在“移除Epic5速与Heroic1速并重归一化”的敏感性中改为`+0.002865`，95% `[0.002522,0.003207]`，与官方主分布的负差相反。因此它不具备稀有端点稳健性。命中链在两种分布下均提高速度效率，但以明显的正式价值、75+和输出60损失为代价。

## 联合组合与发布判断

已显式生成`current_epic2_reachable_heroic4`：Epic保持已确认的2速硬路线，Heroic单独采用可达性门槛4。它不输出联合22速/体力数值，因为当前真实样本是库存中的速度胚子，不能冒充自然掉落分布。

不创建新的速度前瞻批次，原因：

- 完整装备池效率仍为`not_estimated`；
- normal Epic可达性路线对稀有端点敏感，排序不稳；
- 所有显著提高条件22速效率的Epic/rift路线均显著降低正式价值、75+或输出60；
- rift结果来自normal Epic状态映射的独立高跳值模拟，并非真实异界样本。

## 产物与验证

- 主分布：[JSON](speed_priority_22_methodology_v3_official_20260713.json)、[Markdown](speed_priority_22_methodology_v3_official_20260713.md)
- 稀有端点敏感性：[JSON](speed_priority_22_methodology_v3_rare_removed_20260713.json)、[Markdown](speed_priority_22_methodology_v3_rare_removed_20260713.md)
- 新分片目录：`reports/speed_priority_22_methodology_v3_resume_20260713/`
- 定向研究测试8项通过，语法检查和`git diff --check`通过。`tools/run_all_tests.py`首次仅`test_manual_sample_performance.py`失败；该文件隔离运行通过，第二次完整入口取得`ALL TEST FILES PASSED`与退出码0。该一次性Qt波动未修改GUI代码。
