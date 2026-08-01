# 第六次真实列表页视觉字段三帧只读校准报告

## 任务与授权

- 权威任务说明：[纯视觉真实装备列表页视觉字段三帧只读校准第六次任务说明](../纯视觉真实装备列表页视觉字段三帧只读校准第六次任务说明.md)。
- 用户已明确确认执行本文件定义的一次性只读校准；授权不包含输入、点击、导航、强化、选材、确认或资源操作。
- 实际模型：`gpt-5.6-terra + high`；用户偏好的 `gpt-5.6-luna + max` 当前协作接口不可用。

## 执行记录

1. 使用官方 `C:\Program Files\Netease\MuMu Player 12\shell\adb.exe devices -l`，退出码 `0`，发现唯一设备 `emulator-5554`，状态为 `device`。
2. 对该设备执行恰好三次 `exec-out screencap -p`。三帧均在进程内存中完成 PNG 结构、非黑帧和 `1280x720` 视口校验，未落盘。
3. 三帧审计元数据如下；哈希仅作审计，不作为视觉字段判定：

| 帧 | PNG 字节数 | 视口 | SHA-256 |
|---|---:|---|---|
| 1 | 851560 | 1280x720 | `a01e240de4a87dca218e0996f9abce57e0c7b089ada4da9d8b99cdf2fbb7c027` |
| 2 | 851560 | 1280x720 | `a01e240de4a87dca218e0996f9abce57e0c7b089ada4da9d8b99cdf2fbb7c027` |
| 3 | 851560 | 1280x720 | `a01e240de4a87dca218e0996f9abce57e0c7b089ada4da9d8b99cdf2fbb7c027` |

4. 时间戳按采样顺序单调；三帧批次结构校验通过。
5. 尝试建立 `build_production_list_page_pipeline` 时，显式生产 OCR/模板读取器工厂缺失，返回 `ProductionListPageReaderUnavailable: production list OCR and template factories are required`。

## 结论

本次校准在生产识别器前置闸门 fail-closed。未产生视觉字段签名、候选唯一性或目标字段通过结论；用户提供的目标指纹和三帧 PNG 不能替代真实 OCR/模板输出。

## 未执行项

未执行局部 OCR/模板推理、截图落盘、重试、追加采样、第二批采样、输入、点击、导航、强化、选材、确认、资源消耗、底层数据读取、联网、上传或模型下载。

## 下一步

必须另建并完成真实生产 OCR/模板引擎实例接线任务，之后重新建立任务说明并重新取得一次性只读授权。即使后续校准通过，也不授权选择装备或进入详情/强化界面。
