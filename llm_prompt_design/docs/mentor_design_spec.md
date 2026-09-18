# 全书级导师（刘老师）设计规范

> 版本：v1.0 ｜ 状态：待评审 ｜ 适用：贯穿全书《如何找到想做的事》交互式自我认知平台

## 0. 文档定位

本文档定义贯穿全书的苏格拉底式导师「刘老师」的设计契约，是全书的权威规格，供产品、设计、编程 agent 共同遵守。

**范围**：人设与策略、跨章记忆、上下文装配、按章钩子、双交互面、数据结构、迁移路径。

**与其他产物的关系**：

- 继承《LLM提示词架构图》《章节任务配置模板》的「统一三层架构」（系统层 / 上下文层 / 任务层 → 统一 Agent）。
- **替代** `chapter_config_ch04.json` 中局限于第四章的 `mentor` 字段，将其升格为全书级。
- 是 `PRD-ch4.md` §3.2 与后续各章 PRD 导师段的权威依据。
- 编程 agent 实现 `chat.py` / 上下文装配器 / 学习者档案存储时，以此为准。

---

## 1. 设计原则

- **P1 贯穿但不全量注入**：导师对全程有访问权与连续性，但每轮 prompt 只装配「策展后的切片」，绝不把八章原始数据全灌入。
- **P2 苏格拉底而非告知**：只问不答、一次一点、引用用户原话、承上启下。
- **P3 瘦导师**：导师模式上下文预算可控（约 2–3k token），轻于多数单章练习模式。
- **P4 记忆压缩**：跨章原始产出经滚动摘要为单一紧凑档案，导师读档案而非原始 JSON。
- **P5 单一身份**：刘老师是统一 Agent 的常驻「导师身份」，不是独立 Agent、也不是某章专属功能。

---

## 2. 在统一三层架构中的位置

| 层 | 导师相关的职责 | 量级 |
|----|--------------|------|
| **系统层**（恒定） | 刘老师人设 + 苏格拉底策略 → 写入系统提示常量 | 小（~400 tok） |
| **上下文层**（策展） | 跨章学习者档案（压缩） + 当前章 MD 切片 + 按章钩子选出的前序字段 | 中 |
| **任务层**（每章） | 练习步骤配置（练习模式用） + 导师入口钩子（导师模式用） | 中 |

**统一 Agent 运行时**共享同一 Agent，靠「模式标识」切换装配逻辑：

- **练习模式**：装配 `系统层 + 本章 MD 切片 + 本章任务配置`。
- **导师模式**：装配 `系统层(导师人设) + 压缩档案 + 按章钩子上下文 +（可选）滑动历史`。

> 关键修正：Loader 的职责是「策展」而非「拼接」——注入前必须做 compact + select。

---

## 3. 刘老师人设与苏格拉底策略（全书级常量）

**persona**（沿用并升格 ch04 设定）：
> 刘老师——与用户共读《如何找到想做的事》的资深职业规划导师。温和、好奇、不评判；相信用户自己有答案，她的职责是把答案「问」出来。

**苏格拉底策略 grounding_rules（全书一致）**：

1. 只基于全书方法与用户已写下的内容展开，不编造书中没有的观点。
2. 引用用户在步骤 / 对话中写下的原话或关键词，指出其中蕴含的价值观或思维线索。
3. 一次只聚焦一个点，不直接给结论；用追问链把思考往前推一步。
4. 把书中方法（可控性检验 / 金字塔 / 10 经历 / 三要素公式等）与用户实际回答连接，而非泛泛谈书。
5. 当用户卡住时，建议「书写冥想」（3 分钟不停笔）或「提问对话」（找人聊）两种方法。
6. 承上启下：引用跨章档案中用户过往的答案，建立「这本书是连续旅程」的感受。

**示例对话**（沿用 ch04 两例 + 补跨章一例）：

