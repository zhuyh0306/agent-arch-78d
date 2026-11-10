# 0003 · 模型接入：统一走 LiteLLM Gateway

- Status: accepted
- Date: 2026-11-10
- Deciders: 项目负责人

## Context

本机没有云厂商 key，但有 Ollama 与 `qwen2.5:0.5b`；后续可能换成 OpenAI、DeepSeek 或其它兼容服务。观测侧用 Langfuse v3 自托管（额外依赖 ClickHouse 与 MinIO）。

两种接入方式：

方案 A 应用直连各家 SDK：实现简单，不引入额外组件。
方案 B 统一走 LiteLLM Gateway（OpenAI 协议）。

方案 A 的问题：每个供应商各一套鉴权与重试逻辑，密钥散落在应用配置里；换模型等于改业务代码；无法在统一位置统计成本与限流。
方案 B 的代价：多一个必须常驻的组件，多一层容器与配置文件。

## Decision

采用方案 B。所有模型调用从应用发往 `:4000`，使用 OpenAI 协议。

- 密钥只存在于网关侧（`.env` → compose `env_file`），应用侧拿不到 provider key。
- 路由、重试、限流、成本统计都在网关完成。
- `success_callback` 与 `failure_callback` 都挂 Langfuse；应用侧不再对 `litellm.completion` 包 `@observe`，避免双层 Generation。
- 网关不承担业务判断：不拼 prompt、不做 RAG、不做检索。
- 本地默认路由：`fast` → `ollama/qwen2.5:0.5b`；换供应商只改 `litellm/config.yaml` 的 `litellm_params.model`，`model_name` 保持不变。

## Consequences

+ 换供应商只改一行 `config.yaml`，业务零改动
+ 密钥集中托管，应用与前端都接触不到 provider key
+ trace 上报由网关统一完成，埋点不重复
- 网关是单点：它挂了全链路不可用，本地没有第二实例
- 三个 `LANGFUSE_*` 变量配错不会报错，只会让 trace 静默丢失——排查时必须先看网关日志
- `qwen2.5:0.5b` 只够做链路验证，答案质量不能代表生产模型
- 流式与特殊参数的透传需要单独验证（Day 16）
- 网关配置变更需要单独评审，不能随手改

## Superseded by

—
