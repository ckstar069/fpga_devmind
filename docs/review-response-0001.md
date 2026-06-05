# Review Response 0001

本文记录对 [Review 0001](reviews/0001-agent-architecture-review.md) 的处理决定。

## Summary

评审意见接受。当前文档方向正确，但确实偏概念层，需要补齐可执行 Agent runtime contract、claim/evidence 判定规则、FPGA 领域结构化语义和 Phase 1 收窄切片。

## Decisions

### Accepted

- Runtime contract missing。
- Claim confidence policy too loose。
- FPGA domain semantics too free-form。
- Phase 1 too broad。
- SourceLineage missing。
- Memory freshness missing。
- Test evidence too coarse。
- Reflection not a loop。
- StageContract missing。
- Toolbox lacks interface contracts。
- Findings format could be confused with product output。
- Acceptance examples missing。

### Deferred

- VHDL / IP-XACT / Vivado generated wrapper 支持范围。

Reason: 第一阶段明确收窄为 Python + Verilog/SystemVerilog + tests/docs/config。更广 HDL 范围后续再扩。

## Follow-up Documents

本轮新增或补强：

- `docs/runtime-contracts.md`：TaskPlan、ToolCall、Observation、Claim、ReflectionDecision、GroundingDiagnostic 等最小运行时契约。
- `docs/domain-semantics.md`：StageContract、FixedPointSpec、StreamInterfaceSpec、PipelineTimingSpec、FSMBehaviorSpec、RTLSignalSpec、TestObservation、SourceLineage。
- `docs/phase1-scope.md`：Phase 1a / 1b / 1c 收窄路线、样例项目、验收指标。

## Immediate Priority

下一轮设计优先级：

1. 用 `docs/runtime-contracts.md` 约束 Agent 循环。
2. 用 `docs/domain-semantics.md` 收紧 FPGA 语义对象。
3. 用 `docs/phase1-scope.md` 防止 Phase 1 膨胀。
4. 后续再将 toolbox 的第一批工具接口展开到 JSON-like contract。
