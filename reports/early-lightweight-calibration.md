# +0/+3 轻量预测校准报告

- 固定种子：20260710
- 每组合样本：1
- 总样本：6
- 轻量预测耗时：0.00138 秒
- 精确 DP 耗时：65.410263 秒
- 耗时倍率：47381.6x
- 临界/高速度直接停止：0

规则：speed rolls >=2, expected speed >=14, 20-speed probability >=0.2, speed potential >=16, expected effective score >=48, formal cross-tier probability >=0.2

| 分层 | 样本 | 轻量 -> 精确 DP |
|---|---:|---|
| normal_85:Epic:+0 | 1 | review->continue=1 |
| normal_85:Epic:+3 | 1 | stop->stop=1 |
| normal_85:Heroic:+0 | 1 | stop->stop=1 |
| normal_85:Heroic:+3 | 1 | review->continue=1 |
| rift_85:Epic:+0 | 1 | stop->stop=1 |
| rift_85:Epic:+3 | 1 | stop->stop=1 |
