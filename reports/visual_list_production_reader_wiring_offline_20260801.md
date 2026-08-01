# 装备列表页生产 OCR/模板读取器接线离线验证（2026-08-01）

## 范围

本报告仅覆盖固定 `1280x720` 列表页的离线装配入口。入口显式接收 OCR 与模板读取器工厂，连接固定区域注册、内存 PNG 观察源和 `RegisteredListPageLocalRecognizer`；不连接 ADB、不截图、不调用真实 OCR、不产生输入或点击。

## 实现

- `src/e7_enhance/visual_list_production.py` 提供 `build_production_list_page_pipeline`，缺少工厂、工厂构造异常或读取器接口不完整时立即抛出 `ProductionListPageReaderUnavailable`。
- `ListPageSampleFrameCollector` 支持由 pipeline 注入帧源，仍固定收集三帧并交由列表观测器逐帧识别。
- 读取器输出继续经过固定区域、字段白名单、唯一性和 `>=0.98` 门槛；入口不创建测试假实现。

## 离线验证

- 合成三帧 PNG 哈希不同但字段一致：通过完整 pipeline 与列表观测器。
- 缺失 OCR/模板工厂、工厂异常、非法读取器：在产生证据前 fail-closed。
- 低置信度候选列表区域：在产生证据前 fail-closed。
- 定向命令：`python -m unittest tests.test_visual_list_png_source`，7/7 通过。

## 边界

结果仅证明离线装配和契约闸门，不证明真实 MuMu 页面、OCR 模型或模板资产可用。

## Verification addendum

- Serial command: `python -m unittest discover -s tests -p 'test_visual*.py'` -> `114/114` passed, exit code `0`.
- Python 3.9 `py_compile` for `src/e7_enhance/visual*.py` and `tests/test_visual*.py` -> exit code `0`.
- `git diff --check` -> exit code `0`.
