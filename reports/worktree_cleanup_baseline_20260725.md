# 工作区完整清理与 Git 收口安全基线

生成时间：`2026-07-25T01:32:30.7081957+08:00`

## Git 基线

- 起始分支：`codex/batch-013-plus3-verification-20260724`
- 起始 HEAD：`0c41890d8f064c8fdd4af40c3f512cdde80e2708`
- 起始远程差：`ahead=0 / behind=0`
- 当前专用分支：`codex/worktree-cleanup-20260725`
- 远程：`origin=https://github.com/5kjpywnfh8-cmd/epic-7-auto-gear-reinforcer.git`
- Git 跟踪文件：`202`
- 起始已跟踪修改：`31` 个文件，约新增 `3013` 行、删除 `312` 行
- 起始暂存区：`0`
- 写入任务说明和总计划后，折叠状态为 `402` 项：已跟踪修改 `32`、未跟踪文件/目录入口 `370`
- 完整未跟踪文件枚举成功：`255840` 个文件

## 文件系统基线

- 工作区文件总数（排除 `.git`）：`256449`
- 工作区总大小（排除 `.git`）：`2379545803` 字节

| 顶层目录 | 文件数 | 字节数 |
| --- | ---: | ---: |
| `reports` | 255347 | 1972226214 |
| `manual_acceptance` | 539 | 358971633 |
| `runtime_cache` | 18 | 36065690 |
| `samples` | 26 | 4523344 |
| `tools` | 130 | 3258137 |
| `src` | 105 | 1852435 |
| `tests` | 177 | 1381191 |
| `建议结果` | 3 | 32378 |
| `e7_enhance` | 13 | 2923 |
| `__pycache__` | 2 | 404 |
| `.vscode` | 1 | 40 |

## 主要卡顿来源

- `reports/` 占全部文件的绝大多数；其中最大分片目录为：
  - `epic_threshold_matrix_phase_b_formal_r10_resume_20260718`：`47130` 文件，`610313624` 字节
  - `epic_threshold_matrix_phase_b_resume_20260717`：`56436` 文件，`311656136` 字节
  - `speed_priority_22_methodology_v3_resume_20260713`：`26800` 文件，`172290028` 字节
  - `speed_priority_22_official_v2_resume_20260713`：`13400` 文件，`129331134` 字节
  - `speed_priority_22_rare_removed_v2_resume_20260713`：`13400` 文件，`129238466` 字节
- `manual_acceptance/ocr_stage1` 为 `406` 文件、`222247190` 字节，包含游戏截图和 OCR 证据，默认按私人数据处理。
- `runtime_cache` 为 `18` 文件、`36065690` 字节，需确认生成关系后才能清理或精确忽略。

## 既有忽略规则审计

当前 `.gitignore`：

```gitignore
__pycache__/
*.pyc
reports/*.md
!reports/early-lightweight-conversion-20260711.md
```

- `__pycache__/` 与 `*.pyc` 属于可再生成缓存规则，保留候选。
- `reports/*.md` 过宽，可能掩盖权威报告，不符合本任务目标；必须在报告逐份分类后移除或替换为精确规则。
- 当前未因该规则删除或覆盖任何报告。

## 安全状态

- 已创建专用分支，但尚未清理、移动、删除或回退任何待分类文件。
- 已隔离的 415 个精确副本仍位于工作区外恢复目录；未触碰 3 个内容分叉副本和 `.git` 异常引用。
- 私人截图、玩家数据、PCAP、可信快照和操作证据尚未获得本轮外传授权，不得推送。
- 下一阶段先审阅 31 个既有已跟踪修改，再按目录分类 255840 个未跟踪文件。
