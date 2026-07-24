# 工作区未跟踪内容分类清单（2026-07-25）

## 结论

- IDE 显示的一万多个项目不是一万多个代码改动。文档提交 `3b44695` 推送后，本地与远程同步，已跟踪修改和暂存项均为 `0`。
- 精确枚举得到 `2166` 个未跟踪且未忽略文件：`reports` 1876、`manual_acceptance` 276、`samples` 9、根目录 5。
- 其中 `1651` 个是 5 个可再生成的 smoke 分片目录，现以精确路径加入 `.gitignore`；没有删除、移动或上传这些文件。
- 本次规则生效且清单提交后有 `515` 个待决文件保持可见；完成下述 2 个安全合成样本收口后，当前待决数更新为 `513`。不能用宽泛忽略或批量上传收口。

## 精确生成目录

| 路径 | 文件数 | 字节数 | 处置 |
| --- | ---: | ---: | --- |
| `reports/epic_concentration_rescue_v2_hash_smoke_20260720/` | 1 | 3297 | 精确忽略 |
| `reports/riftslash_joint_batch_smoke_20260712/` | 379 | 362747 | 精确忽略 |
| `reports/riftslash_saint_pool_22speed_smoke_20260713/` | 758 | 2922223 | 精确忽略 |
| `reports/riftslash_saint_pool_smoke_20260713/` | 379 | 1082715 | 精确忽略 |
| `reports/speed_priority_22_methodology_v3_smoke_20260713/` | 134 | 823335 | 精确忽略 |
| 合计 | 1651 | 5194317 | 文件原位保留 |

## 保持可见的待决内容

| 分类 | 文件数 | 当前判断 |
| --- | ---: | --- |
| `reports/` 顶层研究或生成报告 | 189 | 需区分权威摘要与可再生成原始输出 |
| `reports/` 顶层 OCR、人工验收或真实操作报告 | 36 | 私人或真实数据，不得在未取得新外传授权时推送 |
| `manual_acceptance/` | 276 | 私人截图、PCAP、日志、记录和操作证据，保持原位 |
| `samples/` | 7 | 均命中真实、实例或 Fribbels 标记，继续 fail closed |
| 根目录内容分叉副本 | 3 | 保持原位，不覆盖权威原件 |
| 根目录历史任务文档 | 2 | 含具体本地连接标识，不推送、不静默改写 |
| 合计 | 513 | 等待分组审阅或精确用户决定 |

`manual_acceptance/` 的当前未跟踪内部只读统计为：根目录 28 个文件，`mumu/` 28 个，`ocr_stage1/` 203 个，`single_item_confirmation/` 17 个；总大小 197821247 字节。分类统计不构成外传授权。

顶层报告的细分类见 [报告分类清单](worktree_cleanup_reports_classification_20260725.md) 与 [JSON](worktree_cleanup_reports_classification_20260725.json)。

A 类 76 个权威报告已分两组提交推送；B 类 98 个可再生成顶层输出已按精确文件路径加入 `.gitignore` 且原文件保留。当前待决未跟踪数为 `339`。

最终私人闸门扫描：剩余 `339` 个文件、`223321159` 字节，最大单文件 `26483765` 字节；51 个待决报告中有 5 个本地 IPv4 端点模式文件、4 个绝对路径模式文件、1 个 PCAP/原始载荷模式文件和 37 个账号/实例字段模式文件。具体值不输出、不上传。

## 安全合成样本收口

- `samples/epic_b_balanced_prospective_20260713.json`：空的盲采集控制 manifest，状态 `collecting_blind`，SHA-256 `6F4221EFB3B1D41AD3F41A7B80DB869ECCA4EED73E52D2D109E76D068FB8D3C7`。
- `samples/epic_conditional_set_coverage_20260712.json`：固定 seed `20260712` 生成的 1092 条合成覆盖样本，SHA-256 `D4F49802CB7342E55D96D25528B1FBF78663508E5A70E8746B6F76D4DB049952`。
- 两个文件均通过 JSON 解析；账号、玩家、实例、Fribbels、MuMu、OCR、PCAP、具体端点和外部解码服务标记命中均为 `0`，可独立纳入版本控制。

## 安全边界

- 未运行 `git clean`、`git reset`、`git restore`、`git checkout` 或批量 `git add`。
- 未删除或覆盖用户文件，工作区外副本隔离目录继续作为恢复来源。
- `.git` 内异常引用保持不变。
- 私人证据、真实样本和顶层真实操作报告均未纳入本次提交。
