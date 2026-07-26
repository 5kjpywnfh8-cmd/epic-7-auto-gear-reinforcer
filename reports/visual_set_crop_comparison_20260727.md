# 纯视觉套装多裁切离线比较报告

状态：`offline_set_crop_comparison_text_wide_pass_icon_low_fail_closed_20260727`。

执行模型：`gpt-5.6-terra + high`。

本报告覆盖固定候选、纯内存比较器、公开合成测试和一次离线用户截图校准。截图只在内存读取；没有执行 ADB、点击或强化，也没有联网或上传。

## 候选区域

下表的像素边界以 `1280x720` 为基准；归一化边界是代码的唯一配置来源。

| 候选 | 通道 | 归一化边界 `(left, top, right, bottom)` | 像素边界 | 预处理标识 |
| --- | --- | --- | --- | --- |
| `set_icon_wide_red` | 图标 | `(0.6796875, 0.7444444444, 0.7265625, 0.8333333333)` | `(870,536)-(930,600)` | `rgba_nearest_neighbor` |
| `set_icon_tight_red` | 图标 | `(0.68359375, 0.75, 0.72265625, 0.8277777778)` | `(875,540)-(925,596)` | `rgba_nearest_neighbor` |
| `set_text_wide_red` | 文字 | `(0.715625, 0.75, 0.875, 0.8333333333)` | `(916,540)-(1120,600)` | `paddle_lanczos_contrast_1_15` |
| `set_text_compact_red` | 文字 | `(0.715625, 0.7555555556, 0.8078125, 0.8222222222)` | `(916,544)-(1034,592)` | `paddle_lanczos_contrast_1_15` |

图标紧裁切与宽裁切均以红装标注 `(875,540)-(925,596)` 为中心。所有候选独立于默认 parser manifest，避免静默改变已有实时区域提取和模板识别契约。

## 比较口径

- 同一 `VisualFrame` 内先提取全部固定候选，再分别调用注入的图标和文字识别器；没有动态扩张、猜测或重试。
- 每个结果记录候选名、归一化/像素边界、预处理、置信度、唯一性、值与拒绝原因。
- 图标和文字均须各自恰有一个 `>=0.98` 的候选，且值一致，才生成接受的套装字段；低置信度、跨候选重复、候选内多匹配、越界、裁切失败和字段矛盾均拒绝。
- 固定输出 `mode=visual_only`、`verification=unverified`、`click_performed=false`。未接入默认 parser 或 PaddleOCR 入口；matcher 仅使用受控首个 `IEND`/调色板解码。

## 验证

- `C:\Users\orangine\AppData\Local\Programs\Python\Python39\python.exe -B -m unittest discover -s tests -p test_set_crop_comparison.py`：4/4 通过，退出码 0。
- `C:\Users\orangine\AppData\Local\Programs\Python\Python39\python.exe -B -m unittest discover -s tests -p test_ocr_paddle.py`：15/15 通过，退出码 0。
- Python 3.9 AST 语法检查（`ocr_regions.py`、`set_crop_comparison.py`、`test_set_crop_comparison.py`）：退出码 0。
- `git diff --check`：退出码 0（仅有既有工作区的 CRLF 警告）。

## 风险与下一步

离线用户截图已验证文字宽/紧候选和模板图标候选；图标仍低于 `0.98`，因此完整套装证据必须继续 fail-closed。任一真实输入不满足完整性、唯一性或 `0.98` 时都必须拒绝；真实只读校准必须另建任务说明并重新取得授权。
## Additional offline screenshot calibration (2026-07-27)

The two user-provided PNGs were read in memory only. No screenshot copy was
written to the repository or uploaded. Local PaddleOCR used the already cached
PP-OCRv4 Chinese models; no model download or network access was attempted.

Text candidates:

- `before_page(1).png`: `set_text_wide_red` produced `速度套装（0/4） @ 0.977467` and an additional annotation line `套装文 @ 0.994424`; `set_text_compact_red` produced `0.974750`. The annotated image is rejected because the annotation creates conflicting/ambiguous local evidence.
- `before_page.png`: `set_text_wide_red` produced `速度套装（0/4） @ 0.981642` and passed the unchanged threshold; `set_text_compact_red` produced `0.961027` and failed.

Icon candidates were compared with the local Fribbels bundle after controlled
first-IEND and indexed-PNG decoding. The best speed-icon score was below the
threshold on both images (`0.853229` for the tight crop on `before_page(1).png`,
`0.792352` on `before_page.png`); no icon candidate was accepted. Therefore no
complete set field was produced, and the visual contract remains
`mode=visual_only`, `verification=unverified`, `click_performed=false`.

This is offline screenshot calibration evidence, not server confirmation and
not an ADB read. The next task must address icon visual matching or obtain a
new approved local icon template before any real read-only calibration.
