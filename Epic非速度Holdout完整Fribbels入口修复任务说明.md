# Epic 非速度 Holdout 完整 Fribbels 入口修复任务说明

## 状态

`completed_collection_paused_0_of_128`

## 根因

- `tools/collect_epic_balanced_holdout.py` 当前对任意输入 JSON 无条件附加 `source_kind=full_fribbels_export` 与 SHA-256，采集模块随后信任该标记，没有真正验证完整 Fribbels 结构。
- 真实 Fribbels 导出使用顶层 `export_time`，格式为 `YYYY-MM-DD HH:MM:SS`，没有 `exported_at`。当前 CLI 不转换该字段，首个真实导入会因缺少带时区时间而失败。
- 当前 collection 仍为 `0/128`，没有污染样本；修复前禁止导入。

## 目标

- CLI 在附加内部来源标记前，必须调用现有 `gui_support.is_fribbels_export()` 验证顶层导出元数据和 Fribbels item 结构；普通 native JSON、列表或伪造 `items` JSON 必须拒绝。
- 对已验证的完整导出，将顶层 `export_time` 按 Fribbels 本地导出时间解释为 Asia/Shanghai `+08:00`，规范化写入内部 `exported_at`；缺失、非法或不晚于候选冻结时间仍由采集器拒绝。
- SHA-256 必须继续对原始文件字节计算，不能对解析后或注入字段后的 JSON 计算。
- collection、freeze 与候选哈希保持不变；不读取 Oracle、动作、风险或效率。

## 测试与验证

- 先增加失败测试：任意普通 JSON 不得被 CLI 升格为完整 Fribbels；合法 `export_time` 必须转换为带 `+08:00` 的 `exported_at`；非法时间必须拒绝。
- 保留现有0/64/128隔离、双重去重和只写一次冻结测试。
- 运行 Holdout 定向测试、GUI support 的 Fribbels 识别测试、语法检查、`git diff --check` 和 `tools/run_all_tests.py`，报告真实退出码。

## 禁止修改

- 不生成或导入真实 holdout 样本；collection 保持 `0/128`。
- 不修改正式策略、DP、资源模型、评分、跳值、GUI业务逻辑、OCR、ADB、Airtest、自动化或历史样本。

## 完成记录（2026-07-18）

- CLI 现在先调用 `is_fribbels_export()`，普通 native JSON、列表和缺少 Fribbels 元数据的伪造 `items` 均拒绝；原始文件 SHA-256 仍按文件字节计算。
- 顶层 `export_time` 已规范化为带 `+08:00` 的内部 `exported_at`，无效时间拒绝；collection 保持 `collecting_blind 0/128`，未导入真实样本。
- 新增三项入口回归测试；后续真实导入前仍需按 Holdout 主任务执行完整导入验证。

## 验证结果（2026-07-18）

- Holdout 与 GUI support 入口定向测试共31项通过。
- 只读使用真实 Fribbels 文件预检成功：识别2467件，`export_time`规范化为`2026-06-10T18:20:00+08:00`，原始文件SHA-256保持一致；未写入collection。
- 语法检查、`git diff --check`、`tools/run_all_tests.py`真实退出码均为0，全量输出`ALL TEST FILES PASSED`。
