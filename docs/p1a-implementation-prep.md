# P1a Implementation Prep

本文把 P1a 从设计文档收敛为实现前清单。它不是实现代码。

## Target

```text
project:
  /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm

stage:
  src/python_model/L6_resource_opt

output:
  /tmp/fpga_devmind/p1a_coarse_sync_l6
```

## Minimal Implementation Shape

第一版可以采用 CLI 触发，但内部必须按 Agent runtime 组织：

```text
fpga_devmind p1a-understand-stage \
  --project /Users/ckstar/Repo/znxt_ofdm/fpga_project_coarse_sync_glm \
  --stage L6_resource_opt \
  --out /tmp/fpga_devmind/p1a_coarse_sync_l6
```

CLI 是外壳，不是产品本体。

## Required Artifacts

```text
project_graph.json
  主结构化产物，符合 phase1a-schema.md。

summary.md
  从 project_graph.json 渲染，主要段落引用 claim ids。

flow.mmd
  从 VisualizationSpec 渲染，节点和边绑定 claim/evidence。

run_metadata.json
  记录输入、工具版本、模型配置摘要、时间、source snapshot。
```

## First Code Slices

建议实现顺序：

```text
1. package / CLI skeleton
2. P1a schema classes
3. project tree scanner
4. Python L6 evidence extractor
5. config parameter extractor
6. claim builder placeholder
7. grounding checker for unsupported confirmed claims
8. JSON graph writer
9. summary / Mermaid renderer
10. P1a smoke run on coarse_sync_glm
```

## Initial Non-LLM First

建议第一版先实现 deterministic evidence pack 和 graph shell，再接 LLM：

```text
Step 1:
  扫描 L6/config，生成 EvidenceItem 和 ProjectProfile。

Step 2:
  用规则/占位 claim 生成最小 project_graph.json。

Step 3:
  验证 renderer 和 grounding checker。

Step 4:
  再把 LLM 接入 claim generation。
```

原因：先把证据、schema、落盘、检查闭环跑通，避免一开始所有问题都混在 prompt 里。

## Minimal Grounding Checks

第一批 checker 只做硬规则：

```text
- confirmed claim 必须有 evidence_ids。
- confirmed claim 不能只引用 comment/doc evidence。
- P1a confirmed claim 不能引用 RTL/test evidence。
- Visualization node/edge 必须有 source_claim_ids。
- summary 主要段落必须引用 claim ids。
```

这些规则足以防止 P1a 退化成无证据报告。

## Provider Handling

模型 provider 后接入，且必须：

```text
- API key 只从环境变量或本地未提交配置读取。
- 日志、graph、summary、metadata 不写 API key。
- provider error 不回显密钥。
```

## Review Gate Before Coding

进入实现前，检查：

```text
- direction-guardrails.md 是否仍满足。
- phase1a-schema.md 是否足够支撑 project_graph.json。
- tool-contracts.md 是否覆盖 P1a 所需工具。
- p1a 输出是否仍只写 /tmp。
```

若实现中需要扩大范围，先更新文档，再考虑是否需要 Review Agent。
