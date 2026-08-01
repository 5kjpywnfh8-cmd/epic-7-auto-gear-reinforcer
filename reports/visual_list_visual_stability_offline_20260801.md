# 装备列表页视觉字段稳定性离线验证报告

日期：2026-08-01

实际模型：`gpt-5.6-terra + high`。用户偏好 `gpt-5.6-luna + max`，当前协作接口不可用 Luna。

## 变更

- 新增列表页专用 `ListPageSampleFrames`/`ListPageSampleFrameCollector`，固定采集三帧并校验来源、视口和时间单调，允许 PNG SHA-256 不同。
- `InMemoryPngListPageObserver` 对三帧分别执行注册局部识别，比较锚点、滚动/页面边界、候选身份、候选视觉指纹、候选槽位和字段值；每帧置信度仍必须达到 `0.98`。
- 只有三帧视觉字段一致后才写入 `visual_fields_stable=true`。导航页闸门仅对 `equipment_list` 且带该标记的不同哈希放行；详情页仍要求三帧哈希完全一致。

## 验证

- `python39 -m unittest discover -s tests -p 'test_visual*.py'`：`108/108` 通过，退出码 `0`。
- `python39 -m py_compile`（本次修改的列表观测器、列表解析器、导航和测试文件）：退出码 `0`。
- `git diff --check`：退出码 `0`；仅有既有计划文件的 LF/CRLF 转换警告。
- 覆盖不同 PNG 哈希但视觉字段一致通过、字段/候选/槽位/锚点漂移拒绝、无 `visual_fields_stable` 标记拒绝、带标记列表页通过、详情页仍拒绝哈希变化。

## 真实设备边界

本轮只完成离线实现和验证，未连接 ADB、未读取截图、未执行 OCR/模板生产推理、未发送任何输入、点击、导航、强化、选材、确认或资源操作。重新进行 MuMu 真实校准必须另建一次性只读任务说明并重新取得授权。
