# 纯视觉 OCR 运行环境修复与依赖复验任务说明

## 目标

定位 Python 3.9 环境中 `paddleocr` 导入权限错误和 `paddle` 循环初始化错误的根因，建立可重复的最小诊断信号，并在取得明确修复授权后验证最小环境修复。修复成功前不得进入真实 OCR、页面识别或点击。

## 唯一权威来源

本文件是本阶段唯一权威任务来源。纯视觉识别接口和 `0.98` 门槛继承《纯视觉 ADB 局部模板与 PaddleOCR 只读识别任务说明.md》；环境命令以项目既有 Python 3.9.2 和 `requirements-ocr.txt` 为准。

## 当前授权范围

本轮先做只读诊断：解释器、模块路径、版本、导入顺序、缓存目录权限和包元数据检查。用户随后明确批准进入下一步，追加允许把 Paddle 缓存重定向到已批准的本地可写工作区 ASCII 路径做一次全新进程导入复验；仍不安装/卸载/升级包，不修改用户目录 ACL，不删除缓存，不联网，不下载模型，不修改系统或游戏环境。

## 执行步骤

1. 完整阅读本文件、`AGENTS.md`、`e7-gear-enhance-plan.md` 以及前置 OCR/ADB 任务说明；检查 `CONTEXT.md`（如存在）和相关 ADR。
2. 建立并运行一个秒级最小复现命令，分别在干净 Python 进程中导入 `paddleocr` 和 `paddle`，记录完整异常类型、首个项目文件、模块 `__file__`、发行版元数据和缓存路径权限。
3. 生成 3-5 个可证伪、按优先级排序的根因假设，再用只读探针逐一验证；不以猜测替代证据。
4. 在用户已授权的范围内，将缓存指向 ASCII 工作区路径（中文仓库路径会被现有 `_configure_cache()` 拒绝），在全新进程复验 `import paddle` 和 `import paddleocr`；不得触碰用户目录缓存。将根因、复验结果和未完成项写回本文件与总计划。

## 禁止修改与操作

- 禁止真实 ADB、截图、OCR、页面导航、点击、强化、选材、重启和资源消耗。
- 禁止 Fribbels、PCAP、TCP、`player_data.json`、外部上传、私人归档读写。
- 禁止修改正式策略、DP、评分、资源模型、GUI、OCR 门槛、Holdout 和自动化规则。
- 禁止触碰 `refs/heads/main - 副本`；禁止用 `git add -A`。

## 验证要求

- 最小复现必须稳定重现用户看到的 `PermissionError` 与 `AttributeError`，并报告实际 Python 版本和退出码。
- 诊断探针无网络且可重复；唯一允许的持久化是已批准 ASCII 工作区路径下的 Paddle 导入缓存目录，不得把 import 失败写成模型或页面问题。
- 执行模型记录为 `gpt-5.6-terra + high`；如实际不可用必须如实记录替代模型。

## 停止条件

- 任何探针需要写入受保护缓存、安装包、联网或改变系统权限时停止并向用户请求单独修复授权。
- 根因证据不足、工作区缓存导入仍失败或需要写入工作区外路径时停止，不继续真实 OCR 或点击链路。

## 当前状态

`repair_verified_ascii_cache_imports_ready_for_readonly_ocr_20260726`

## 最小复现与证据

- Python `3.9.2` 的最小干净进程 `import paddle` 退出码 `1`， traceback 落在 `paddle/dataset/common.py:62` 的 `must_mkdirs(DATA_HOME)`，目标为 `C:\Users\orangine\.cache\paddle\dataset`，异常为 `PermissionError: [WinError 5] 拒绝访问`。
- `import paddleocr` 的链路为 `paddleocr/paddleocr.py:21 -> paddle.utils -> paddle.__init__ -> paddle.dataset.__init__ -> paddle.dataset.cifar -> paddle.dataset.common`，同样在创建缓存目录处失败；尚未进入 OCR 引擎或模型下载。
- `pip show` 只读结果：`paddlepaddle 2.6.2`、`paddleocr 2.10.0`、`Pillow 11.3.0`，与 `requirements-ocr.txt` 版本要求一致。
- `C:\Users\orangine\.cache` 本身 ACL 显示当前用户有 `FullControl`，但目标 `paddle` 目录不存在；结合当前执行环境对工作区外写入的沙箱限制，首要阻断是运行环境写入闸门，不是包缺失或版本冲突。
- 先前的 `AttributeError: partially initialized module 'paddle' has no attribute 'tensor'` 未在干净进程复现；它是第一次导入异常后同进程继续导入造成的部分初始化二次症状，不能作为独立根因。

## 假设验证结论

1. **运行环境禁止创建用户缓存目录：已确认/最高优先级。** 预测是干净导入在 `must_mkdirs(DATA_HOME)` 失败，实际 traceback 完全吻合。
2. **普通 ACL 拒绝：已降低。** 只读 ACL 显示用户对父目录有完整控制，目标目录不存在；仍不能在本任务中通过写入测试改变环境。
3. **Paddle/PaddleOCR 版本不匹配或安装损坏：已降低。** 包版本与项目要求一致，失败发生在缓存目录创建之前。
4. **部分初始化是首要根因：已排除。** 干净 `import paddle` 仍稳定得到 `PermissionError`；部分初始化只解释后续同进程的 `AttributeError`。
5. **模型下载/网络导致失败：已排除当前导入路径。** traceback 在 OCR 引擎构造和模型下载之前终止。

## 未完成项与所需授权

- 修复前的“缓存写入权限”阻断已由下方授权复验闭环；真实 ADB/OCR 尚未执行，当前未完成项转为页面、模板和字段证据复验。
- 真实局部 OCR 需要另建或启用独立只读复验任务；不扩展为点击、强化或资源操作。

## 修复复验结果

- 按用户授权使用已批准的 ASCII 工作区缓存根目录 `C:\Users\orangine\.codex\visualizations\2026\07\26\019f9d27-a93e-71b3-aa44-075947551a35\paddle_import_probe`，未触碰 `C:\Users\orangine\.cache`。
- 全新 Python `3.9.2` 进程先调用现有 `_configure_cache()`，随后 `import paddle` 成功报告 `2.6.2`，`import paddleocr` 成功报告 `2.10.0`，退出码 `0`。
- 未构造 OCR 引擎、未下载模型、未执行 ADB、截图、真实 OCR、页面导航或任何游戏操作。
- 根因闭环：默认缓存目录的工作区外写入被拦截；中文仓库路径又被 `_configure_cache()` 的 ASCII 保护拒绝；使用可写 ASCII 缓存后包导入正常。

## 下一步

建立或执行“真实 ADB 局部识别只读复验”任务：只取一次内存截图，运行局部模板/PaddleOCR，继续保持 `mode=visual_only`、`verification=unverified`，不点击、不强化。
