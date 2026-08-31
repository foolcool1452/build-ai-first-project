# Work Rounds v2: session-bounded, verification-first design

Status: accepted (2026-08-31; session-boundary semantics amended per user decision — rounds loop inside one session by default, suspended/resume only when the session must end)
Last verified: 2026-08-31
Sources: 2026-08 长程 Agent 与 Agent 集群调研报告（METR/Cognition/Anthropic/Manus 工程实证）；AgentMesh 项目汇报（任务卡精确度-成本数据）；v3.1.0 两轮独立审查结论

## 1. 调研输入 → 设计约束（每条约束都有出处）

| # | 调研证据 | 对轮次设计的强制约束 |
|---|---|---|
| R1 | METR：50% 视界 10h+ 但 **80% 视界仅 1-3h**；误差随步数复利；隐式状态恢复是最差项 | 轮次必须同时是**审查边界**和**会话边界**——增量要小到"敢托付"，状态交接要走结构化工件而非对话记忆 |
| R2 | Anthropic harness 模式：initializer 预写验证清单（passing:false）；**每个 session 只做一个 feature 且以"可合并"收尾**；验证器是编排者 | 轮次的验证命令在 **OPEN 时预承诺**（不是审查时才发现）；一轮 = 一次会话的可交付 |
| R3 | Cognition：零共享上下文审查者平均每 PR 抓 2 虫（58% 严重）；自评会"自信地夸自己" | 审查子 agent 只拿目标+合并 diff+证据，且**必须亲自重跑验证命令**，不信任会话自述 |
| R4 | Anthropic 规划/生成/评估三角："context anxiety"——**完整上下文重置 + 结构化交接比压缩更治本** | 轮次优先**会话有界**：宁可开新会话接续下一轮，不做会话内无限轮 |
| R5 | Manus：recitation（重写 todo）、失败证据留在上下文、文件系统即终极记忆 | 轮次条目保留**失败尝试**记录；计划 Progress 是 recitation 表面 |
| R6 | METR：作弊率与能力同步增长（史上最高）；Copilot 自主成功率 67.9% < 人类 87.1% | 审查者**重跑**验证命令而非采信会话声明；发现处置逐条留痕 |
| R7 | AgentMesh 实测：任务卡精确度与成本成反比（1/8）；并行写者必须分区 | OPEN 时写清目标与分区；预算与分区留痕在轮次条目 |
| R8 | Managed Agents：session=append-only 事件日志、harness 无状态可重建 | 计划+注册表+轮次条目 = append-only 状态；新会话从工件重建，不从聊天重建 |

## 2. 重设计后的标准轮次协议

**一轮 = 一个写入会话的一次验证前置、审查收口的工作单元。默认在会话内循环；仅当会话被迫结束时进入 suspended，由下一个写入会话以同一 Round id 复开。**（会话有界为首选实践，非强制——2026-08-31 用户决策）

```text
OPEN    注册表置 active；计划内追加 Round N 条目：
        目标 + 【Verify: 证明本轮完成的命令，OPEN 时预承诺】+ 子 agent 预算 + 并行分区
EXECUTE 写入（主会话或分区内的写子 agent）；失败尝试记入条目
VERIFY  运行 OPEN 承诺的验证命令；证据落条目
REVIEW  零共享上下文审查子 agent：拿目标+合并 diff+证据，并【亲自重跑 Verify】；
        发现逐条 accept/reject + 理由
  ↺     EXECUTE→VERIFY→REVIEW 重复
CLOSE   文档对账或声明无需；注册表置 idle；计划 Next action = 交接给下一轮/下一会话
```

**会话边界规则**：优先一轮一会话。会话被迫中途中断时轮次进入 `suspended`（不是关闭）——状态在计划的 Next action 与条目内，下个会话以同一 Round id 复开；连续两轮无法收敛 → 回到 Plan 重规划（不是 Archive）。

**收敛与闭合**（沿用 v3.1.0 已引入、本轮细化）：审查返回零新发现即收敛；连续两轮只有"带理由的拒绝"即震荡停止；预算先耗尽 → 重规划。

## 3. 相对 v3.1.0 的设计变更

| 变更 | v3.1.0 现状 | v2 设计 | 依据 |
|---|---|---|---|
| 验证预承诺 | 条目只有 Review 事后记录 | 新增 **Verify 行**，OPEN 时定义 | R2/R3/R6 |
| 会话有界 | 轮次在会话内部循环 | 优先一轮一会话；中断=suspended 可复开 | R1/R4 |
| 审查强度 | 审查者看 diff+证据 | 审查者**重跑 Verify** | R3/R6 |
| 失败留痕 | 只有发现处置 | 条目内保留失败尝试 | R5 |
| 其余全部沿用 | 预算/分区/零上下文/处置纪律/不滥用判据/单写入组合 | 不变 | — |

## 4. 条目格式（拟）

```markdown
### Round N — YYYY-MM-DD — <goal>

- Verify: <证明本轮完成的命令；OPEN 时预承诺>
- Research: findings or decision; subagents used: N (why).
- Execute: what changed; evidence; writer partition if parallel.
- Review: findings; each accepted/rejected with a reason; reviewer re-ran Verify.
- Close: docs reconciled or "none"; suspended → resumed as Round N (cont.); or closed.
```

（Over-budget 理由并入 Research 行的 "(why)"，减一行。）

## 5. 明确不做

- 不为轮次/条目新增校验码（沿用用户决策：纯文档强化）；
- 不引入 JSON 状态机（Markdown 条目 + 计划 checkbox 已满足 R5/R8 在单写入规模下的需要；跨 agent 规模化属于 AgentMesh 的 Hub 课题）;
- 不改变 lite profile 与注册表语义（单写入不变量、豁免规则原样）。

## 6. 实施面（获批后）

`references/workflows.md` Work rounds 节重写（协议+边界规则+闭合收敛）、`docs/plans/TEMPLATE.md` 条目格式升级、自测断言更新（Verify 行存在性）、`README` 版本 3.2.0、research 本文档回填 complete、round7 归档与恢复演练、发布 v3.2.0。
