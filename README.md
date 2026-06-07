# fpga_devmind

`fpga_devmind` 是 FPGA 开发-理解一体 Agent 的理解层原型。它的目标不是做传统静态分析器、检查器或审计工具，而是帮助用户理解由 `ai_project_template` 创建并由 AI agent 推进的 FPGA 项目在各阶段到底实现了什么。

当前短期重点：

```text
read -> graph -> explain -> trace -> query -> freshness
```

长期方向是与 `ai_project_template` 融合，形成真正的 FPGA Develop-Understand-Verify Agent：开发、理解、语义记忆、可视化、验证辅助和后续审计逐步一体化。

## Current Status

当前仓库已有 P1a V0.1 候选：一个只读、确定性、无 LLM 的单阶段理解层原型。

它可以读取两个代表性样本项目的 `L6_resource_opt` 阶段，生成：

```text
project_graph.json
trace_index.json
memory_manifest.json
summary.md
flow.mmd
trace.md
run_metadata.json
```

这些 artifact 用于表达阶段做了什么、证据来自哪里、哪些关系只是推断、生成结果是否已经过期。

P1a V0.1 不是完整 Agent，也不声称已经完成 LLM/ReAct 推理、跨阶段记忆、L6-to-RTL 映射或验证覆盖解释。它先把 Agent 后续需要依赖的 evidence shell、ProjectGraph、TraceIndex、query 和 freshness 基线跑通。

## Quickstart

运行只读 smoke：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-smoke \
  --out-root /tmp/fpga_devmind/p1a_smoke
```

运行单个阶段理解：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --out /tmp/fpga_devmind/p1a_coarse_sync_l6
```

查询生成结果：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-query \
  --artifacts /tmp/fpga_devmind/p1a_coarse_sync_l6 \
  --question "L6 实现了什么流程"
```

查看不确定项：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-query \
  --artifacts /tmp/fpga_devmind/p1a_coarse_sync_l6 \
  --question "有哪些不确定"
```

检查生成结果是否过期：

```bash
PYTHONPATH=src python3 -m fpga_devmind.cli p1a-freshness \
  --artifacts /tmp/fpga_devmind/p1a_coarse_sync_l6
```

更完整的说明见 [P1a V0.1 quickstart](docs/p1a-v0.1-quickstart.md)。

## Direction Guardrails

- LLM/Agent 是长期语义理解主引擎；静态分析只做证据抽取、索引和约束辅助。
- 输出应围绕 `ProjectGraph`、`TraceIndex`、`VisualizationSpec`、可追溯证据和不确定项，而不是普通报告。
- 短期不做 PASS/HOLD、finding、规则引擎或自动审计。
- 图中的启发式关系必须标注为 inferred，不能伪装成已证明 dataflow。
- 默认输出写入 `/tmp` 或 `/private/tmp`。
- 不修改任何 `fpga_project_*` 目标项目。
- 不运行 Vivado、synthesis、implementation 或 bitstream。
- 不读取、记录、提交 API key。

## Documentation

- [Docs index](docs/README.md)
- [Direction guardrails](docs/direction-guardrails.md)
- [Agent-first architecture](docs/agent-first-architecture.md)
- [P1a V0.1 quickstart](docs/p1a-v0.1-quickstart.md)
- [P1a V0.1 acceptance](docs/p1a-v0.1-acceptance.md)
- [P1a+ Semantic Agent Layer](docs/p1a-plus-semantic-agent.md)
- [Implementation status](docs/implementation-status.md)
- [Review process](docs/review-process.md)
