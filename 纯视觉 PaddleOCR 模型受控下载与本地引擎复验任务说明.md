# 纯视觉 PaddleOCR 模型受控下载与本地引擎复验任务说明

## 目标

在用户明确授权下，将 PaddleOCR 中文识别所需模型下载到已批准的 ASCII 工作区缓存，并在全新 Python 3.9.2 进程中验证本地模型文件可见、Paddle/PaddleOCR 引擎可初始化且不会再次触发下载。完成后仍停留在只读视觉识别准备阶段。

## 唯一权威来源

本文件是本轮唯一权威任务来源。PaddleOCR 识别协议、局部区域和 `0.98` 字段门槛继承《纯视觉 ADB 局部模板与 PaddleOCR 只读识别任务说明.md》；ADB 帧源继承《纯视觉 ADB 截图与受控点击迁移任务说明.md》。

## 授权范围

用户已明确授权采用 PaddleOCR 引擎并允许受控联网下载模型。授权仅覆盖：

- 访问 PaddleOCR 官方模型下载地址；
- 将模型写入已批准的 ASCII 工作区缓存目录；
- 在本地构造一次 OCR 引擎并验证模型加载。

## 禁止修改与操作

- 禁止 ADB `devices`、`screencap`、`input tap`、`swipe`、`keyevent`，禁止截图、OCR 识别、页面导航、点击、强化、选材、重启和资源消耗；
- 禁止 Fribbels、PCAP、TCP、`player_data.json`、底层装备读取器、外部上传和私人归档读写；
- 禁止修改正式策略、DP、评分、资源模型、GUI、OCR 门槛、Holdout、自动化规则和既有 ADB/Windows 生产代码；
- 禁止写入用户默认缓存目录，禁止修改系统权限，禁止触碰 `refs/heads/main - 副本`，禁止使用 `git add -A`。

## 输入与执行步骤

1. 在全新 Python 3.9.2 进程中调用现有 `_configure_cache()`，确认 `PADDLE_HOME`、`PADDLEOCR_HOME` 和用户目录均位于批准的 ASCII 工作区缓存；
2. 访问 PaddleOCR 官方模型资源，下载中文检测、识别和方向分类（如实际版本不需要则记录省略）模型到上述缓存；不下载其他模型或游戏数据；
3. 校验下载响应、文件大小、扩展名/目录结构和必要模型文件，拒绝空文件、损坏文件或路径漂移；
4. 在新的离线 Python 进程中导入 `paddle`、`paddleocr`，构造一次 `PaddleOCR(lang="ch", use_angle_cls=False, show_log=False)`，确认初始化不触发网络访问；
5. 运行与本任务相关的离线测试、语法检查和 `git diff --check`，精确审阅差异；只暂存本任务说明、总计划和必要的运行时配置/测试文件。

## 产物

- 模型缓存根目录、模型文件清单、字节数和校验摘要（不包含截图或游戏数据）；
- Paddle/PaddleOCR 版本、引擎初始化结果和退出码；
- 本文件与 `e7-gear-enhance-plan.md` 的状态、验证结果、未完成项、风险和下一步。

## 验证要求

- 下载失败、网络超时、模型文件不完整、缓存路径非 ASCII、引擎初始化异常或检测到隐式联网时立即 fail-closed，不重试；
- 结果不得表述为页面识别成功、服务器确认或强化成功；后续真实 OCR 仍需单独任务和明确授权；
- 执行模型记录为 `gpt-5.6-terra + high`。

## 停止条件

任何步骤需要写入批准目录之外、修改系统权限、执行 ADB/游戏操作、读取或上传游戏数据，或模型下载源无法确认属于 PaddleOCR 官方资源时，立即停止并报告阻断。

## 当前状态

`model_downloaded_offline_engine_verified_20260726`

## 执行记录

- 执行模型：`gpt-5.6-terra + high`。
- `_configure_cache()` 将 `USERPROFILE`、`HOME`、`PADDLE_HOME` 和 `PADDLEOCR_HOME` 限定到批准的 ASCII 工作区缓存；未触碰默认 `C:\Users\orangine\.cache`。
- PaddleOCR 官方模型下载完成，使用的官方资源为：
  - `https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_det_infer.tar`
  - `https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_rec_infer.tar`
  - `https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar`
- 缓存共 9 个模型文件，合计 `18,032,845` 字节；检测、识别和方向分类目录均包含 `inference.pdmodel` 与 `inference.pdiparams`，并保留对应 `.info` 文件。
- 以相对路径、文件大小和 SHA-256 组成的缓存清单摘要为 `94ddad6c342e222483498b8ab6a88286393a3b3071746156477d0016979bdc31`。
- 全新 Python `3.9.2` 进程导入 `paddle 2.6.2`、`paddleocr 2.10.0` 并构造 `PaddleOCR(lang="ch", use_angle_cls=False, show_log=False)` 成功，退出码 `0`；离线探针只允许缓存命中目录通过，未执行网络下载。
- 初次离线探针曾把 `maybe_download` 无条件拦截，误报缓存命中为失败；修正为“完整本地模型目录通过、缺文件才拒绝”后复验通过，期间未发生第二次联网下载。
- 下载和初始化阶段未执行 ADB、截图、OCR 识别、页面导航、点击、强化、选材、资源消耗、底层数据读取或外部上传。

## 未完成项、风险与下一步

- 尚未在真实 ADB PNG 上调用 OCR；模型可用不等于页面、装备或字段识别成功。
- 模型缓存位于本机批准的工作区可视化目录，部署到其他机器时必须重新准备同版本模型缓存或走同等授权流程。
- 下一步建立/执行新的“真实 ADB 局部模板与 PaddleOCR 只读复验”任务：单次内存截图、局部识别、`0.98` 字段门槛和 `VisualEvidence` 绑定；仍不点击、不强化、不选材、不消耗资源。
