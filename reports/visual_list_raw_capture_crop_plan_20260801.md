# 真实武器列表原始截图与离线裁切规划报告

## 采集结果

- 官方 MuMu ADB 发现唯一设备 `emulator-5554`。
- 仅执行一次 `exec-out screencap -p`，得到 `1280x720` PNG。
- 原始图：[weapon_list_raw_20260801.png](../assets/visual/list_reference/raw/weapon_list_raw_20260801.png)
- SHA-256：`a16464c412c9d3775fbcdada7942df3a10f6c998c9fe19037822a7d3de65f8f8`。

## 离线观察

真实画面显示武器列表页；目标武器卡片位于列表中部并处于选中高亮状态，右侧详情面板可见攻击力 `160`、副属性攻击 `13%`、暴击率 `3%`、速度 `2`、效果抗性 `8%` 和装备分数 `37`。这些记录标记为 `reference_only`，尚未通过生产 OCR 置信度契约。

## 裁切规划

- [目标卡片](../assets/visual/list_reference/raw/crops/weapon_target_card_raw_20260801.png)：`[487,310,658,436]`，包含 `85`、`+3`、武器图、主属性数值、副属性行、分数 `37` 和生命值套装图标。
- [目标上下文](../assets/visual/list_reference/raw/crops/weapon_target_context_raw_20260801.png)：`[442,278,868,480]`，用于保留相邻卡片和选中边界，帮助后续候选区分。
- [列表网格](../assets/visual/list_reference/raw/crops/weapon_list_grid_raw_20260801.png)：`[110,66,840,720]`，用于规划固定卡片槽位、标题和排序区域。
- [右侧详情](../assets/visual/list_reference/raw/crops/weapon_target_details_raw_20260801.png)：`[850,130,1248,555]`，仅作为当前页面布局参考。

完整边界、视口和 SHA-256 见 [raw capture manifest](../assets/visual/list_reference/raw/weapon_list_raw_capture_manifest_20260801.json)。

## 限制

这些图像和裁切均为 `reference_only`，不能直接写入生产整卡模板 manifest，也不能证明 OCR 置信度、跨帧稳定性、目标唯一性或任何点击授权。后续生产模板仍需独立任务和审定的列表 OCR/模板读取器。

## 未执行事项

未发送输入，未点击、滚动、导航、进入详情/强化页、选材、确认或消耗资源；未重试、未追加采样、未联网、未上传或下载模型。