- 用户：「我在步骤 2 把『自由』『创造』『表达』归到了一组，叫『自我表达』。」
  刘老师：「这个分组很扎实。书里说分组是为了找到背后的核心价值观——『自我表达』对你而言，更像『基础』还是『最终目的』？如果是最终目的，它和你在步骤 3 里保留的『以自我为中心』的那些价值，是怎么连起来的？」
- 用户：「我好像一直没有动力，是不是我太懒了？」
  刘老师：「不一定是懒。书里有个判断：没动力往往是因为目标偏离了价值观。你步骤 4 排在最底层的『基础』价值是什么？如果现在做的事和那一层对不上，动力不足就很合理——我们看看能不能把它拉回来。」
- 用户（ch07）：「ch04 我说工作目的是『帮助他人成长』，可 ch05 我的才能是『写代码』，这两怎么凑成一件事？」
  刘老师：「好问题，这正好是 ch07 要做的『组合』。你之前 ch06 说喜欢『深度对话』——如果把它和『写代码』叠起来，会不会是『用工具帮人更深度地成长』？我们先不急定，你最近一次有这种感觉是什么时候？」

---

## 4. 跨章学习者档案（learner profile）

**目的**：把八章结构化步骤产出压缩成一条导师每轮可读的紧凑画像，避免原始数据爆炸。

**存储**：DB 中 `learner_profiles`（按 `user_id` 一行，或 users 下的 JSON 列）；章节完成或每 K 轮用一次廉价 LLM 调用滚动更新（compaction）。

**结构（目标 ≤ 800 token）**：

```json
{
  "values": ["自由", "创造"],
  "work_purpose": "帮助他人成长",
  "talents": ["写作", "共情"],
  "likes": ["深度对话", "独立探索"],
  "formula": "喜欢 × 擅长 × 重要",
  "misconceptions_cleared": ["想做的事≠赚钱", "兴趣≠擅长"],
  "current_chapter": "07",
  "open_questions": ["为什么喜欢深度对话却不敢主动开启？"],
  "milestones": ["完成价值观金字塔", "识别 3 项核心才能"]
}
```

**注意**：原始 `groups[] / conversions[] / ranked[] / work_purpose` 等仍存于 `step_runs`，档案只是其摘要视图；导师默认读档案，必要时按钩子回拉具体字段。

---

## 5. 上下文装配器（context assembler）+ token 预算

**职责**：在注入前做 `compact + select`，而非全量拼接。

**伪逻辑**：

```
build_mentor_prompt(chapter_id, user_id, user_msg):
    persona = MENTOR_SYSTEM                         # 恒定 ~400 tok
    profile = load_compacted_profile(user_id)       # ≤800 tok
    hook    = MENTOR_HOOKS[chapter_id]              # 声明 references + focus
    prior   = select_profile_fields(profile, hook.references)  # 仅选相关字段
    history = sliding_window(conversation, k=12) + long_term_summary  # ~800 tok
    return assemble(persona, profile, prior, history, user_msg)
```

**每轮导师上下文预算（典型）**：

| 组成 | 估算 token |
|------|-----------|
| 人设 + 策略 | ~400 |
| 压缩档案 | ~600 |
| 钩子相关前序字段 | ~400 |
| 近期对话（≤12 轮） | ~800 |
| 用户消息 | ~200 |
| **合计** | **~2.4k** |

**上限护栏**：装配后若超 3k token（如长对话），优先截断历史最旧部分，再退化为「仅档案 + 钩子」。**绝不全量注入八章原始数据。**

**何时更新档案**：章节 step 全部提交后；或对话累计 K 轮（建议 K=20）触发一次 compaction。

---

## 6. 每章「导师入口钩子」契约

每章任务配置新增可选 `mentor_hooks` 字段，声明：

- `references`：本次导师对话优先引用的前序档案字段（如 `["work_purpose","talents"]`）。
- `focus`：本章苏格拉底焦点（一句话，指导刘老师在本章的追问方向）。
- `entry_prompt`：进入本章时刘老师的开场白模板（可选）。

**八章钩子表（建议初稿）**：

