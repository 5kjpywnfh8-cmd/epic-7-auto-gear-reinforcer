# 第七史诗装备强化判断工具

主分支提供 JSON 输入下的评分、体系判断、强化止损、资源模型和模拟校准。OCR / ADB 自动化在本地 P4 开发线中推进，尚未合入主分支，完整自动强化循环尚未完成。

## 开发进度

文档更新于 2026-10-23。以下区分 GitHub 主分支已发布功能与本地 P4 实验能力；离线验证记录截至 2026-09-15，不代表完整实机验收通过。

| 范围 | 当前状态 |
| --- | --- |
| 主分支可用功能 | JSON 装备评分、强化建议、批量分析、资源估算、模拟与策略校准；运行方式见下文。 |
| 本地 P4 实验能力（未发布） | 已有截图识别、六部位及分页的只读扫描代码，以及受限单件、单区间强化执行代码；仍需完成修复后的实机复验。 |
| 全循环强化 | 尚未打通多件调度、单件连续区间强化、强化后返回列表并重新定位、与六部位及分页扫描的整体联动；完整实机验收未完成。 |

### 本地修复与验证记录

2026-09-15 已在本地修复两处识别链路问题，尚未发布到主分支：

- 裁剪识别结果合并时丢失经验进度，导致强化结果无法核验；现保留有效的经验进度，继续执行跨帧一致性核验。
- 副属性 `7 (+3)` 被数值解析拒绝，导致该副属性丢失；现按当前总值 `7` 解析，并保留严格的格式检查。

当日相关离线测试共 **492 项通过**，包含历史实机截图及缓存模型回复的回归验证。这些结果只证明相应代码路径通过离线检查，不能证明实机全循环已完成。本次 README 更新未重新运行程序测试，也未进行新的实机验收。

### 下一验收目标

采用“小样本完整闭环”：在同一次验收中覆盖六部位切换、翻页、多件处理，以及单件的“识别 → 策略判断 → 分段强化 → 身份、等级与资源核验 → 重新判断 → 返回列表 → 下一件”。按策略停止或达到 `+15` 后结束该件处理。

先接通调度与持久化结算，运行时使用明确的金币、材料累计预算；达到上限即停止。识别或导航失败时有限重试后跳过；已发送强化动作但结果未知时暂停，恢复时不得重复发送。每步保留本地证据，验收报告明确列出已覆盖、未覆盖及失败项。预算不足或样本不满足覆盖要求时，不标记为完整通过。

本轮验收仅包含强化，出售、提取不在范围内。P4 尚无面向主分支用户发布的全循环启动命令。

## 参考来源

规则资料、外部项目参考和许可证边界见 [REFERENCES.md](REFERENCES.md)。

## 快速运行

```powershell
python main.py suggest --input samples/gear.json
python main.py suggest --input samples/gear.json --debug
python main.py batch --input samples/gears.json --output reports/latest.md
python main.py resource
python main.py resource --gear-source rift_hunt
python main.py simulate --runs 5000 --item-source normal_85
python main.py simulate --input samples/gear.json --runs 5000 --item-source rift_85 --debug
python main.py calibrate --runs 10000 --item-source normal_85
python main.py calibrate --runs 10000 --item-source rift_85 --debug
```

默认输出只显示强化前需要看的摘要；`--debug` 输出完整评分、模拟和校准字段，方便和旧工具回归对比。

## 命令说明

- `suggest`：对单件装备给出继续、谨慎继续或停止建议。
- `batch`：批量分析装备样本。
- `resource`：查看红装强化资源账本。金币和强化经验按同一次 8 体力共同产出计算，体力等价取瓶颈资源。
- `simulate`：从 `+0` 掉落或指定装备开始模拟强化。默认 `--strategy full` 跑到 `+15`，用于观察最终分布；`--strategy current` 复用当前止损建议。
- `calibrate`：生成多组阶段门槛，从 `+0` 到 `+15` 完整模拟，按 `cost_per_success` 排序并输出前 5 名策略。

## 校准口径

校准从 `+0` 胚子开始，成本包含：

- 装备获取体力。
- 强化金币和强化经验的体力等价。
- 停止后出售回收的金币和强化经验等价。

成品成功线：

- 普通 85、紫装、异界 85 使用同一套 `+15` 重铸后要求。
- 非鞋速度装：最终重铸速度 `>= 22`。
- 非速度装：命中目标体系，且重铸有效分 `>= 60`，且转换后有效副属性 `>= 3`。
- 原本已经命中百里体系的装备仍视为成功。

转换石第一版规则：

- 每件装备最多考虑转换 1 个无效副属性。
- 只允许转换 `rolls <= 2` 的无效副属性，也就是初始词条或最多吃过 1 跳。
- 转换目标必须属于当前目标体系，且不能与已有副属性或主属性冲突。
- 转换后数值按期望均值估算。
- 转换石成本暂不计入 `cost_per_success`，但 debug 会标记 `conversion_needed`。

策略门槛同时看：

- `expected_final_reforge_score`：预计强化到 `+15` 后重铸有效分。
- 预计 `+15` 后重铸速度。
- 当前有效副属性数量，允许可转换词条补足 1 条。

参考 [zhaoyifan0528/e7](https://github.com/zhaoyifan0528/e7) 的阶段门槛搜索思路。本工具不照搬其跳值概率、数值或代码，当前实现按用户确认的 85 装跳值范围等概率模拟，并保留 `+12` 止损节点。完整来源说明见 [REFERENCES.md](REFERENCES.md)。

## 输入结构

```json
{
  "set": "Speed",
  "slot": "Weapon",
  "mainStat": { "type": "Attack", "value": 525 },
  "enhance": 12,
  "level": 85,
  "rank": "Epic",
  "substats": [
    { "type": "Speed", "value": 12 },
    { "type": "CriticalHitChancePercent", "value": 8 },
    { "type": "CriticalHitDamagePercent", "value": 14 },
    { "type": "AttackPercent", "value": 12 }
  ],
  "rollHistory": []
}
```

## 主分支工具的当前边界

- 主分支 JSON 工具不接 OCR；本地 P4 的截图识别尚未发布。
- 主分支 JSON 工具不自动点击模拟器。
- 主分支 JSON 工具不消耗游戏资源。
- 不处理 88 装。
- 没有强化历史时按当前总值和剩余期望做保守预测。
