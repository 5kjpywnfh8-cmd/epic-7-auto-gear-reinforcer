# Epic 非速度 Holdout 可信 PlayerData 快照适配与首次导入任务说明

## 状态

`completed_collection_6_of_128`

## 输入

`D:\VScode\E7-tools\Epic-7-tools.v1.2\data_store\players\player_018a617ef2f1\snapshots\20260718_165444\player_data.json`

- 顶层为 `metadata/player/equipment/items/...`；`metadata.source=fribbels_mumu_reader`。
- `metadata.imported_at=2026-07-18T16:54:44+08:00`，晚于候选冻结时间。
- `items` 与 `equipment` 均为2565件；item保留 `id/ingameId/gear/rank/set/level/enhance/main/substats/raw` 完整Fribbels字段。

## 目标与边界

- 增加只读容器适配：仅当 `metadata.source=fribbels_mumu_reader`、`item_count`与`items/equipment`数量一致、装备项完整含Fribbels结构、`imported_at`带时区时，才转换为现有完整Fribbels intake payload。
- 快照时间使用 `metadata.imported_at`，不得使用旧的 `metadata.export_time`；原始文件SHA-256仍按文件字节计算。
- 经验证的Fribbels装备项缺少`itemSource`时，适配层显式补`normal_85`，与本项目既有Fribbels导入口径一致；不得接受显式标为其他来源的装备。
- 不改变候选冻结文件、候选规则、128件目标或64/64隔离；这是容器格式适配，不读取动作、Oracle、风险或效率。
- 测试通过后导入上述唯一文件，报告 accepted、remaining 和排除原因汇总；不得展示或分析单件候选结果。

## 测试与验证

- 先增加失败测试：伪造reader元数据、数量不一致、缺少raw结构、无时区imported_at均拒绝；合法wrapper转换成功并补`normal_85`。
- 保留原始完整Fribbels导入、普通JSON拒绝、0/64/128隔离和去重测试。
- 导入前用临时collection预跑；确认真实collection仍为0/128后才执行一次正式导入。
- 运行定向测试、语法检查、`git diff --check`和`tools/run_all_tests.py`，记录真实退出码。

## 禁止修改

- 不修改正式策略、DP、资源模型、评分、跳值、GUI业务逻辑、OCR、ADB、Airtest或自动化。
- 不修改冻结候选或历史样本，不运行Oracle、联合资源池或holdout验证。

## 完成与验证（2026-07-18）

- 新增可信wrapper验证；合法player snapshot使用带时区的`metadata.imported_at`，严格校验source、item_count、items/equipment身份及完整raw结构，并为缺失来源的Fribbels项补`normal_85`。
- 定向9项通过；临时collection预跑预计接受6件后，才执行一次正式导入。
- 正式导入接受6件；排除`known_instance_id=277`、`not_plus0=692`、`outside_normal_85_epic_scope=1514`、`boots=21`、`speed_hard_route=55`。当前`collecting_blind 6/128`，剩余122件。
- 语法检查、`git diff --check`和`tools/run_all_tests.py`真实退出码均为0，全量输出`ALL TEST FILES PASSED`。未生成manifest，未读取Oracle、动作、风险或效率。