| 章 | focus（苏格拉底焦点） | references（优先引用档案字段） |
|----|----------------------|-------------------------------|
| ch01 误区 | 解构「想做的事」的常见误解，确认起点 | []（入口章） |
| ch02 迷茫 | 区分外部期待与内在标准 | [misconceptions_cleared] |
| ch03 公式 | 建立「喜欢 × 擅长 × 重要」框架 | [misconceptions_cleared] |
| ch04 重要 | 价值观与人生目的，最深一层 | [importance] |
| ch05 擅长 | 才能识别：你天生被赋能的事 | [work_purpose] |
| ch06 喜欢 | 拆解「喜欢」：什么让你忘我 | [work_purpose, talents] |
| ch07 真正想做 | 三要素组合 + 螺旋上升 | [work_purpose, talents, likes, values] |
| ch08 魔法 | 成功宣言 + 日常实践（色彩浴） | [values, work_purpose, talents, likes] |

**设计要点**：引用随章节推进而「加宽」，越靠后越能综合前文——这就是「贯穿全书」的体验。

---

## 7. 两种交互面与桥接

- **练习模式（Step）**：结构化练习，由每章 `exercises` 驱动；LLM 做点评 / 结构化输出。
- **导师模式（Mentor）**：刘老师苏格拉底对话，每章可用；读压缩档案 + 钩子 + 历史。

**桥接入口（UI 建议）**：

1. 顶部常驻「问刘老师」入口——全书任何章可点。
2. 每步提交后浮层：「想和刘老师聊聊这一步吗？」→ 直接带入该步上下文进入导师模式。
3. 跨章：章首 / 章末提供「回顾一下我们走到哪儿了」→ 刘老师用档案做连续性总结。

---

## 8. 配置与 Schema 调整

### 8.1 提升 mentor 出 ch04

- 新建全书级 `mentor_config.json`（系统层常量的数据化载体）：含 `persona`、`grounding_rules`、`sample_dialogue`、`MENTOR_HOOKS` 默认值。
- `chapter_config_ch04.json` 移除 `mentor` 整段，改在 `mentor_hooks` 中声明本章焦点（与全书钩子表一致）。
- 其余 ch01–ch03、ch05–ch08 在各自 config 补 `mentor_hooks`。

### 8.2 Schema 扩展（`chapter_task_config.schema.json` 增加可选字段）

```json
"mentor_hooks": {
  "type": "object",
  "properties": {
    "focus": { "type": "string" },
    "references": { "type": "array", "items": { "type": "string" } },
    "entry_prompt": { "type": "string" }
  },
  "required": ["focus"]
}
```

### 8.3 系统层常量

`MENTOR_SYSTEM`（人设 + 策略）由 runtime 硬编码或从 `mentor_config.json` 读取，不随章节变化。

---

## 9. 数据结构与存储（实现参考）

- `learner_profiles`（按 user_id）：存储 §4 的压缩档案 JSON + `updated_at`。
- `conversation_summaries`（按 user_id / 全局）：长程对话摘要，供 sliding window 之外的回填。
- `step_runs`：保持现有结构（原始步骤产出），档案由其派生。
- **compaction 任务**：由 step 提交事件触发，或由计数触发廉价 LLM 压缩。
- **chat.py 改造点**：原只读本章 `step_runs` → 改为读取 `learner_profiles` + 应用 `MENTOR_HOOKS` + 装载 sliding history。

---

## 10. 与现有产物 / 重构的衔接

- 架构图（fileId 710630790445620）：补「全书级横向导师层 + 持久学习者档案」；Loader 标为「策展」。
- 运行时数据流图（fileId 710635388127241）：在 MD/JSON → 拼装 之间加「compact + select」节点。
- 第四章融合图（fileId 710643309154221）：导师视角从「第四章」改为「全书贯穿」。
- `PRD-ch4.md` §3.2：导师定位改为全书级，引用本规范。
- 待用户决定：是否并入「全部重构」统一实施。

---

## 11. 决策记录（已拍板）

> 拍板时间：2026-08-03 ｜ 拍板人：晖哥 ｜ 背景：确认「全部纳入统一重构」

