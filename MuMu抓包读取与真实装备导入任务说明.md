# MuMu 抓包读取与真实装备导入任务说明

本文件是项目读取 Epic Seven MuMu 真实数据的唯一权威来源。聊天中的旧路径、旧 IP、旧命令或旧读取器说明均不得覆盖本文件。

## 目标

在用户明确授权后，通过已迁移的本地读取器自动发现 MuMu、在模拟器内抓取 Epic Seven 同步流量、经 Fribbels API 解码并写出标准 `player_data.json`，随后按项目边界导入真实样本档案。

## 范围

- 只读检查 MuMu ADB、Root 和 `tcpdump`。
- 重启 Epic Seven，自动尝试关闭登录页和公告页，并抓取 240 秒网络流量。
- 把抓到的 TCP 载荷上传到指定 Fribbels API 解码。
- 写入 `current`、`imports` 和 `snapshots` 三类标准数据产物。
- 校验合格后，可把 `player_data.json` 导入本项目真实样本档案。

## 禁止修改项

- 不强化、出售、转换装备，不消耗游戏资源，不启动 Airtest 或无人值守强化。
- 不修改正式策略、DP、评分、资源模型、跳值表、GUI、OCR、自动化或 Holdout 结论。
- 不修改 FribbelsE7Optimizer 安装目录。
- 不安装 Npcap，不修改 Windows 或 MuMu 的系统网络设置。
- 不写死或复用任何 `192.168.x.x:5555` 地址；读取器必须自动发现在线 MuMu。
- 不直接修改生成的 JSON，不把 PCAP、旧 `gear_fribbels_*.json` 或手工数据冒充本次新快照。

## 权限与权威输入

- 允许读取和修改：`D:\VScode\Epic-7-tools.v1.2`。
- 允许通过 ADB 自动发现并控制 MuMu：在模拟器内运行 `su -c tcpdump`、重启 Epic Seven、自动尝试关闭登录/公告页。
- 允许把本账号抓到的 TCP 载荷发送到：`https://krivpfvxi0.execute-api.us-west-2.amazonaws.com/dev/getItems`。
- 上述外部传输授权仅用于本任务的 Fribbels 装备数据解码。

固定组件：

| 项目 | 路径/值 |
| --- | --- |
| 工作目录 | `D:\VScode\Epic-7-tools.v1.2` |
| Python 入口 | `D:\VScode\Epic-7-tools.v1.2\local_tools\read_mumu.py` |
| CMD 入口 | `D:\VScode\Epic-7-tools.v1.2\scripts\read_mumu.cmd` |
| Python | `C:\Users\orangine\AppData\Local\Programs\Python\Python39\python.exe` |
| MuMu ADB | `C:\Program Files\Netease\MuMu Player 12\shell\adb.exe` |
| Epic Seven 包名 | `com.zlongame.cn.epicseven` |
| 本地玩家 ID | `mumu_live` |

## 标准执行步骤

### 1. 检查 MuMu 在线状态

```powershell
& 'C:\Program Files\Netease\MuMu Player 12\shell\adb.exe' devices -l
```

- 至少存在一个状态为 `device` 的 MuMu。
- 读取器会自动选择在线设备；标准命令不传 `--device`，不得从历史记录复制 IP。

### 2. 检查运行前置条件

- MuMu 已启用 Root。
- 模拟器内可执行 `su -c tcpdump`。
- Epic Seven 包名为 `com.zlongame.cn.epicseven`。
- 不要求固定游戏服务器 IP、端口或网络出口。

### 3. 执行真实读取

```powershell
Set-Location 'D:\VScode\Epic-7-tools.v1.2'
& 'C:\Users\orangine\AppData\Local\Programs\Python\Python39\python.exe' -B `
  'D:\VScode\Epic-7-tools.v1.2\local_tools\read_mumu.py' `
  --player-id mumu_live `
  --seconds 240 `
  --auto-enter-seconds 105
```

该命令必须由读取器自行完成：

- 从 `adb devices -l` 自动发现 MuMu；
- 在模拟器内通过 `su -c tcpdump` 抓包；
- 重启 Epic Seven 并尝试关闭登录/公告页；
- 抓取 240 秒，不依赖固定服务器 IP、端口或网络出口；
- 上传 TCP 载荷到 Fribbels `/dev/getItems`；
- 标准化并写入 `player_data.json`。

### 4. 检查标准产物

当前文件：

`D:\VScode\Epic-7-tools.v1.2\data\players\mumu_live\current\player_data.json`

原始证据：

`D:\VScode\Epic-7-tools.v1.2\data\players\mumu_live\imports\<时间戳>\`

不可变快照：

`D:\VScode\Epic-7-tools.v1.2\data\players\mumu_live\snapshots\<时间戳>\`

必须先检查上述路径是否落盘，再判断命令超时或非零退出是否真的失败。

### 5. 输出校验

- `player_data.json` 时间戳属于本次运行，不是旧文件。
- 装备列表非空，记录的装备数量与数组长度一致。
- 实例 ID 完整且唯一。
- 所有装备保留完整 `raw` 字段。
- `imports/<时间戳>` 中存在本次原始 PCAP 和 Fribbels 原始响应。
- `snapshots/<时间戳>` 与 `current/player_data.json` 对应同一次读取。
- 记录 `player_data.json` 的 SHA-256、字节数、装备数量和异常警告。

### 6. 导入项目真实档案

仅在输出校验通过后执行：

```powershell
Set-Location 'C:\Users\orangine\Documents\第七史诗强化装备脚本'
& 'C:\Users\orangine\AppData\Local\Programs\Python\Python39\python.exe' -B `
  tools\collect_epic_plus0_archive.py `
  --import-json 'D:\VScode\Epic-7-tools.v1.2\data\players\mumu_live\current\player_data.json'
