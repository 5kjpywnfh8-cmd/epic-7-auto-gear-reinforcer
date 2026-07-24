# MuMu 同账号实时装备数据读取与 OCR 影子刷新任务说明

## 目标

使用已迁移的 MuMu 读取器获取当前同账号的标准 `player_data.json`，在不改变装备状态的前提下更新真实样本档案，并为仓库详情与背包详情分别提供同期 OCR 配对真值。

## 唯一权威来源

- 抓取与转换规则：根目录《MuMu抓包读取与真实装备导入任务说明.md》。
- 读取器根目录：`D:\VScode\Epic-7-tools.v1.2`。
- 当前标准输出：`D:\VScode\Epic-7-tools.v1.2\data\players\mumu_live\current\player_data.json`。
- 旧 `D:\VScode\E7-tools\...\game_read`、`fribbels_mumu_reader.py`、固定 IP 和 `gear_fribbels_*.json` 流程只作历史对照。

## 范围

- 运行标准 MuMu 真实读取命令，自动发现在线设备并生成 `player_data.json`。
- 校验 `current`、`imports`、`snapshots` 属于同一次读取。
- 合格数据可写入真实 `+0` 样本档案；冻结 Holdout 不得继续写入。
- OCR 只允许把同一次读取的结构化装备与截图进行唯一配对，不执行游戏点击或策略修改。
- `warehouse_detail` 与 `backpack_detail` 必须独立标记、独立模板、独立统计。

## 禁止修改项

- 不修改正式策略、DP、评分、资源模型、跳值、转换规则、`next_check_at`、GUI、OCR 自动点击或 Holdout 结论。
- 不强化、出售、转换装备，不消耗游戏资源，不启动 Airtest 或无人值守流程。
- 不写死 MuMu IP，不修改 FribbelsE7Optimizer，不安装 Npcap，不修改系统网络设置。
- 不把 PCAP、旧 JSON、手工转写字段或失败的 `0 items` 结果直接当作 OCR 真值。
- 不把人工目读字段冒充 OCR 输出，不猜测 `instanceId`。

## 标准执行步骤

1. 完整阅读《MuMu抓包读取与真实装备导入任务说明.md》和本说明。
2. 执行：

```powershell
& 'C:\Program Files\Netease\MuMu Player 12\shell\adb.exe' devices -l
Set-Location 'D:\VScode\Epic-7-tools.v1.2'
& 'C:\Users\orangine\AppData\Local\Programs\Python\Python39\python.exe' -B `
  'D:\VScode\Epic-7-tools.v1.2\local_tools\read_mumu.py' `
  --player-id mumu_live `
  --seconds 240 `
  --auto-enter-seconds 105
```

3. 不传 `--device`，由读取器从 `adb devices -l` 自动选择状态为 `device` 的 MuMu。
4. 检查 `current/player_data.json`、同时间 `imports/<时间戳>` 和 `snapshots/<时间戳>`。
5. 校验时间、装备数量、实例 ID 唯一性、`raw` 完整性、文件 SHA-256 和读取器警告。
6. 只有校验通过后才导入真实样本档案；Holdout 非 `collecting_blind` 时不得写入。
7. OCR 配对使用同一次读取的 `player_data.json`；强化等级可按任务说明允许的节点阶梯规则比较，但其余字段必须完全一致。
8. 同步本说明、对应 OCR 任务说明和 `e7-gear-enhance-plan.md`。

## 产物

- `D:\VScode\Epic-7-tools.v1.2\data\players\mumu_live\current\player_data.json`。
- `imports/<时间戳>/` 中的 PCAP 与 Fribbels 原始响应。
- `snapshots/<时间戳>/` 中的不可变快照。
- 真实样本档案导入记录与排除清单。
- OCR 配对 manifest、匹配状态和字段级影子报告（仅当存在多个唯一 matched 样本）。

## 验证要求

- ADB 自动发现至少一个在线 `device`。
- MuMu Root 与模拟器内 `tcpdump` 可用。
- 标准命令不包含固定 IP。
- 当前、原始证据和快照三者时间一致。
- 装备非空、实例 ID 唯一、所有装备含 `raw`。
- 导入前后正式策略和 Holdout 状态不变。
- 运行相关定向校验和 `git diff --check`。

## 失败与停止条件

- 失败时报告读取器完整输出，并按 ADB、Root/tcpdump、空抓包、未抓到同步、Fribbels 解码、UDP/加速器或其他接口流量分类。
- 外层超时后先检查 `current`、`imports`、`snapshots` 是否已落盘，不得立即重复抓包。
- 输出缺少可信时间、装备、实例 ID、`raw`、PCAP 或原始响应时，不得导入或进行 OCR 配对。
- 任何需要强化、出售、转换、安装依赖、修改网络设置或改变正式策略的动作立即停止。

## 当前状态（2026-07-21）

`fresh_snapshot_authorized_for_warehouse_pairing_20260721`：用户已要求继续配对，当前先用新入口刷新并校验 `mumu_live/current/player_data.json`。校验通过后更新真实样本档案，并仅对 `warehouse_detail` 的 `ocr-0006` 执行严格唯一配对；`backpack_detail` 仍单独采样和统计。
