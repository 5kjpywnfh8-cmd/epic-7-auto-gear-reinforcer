# MuMu Fribbels 载荷上限与分批解码任务说明

## 目标

在不改变 MuMu 截图导航、抓包、装备强化、材料选择或正式策略的前提下，解决 Fribbels `413 Request Entity Too Large`：对同一批 PCAP 提取出的 TCP payload groups 做确定性大小受限分批，逐批调用既有 Fribbels 解码接口，并合并可验证的装备/英雄结果。

## 范围与授权

- 仅修改 `D:\VScode\Epic-7-tools.v1.2\readers\mumu_capture\fribbels_decode.py` 及其公开测试，以及本说明和 `e7-gear-enhance-plan.md`。
- 允许使用用户已授权的本账号 TCP 载荷调用既有 Fribbels 接口；本任务不新增任何外部服务或传输目标。
- 使用模型：`gpt-5.6-terra + high`。

## 禁止项

- 不读取、恢复、暂存或上传私人归档；不修改正式策略、DP、评分、资源模型、GUI、OCR、Holdout 或自动化规则。
- 不修改 MuMu 页面导航、ADB 坐标、抓包过滤器、游戏状态或资源；不强化、不选材、不改变装备、不导入档案。
- 不把旧 `current/player_data.json` 或历史 Fribbels JSON 当作本批新鲜结果。
- 不静默丢弃超大单组；若单个 TCP group 本身超过请求上限，必须 fail-closed 并报告。

## 权威输入

- 失败批次：`D:\VScode\Epic-7-tools.v1.2\data\players\mumu_live\imports\20260726_115345\mumu_capture.pcap`。
- 既有接口：`https://krivpfvxi0.execute-api.us-west-2.amazonaws.com/dev/getItems`。
- 当前提取契约：按 TCP ACK 分组、按 TCP sequence 排序、重复 payload 去重后形成 hex group 数组。

## 执行步骤

1. 离线统计失败 PCAP 的 group 数量、单组大小、整体 JSON 请求体大小和确定性分批数量；不发送网络请求。
2. 设计请求体预算，保留 JSON 包装开销，保证每批 `data` 数组不超过预算；单组超限立即停止。
3. 先增加公开测试：边界分批、确定性顺序、单组超限 fail-closed、批次结果合并去重、任一批失败即整体失败。
4. 实现分批解码和结果合并；保留每批诊断，不写入部分成功的 `player_data.json`。
5. 使用失败 PCAP 做离线提取/分批 smoke；只有代码审阅和离线测试通过后，才允许另行执行一次获准的真实分批 API 验证。

## 产物

- 分批解码实现及公开测试。
- 本说明和总计划同步记录。
- 真实分批成功时，才生成同批完整 `player_data.json`、`reader_result.json`、snapshot；任一批失败则只保留诊断和原始 PCAP。

## 验证要求

- Python 3.9 语法检查、分批公开测试、失败 PCAP 离线统计和 `git diff --check` 全部通过。
- 不得把离线分批数量或模拟结果写成真实解码成功。

## 停止条件

- 无法证明批次边界、单组超过预算、API 返回非 `SUCCESS`、批间结果无法唯一合并，或需要扩大到其他外部服务时立即停止。

## 当前状态

`batched_api_validation_failed_zero_items_20260726_115345`

已确认现有代码没有本地 Fribbels 解密算法，必须通过既有 API。失败 PCAP 离线审计显示：原始 TCP payload `18,283,414` 字节中，有 `1` 条超大 TLS 流 `16,820,767` 字节，按“超大且明确 TLS”规则排除并记录；剩余 `525` 个可解码 group 的 JSON 请求体约 `2,901,695` 字节，落在 `7,000,000` 字节预算内，预计 `1` 批。

已完成分批实现：固定预算、确定性顺序、单组超限 fail-closed、批次结果按实例 ID 去重合并、任一批失败不写部分结果；公开测试和 Python 3.9 语法检查通过。对批次 `20260726_115345` 的一次分批 API 请求未触发 `413`，但 Fribbels 解出 `0` 件装备；没有生成新的 `player_data.json`、`reader_result.json` 或 snapshot，`current` 仍为历史文件。当前停止，不重传 TLS 流、不盲目改变分片、不导入或操作游戏。
