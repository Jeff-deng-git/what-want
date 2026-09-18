# 第三章落地级步骤设计：设计侧回复

> 对应评审：`docs/ch03_落地级步骤设计_开发review.md`（2026-08-08）
> 回复人：设计侧　|　范围：§3 设计冲突、§8 待确认项 Q1–Q11，以及 §4/§5/§7 采纳情况
> 一句话结论：开发侧 review 的判断基本与设计稿一致；唯一确属真实缺陷的是 **§3.1（mentor_hooks.references 被误注入步骤分析 prompt）**，已确认并给出契约级修复方案，且本次已顺手把设计侧权威制品改到位。

---

## 0. 总体结论

- 字段契约、`lockable`/`readonly` 语义、canonical 类型、四阶段流程、跨章依赖——设计稿与开发侧**已对齐，无需颠覆性改动**。
- 真实需修的点只有一个：**§3.1 步骤分析上下文与导师上下文在当前 `build_step_prompt()` 中被混用**。开发侧判断正确，设计侧确认采纳「显式拆分 `step_context.references` 与 `mentor_hooks.references`」方案。
- 其余 §3.2–§3.4 经核实，设计稿已符合开发侧推荐；仅 PRD-ch3 第 98 行有一处字段名不一致，本次已勘误。

---

## 1. §3.1 步骤分析 vs 导师上下文混用 —— 确认属实，给出修复契约

**核实结果**：`platform/backend/app/runtime/assembler.py` 的 `build_step_prompt()`（约 394–396 与 416–417 行）确实用 `mentor_hooks.references` 选中 profile 字段，注入步骤分析的 `[learner cross-chapter profile]` 块。ch03 的 `mentor_hooks.references = ["misconceptions_cleared","external_voices"]` 是 **ch01** 字段，于是 ch03 阶段2 分析会被 ch01 档案污染——与落地文档「阶段1 无依赖、不读前章产出」直接矛盾。

**设计侧结论（采纳开发侧方案）**：步骤分析上下文与导师上下文显式拆开。
- 新增顶层配置 `step_context.references`：仅供**步骤分析** prompt 使用。
- `mentor_hooks.references`：仅供**导师对话** prompt 使用（保持不变）。
- ch03 步骤分析**不读任何上游**，故 `step_context.references = []`。

**契约级变更（本次已落地，见 §5）**：
- `chapter_config_ch03.json` 新增 `"step_context": { "references": [] }`。
- `config/schema/chapter_task_config.schema.json` 新增同级 `step_context` 属性（结构同 `mentor_hooks.references`）。

**对运行时的要求（开发侧实现，见 §6）**：`build_step_prompt()` 的 profile 块应改读 `chapter_cfg.get("step_context", {}).get("references", [])`；**为兼容尚未评审的章节，当 `step_context` 缺省时回退到 `mentor_hooks.references` 的当前行为**，避免 ch05–ch08 在未评审前被意外改变。

---

## 2. §3.2 导师 references 三版本 → 统一为 ch01 两字段

**核实**：`compaction.py` 的 `PROFILE_FIELDS` 白名单确认 `misconceptions_cleared`/`external_voices`（ch01）、`reclaim_item`/`internal_external_ratio`（ch02）均为真实 canonical 字段。

**设计侧结论**：ch03 导师上下文 = **ch01 的 `misconceptions_cleared` + `external_voices`**，**不**含 `reclaim_item`。
- 理由：落地文档 §0 已明确「ch2 产出（reclaim_item / internal_external_ratio）只被 ch4 引用」；ch03 是 ch4 的上游种子章，但其导师只需 ch01 锚点建立连续性。
- 故 **Q2 采纳「不含 reclaim_item」版本**；**Q3 结论：`reclaim_item` 确是 ch02 正式 canonical 字段，但 ch03 导师不引用它**（仅 ch04 引用）。

**待勘误**：PRD-ch3.md 第 98 行原写「ch2 的 `reclaim_item`（跨章）」，与 config/落地文档冲突，本次已修正为仅引用 ch1 `external_voices`（见 §5）。工程实施交接文档若仍只列 `misconceptions_cleared`，亦应同步为两字段（设计侧另行跟进）。

---

## 3. §3.3 lockable 语义 —— 已一致，确认采纳

