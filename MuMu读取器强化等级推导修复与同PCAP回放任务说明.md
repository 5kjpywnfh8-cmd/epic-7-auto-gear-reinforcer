# MuMu 读取器强化等级推导修复与同 PCAP 回放任务说明

## 目标

修复 `D:\VScode\Epic-7-tools.v1.2` 新读取器把全部装备强化等级写成 `0` 的确定性转换错误，并使用已经抓取的同一 PCAP 离线回放生成可信快照，不再次控制游戏或抓包。

## 范围

- 修改 `readers/mumu_capture/fribbels_decode.py` 的装备强化等级推导。
- 补外部读取器定向回归测试。
- 只读参考旧已验证转换器的品质偏移算法，不复制无关逻辑。
- 修复后用 `--input-pcap` 回放 `imports/20260722_000656/mumu_capture.pcap`，生成新的标准快照。

## 禁止修改项

- 不重新抓包、不重启或点击 MuMu，不强化、出售、转换装备。
- 不修改项目正式策略、DP、资源模型、评分、GUI、OCR 自动点击、自动化或 Holdout。
- 不覆盖旧 `20260722_000656` imports/snapshots；回放必须生成新的 player ID 或新时间戳证据。
- 不安装依赖、不修改系统网络设置或 FribbelsE7Optimizer。
- 不根据主属性数值猜强化等级。

## 输入与权威口径

- 错误代码：`_convert_item()` 当前使用 `raw.get("enhance") or 0`，而 Fribbels 原始装备没有 `enhance` 字段。
- 权威推导：由副属性 `op` 事件数量与品质初始偏移计算，并限制最大事件数。
- 品质最大副属性事件数：Normal `5`、Good `6`、Rare `7`、Heroic `8`、Epic `9`。
- 品质初始偏移：Normal `0`、Good `1`、Rare `2`、Heroic `3`、Epic `4`。
- `count = min(len(ops)-1, max_count)`；`enhance = max((count-offset)*3, 0)`。
- 该口径将游戏画面 `+13/+14` 归一到 `+12`，与项目强化节点规则一致。
- 失败快照：`mumu_live/current/player_data.json`，SHA-256 `FBC7C69160356C1679473D6A3FC4E38ED87F15A1A4ED0DAE29C20A19DD9D821E`，`2668/2668` 件 `enhance=0`，禁止导入。
- 回放输入：`D:\VScode\Epic-7-tools.v1.2\data\players\mumu_live\imports\20260722_000656\mumu_capture.pcap`。

## 执行步骤

1. 为 Epic/Heroic 的 `+0/+3/+6/+9/+12/+15` 事件计数补失败测试，并覆盖转换词条注记不增加 rolls 但仍占 `op` 事件的位置。
2. 最小修复 `_convert_item()`；不改抓包、API、标准写盘或其他转换字段。
3. 运行外部读取器定向测试和语法检查。
4. 主 agent 审阅后用 `--input-pcap` 与新 player ID `mumu_live_replay_fixed` 离线回放同一 PCAP。
5. 校验新快照强化等级分布不再全 0、实例 ID 唯一、raw 完整，并与旧已验证导出对共同实例抽样对拍。
6. 通过后再恢复项目档案适配和 batch 002 配对；失败时停止，不导入。

## 产物

- 外部读取器代码与测试。
- 新回放 `player_data.json`、imports/snapshots 证据和 SHA-256。
- 强化等级分布与共同实例对拍结果。
- 同步更新本说明、MuMu/OCR 任务说明与总计划。

## 验证要求

- 原始 `raw` 无 `enhance` 字段时仍正确推导节点等级。
- Epic 九个副属性事件推导 `+15`；Heroic 八个事件推导 `+15`。
- 回放快照不得出现 `2668/2668` 全 0。
- 与旧已验证 `gear_fribbels_20260719_221033.json` 的共同实例，强化节点必须一致；不一致必须列明并停止导入。
- `git diff --check` 和外部定向测试通过。

## 停止条件

- 外部仓库写权限、测试或 PCAP 回放失败时停止并报告。
- 强化等级仍全 0、共同实例不一致或 raw 证据缺失时不得继续项目导入和 OCR 配对。

## 当前状态

`blocked_by_external_write_permission`：`gpt-5.6-terra + high` 已定位并设计最小修复，但 `apply_patch` 无法写入 `D:\VScode\Epic-7-tools.v1.2`，代码、测试和数据均未改变。当前不绕过权限；本轮配对改用《MuMu新player_data结构档案与OCR配对适配任务说明.md》的项目内 raw 证据桥接。外部源修复仍待未来获得可写权限后执行。
