# 工作区副本只读盘点报告（2026-07-25）

- 状态：`partial_direct_inventory_complete_full_workspace_untracked_scan_deferred`
- 范围：根目录和 `e7_enhance`、`manual_acceptance`、`reports` 的一级直接文件；未递归进入更深层目录。
- 盘点候选：418 个；精确一致 415 个；大小分叉 3 个；哈希分叉 0 个；缺少原件 0 个。
- Git 基线：分支 `codex/batch-013-plus3-verification-20260724`，HEAD 与远程均为 `5f755af`；已跟踪改动 31 个；暂存 0 个。
- 已发现候选的 Git 状态：tracked=0，ignored=126，untracked_or_unignored=292。
- 全工作区未跟踪扫描：未执行。原因是避免递归扫描大量文件造成卡顿；因此本报告不宣称全工作区盘点完成。

## 一级目录统计

| 范围 | 直接文件数 | 直接副本数 | 直接字节数 | 联接/重解析点 |
|---|---:|---:|---:|---:|
| root | 165 | 82 | 1750544 | 0 |
| .agents | 0 | 0 | 0 | 0 |
| .codex | 0 | 0 | 0 | 0 |
| .git | 15 | 7 | 43664 | 0 |
| .vscode | 1 | 0 | 40 | 0 |
| e7_enhance | 6 | 3 | 562 | 0 |
| manual_acceptance | 62 | 31 | 87149092 | 0 |
| reports | 610 | 302 | 248185924 | 0 |
| runtime_cache | 0 | 0 | 0 | 0 |
| samples | 12 | 0 | 4517542 | 0 |
| src | 0 | 0 | 0 | 0 |
| tests | 59 | 0 | 402596 | 0 |
| tools | 47 | 0 | 1021654 | 0 |
| __pycache__ | 2 | 0 | 404 | 0 |
| 建议结果 | 3 | 0 | 32378 | 0 |

## 分类统计

| 目录 | 完全一致 | 大小分叉 | 哈希分叉 | 缺少原件 |
|---|---:|---:|---:|---:|
| e7_enhance | 3 | 0 | 0 | 0 |
| manual_acceptance | 31 | 0 | 0 | 0 |
| reports | 302 | 0 | 0 | 0 |
| 第七史诗强化装备脚本 | 79 | 3 | 0 | 0 |

## 内容分叉清单

| 候选副本 | 对应原件 | 副本字节 | 原件字节 | 副本 SHA-256 | 原件 SHA-256 | Git 状态 | 建议 |
|---|---|---:|---:|---|---|---|---|
| e7-gear-enhance-plan - 副本.md | e7-gear-enhance-plan.md | 295322 | 304306 | 4B23EEDFABECD3D01080B4BE1DC7D9FB6BF9F03138274C977F1D8410B07410EA | 56145232E2A08FC46828BA3FA1D07AE7006FE48F122A357B4A126FEA89CA8370 | untracked_or_unignored | manual_review |
| 单件人工确认强化结果离线汇总器任务说明 - 副本.md | 单件人工确认强化结果离线汇总器任务说明.md | 4392 | 5904 | 0DEE5DE2ED22B41EE3525F72DACA85B56C3D3D77ACF64581E9BF48F51719009E | 2CA33D44217CFFE73494D964F9C0CD40B28F65C2CF4A5678FBB67019D7929142 | untracked_or_unignored | manual_review |
| 单件人工确认强化结果验证任务说明 - 副本.md | 单件人工确认强化结果验证任务说明.md | 14644 | 26347 | 86479F4BC1774A132367252D1D037F1EB24B148D9925C27B251D057655513160 | 5120CA705E429C039BD26C382C65C0A50402D69453D6809B06A1E2E1A5AFBC18 | untracked_or_unignored | manual_review |

## Git 内部条目

检测到 `.git` 目录内名称含“副本”的内部条目 7 个；这些条目不是工作区候选，按任务边界未读取、未修复、未删除。

## 结论与停止点

- 415 个完全一致副本只能标记为“可恢复隔离候选”，不能据此删除或移动。
- 3 个根目录文档副本与当前原件大小不同，全部保留并转人工审阅；不能用旧副本覆盖当前文档。
- 盘点期间未删除、移动、重命名、覆盖文件，未修改 Git 配置、引用、索引，也未结束任何进程。
- 逐项候选路径、原件路径、大小、SHA-256、分类、Git 状态和建议动作见同目录 JSON 报告。
- 下一步必须由用户逐项确认隔离目标、目标目录和恢复方式；在此之前保持 `destructive_cleanup_not_authorized`。
