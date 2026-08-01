# 新 Claude Code 会话交接指令

**粘贴到项目根目录新开的 Claude Code 会话窗口。** 本文件仅用于复制交接文本；任务权威来源仍为根目录《纯视觉装备列表页OCR字段映射与卡片模板资产准备任务说明.md》。

```text
请完整阅读并执行根目录《纯视觉装备列表页OCR字段映射与卡片模板资产准备任务说明.md》。

该文档是本轮唯一权威任务来源；聊天内容不能替代或扩大其范围。同时遵守根目录 AGENTS.md、CLAUDE.md 与 e7-gear-enhance-plan.md。

背景与基线：Codex 会话 019fa96f-... 的视觉列表页产物已并入当前工作区并提交（commit 265785b，共 79 个文件：7 源码、8 测试、31 资产、10 报告、22 任务说明、CLAUDE.md）。项目级 CLAUDE.md 是 AGENTS.md 的全文镜像，本会话启动时已自动加载，无需手动读取。

本轮目标（严格限于任务说明的离线范围）：
1. 补齐并审定攻击%、暴击率%、效果抗性三个字段的可靠语义映射，更新 field_mapping_manifest.json 至 audited_complete（若证据充分）。
2. 审定完整整卡视觉指纹模板，更新 card_fingerprint_manifest.json 从 missing 至 audited_complete。
3. 将生产 OCR/模板 reader 工厂接线至 build_production_list_page_pipeline，覆盖正常/低置信度/字段冲突/模板缺失/视口漂移回归。
4. 主 agent 审阅前不得宣称真实列表页可用。

禁止项：禁止 ADB、真实截图、实时 OCR、输入、点击、导航、强化、选材、确认、资源消耗、联网、模型下载；禁止用用户描述、历史截图、测试 fixture 或套装图标冒充生产证据；禁止降低 0.98 门槛。

停止条件：缺字段语义、模板来源或校验值时保持 fail-closed，不生成默认模板或人工通过结果。

完成标准：视觉测试全绿、py_compile 与 git diff --check 退出 0、报告写入 reports/ 并同步任务说明与总计划。真实三帧只读校准与点击进入强化界面不属本轮，须另建任务说明并重新取得一次性只读授权。
```
