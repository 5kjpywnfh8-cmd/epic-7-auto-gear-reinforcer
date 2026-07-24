# Epic 非速度 +3 样本冻结隔离修正任务说明

## 目标

修正前瞻样本在 64 件时允许提前查看 Oracle、但在 128 件时才重新按哈希分组造成的冻结验证污染风险。

本任务只修正采集状态机、manifest 使用约束、文档和测试；不运行 Oracle、不读取现有或未来样本的效用、不修改正式策略、GUI 业务逻辑或采集范围。

## 已确认偏差

当前实现：

- 有效 pair 达到 64 件后返回 `ready_for_oracle_screen_only`；
- 达到 128 件时，才按 `SHA256(sample_id)` 排序并重新划分 64 件开发集、64 件冻结验证集。

如果在 64 件时运行 Oracle，先前已查看效用的样本在 128 件重新分组后可能落入 `frozen_validation`。此时冻结验证集不再独立，不能用于发布闸门。

## 权威修正口径

- 0--127 件：始终为 `collecting_blind`，不得运行 Oracle、候选预测或阈值研究。
- 64 件只作为采集进度里程碑，不产生研究权限。
- 达到至少 128 件后，必须先生成一次性 manifest。
- manifest 固定 64 件 `development` 和 64 件 `frozen_validation`。
- manifest 生成后，只允许 Oracle 和候选研究读取 `development` 组。
- `frozen_validation` 在候选规则、特征、阈值和预测哈希全部冻结前不得读取 Oracle、预测或人工标签。
- 未提供 manifest 的 Oracle/研究命令必须拒绝运行该前瞻数据集。

## 实现要求

1. 将进度状态改为：
   - `<128`：`collecting_blind`；
   - `>=128` 且 manifest 不存在：`ready_to_freeze_manifest`；
   - manifest 存在：明确报告开发集和冻结验证集数量。
2. 删除或停止使用 `ready_for_oracle_screen_only` 语义；保留 `remaining_to_64` 仅作进度显示。
3. manifest 继续写入数据 SHA、规则哈希、分组和纳入/排除记录，并保持 write-once。
4. 后续 Oracle 工具接入时必须显式接收 manifest，只加载 `development` 的 sample ID。
5. 如果冻结时数据集超过128件，明确记录未纳入本轮 manifest 的 pair 及原因，禁止静默遗漏。
6. 不查看当前采集数据的装备内容、效用或候选结果；当前为0件时只做结构测试。

## 失败回归测试

至少覆盖：

- 64件时状态仍为 `collecting_blind`；
- 64--127件不能生成 manifest，也不能获得 Oracle 权限；
- 128件时先冻结，再得到固定64/64分组；
- manifest 二次调用不改变任何分组；
- 开发集读取器不会返回冻结验证样本；
- 不提供 manifest 时，研究入口拒绝读取该前瞻数据集；
- 超过128件时，未纳入样本具有明确排除记录；
- 修正不改变采集配对、正式建议或 GUI 返回值。

## 验收

最终报告必须明确：

- 为什么旧 64 件 Oracle 初筛会污染未来验证集；
- 新状态机；
- manifest 前后允许和禁止的操作；
- 64/64数据隔离测试结果；
- 当前真实 pair 数量。

本轮不得运行 Oracle、候选研究、五 seed 联合资源池或创建新的48件前瞻批次。