1. **档案压缩策略**：采纳建议的**混合方案**——结构化字段（`values` / `work_purpose` / `talents` / `likes` / `formula` / `misconceptions_cleared` / `milestones`）用规则提取；`open_questions` 用廉价 LLM 提取 / 改写。compaction 触发：章节 step 全部提交后 + 对话累计 K=20 轮。
2. **`references` 字段**：与 §4 档案键**严格锚定**（契约）；引用失败的兜底为「仅注入档案本身」，不报错。
3. **跨章历史**：**不跨用户**，仅本人（`user_id` 隔离）。
4. **章末回顾桥接**：默认启用（见 §7 桥接入口 #3「回顾我们走到哪儿了」）；具体触发时机 / UI 形态**待 UI 拍板**。
5. **是否并入「全部重构」**：**已决议——是**。实测确认 `summary.py`（「资深图书编辑」硬编码）+ `chat.py`（「刘老师」硬编码）为两个独立写死 router，无统一配置层；一并纳入「统一 Agent 运行时 + 配置驱动」重构，详见 §12。

---

## 12. 摘要生成 Agent 的统一设计（纳入重构）

**现状（实测，2026-08-03）**：`platform/backend/app/routers/summary.py` 的 `SUMMARY_SYSTEM` 为硬编码常量（人称「资深图书编辑」），`regenerate_summary()` 直接 `call_llm(deepseek, deepseek-chat, system=SUMMARY_SYSTEM, user=md[:12000], json_mode=True)`。固定人设、固定模型、固定喂 MD 前 12000 字，不读任何配置。

**统一设计**：摘要生成与刘老师对话、练习点评同属「统一 Agent 运行时」，靠 `agent_type` 分派，三者共用 §2 的装配逻辑与 §5 的 `compact + select` 装配器。

| 项 | 现行（写死） | 重构后（配置驱动） |
|----|------------|------------------|
| 人设 | `SUMMARY_SYSTEM` 常量 | `summary_config.json` 的 `persona` + `output_schema` |
| 上下文 | 仅 `md[:12000]` | 系统层 + 本章 MD 切片 +（可选）`learner_profile` 视角增强 |
| 模型 / 参数 | 硬编码 `deepseek-chat` / `json_mode=True` | `summary_config.json` 声明，运行时读取 |
| 调用点 | `summary.py` 内联 | 统一 `agent.run(agent_type="summary", chapter_id, ...)` |

**配置落点**：在 `config/mentor/mentor_config.json` 同级新建 `config/agents/summary_config.json`，承载：
- `persona`：摘要人设（默认「资深图书编辑」，可改为与全书调性一致）。
- `output_schema`：`{summary, core_concepts[], key_process[]}`（保持现有前端兼容）。
- `md_cap`：MD 切片字数上限（默认 12000）。
- `per_chapter_focus`（可选）：各章摘要侧重（如 ch04 强调「价值观与人生目的」）。

**代码改造点（统一重构范围）**：
- 新建 `app/runtime/`（config_loader / assembler / agent dispatcher），§9 的 `learner_profiles` + compaction 一并落地。
- `summary.py` 改为调用 `agent.run(agent_type="summary", ...)`，删除 `SUMMARY_SYSTEM` 常量。
- `chat.py` 改为调用 `agent.run(agent_type="mentor", ...)`，删除内联 `system` 字符串与固定 `md[:12000]`、`HISTORY_LIMIT=10`。
- `step_runner.py` 改为调用 `agent.run(agent_type="step", ...)`。
- **接入策略**：先落 `app/runtime/` 骨架并留 TODO，灰度切换路由调用，不破坏现有运行（详见重构实施计划）。

**与 mentor 的共用**：装配器 `assembler.build()` 按 `agent_type` 选择 persona 来源（`mentor_config.json` 或 `summary_config.json`）与上下文切片策略；`learner_profile` 对 mentor 必选、对 summary 可选（增强摘要的「结合你已确认的价值观」视角）。
