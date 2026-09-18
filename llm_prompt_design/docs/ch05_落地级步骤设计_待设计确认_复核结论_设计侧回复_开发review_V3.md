# ch05 落地级步骤设计：对「复核结论_设计侧回复」的开发终审（V3）

> 审核日期：2026-08-11
>
> 审核依据（优先级）：
> 1. `docs/ch05_落地级步骤设计.md`（本章最终设计入口）
> 2. `config/chapters/chapter_config_ch05.json`（字段与运行时参数权威源；发布后以 DB active config 为准）
> 3. `docs/PRD/PRD-ch5.md`（LLM 提示词与交互规范）
> 4. `docs/工程实施交接文档.md`（跨章 producer / consumer 总览）
> 5. `docs/ch05_落地级步骤设计_待设计确认_复核结论_设计侧回复.md`（本轮设计侧回复）
>
> 本文件目的：在 ch05 进入实现前，消除仍会造成前端、后端、Prompt 与测试实现分叉的契约矛盾。未在本文件确认的 ch07 配置/PRD 改动仍留在 ch07 范围，本轮不扩展实现范围。

---

## 0. 终审结论

ch05 的两步结构、角色、上游/下游关系、`10+` 非硬门槛、导师只读取 submitted 输出等主设计已经明确；但以下 **4 项为实施阻塞项（P0）**，需要设计侧明确唯一口径并同步至最终设计文件。

开发侧不建议在 P0 未统一前开始实现，否则会再次出现「配置、原型、Prompt、运行时各按不同理解实现」的返工风险。

---

## 1. P0：step-1 的 `rating` 字段是否存在，尚未形成唯一 schema

### 1.1 已核验到的冲突

| 来源 | 当前表述 |
|---|---|
| `chapter_config_ch05.json` step-1 `item_schema` | 字段为 `text`、`locked`、`source`；**没有 `rating`**。 |
| 同一 config 的 step-1 `instruction` | 仍写「每项形如 `{text, rating:初始为空, locked:false}`」。 |
| `PRD-ch5.md` Step-1 system prompt | 要求输出 `{text, rating:null, locked:false, source:null}`。 |
| `PRD-ch5.md` Step-1 JSON 示例 / 数据模型说明 | 仍以 `{text, rating:"", locked:false}` 表示 step-1 结果，并写「step-1 与 step-2 均为 `{text, rating, locked}`」。 |
| 本轮设计侧回复 | 明确说 step-1 不评级，config step-1 item_schema 已移除 `rating`。 |
| 工程实施交接文档 §7.5 | 明确写 step-1「无 rating」。 |

### 1.2 需要设计侧拍板的唯一问题

**step-1 `talents` 的 canonical item schema 究竟是哪一个？**

请二选一，不保留并行口径：

1. **建议方案 A：step-1 不含 `rating`**
   - schema：`{text, locked, source?}`；
   - `rating` 仅由 step-2 引入；
   - step-1 前端不显示评级控件；
   - 若旧 LLM 偶发返回 `rating:null`，后端可兼容忽略，但该字段不属于 canonical 输出。
2. 方案 B：step-1 固定含 `rating:null`
   - 则 config 的 step-1 `item_schema` 必须显式加入可空 `rating`；
   - 前端需要明确不渲染、但保存该字段；
   - 交接文档「无 rating」需同步改写。

### 1.3 开发侧建议

建议采用 **方案 A**。第五章的评级动作在 step-2，step-1 持有空 `rating` 没有用户价值，只会增加 renderer、数据校验与下游兼容复杂度。

### 1.4 设计侧确认后需同步的位置

- `config/chapters/chapter_config_ch05.json`：step-1 `instruction` 与 `item_schema`；
- `docs/PRD/PRD-ch5.md`：§3.1.1 输出约束、§5.1 示例、§5 数据模型说明、验收清单；
- `docs/ch05_落地级步骤设计.md`：§4 / §6 / §8 对 step-1 schema 的描述；
- `docs/工程实施交接文档.md`：§7.5（若非方案 A）。

---

## 2. P0：100 例引用项的归属与合并路径相互矛盾

### 2.1 当前存在的两套互斥实现口径

**口径 1：`reference_strengths` 是 step-2 的独立用户输入，首次运行时后端合并。**

本轮设计侧回复与落地文档的时序表述为：

