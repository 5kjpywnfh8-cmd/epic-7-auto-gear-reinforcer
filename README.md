# 第七史诗装备强化判断工具

当前阶段先做 JSON 输入下的评分、体系判断、强化止损、资源模型和模拟校准。OCR 和 ADB 自动化按计划放到后续阶段。

## 协作与文档

项目级 agent 规则见 [AGENTS.md](AGENTS.md)。每次讨论形成结论或下一步时，必须同步更新 [e7-gear-enhance-plan.md](e7-gear-enhance-plan.md)；每个可执行任务必须先建立独立的 `*任务说明.md`，聊天指令不能替代本地文档。简单实现、测试、研究器改动和文档同步默认由内部子 agent 自动执行；当前仅禁用在回复中自动发布面向人类的子 agent 续作指令。只有用户明确索要时，才按固定标题“给子 agent 的续作指令：”和紧随其后的 `text` 代码块格式提供。

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
- 转换后数值按对应目标属性和最终强化次数的合法满值计算；未转换原生值必须同时保留用于解释。
- 85/90 级满值使用 Fribbels `Constants.modValues.reforged.greater` 的上端值，即 Greater 转换石、100% 品质；这张转换石表独立于普通/异界强化跳值表。
- 转换石成本暂不计入 `cost_per_success`，但 debug 会标记 `conversion_needed`。

策略门槛同时看：

- `expected_final_reforge_score`：预计强化到 `+15` 后重铸有效分。
- 预计 `+15` 后重铸速度。
- 当前有效副属性数量，允许可转换词条补足 1 条。

早期 `+0/+3` debug 还会独立展示“终局 75+ 未来可期概率”：它以终局重铸后的全部副属性官方 GS `>=75` 为目标，不按某个体系过滤，也不包含主属性。它与正式“体系 x 部位”的低档达标概率并存；已有合格正式候选时正式体系始终优先。75+ 仅作为后备复核信息，当前没有发布任何仅凭该概率自动继续的规则。

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

## 当前边界

- 不接 OCR。
- 不自动点击模拟器。
- 不消耗游戏资源。
- 不处理 88 装。
- 没有强化历史时按当前总值和剩余期望做保守预测。
