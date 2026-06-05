# Evidence Grounding Policy

本文定义 `fpga_devmind` 的证据约束策略。它是防止 Agent 幻觉、误读和过度自信的核心机制。

## 基本原则

1. 没有证据的结论不能写成确定事实。
2. 每个主要工程语义结论必须绑定 `evidence_ids`。
3. 注释、文档和文件名可以作为证据，但不能单独当作强事实。
4. 源码、RTL、测试、配置之间发生冲突时，要显式标注冲突。
5. 不确定性是一等输出，不是失败。
6. Agent 的输出应区分 `confirmed`、`inferred`、`unknown`。

## 证据类型

```text
source_code
  Python 源码实现、类、函数、表达式、状态变量。

rtl
  Verilog/SystemVerilog module、port、signal、always、assign、实例化。

test
  pytest、cross-compare、cocotb、断言、层级信号观测。

config
  parameters.py、external_libs.yaml、projects.yaml、pyproject。

doc
  README、docs/design、阶段说明、架构说明。

comment
  源码注释、RTL 头注释、普通注释。

report
  仿真或阶段报告，但当前阶段不运行 Vivado 或综合流程。
```

## 证据强度

### Strong

可作为强证据：

- 源码中实际执行的计算逻辑。
- RTL 中实际声明和连接的 module、signal、always、assign。
- 测试中的断言、层级信号观测、明确预期值。
- 配置中的明确参数值。

### Medium

可作为中等证据：

- 设计文档中的架构描述。
- 阶段说明。
- RTL 头注释中的映射说明。
- 测试名称和测试场景描述。

### Weak

只能作为弱证据：

- 普通注释。
- 文件名。
- 符号命名相似。
- 未被代码或测试交叉验证的说明。

## 结论置信状态

```text
confirmed
  至少有强证据，且没有明显冲突。

supported
  有中等证据和部分强证据，但映射或解释还不完整。

inferred
  主要基于命名、结构相似、上下文推断；必须显式标注。

unknown
  证据不足，不能形成解释。

conflicted
  源码、RTL、文档、测试之间存在冲突。
```

运行时中的具体结论应表达为 `CandidateClaim`，并带有 `claim_type`。不同 claim 类型需要不同证据组合，详见 [Runtime Contracts](runtime-contracts.md)。跨阶段或 L6-to-RTL 映射不能因为单一强证据就自动提升为 `confirmed`。

## 映射规则

### L6 到 RTL 映射

强映射通常需要至少两类证据：

```text
L6 class/function/state
RTL module/signal/instance
top-level connection
test observation
```

只有注释说“RTL 对应 L6”时，最多是 `supported` 或 `inferred`，不能直接 `confirmed`。

### 概念别名映射

同一概念跨阶段可能改名，例如：

```text
lts_start
o_lts_start
result_lts_start_r
fpd_lts_start_capture_r
```

别名映射需要结合：

- 数据来源。
- 下游用途。
- 时序位置。
- 文档解释。
- 测试观测。

不能仅凭名字相似。

### 实现细化

L6/RTL 常会引入资源化细节，例如：

- LUT。
- DSP 复用。
- reciprocal multiply。
- shift / align / divide。
- 更宽内部 Q 格式。
- pipeline latency。

这些不应被简单标成“等价”或“不等价”，而应优先标为：

```text
implementation_refinement
rtl_refinement
resource_mapping
timing_refinement
```

## 冲突处理

冲突示例：

- 文档说四个 stage，代码中实际五个 stage。
- 注释说 L6 与 L5 算法一致，但 L6 引入额外归一化路径。
- RTL 头注释声明对应某个 L6 函数，但信号连接无法支持。
- 测试名称覆盖 CFO，但断言只检查 valid。

输出应包括：

```text
UncertaintyNote
- reason: conflicting_evidence
- current_interpretation
- evidence_ids
- needed_evidence
```

## 输出要求

每个主要输出块都应能回答：

```text
这个结论来自哪些证据？
证据强度如何？
有没有相反证据？
哪些部分是推断？
哪些部分未知？
```

不合格输出示例：

```text
RTL 完全实现了 L6。
```

合格输出示例：

```text
RTL top 中的 s0/s1/s2/s3 子模块与 L6 中的四个 stage 存在结构映射。
该结论由 L6 class 定义、RTL module 定义、top 实例化共同支持。
但 RTL 中 reciprocal LUT 和内部 Q(3,11) 细节在 L6 中未完全显式表达，因此这些节点标为 rtl_refinement。
```

## 禁止输出风格

当前阶段避免：

- PASS / HOLD。
- 放行 / 阻断。
- finding 列表作为主体。
- 自动判定实现正确或错误。
- 没有证据锚点的确定性判断。

这些能力未来可以作为 Review / Audit Agent 扩展，但必须建立在可靠理解图之上。
