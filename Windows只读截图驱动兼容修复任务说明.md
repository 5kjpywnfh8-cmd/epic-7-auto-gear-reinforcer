# Windows 只读截图驱动兼容修复任务说明

## 目标

修复真实只读预检暴露的 Windows 捕获兼容问题：为纯视觉平台提供一个不依赖 `SetIsBorderRequired` 的、可注入且 fail-closed 的只读截图驱动实现，使后续能够在不发送窗口输入的前提下读取已存在窗口的 PNG 客户区画面。

## 范围

- 审阅 `src/e7_enhance/visual_platform.py`、`src/e7_enhance/visual_adapter.py` 及对应公开测试，冻结现有 `WindowsReadOnlyDriver`/`LazyWindowsReadOnlyBackend` 兼容边界。
- 新增或调整一个具体的 Windows 只读捕获后端/适配 seam，避免依赖 Computer Use 当前失败的 `SetIsBorderRequired` 接口；优先使用现有系统能力和依赖注入，不隐式安装第三方包。
- 保持返回值为 PNG 字节，并校验唯一窗口、客户区尺寸、视口、时间戳、来源和非空载荷；异常统一 fail-closed，禁止自动重试。
- 补充 fake/offline 公开测试，覆盖捕获成功、窗口缺失、客户区变化、非 PNG/空载荷、后端异常和惰性构造。

## 禁止修改与禁止操作

- 不连接、激活、移动、点击或控制 MuMu/Epic Seven；不调用 ADB，不发送键盘/鼠标输入，不启动真实截图或 OCR。
- 不强化、不选材、不改装备、不消耗资源，不读取或上传游戏底层数据，不调用 Fribbels 或其他外部接口。
- 不修改正式策略、DP、评分、资源模型、GUI、OCR 门槛、Holdout、自动化规则或多节点新鲜快照契约。
- 不安装依赖、不修改系统设置、不读取或处理私人归档；不修改或删除 `refs/heads/main - 副本`；不得使用 `git add -A`。

## 权威输入

- 本文件是本轮唯一任务来源。
- 上游边界：[纯视觉真实 Windows 只读预检任务说明.md](纯视觉真实 Windows 只读预检任务说明.md)、[纯视觉只读截图与局部识别接入任务说明.md](纯视觉只读截图与局部识别接入任务说明.md)。
- 失败证据：真实预检调用 `get_window_state({ include_screenshot: true })` 返回 `SetIsBorderRequired failed: 不支持此接口 (0x80004002)`。

## 执行步骤

1. 只读审阅当前后端协议、调用方和公开测试，先写失败测试冻结兼容边界。
2. 实现最小具体后端或兼容 seam；真实系统依赖缺失时必须显式失败，不得隐式安装、启动或切换设备。
3. 运行新增测试、视觉适配/运行时/点击器/采样/OCR 平台接线回归、Python 语法检查和 `git diff --check`。
4. 精确审阅 diff，确认没有修改禁止项；将完成项、验证结果、未完成项、风险和下一步同步回本文件与总计划。
5. 仅提交明确相关文件并推送当前分支；真实窗口预检需另行授权，不在本任务内执行。

## 产物

- 不依赖 `SetIsBorderRequired` 的 Windows 只读截图后端/适配 seam。
- 对应 fake/offline 公开测试和验证记录。
- 本文件与 `e7-gear-enhance-plan.md` 的状态记录。

## 验证要求

- 新增测试退出码为 `0`；既有视觉相关回归不退化。
- Python 语法检查和 `git diff --check` 通过。
- 明确区分 fake/offline 验证与真实窗口预检；不得声称真实截图、OCR、服务端确认或强化成功。

## 停止条件

- 任何步骤需要真实窗口输入、设备控制、网络上传、底层数据读取、强化、选材或资源操作时立即停止。
- 无法稳定校验窗口、视口、PNG 字节、来源或时间戳时 fail-closed，禁止自动重试。

## 当前状态

`task_established_awaiting_offline_driver_implementation`

- 执行模型记录：`gpt-5.6-terra + high`。
- 上游真实预检已因 `SetIsBorderRequired` 不支持而 fail-closed；本轮尚未修改代码，尚未连接真实窗口。