设计稿 §6 / §8.4 已写明：真实锁定 = 整步提交态（`edit_output` 在 submitted 返回 409；`submit_step` 触发 compaction）；`lockable`/`readonly` 仅 schema 意图声明，运行时强制靠提交态。

**Q6 结论**：完全采纳开发侧推荐——提交前可编辑、提交后整步锁定、不做 per-item 永久锁定。无需改动。

---

## 4. §3.4 输出 canonical 类型 —— 已一致，确认采纳

核实 config：`importance`/`talents`/`likes` 为 `editable_list`（item 仅 `text` 子字段），`intersection` 为 `text` + `readonly`；profile 落库即字符串数组。

- **Q4**：每组 3–5 项，前后端统一校验（config 已有 `min_items=3`/`max_items=5`，开发侧在输入/输出两端校验即可）。
- **Q5**：最终 profile 为字符串数组；`lockable` 等 UI 意图**不**写入 profile 业务数据。
- **Q7**：`intersection` 只读、不可编辑（config 已 `readonly:true`）。

---

## 5. 设计侧已落地的契约变更（本次回复同步执行）

> 改前均已备份至 `.backups_ch03_review_20260808/`。

1. `config/chapters/chapter_config_ch03.json`：新增 `"step_context": { "references": [] }`。
2. `config/schema/chapter_task_config.schema.json`：新增顶层 `step_context`（结构同 `mentor_hooks.references`，可选）。
3. `docs/PRD/PRD-ch3.md` 第 98 行：删除「ch2 的 `reclaim_item`（跨章）」，改为仅引用 ch1 `external_voices`，与 config 对齐。

校验结果：两份 JSON 合法；`check_config_consistency.py` 中 **ch03 显示 [OK]（无漂移）**；`test_context_integrity.py` + `test_config_consistency.py` **24 passed**。

---

## 6. 需开发侧实现的变更（设计契约已明确，按 review §6 计划执行）

- **assembler `build_step_prompt()`**：profile 块改读 `step_context.references`；`step_context` 缺省时回退 `mentor_hooks.references`（向后兼容）。
- **`seed_roles.py` PSYCHOLOGIST_SYSTEM**：按 §4.1 补强 ch03 专属约束（逐项引用三组输入、区分技能/才能、职业名/领域、证据不足标「可能」、严格 JSON）。
- **前端**：采纳四阶段专属 renderer（§5.1 / Q10）；实现三圆陈列 + 交集回填 + 锁定态 + 失败恢复（§5.2）。
- **后端 steps.py / compaction.py**：按 §5.2 实现输出与状态校验、草稿保留、重跑不覆盖历史、profile 只写最终确认结果。
- **测试**：采纳 §7 全部 14 项验收场景（Q11 纳入本期 E2E）。

---

## 7. §4 / §5 / §7 采纳情况

- §4.1–§4.3：全部采纳，属 Prompt/角色补强（开发侧实现）。
- §5.1 四阶段专属前端：采纳（Q10 = 是）。
- §5.2 / §5.3 数据链不被覆盖：采纳，架构已在落地文档 §8.7「双层持久化」中具备。
- §7 验收 14 项：全部纳入（Q11 = 是）。

---

## 8. 待确认项汇总表（Q1–Q11 设计侧结论）

| 编号 | 待确认项 | 开发侧推荐 | 设计侧结论 |
|---|---|---|---|
| Q1 | ch03 步骤分析是否读前章 profile？ | 不读；拆 step_context / mentor_hooks | **不读**；新增 `step_context.references = []` |
| Q2 | ch03 导师引用哪些 profile 字段？ | misconceptions_cleared + external_voices | **misconceptions_cleared + external_voices**（不含 reclaim_item） |
| Q3 | reclaim_item 是否 ch02 正式字段？ | 是则纳入 | **是 ch02 正式字段，但 ch03 导师不引用**（仅 ch04 用） |
| Q4 | 三组列表项数范围？ | 3–5，统一校验 | **3–5**（config 已 min/max） |
| Q5 | 最终 profile 列表类型？ | 字符串数组，不带 UI 字段 | **字符串数组** |
| Q6 | lockable 语义？ | 提交前可编辑，提交后整步锁 | **采纳，与 §8.4 一致** |
| Q7 | intersection 是否可编辑？ | 只读 | **只读**（config readonly:true） |
| Q8 | 步骤 Prompt 是否引书本章节内容？ | 可引，须转译 | **采纳**；assembler 已支持 chapter_md 切片 |
| Q9 | 缺前章字段时导师如何处理？ | 跳过缺失、不臆造 | **采纳**；必要时提示上下文不完整 |
| Q10 | 是否接受四阶段专属前端？ | 接受 | **接受** |
| Q11 | 是否纳入本期 E2E 验收？ | 纳入 | **纳入**（§7 全部 14 项） |

