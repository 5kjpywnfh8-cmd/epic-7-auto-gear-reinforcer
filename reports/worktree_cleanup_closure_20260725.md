# 工作区完整清理与 Git 收口报告

## 结果

- 状态：`worktree_cleanup_complete_after_closure_push`
- 分支：`codex/worktree-cleanup-20260725`
- 归档位置：`%USERPROFILE%\Documents\第七史诗强化装备脚本_私人证据归档_20260725\`
- 可恢复移动：`339/339` 个文件，`223321159` 字节
- 源文件剩余：`0`
- 移动后未跟踪文件：`0`
- 删除、覆盖、内容改写、私人数据上传：均为 `0`

## 完整性验证

- 源集合 SHA-256：`1b33e73a3cfdb243bb1cf91bb58d0300ae727c9152a7698463f192fd94f9b76a`
- 目标集合 SHA-256：`1b33e73a3cfdb243bb1cf91bb58d0300ae727c9152a7698463f192fd94f9b76a`
- 目标逐文件大小与 SHA-256：`339/339` 通过
- JSON 恢复清单 SHA-256：`5bd788ace12ea3140358fcb48c096187c7e1cf41c6de9e9764cb12fbe4d17796`
- CSV 恢复清单 SHA-256：`c3030b08dd73e11659767d5338f1fd307075352d99311db2a480d6cb6cb86f9a`

## 恢复边界

- 归档内 `restore_manifest_20260725.json` 和 `restore_manifest_20260725.csv` 保存原相对路径、字节数和逐文件 SHA-256。
- 恢复时只能写回不存在的原相对路径，出现目标冲突必须停止；恢复后须重新核对字节数和 SHA-256。
- 本报告不包含私人文件明细，归档清单不进入 Git、不上传远程。

## 验证说明

- 本批操作仅移动未跟踪私人证据并更新文档，没有修改代码、正式策略、DP、评分、资源模型、GUI、Holdout、OCR 门槛或自动化规则。
- 统一全量测试此前已通过，退出码 `0`，输出 `ALL TEST FILES PASSED`；本批无代码变化，不重复运行全量测试。