1. step-1 submitted 后，得到仅由五问衍生的 `step-1.talents`；
2. 用户在 step-2 100 例抽屉点「引用」，内容进入 `user_answers.reference_strengths`；
3. 首次 step-2 LLM 运行前，assembler 合并 `step-1.talents` 与 `reference_strengths`、去重并标记来源；
4. LLM 产出 canonical step-2 `talents`。

**口径 2：引用时直接并入当前编辑中的 `talents`，不再单独注入 `reference_strengths`。**

以下现有内容仍采用此口径：

- 落地文档的「100 例清单抽屉」说明写「点引用即加入 `talents` 列表」；
- PRD Step-2 user prompt 注释写「已在运行时并入 step-2 当前编辑中的 talents，不再单独注入 `reference_strengths`」；
- ch05 mockup 的 `addFromExample()` 同时把项目 push 到 `talents` 和 `referenceStrengths`，即一份数据有两个可编辑归属；
- mockup 仍使用 `fromExample`，与正式 schema 的 `source:"100_examples"` 不一致。

两套口径不能并存：前者会让后端拥有唯一合并入口，后者会让前端先行构造 canonical 输出，二者会导致重复注入、重复项、锁定与来源标记不一致。

### 2.2 需要设计侧拍板的唯一数据流

开发侧建议确认以下**后端统一合并方案**：

```text
用户点「引用」
  → 仅写 step-2 编辑态 user_answers.reference_strengths
  → 用户点「运行 LLM」
  → 后端读取已 submitted 的 step-1.talents
  → 后端合并 + 去重 + 对仅来自 100 例的项标 source:"100_examples"
  → LLM 依据唯一候选清单建议评级、生成 user_manual
  → parsed_output.talents 成为唯一可编辑 / 可锁定的 canonical 列表
  → 用户确认后提交
```

若设计侧改选「前端先并入 `talents`」方案，也可以，但必须明确：

- `reference_strengths` 是否还存在于 config / API；
- 前端如何在尚无 `parsed_output.talents` 的首次运行前构建列表；
- 后端如何避免把同一引用项再次注入 Prompt；
- `source`、锁定、顺序、重新生成分别由谁保证。

### 2.3 需要同时明确的来源与去重规则

请在最终设计中补充以下三个边界：

1. 五问长处与 100 例引用项文本去重后，若文本相同，保留哪一项的 `source`？
   - 开发建议：保留五问衍生项，`source:null`；因为该项已有用户个人证据，100 例只是辅助触发。
2. 用户在 step-2 手动新增的长处，`source` 是否固定为 `null`？
   - 开发建议：是。只有来自抽屉点击「引用」的项可标记 `"100_examples"`。
3. 去重的比较规则是什么？
   - 开发建议：对 `text` 做首尾空白清理、连续空白归一化后精确去重；不做语义近似合并，避免把不同才能误合并。

### 2.4 持久化措辞需修正

`reference_strengths` 不进入 `learner_profile` 已明确；但只要它随 `/run` 发送，就会作为该次 `step_runs.user_answers` 的一部分保存。最终设计应将「不单独持久化」改为：

> `reference_strengths` 不作为 profile 字段或独立数据库列持久化；它仅随当前 step-2 run 的 `user_answers` 保存，用于可追溯的本次 LLM 输入。

否则开发侧容易误解为完全不落库，导致重新进入草稿后丢失引用内容。

---

## 3. P0：设计写成“提交后运行 LLM”，但平台状态机是“运行后提交”

### 3.1 设计文案当前的问题

落地文档 / 本轮回复的四步时序写为「step-2 提交 → assembler 合并去重 → 喂给 LLM 首次运行」。

这与平台已稳定使用的状态机不一致：

```text
保存草稿（draft，可选）
  → 运行 LLM（/run，得到 saved + parsed_output）
  → 用户编辑、评级、锁定（仍为 saved）
  → 提交（/submit，变为 submitted；仅此时可供下游引用和 profile 归档）
```

当前后端也明确要求 `/submit` 只能提交一个 `saved` 的成功 LLM 结果；它不会调用 LLM。

### 3.2 需要设计侧确认的文案/交互契约

请确认 ch05 和其它已完成章节一样采用上述状态机，并把所有「提交后由 LLM 生成 / 提交时喂给 LLM」改为：

> 点击「运行 LLM」时，将已 submitted 的 step-1 `talents` 与本次 `reference_strengths` 合并去重后送入 LLM；LLM 结果保存为可编辑草稿。用户完成评级、增删、锁定后，点击「提交」确认本步并供后续章节使用。

