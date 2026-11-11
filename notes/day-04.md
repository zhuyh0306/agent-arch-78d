# Day 4｜LLM 原理与成本模型（90min）

日期：2026-11-10
用时：约 90 / 90
今日验收物：`eval/cost/cost-model.csv`（三档：单次 / 千次 / 月）+ 可重算脚本 `eval/cost/cost_model.py`

## 精读笔记（3 条，能复述才算）

1. **计费按 token 不按字；同一段中文的 token 成本约是英文的 2.8 倍**
   - 出处：OpenAI Tokenizer 页（https://platform.openai.com/tokenizer，本机 403，见「偏差」）改为本地 `tiktoken` 的 `o200k_base` 实测；DeepSeek 价目页写明「A token… can be a word, a number, or even a punctuation mark. We bill model usage based on the total number of input and output tokens」。
   - 实测：同一段系统提示，中文 204 字 → 136 token（1.50 字/token），英文 563 字符 → 132 token（4.27 字符/token），同义内容中文要付 2.8 倍 token。BPE 切的是子词，中文没有空格边界，切分粒度天然更碎。
   - 落点：`eval/cost`（测算口径）+ `packages/contracts`（未来把 `max_input_tokens` 写进契约）。提示词不能按「字数」估预算，必须按目标模型的 tokenizer 数。

2. **KV cache 预分配浪费 60–80%，PagedAttention 用「块表」把它压到接近零；上下文既花钱又占显存**
   - 出处：vLLM / PagedAttention，https://arxiv.org/abs/2309.06180（ar5iv 第 2 节）：现有系统按最大长度预分配，「only 20.4% - 38.2% of the KV cache memory is used to store actual token states」；摘要称实现「near-zero waste in KV cache memory」与「2-4× throughput with the same level of latency」。做法是把 KV cache 切成固定块，用 block table 做逻辑块 → 物理块的映射，像虚拟内存分页。
   - 落点：`infra`（自建推理时才会用到，当前不部署）。今天只记结论：自托管的并发上限经常卡在 KV cache 显存而不是权重；上下文变长同时抬高 API 账单和显存占用，所以「上下文预算」是一个跨层的旋钮。

3. **Attention 的代价对序列长度是平方级；缩放 √dk 是为了不让 softmax 进饱和区**
   - 出处：Attention Is All You Need，https://arxiv.org/abs/1706.03762（ar5iv 3.1）：`Attention(Q,K,V)=softmax(QKᵀ/√dk)V`，除以 √dk 是防止点积随维度变大后 softmax 梯度消失；Figure 2 画的是单头 Scaled Dot-Product Attention 与多头拼接。
   - 落点：`skills/retrieval` 与 `runtime`。自注意力每层复杂度 O(n²·d)，长上下文不是「免费的容量」：塞满 1M token 的一次调用，按 DeepSeek Flash 缓存未命中的 $0.15/M 算就是 $0.15/次，30,000 次/月即 $4,500——和本场景默认的几十美元差三个数量级。检索返回条数与历史裁剪必须有硬上限。

## 扫读：模块归属

| 资料 | 归属模块 | 一句话判断依据 |
|------|---------|---------------|
| BPE 与 token 计数 | eval/cost；未来 contracts | 测算放 eval；请求前的预算校验属于契约 |
| DeepSeek 价目与峰谷 | eval/cost/prices.csv | 价格是输入数据，不进生产配置 |
| KV cache 与 PagedAttention | infra（自建推理时） | 只有自己跑 vLLM 才需要调，云端 API 由厂商负责 |
| Attention 复杂度 | skills/retrieval + runtime | 决定 chunk 预算与历史裁剪上限 |
| 系统提示与工具 schema | packages/contracts（后期） | 属于接口定义，不是文案 |

## 产出

- `eval/cost/scenario.json`：一次真实形态的 DataAgent 问答（中文 system + 3 个工具 schema + 3 段检索片段 + 4 轮历史含两条 SQL 结果 + 最终输出），所有可变量都在数据文件里。
- `eval/cost/prices.csv`：DeepSeek 官方价，按模型 × 峰/谷 × 缓存命中/未命中拆列，带 `source` 与 `checked_at`；改价只改这张表。
- `eval/cost/cost_model.py`：用 `tiktoken` 数各段 token，按「前缀缓存只覆盖 system+工具」计算单次/千次/月三档，并输出输入成本占比与「输入开始压过输出」的 token 阈值。
- `eval/cost/cost-model.csv`：24 行（2 模型 × 2 费率 × 2 缓存 × 3 档），当前基线结果。
- `eval/cost/requirements.txt`：`tiktoken==0.14.0`，仓库不设根 pyproject，依赖按目录声明。

## 验证