---

## 9. 实施分工说明（设计侧不抢开发活）

- **assembler.py 运行时代码修改 = 开发侧实施**：本回复 §3.1 已核实并指出 bug——`build_step_prompt()` 误用 `mentor_hooks.references` 把 ch01 档案注入 ch03 步骤分析，与「阶段1 无依赖」矛盾；§6 已将其列为「需开发侧实现的变更」并给出修复契约（profile 块改读 `step_context.references`、缺省回退 `mentor_hooks.references`）。**该代码由开发侧执行，设计侧不改运行时代码**；若开发实施时发现设计与实现不一致，须回头与设计侧沟通。
- **ch04 数据库漂移 = 开发侧 reseed 动作**：`check_config_consistency.py` 显示 ch04 有 `exercises,mentor_hooks` 漂移，系之前改 ch04 config 后未重灌 DB 所致（落地文档要求改完 JSON 必须 reseed）。**reseed 属开发侧实施**，请开发侧在 review ch04 时一并执行；与本次 ch03 review 无关，ch03 本身为 [OK]。
- ch04 你（产品/设计负责人）晚点 review，本次设计侧未动 ch04 交付物。

---

## 10. 第 2 轮开发反馈回复（2026-08-09）

> 对应开发侧追加问题：① 阶段1 右栏是否继续展示 ch01 external_voices；② ch03 专属 Prompt 是否放入 assembler 的 ch03 contract 而非改全局 psychologist role；③ ch03 active DB config 仍缺 step_context，需重新发布。

### 10.1 ① 阶段1 右栏 external_voices 展示 → 显式建模为 `ui_context`

**核实**：落地文档 §136 原已设计「阶段1 外部声音回响」（右栏展示 ch01 external_voices 作防跑偏提示），mockup 第 520 行 ref-line 与之对应。该展示仅属 UI 提示，**不进入步骤分析 prompt**（步骤分析已由 `step_context.references=[]` 隔离），但此前未在契约里显式声明，属于隐式依赖。

**设计侧决定**：采纳 dev 第二选项——**显式建模为 `ui_context`**，不删除。
- 理由：该提示有真实教学价值（防止用户把"外部期待"填进"重要"），且显式建模后，步骤分析 / 导师对话 / UI 提示 三路上下文彻底解耦，step-1 练习逻辑仍保持零前章依赖。
- 替代方案（未采用，留作开放点）：若产品侧更想要"阶段1 完全零前章展示"，可把 `ui_context.references` 置空 `[]`，连续性改由导师对话（mentor_hooks）承载。

**设计侧已落地（本轮，改前备份于 `.backups_ch03_review2_20260809/`）**：
- `config/schema/chapter_task_config.schema.json`：新增顶层 `ui_context`（可选，结构同 step_context/mentor_hooks，含 `references`）。
- `chapter_config_ch03.json`：新增 `"ui_context": { "references": ["external_voices"] }`。
- 落地文档 §136 改写、§8.3 新增 `ui_context` 说明。
- mockup 第 520 行 ref-line 标注"来自 ui_context · 仅 UI 提示，不参与步骤分析"。

**开发侧待办**：前端渲染阶段1 右栏提示时，从 `ui_context.references` 取字段注入；**不得**将其路由进步骤分析 prompt（步骤分析只读 `step_context`）。

### 10.2 ② ch03 专属 Prompt → 按章节注入（contract），不改全局 psychologist role

