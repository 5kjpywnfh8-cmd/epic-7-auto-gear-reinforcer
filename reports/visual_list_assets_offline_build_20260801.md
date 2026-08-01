# 装备列表页字段映射与卡片模板资产离线接线报告

## 结论

离线接线完成，生产入口保持 fail-closed；真实三帧校准仍未解阻。

## 变更

- 新增 `src/e7_enhance/visual_list_assets.py`，严格校验字段映射和整卡指纹 manifest 的 schema、状态、来源、置信度、视口、路径和 SHA-256。
- 新增 `build_production_list_page_pipeline_from_assets`，在任何 frame capture 前加载两类资产；资产缺失或未达到 `audited_complete` 时抛出 `ProductionListPageReaderUnavailable`。
- 新增字段映射 manifest（明确缺少 `AttackPercent`、`CriticalHitChancePercent`、`EffectResistancePercent`）和整卡指纹 manifest（`missing`、`full_card` 尚无模板）。套装图标和历史 crop 未被当作整卡模板。

## 验证

- `python -B -m unittest discover -s tests -p 'test_visual*.py'`：`117/117` 通过。
- 补强后 `python -B -m unittest discover -s tests -p 'test_visual_list*.py'`：`39/39` 通过，覆盖 `audited_complete` manifest 缺少八个必需列表字段时的拒绝。
- Python 3.9 `py_compile`：退出码 `0`。
- `git diff --check`：退出码 `0`，仅有既存换行格式警告。
- 资产专测覆盖：仓库 manifest 缺失时 fail-closed、完整 fixture 哈希匹配、未审定字段拒绝。

## 真实设备边界

本轮未运行 ADB、未截图、未实时 OCR、未发送输入、未点击、未导航、未强化、未选材、未确认、未消耗资源、未联网、未上传或下载模型。

## 剩余阻断

缺少可靠的攻击%、暴击率%、效果抗性列表语义和完整卡片视觉指纹模板，不能把用户描述、历史截图或参考 crop 写成生产证据。补齐并审定这些资产及真实 OCR reader 工厂后，才可另建任务重新授权三帧只读校准。