| 检查 | 命令 | 结果 |
|------|------|------|
| token 拆分 | `python eval/cost/cost_model.py` | system 136 / tools 284 / history 581 / context 148 / question 20，输入 1,169，输出 221 |
| 中英文对比 | 同上 | zh 1.50 字/token，en 4.27 字符/token，同义内容中文 2.8× token |
| 三档表 | 同上 + `eval/cost/cost-model.csv` | Flash 谷时命中缓存：$0.0002/次、$0.25/千次、$7.39/月 |
| 最贵组合 | 同上 | V4-Pro 峰时未命中：$0.0024/次、$2.42/千次、$72.55/月，是最便宜组合的 9.8× |
| 可复现 | 连跑两次后 `diff` | 输出逐字节一致 |
| 缓存的真实收益 | 对比 hit / miss 两行 | 前缀只占输入 36%，账单降 20%，不是「省一半」 |
| 峰谷差 | 对比 peak / offpeak | 同一请求正好 2 倍 |
| 输入 vs 输出 | 脚本阈值行 | in > 884 token（Flash 谷时未命中）输入成本才压过输出 |
| 布局未漂移 | `bash infra/scripts/check_layout.sh` | `layout ok` |
| OpenAI 页面可达性 | `curl` tokenizer / pricing | 均 403，改用本地 tiktoken + DeepSeek 官方价目 |
| PagedAttention 实测 | — | **未实测**：本机无 GPU、未部署 vLLM，只做资料笔记 |

## 与课程文档的偏差（主动讲出来）

1. 课程让读 OpenAI Tokenizer 在线页，本机 403。改为本地 `tiktoken` 数自己的真实提示词——更贴近项目，但 `o200k_base` 不是 DeepSeek 的分词器，对 DeepSeek 的 token 数只是近似（偏差幅度未测）。
2. 课程的价格示例基于 OpenAI，本机 OpenAI 定价页同样 403。改用 DeepSeek 官方价目（也是网关可路由的云端模型），并按官方页的峰/谷、缓存命中/未命中拆开——课程的单值模型会同时高估和低估：同一模型最便宜与最贵组合相差约 3 倍（$0.0002 vs $0.0006/次）。
3. 「成本大头是上下文」需要门槛，不是口号：本轮 1,169 入 / 221 出，输入占 57%（未命中）/ 46%（命中），只算勉强过半。短问答（588 入）时输出占 60%——先测再优化，别把口诀当结论。
4. 缓存只对稳定前缀生效：system + 工具 schema 占输入 36%，因此账单只降 20%；检索片段和历史每轮都变，不会被命中。想靠缓存省钱，先设计「稳定前缀」。
5. 本机开发走 Ollama `qwen2.5:0.5b`，API 成本为 0；这张表只适用于切到云端路由之后。本地成本是电费和机器时间，未计入。
6. 月成本按 1,000 次/天 × 30 天 = 30,000 次假设，不是实测流量；真实基线要等网关接了 Langfuse 后按实际 token 量回填。
7. DeepSeek 1M 上下文是价目表事实，不代表该用完：1M 输入按 Flash 未命中价 = $0.15/次，$4,500/月，和默认场景差三个数量级。

## 三行收尾

- 卡点：OpenAI 的 tokenizer 与 pricing 页都是 403；本机两个 venv 都没有 `tiktoken`，仓库又不允许根 pyproject，得先想清楚依赖放哪。
- 绕过：用 `uv` 在仓库外建 `agent-arch-cost` venv 装 `tiktoken`，依赖清单放 `eval/cost/requirements.txt`；价格与场景都做成数据文件，脚本只做计算。
- 下次：给价目表加 `checked_at` 后要定期复核；等网关接上真实调用，用 Langfuse 的实际 token 数校准这里的估算，而不是继续用假设值。

## 已知限制

- token 数用 OpenAI `o200k_base` 近似 DeepSeek 分词，未做交叉校准；换模型/换分词器后三档数字要重跑。
- PagedAttention 只有资料笔记，没有实测；本机无 GPU，短期也不会部署 vLLM。
- 月档的 30,000 次是假设值，非流量实测。
- 缓存假设只覆盖 system + 工具 schema；若未来把检索片段也做成稳定前缀，成本会再降，需要重算。
- 峰谷按 UTC 划分（01:00–04:00、06:00–10:00 工作日为峰时），价格表未按实际流量分布加权。
- 复述自测（合上资料讲 3 条笔记）由本人完成，本文只保证笔记与出处齐全。

## 验收

- [x] 三档成本表存在且可复现（`eval/cost/cost-model.csv`，连跑两次一致）
- [x] 单次成本拆到 system / 工具 / 上下文 / 输出四段，且能指出各段 token 数
- [x] 能讲清为什么同一段中文比英文贵 2.8 倍，以及它对提示词预算的影响
- [x] 能讲清 KV cache 浪费与 PagedAttention 的块表，以及上下文为什么同时花钱和占显存
- [x] 能给出「输入成本压过输出」的阈值，并说明短问答里输出可能是大头
- [x] 缓存与峰谷两个折扣的真实幅度已量化（20% / 2×），不是拍脑袋
- [x] 三行 notes 已记录
- [ ] 口述自测（由本人完成）
