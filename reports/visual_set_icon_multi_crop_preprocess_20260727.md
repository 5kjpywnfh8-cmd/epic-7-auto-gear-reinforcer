# 纯视觉套装图标多方案预处理离线报告

状态：`offline_visual_set_icon_raw_multi_crop_speed_identified_below_threshold_fail_closed_20260727`。

执行模型：`gpt-5.6-terra + high`。

## 范围与输入

本轮主结果只在进程内读取用户明确指定的 `manual_acceptance/single_item_confirmation/operation_013_plus3_20260724_112042/before_page.png`，使用既有本地 Fribbels 套装模板比较固定图标候选。PNG 可完整解码，声明视口与解码视口一致，均为 `1280x720`，文件为 `782524` 字节，帧 SHA-256 为 `99cf7852d24298102ba9b43583c60a7fbc683104d535cebfd499eaa91052a12a`。没有复制、改写或保存任何截图、裁切或像素内容；没有执行 OCR、ADB、页面导航、点击、强化、底层读取、联网或上传。

两张 `Downloads` 参考图带有人工标注，只保留为历史对照；其分数不参与本轮原图的通过或拒绝结论。

## 未标注原图固定方案结果

正式 matcher 仍使用既有固定最近邻尺度 `0.5`、`1.0`、`2.0`。三种裁切均未达到 `0.98`，并且最佳模板不是已知正确的 `speed`：

| 候选 | 像素边界 | 最佳本地模板 | 尺度 | 分数 | 唯一 | 通过 | 拒绝原因 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `set_icon_wide_red` | `(870,536)-(930,600)` | `destruction` | `1.0` | `0.805320` | 是 | 否 | `low_confidence` |
| `set_icon_tight_red` | `(875,540)-(925,596)` | `fervor` | `1.0` | `0.797220` | 是 | 否 | `low_confidence` |
| `set_icon_inner_red` | `(880,545)-(920,591)` | `destruction` | `0.5` | `0.787236` | 是 | 否 | `low_confidence` |

为区分裁切问题与模板尺寸问题，另在单次进程内做有限固定尺度对照：`0.5`、`0.625`、`0.75`、`0.875`、`1.0`、`1.25`、`1.5`、`2.0`。该对照不修改生产常量，也不接入正式 matcher。`0.75` 在三种裁切上均唯一、正确选出 `speed @ 0.862984`，是本轮最高分；`0.875` 也选出 `speed`，最高 `0.844210`。所有结果仍低于 `0.98`，因此尺寸更接近可以修正候选身份，但不能形成自动化证据。

结论固定为无图标锚点、无正式套装字段，继续 `mode=visual_only`、`verification=unverified`、`click_performed=false` 与 fail-closed。

## 带标注下载图历史对照

所有边界由 `ocr_regions.py` 的归一化配置推导。比较器只接受本地模板的固定最近邻尺度 `0.5`、`1.0`、`2.0`；样本被解码为 RGBA 后按模板 alpha 掩码评分，不改变图标语义、未进行动态搜索、阈值映射或自动重试。

| 候选 | 归一化边界 | 像素边界 | 预处理 | 最佳本地模板 | 尺度 | 分数 | 唯一 | 通过 | 拒绝原因 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `set_icon_wide_red` | `(0.6796875, 0.7444444444, 0.7265625, 0.8333333333)` | `(870,536)-(930,600)` | `rgba_nearest_neighbor` | `pursuit` | `1.0` | `0.792352` | 是 | 否 | `low_confidence` |
| `set_icon_tight_red` | `(0.68359375, 0.75, 0.72265625, 0.8277777778)` | `(875,540)-(925,596)` | `rgba_nearest_neighbor` | `pursuit` | `1.0` | `0.792352` | 是 | 否 | `low_confidence` |
| `set_icon_inner_red` | `(0.6875, 0.7569444444, 0.71875, 0.8208333333)` | `(880,545)-(920,591)` | `rgba_nearest_neighbor` | `destruction` | `0.5` | `0.773825` | 是 | 否 | `low_confidence` |

该表仅保留此前带标注 `Downloads\before_page.png` 的历史结果。三种候选的最佳模板均唯一，但最高 `0.792352 < 0.98`；不得将该表与本轮未标注原图结果混用。套装文字、绿色人工标注及任何其它字段均未读取，也没有参与图标证据。

## 代码与公开验证

- `ocr_regions.py` 新增固定主体内缩候选 `set_icon_inner_red`；默认 parser manifest 未变。
- `visual_set_template_matcher.py` 仅将该显式候选名加入既有允许名单，继续复用固定尺度、`0.98` 与唯一性规则。
- `test_set_crop_comparison.py` 覆盖五个候选的可审计像素边界和主体内缩候选元数据。
- `test_visual_set_template_matcher.py` 覆盖主体内缩候选名能经过既有本地 matcher，且没有放宽阈值。
- `Python39 -B -m unittest discover -s tests -p test_set_crop_comparison.py`：`5/5` 通过，退出码 `0`。
- `Python39 -B -m unittest discover -s tests -p test_visual_set_template_matcher.py`：`14/14` 通过，退出码 `0`。
- `Python39 -B -m unittest discover -s tests -p test_visual_adb_recognition.py`：`8/8` 通过，退出码 `0`。

- Python 3.9 AST 语法检查（`ocr_regions.py`、`visual_set_template_matcher.py`、两份公开测试）：通过，退出码 `0`。
- `git diff --check`：通过，退出码 `0`；仅报告既有工作区文件的 CRLF 转换提示，无空白错误。

## 风险与下一步

未标注原图证明裁切与 `0.75` 尺度能把最佳身份修正为正确的 `speed`，但像素相似度仍只有 `0.862984`，说明现有 Fribbels 图标与游戏内渲染之间仍存在显著外观差异，单纯继续移动裁切边界不足以达到 `0.98`。不能把唯一但低分的匹配、文字通道或人工知识提升为图标证据。下一步应独立评估游戏内只读图标模板或可审计的前景/边缘特征匹配；任何模板资产变更、真实只读校准或点击接线都需要新的任务说明和明确授权。