& 'C:\Users\orangine\AppData\Local\Programs\Python\Python39\python.exe' -B `
  tools\collect_epic_plus0_archive.py --progress
```

- 实例 ID 与规范化指纹双重去重。
- Holdout 只有状态为 `collecting_blind` 才允许写入；当前旧批次已冻结，不得继续写入。
- OCR 配对必须使用同一次读取的 `player_data.json`，不得回退到旧快照补齐匹配。

## 失败处理

失败时必须保留并报告读取器完整输出，不得只写“读取失败”。至少区分：

| 分类 | 处理 |
| --- | --- |
| ADB 未连接 | 重新执行 `adb devices -l`，检查是否存在状态为 `device` 的 MuMu；不得手工写死 IP。 |
| Root/tcpdump 不可用 | 启用 MuMu Root 并完全重启模拟器；不安装 Npcap。 |
| 抓包为空 | 报告 PCAP 路径、字节数和完整读取器输出。 |
| 未抓到账号同步 | 保留本次 `imports`，报告 `0 items` 或同步诊断，不把旧 JSON 当新结果。 |
| Fribbels 解码失败 | 报告 API 错误和抓包诊断；不得手工改响应。 |
| UDP 或其他接口流量 | 报告读取器关于加速器、UDP 或网络接口的完整诊断；不得修改系统网络设置。 |
| 外层命令超时 | 先检查 `current`、`imports`、`snapshots` 是否已经落盘，再决定是否重跑。 |

同一失败在没有环境变化时不得盲目重复抓包。

## 产物

- 新读取器生成的 `current/player_data.json`。
- 对应 `imports/<时间戳>` 中的 PCAP 与 Fribbels 原始响应。
- 对应 `snapshots/<时间戳>` 中的不可变快照。
- 本项目真实档案导入结果、排除原因和进度。
- 同步更新本说明、相关 OCR 任务说明和 `e7-gear-enhance-plan.md`。

## 验证要求

- 新根目录、Python 入口、CMD 入口、Python 和 ADB 路径均存在。
- `scripts\read_mumu.cmd` 实际调用 `local_tools\read_mumu.py`。
- 标准命令不包含固定 `--device` 或任何 `192.168.x.x` 地址。
- 文档中旧读取器路径只允许出现在明确的历史对照段落。
- 完成文档更新后运行链接/路径检查和 `git diff --check`。

## 停止条件

- ADB 无在线 `device`、MuMu 未启用 Root、`tcpdump` 不可用或 API 解码失败时停止并报告完整输出。
- 输出缺少可信时间、装备数组、实例 ID、`raw`、PCAP 或原始响应时，不得导入项目档案。
- 任何需要安装依赖、修改网络设置、修改 FribbelsE7Optimizer、强化/出售/转换装备或改正式策略的要求，必须停止并另建任务。

## 当前状态（2026-07-21）

`fresh_read_authorized_for_ocr_pairing_20260721`：用户已明确要求继续仓库详情配对，本轮获准按 240 秒自动发现命令生成新的 `mumu_live/current/player_data.json`。读取完成前不得更新 OCR manifest；输出校验通过后只导入真实样本档案，不写冻结 Holdout。

## 历史记录（仅作对照，已被上文覆盖）

- 2026-07-19 与 2026-07-21 曾使用 `D:\VScode\E7-tools\...\game_read\fribbels_mumu_reader.py`、手工 ADB 地址和旧 `gear_fribbels_*.json` 流程；对应成功与失败数据仍保留为历史证据。
- 旧流程的固定 IP、手工 PCAP 拉取、手动背包导航和旧输出路径均不得作为当前执行指令。

## 2026-07-22 batch 005 OCR 前置读取

- 初次 `adb devices -l` 为空，标准读取器按预期拒绝启动并报告 `未发现在线 MuMu ADB 设备`；该次没有抓包或写新数据。
- 只读检查确认运行实例 0 的 Root 与 ADB 调试已开启，且网络为桥接模式。本地 NAT `host_port` 不监听时，不得继续尝试该端口；只能读取当前运行实例日志最新的 `wifi_ip`，连接后再次以 `adb devices -l` 验证状态必须为 `device`。日志实时地址仅作当次恢复，不得写死到读取器、命令或文档。
- 恢复后标准命令成功完成批次 `20260722_132045`，退出码 `0`：装备 `2670`、英雄 `387`。
- 当前 `player_data.json` 为 `2593245` 字节，SHA-256 `3D74E2D69147D5A1053F0EBCCC217ED2C64842FA2CE91CCE6413E5FEA364185B`，实例 ID `2670/2670` 唯一。
- 同批 `reader_result.json` 为 `6460153` 字节，SHA-256 `3831F40814C015166794BF44FBD55D153668532D549E612AFF431C24E42F900B`，保留 `raw=2670/2670`；PCAP、Fribbels 原始响应和不可变快照齐全。
- 规范化 `player_data.json` 不内嵌 raw；OCR 配对必须同时使用同批 `reader_result.json` 的 raw 证据。上文“所有装备保留完整 raw 字段”按此双文件证据口径执行，禁止因 `player_data.json` 无 raw 误判读取失败。
- 新快照已导入真实 Epic +0 档案，累计接受 `382` 件；已冻结 Holdout 未写入。OCR 后续状态见[batch 005 前置报告](reports/ocr_stage1_backpack_batch_005_reader_20260722.md)。
