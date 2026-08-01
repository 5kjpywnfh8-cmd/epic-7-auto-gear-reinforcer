# opencode 图片识别转发插件任务说明

## 目标

为 opencode 增加自定义工具 `analyze_image`：当主模型（DeepSeek V4 Flash，纯文本）遇到图片时，调用该工具把图片转发给 opencode-go 套餐内的视觉模型（默认 `gpt-5.6-luna`），识别结果以文本返回，使纯文本模型获得"看图"能力（方案 A：MCP/自定义工具转发）。

## 范围

- 新增全局插件 `C:\Users\orangine\.config\opencode\plugins\vision-relay.ts`（全局生效，不限于本项目）。
- 若全局插件目录不存在则创建。
- 仅新增文件；不修改现有 opencode 配置、auth.json、模型选择、其他插件或本项目任何业务文件。

## 禁止修改项

- `auth.json`、`opencode.json` / `opencode.jsonc`（全局与项目级）、`package.json`、本项目源码、`e7-gear-enhance-plan.md` 之外的文档按文档同步规则处理。
- 不引入需要用户额外付费或额外 API key 的依赖；一切调用走既有 opencode-go 套餐授权。

## 输入与权威口径

- 网关：`https://opencode.ai/zen/go/v1`（OpenAI 兼容，来自 models.dev 的 opencode-go provider 定义），实际请求 `POST /chat/completions`。
- 认证：`~/.local/share/opencode/auth.json` 中 `opencode-go` 条目（type + key），或环境变量 `OPENCODE_API_KEY`。
- 视觉模型：默认 `gpt-5.6-luna`（attachment: true，input 含 image/pdf，来自 models.dev opencode-go 模型表）。备用视觉模型：`qwen3.7-plus`、`kimi-k3`、`grok-4.5`、`mimo-v2.5`。
- 插件框架：`@opencode-ai/plugin`（全局 `package.json` 已声明 1.17.13），官方插件文档 https://opencode.ai/docs/plugins/（custom tools 章节）。

## 执行步骤

1. 创建任务说明并同步总计划（本文档与 `e7-gear-enhance-plan.md`）。
2. 用 python 冒烟测试网关：读 auth.json key，POST `gpt-5.6-luna`，附一张本地小图 base64，确认返回文本（验证 endpoint 路径、认证、模型 ID、image_url 格式）。
3. 编写 `vision-relay.ts` 插件：
   - 工具名 `analyze_image`；参数 `image_path`（必填，支持绝对/相对路径）、`question`（可选）。
   - 校验文件存在、大小上限 8MB；推断 mime；转 base64 data URL。
   - fetch 网关 `chat/completions`，model 默认 `gpt-5.6-luna`，返回 `choices[0].message.content`；失败给出可读错误（含状态码与截断响应体）。
4. 类型检查：在全局配置目录执行 `bunx tsc --noEmit`（或等价检查），确保插件语法与类型正确。
5. 汇报与文档同步。

## 产物

- `C:\Users\orangine\.config\opencode\plugins\vision-relay.ts`（TypeScript 插件源码）。
- 本任务说明 + 总计划同步记录（含测试结果与使用说明）。

## 验证要求

- 网关冒烟测试必须真实调用成功（HTTP 200 且 content 非空），记录请求模型、状态码、返回片段。
- 插件文件通过类型检查；opencode 重启后插件应自动加载（用户重启后可用 `analyze_image` 工具）。
- 无法在会话内重启 opencode 验证插件加载的，需明确标注为待用户重启确认。

## 停止条件

- 冒烟测试失败且无法在合理次数内修复时停止，标记未完成并说明阻断原因（网关地址/模型 ID/认证任一不成立）。
- 用户叫停。

## 当前状态

- 已完成（2026-08-01）。全部执行步骤完成：
  - 网关冒烟测试通过：`https://opencode.ai/zen/go/v1/chat/completions` + opencode-go key + 浏览器 UA 可用；视觉模型 kimi-k3 / mimo-v2.5 / qwen3.7-plus 真实识别成功；gpt-5.6-luna 与 grok-4.5 不可用（详见总计划记录）。
  - 插件 `vision-relay.ts` 已写入全局插件目录，工具 `analyze_image`（默认模型 kimi-k3，max_tokens 8000）。
  - `tsc --noEmit` 通过（exit 0）；node 直调核心函数 `analyzeImage` 真实识别成功。
  - 待办：用户重启 opencode 后确认插件加载与工具可用（会话内无法自验，已记录风险）。
- 执行者：opencode 主 agent（deepseek-v4-flash）直接实现，未派子 agent；用户偏好模型 gpt-5.6-luna 当前不可用（该模型在 opencode-go 网关裸 API 下不可调用），未使用。