**设计侧决定**：**同意 dev 强烈推荐**——ch03 专属 Prompt 约束放入 assembler 的 **ch03 contract（按章节注入）**，而非修改全局 `psychologist` role。
- 理由：全局 `psychologist` role 被 ch02/ch04/ch06 共用，改全局会污染其他章节。ch03 的专属行为（步骤分析不读前章、导师引用 ch01、UI 回响 external_voices）已全部可由 per-chapter 契约字段表达（`instruction` / `step_context` / `mentor_hooks` / `ui_context`），无需动全局 role。
- **纠正第一轮 §6**：原 §6 写"在 `seed_roles.py` 的 PSYCHOLOGIST_SYSTEM 补强 ch03 约束"表述过重。正确口径是——ch03 专属约束来自 per-chapter 契约注入；全局 PSYCHOLOGIST_SYSTEM 保持通用，**仅在 dev 确认确有无法靠契约覆盖的缺口时**（dev review §6 原话"如确认需要"）才考虑补强，且仍须评估对其他章影响。

**开发侧待办**：`assembler.py` 按 ch03 contract 注入专属 Prompt（instruction + step_context 控制步骤分析、mentor_hooks 控制导师、ui_context 控制 UI），不修改 `seed_roles.py` 的全局 `PSYCHOLOGIST_SYSTEM`。

### 10.3 ③ ch03 active DB config 缺 step_context → 重新发布（reseed）

**事实确认**：`chapter_config_ch03.json` 现已含 `step_context.references=[]`（本轮再加 `ui_context`），但**活跃 DB 中的 ch03 config 仍是旧版、缺这两个字段**——属"设计契约已更新、DB 未同步"的漂移。

**分工确认（设计侧不抢实施）**：reseed / 重新发布 active config 属**开发侧实施动作**（按既定边界：重灌数据库归开发）。设计侧职责是确认契约正确并交付配置，**不自行跑 reseed**。请开发侧在落地 ch03 时执行 reseed，使 active DB 与文件一致（消除 DRIFT）；本轮新增的 `ui_context` 同理需随 reseed 一并入 DB。

### 10.4 本轮设计侧改动汇总
- 新增 schema 字段 `ui_context`（顶层，可选）。
- ch03 config 新增 `ui_context.references: ["external_voices"]`。
- 落地文档 §136、§8.3 同步。
- mockup ref-line 标注 ui_context 来源。
- 纠偏：第一轮 §6 的"在全局 PSYCHOLOGIST_SYSTEM 补强"改为"按章节 contract 注入"。

### 10.5 设计侧补充确认：ui_context 数据接口 / 展示 / 缺失 / 边界（2026-08-09 第 3 轮）

> 对应开发侧追加四点追问。以下为设计侧最终结论，**均已在落地文档 §136 补充协议为硬约束**。

1. **数据接口 → 步骤详情接口返回已过滤 `ui_context`（不新增用户级端点）**
   - 后端据 `ui_context.references` 从 profile 取出并映射为渲染结构，随 ch03 步骤详情一并返回；**前端禁止直接读 `learner_profile` 全文**。
   - 返回结构：`ui_context.external_voices: [{ misconception_id, misconception_label, voice_text }]`；`misconception_label` 由 ch01 静态清单 id 1–5 映射，仅保留非空 voice，按 `misconception_id` 升序。
   - 备选：仅当 ui_context 后续被多屏复用时，才评估抽成独立 `GET /api/learner-profile/ui-context`。

2. **展示格式 → 标签 + 原文，按编号升序**
   - 每条声音**同时显示误区标签与原文**（如「误区 3 · 必须是对别人有益的事：我爸总说…」），非裸文本。
   - 多条**按误区编号升序**（与 ch01 勾选顺序一致、可预期）。

3. **缺失数据（硬规则，无备选） → 全空隐藏、部分只显已有、不显占位文案**
   - `external_voices` 完全为空/缺失 → **整块隐藏**回响区（导师对话已承载 ch01 连续性），**不显示任何占位文案**。
   - 部分缺失 → **只渲染已存在的声音**，不补占位、不造假、不显占位文案。

4. **保存与 Prompt 边界 → 仅渲染，四不**
   - ui_context **仅用于右栏渲染**；**不写入** ch03 `user_answers`；**不进入**步骤分析 Prompt（assembler 不得把 `ui_context` 路由进 `build_step_prompt`）；**不作为** LLM 分析证据（psychologist role 不接收任何 `external_voices` 文本）。
   - 后端步骤详情序列化器可填充 `ui_context`，但 Prompt 汇编器必须忽略它。