此项需同时覆盖 step-1：step-1 也应是「五问填写 → 运行 LLM → 审阅初步长处 → 提交 step-1」，而非用户填写五问后直接提交并同步等待 LLM。

---

## 4. P0：step-2 的空评级是否允许提交，尚未定义

### 4.1 当前不一致

- step-2 config 的 `rating` enum 包含 `""`；
- 设计文字写「给每项长处标 ◎〇△」；
- ch07 明确以 `rating=="◎"` 的长处为主原料；
- 尚无规则说明未评级项在 step-2 提交、profile 与 ch07 消费时应如何处理。

### 4.2 需要设计侧拍板

请明确以下二选一：

1. **提交前必须每项评级**：提交时逐项校验，空评级提示用户完成选择；
2. **允许保留未评级项**：明确空值的 UI 文案、profile 形态与 ch07 处理规则（开发建议：未评级项不进入 ch07 的 ◎ 优先集合，但仍作为候选信息保留）。

开发侧倾向方案 2：不因为尚不确定的长处阻断用户完成本章，但需由设计侧明确其下游语义。

---

## 5. 已确认、无需重复讨论的内容

以下设计已足以进入开发，不是本轮问题：

1. ch05 是 **2 个真实 step**，不是旧九宫格单步方案；
2. step-1 / step-2 的角色均为 `psychologist`；
3. step 内无 profile 上游注入，`step_context` 与 `ui_context` 均为空；
4. `work_purpose` 仅通过 `mentor_hooks` 供刘老师对话引用，不进入普通 step Prompt；
5. mentor 仅读取 ch05 已 submitted 的输出和 ch04 `work_purpose`；
6. `10+` 是引导目标，不得为凑数产生幻觉；
7. `commentary` / `user_manual` 不进入 learner profile；
8. 单项 locked 仅影响下一次重生成；已 locked 项必须原内容、原位置保留；整步 submitted 后不可编辑；
9. ch05 step-2 的 `talents` 覆盖 ch03 的初始 `talents`；
10. ch07 正式 producer map 已拍板为 `work_purpose(ch04) + talents(ch05) + likes(ch06)`，`importance` 不属于该 producer map。ch07 配置/PRD 的后续同步留在 ch07 范围。

---

## 6. 实际核验记录（供设计侧定位）

| 问题 | 已核验文件与位置 |
|---|---|
| step-1 schema 没有 rating | `config/chapters/chapter_config_ch05.json` step-1 `item_schema` |
| step-1 instruction 仍要求 rating | `config/chapters/chapter_config_ch05.json` step-1 `instruction` |
| PRD 仍含 step-1 rating | `docs/PRD/PRD-ch5.md` §3.1.1、§5.1、§5 数据模型、验收摘要 |
| 后端真实状态机 | `platform/backend/app/routers/steps.py` 的 `/run`、`/submit`；`/submit` 只接受 saved run |
| 下游只读 submitted 前序 step | `platform/backend/app/runtime/agent.py` 的 `_load_prior_outputs()` |
| 当前 assembler 未实现 ch05 专用 merge/dedup | `platform/backend/app/runtime/assembler.py` 的 `build_step_prompt()`；目前只有 ch04 step-2 特判 |
| 原型仍采用直接 push talents / `fromExample` | `platform/prototype/ch05_exercise_mockup.html` 的 `submitStep1()`、`addFromExample()` |

---

## 7. 设计侧回复模板（建议）

请按以下格式逐项回复，避免只描述意图、未形成可测试契约：

| P0 项 | 选择 / 固定规则 | 需要同步的权威文件 | 是否需要更新 mockup |
|---|---|---|---|
| §1 step-1 rating | 方案 A / B，完整 item schema | config / PRD / 落地 / 交接 | 是 / 否 |
| §2 100 例数据流 | 后端合并 / 前端先并入，完整时序 | config / PRD / 落地 / mockup | 是 / 否 |
| §3 状态机 | 确认「运行 LLM → saved → 提交」或给出替代 API 设计 | PRD / 落地 / mockup | 是 / 否 |
| §4 空评级 | 提交必选 / 可为空及下游规则 | config / PRD / 落地 / mockup | 是 / 否 |

设计侧确认并完成文档同步后，开发侧将以最终 config + 落地文档为准开始 ch05 实施，并先补齐对应 API/级联/锁定/profile/导师上下文的自动化测试。
