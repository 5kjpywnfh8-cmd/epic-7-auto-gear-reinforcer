# 纯视觉 ADB 截图与受控点击迁移任务说明

## 目标

将 MuMu 的纯视觉主路线明确为“ADB 截图 -> 局部模板/PaddleOCR 识别 -> 视觉决策 -> 单次受控 ADB 点击 -> 新截图后验”，本轮只完成并验证只读 ADB 截图帧源，接入现有 `VisualFrame` / `PlatformFrameSource` / `VisualAdapterSampler` 链路。

## 唯一权威口径

本文件是本轮唯一权威任务来源。当前目标装备、资源上限、视觉模式和既有离线规划结论以 `e7-gear-enhance-plan.md` 中最新条目为准；视觉结果必须标记 `mode=visual_only`、`verification=unverified`，不得表述为服务器确认。

## 范围

1. 在任何真实采集前运行 MuMu 官方 `adb.exe devices -l`，只接受自动发现且状态为 `device` 的唯一设备。
2. 只使用 `adb exec-out screencap -p` 获取 PNG，接入现有帧源、稳定帧、帧哈希、视口、时间戳、局部区域、PaddleOCR 和字段置信度门槛。
3. 补充 fake ADB 截图、设备发现、PNG、旋转/视口、稳定帧失败和完整适配链路测试。
4. 在代码与离线测试通过后执行一次定向真实只读预检；真实预检只读取截图，不落盘私人截图、不上传数据。

## 明确禁止

- 本轮不得调用 ADB `input tap`、`swipe`、`keyevent`，不得点击游戏、强化、选材、消耗资源、重启游戏或导航页面。
- 不得使用 Fribbels、PCAP、TCP 载荷、`player_data.json`、装备底层数据读取器或任何外部上传。
- 不得降低或绕过既有稳定帧、视口、局部识别和 0.98 字段置信度门槛。
- 不得修改正式策略、DP、评分、资源模型、GUI、OCR 门槛、Holdout、自动化规则或 Windows 截图备用实现；Windows 方案仅保留为非 ADB 场景备用。
- 不得读取、恢复、暂存或上传私人归档；不得触碰或删除 `refs/heads/main - 副本`。

## 输入与执行步骤

1. 完整阅读本文件及 `AGENTS.md`、`e7-gear-enhance-plan.md`。
2. 只读审阅现有视觉帧源、适配器采样器、点击器和公开测试，确定兼容接口。
3. 在不改变既有门槛与自动化规则的前提下实现 ADB 设备发现和只读 PNG 帧源。
4. 增加 fake 后端与异常 fail-closed 测试，运行定向测试、语法检查和 `git diff --check`。
5. 精确审阅 diff，仅暂存本任务文件，提交并推送当前分支。
6. 取得真实只读预检授权后，先运行官方 `adb.exe devices -l`，再执行一次 `exec-out screencap -p`，只在内存中验证 PNG、稳定帧、哈希、视口和局部区域边界。

## 产物

- ADB 只读帧源及其 fake 测试。
- 公开测试与定向验证结果。
- 本文件和 `e7-gear-enhance-plan.md` 中的完成项、验证结果、未完成项、风险和下一步记录。

## 验证要求

- 设备不可用、设备不唯一、命令失败、空/损坏/非 PNG、旋转或视口漂移、黑屏、旧帧、区域越界、锚点缺失、低置信度、字段矛盾均必须统一 fail-closed，禁止自动重试。
- 保持现有离线视觉运行时、点击器接口和公开测试兼容。
- 记录实际使用模型；按用户要求优先 `gpt-5.6-terra + high`，若不可用如实记录替代模型。

## 停止条件

- 文档未创建并完整阅读前，停止所有 ADB、截图、OCR、点击和代码修改。
- 任一只读前置条件失败，停止真实预检，不进行重试或任何游戏操作。
- 只有在另建任务说明并取得用户明确授权后，才可进入真实单次受控点击。

## 完成项与验证记录

- 新增 `src/e7_enhance/visual_adb.py`：自动发现唯一 `device` 状态设备，接入 `PlatformFrameSource`，只生成 `exec-out screencap -p` PNG 帧；不提供 ADB 输入、导航、OCR、底层读取或上传接口。
- 新增 `tests/test_visual_adb.py`：覆盖设备发现、命令白名单、损坏 PNG/CRC、内置黑屏拒绝、设备身份变化、旋转/视口漂移、稳定帧与 `VisualAdapterSampler` 全链路。
- 追加禁止 `192.168.x.x:5555` 序列号、完整 PNG 解码和 all-black fail-closed 校验；保留可注入内容校验器用于后续页面/锚点策略。
- `python -m unittest discover -s tests -p 'test_visual_adb.py'`：6/6，退出码 0。
- `python -m unittest discover -s tests -p 'test_visual_*.py'`：40/40，退出码 0。
- Python 语法检查与 `git diff --check` 通过；实际模型记录为 `gpt-5.6-terra + high`。
- 全量 `python -m unittest discover -s tests`：534 项，504 通过、7 失败、23 错误；失败集中于工作区缺失的私人归档/历史 holdout 文件和既有研究矩阵/策略清单状态，未读取、恢复或修改这些文件，不归因于本任务 ADB 改动。

## 未完成项与风险

- 尚未执行真实 `adb.exe devices -l` 或 `exec-out screencap -p`；尚未验证当前 MuMu 的真实 PNG 编码、视口和黑屏阈值。
- 尚未接入真实局部模板/PaddleOCR，也未执行任何点击、页面导航、强化、选材或资源操作。
- 真实预检必须只在内存中读取并校验一帧，不落盘私人截图、不上传数据；任一设备、PNG、视口、黑屏、旧帧、区域或证据条件失败即停止且不重试。

## 当前状态

`offline_adb_frame_source_verified_pending_real_readonly_preflight`
