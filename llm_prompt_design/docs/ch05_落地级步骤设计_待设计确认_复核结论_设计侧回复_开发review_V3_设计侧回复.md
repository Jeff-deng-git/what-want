# ch05 设计侧对「开发终审 V3」的回复（v4）

> 审核依据与 V3 一致（落地文档 / config / PRD / 交接文档 / V3 自身）。本回复针对 V3 的 4 个 P0，逐条拍板并给出已同步的权威文件与 mockup 改动。
> 命名规范：原文件名 + `_设计侧回复` 后缀；本文件为 V3 终审的第 4 轮回复。
> 正文引用 `step-1`/`step-2` 为 ch05 的 step_id（V3 文中的 `step_1` 为笔误，已按实际字段核对）。

---

## 0. 总体结论

V3 指出的 4 个 P0 **全部属实**，设计侧逐一确认并已在权威文档与 mockup 中统一口径。核心拍板：

1. **step-1 不含 `rating`**（方案 A）；
2. **100 例引用走「后端合并」口径**（点引用仅写 `reference_strengths`；点击运行 LLM 时后端合并去重）；
3. **状态机统一为平台既有「运行 LLM(/run) → saved → 编辑 → 提交(/submit)」**（修正此前文档误写的"提交后运行 LLM"）；
4. **step-2 允许未评级项提交**（方案 2，明确下游语义）。

---

## 1. 决策表（对齐 V3 §7 模板）

| P0 项 | 选择 / 固定规则 | 已同步的权威文件 | 是否更新 mockup |
|---|---|---|---|
| §1 step-1 rating | **方案 A**：step-1 canonical = `{text, locked, source?}`（无 rating）；rating 仅由 step-2 引入 | config / PRD / 落地 / 交接 | 否（mockup 仅 step-2 渲染评级控件，step-1 无评级 UI） |
| §2 100 例数据流 | **后端合并**：点「引用」仅写 `user_answers.reference_strengths`；点击「运行 LLM」时后端合并 `step-1.talents` ∪ `reference_strengths` 去重、标 `source:'100_examples'` | config / PRD / 落地 / mockup | **是** |
| §3 状态机 | **确认平台既有状态机**：运行 LLM(/run) → saved（可编辑草稿）→ 编辑/评级/锁定 → 提交(/submit)。`/submit` 不调 LLM | PRD / 落地 / mockup | **是** |
| §4 空评级 | **方案 2（允许为空）**：提交不强制每项评级；未评级项 `rating:""`，明确 UI 文案、profile 形态与 ch07 处理规则 | config / PRD / 落地 / mockup | **是**（未评级显示「未评级」标记） |

---

## 2. §1 step-1 rating —— 方案 A

**拍板**：step-1 `talents` canonical item schema = `{text, locked, source?}`，**不含 `rating`**。`rating` 字段仅由 step-2 引入（step-2 schema = `{text, rating, locked, source?}`）。

**已同步（残留已全部清除，grep 校验 = 0）**：
- `config/chapter_config_ch05.json`：step-1 `instruction` 删除「每项形如 `{text, rating:初始为空, locked:false}`」，改为「每项形如 `{text, locked:false}`；**step-1 不评级**」；step-1 `item_schema.fields` 维持 `[text, locked, source]`（无 rating）。
- `docs/PRD/PRD-ch5.md` §3.1.1（输出 JSON 示例 + canonical schema 行）、§5.1（数据模型说明）、§8.3 待确认项 #3：将 "step-1 与 step-2 均为 `{text, rating, locked}`" / "`rating:null`" / "`rating 默认空`" 全部改为 step-1 无 rating、step-2 才有。
- `docs/ch05_落地级步骤设计.md` §4 canonical schema 行已分拆为 step-1 / step-2 两段；§6 / §8 描述同步。
- `docs/工程实施交接文档.md` §7.5 早已写 "step-1 无 rating"，无需改（与方案 A 一致）。

---

## 3. §2 100 例数据流 —— 后端合并口径

**拍板**：采用 V3 §2.2 推荐的后端统一合并方案（口径 1），并补充 V3 §2.3 / §2.4 三处边界。

**唯一数据流（最终）**：
```
用户点「引用」
  → 仅写 step-2 编辑态 user_answers.reference_strengths
  → 用户点「运行 LLM(/run)」
  → 后端读取已 submitted 的 step-1.talents
  → 后端合并 + 去重 + 对仅来自 100 例的项标 source:"100_examples"
  → LLM 依据唯一候选清单建议评级、生成 user_manual
  → parsed_output.talents 成为唯一可编辑 / 可锁定的 canonical 列表
  → 用户完成评级、增删、锁定后点「提交(/submit)」确认
```

**去重与来源规则（已写入落地 §4，作为开发侧实现约束）**：
1. 五问长处与 100 例引用项文本相同 → **保留五问衍生项（`source:null`）**，100 例项不覆盖；
2. 用户手动新增项 `source` 固定为 `null`；仅来自抽屉「引用」的项可标 `"100_examples"`；
3. 去重规则：对 `text` 做首尾空白清理 + 连续空白归一化后**精确去重**（不做语义近似合并）。

**持久化措辞修正（已写入落地 §4）**：
> `reference_strengths` **不作为 profile 字段或独立数据库列持久化**；它仅随当前 step-2 run 的 `user_answers` 保存，用于可追溯的本次 LLM 输入（草稿可重新进入，不会因不进 profile 而丢失）。

**已同步**：
- `docs/PRD/PRD-ch5.md` §3.1.2 Step-2 system prompt 与 user prompt 模板：删除"已在运行时并入 talents / 不再单独注入"的口径 2 表述，改为"运行时后端把步骤1长处 ∪ 100例引用合并去重后形成候选清单送入 LLM；请勿把 `reference_strengths` 再次单独注入"。prompt 模板显式列出【步骤1已确认长处】与【从100例引用参考长处】两个区块（`step_2.answers.reference_strengths`）。
- `docs/ch05_落地级步骤设计.md` §2 时序、§7 抽屉文案、§10 P1-7：统一为口径 1（点引用仅写 reference_strengths；运行 LLM 时后端合并）。
- `platform/prototype/ch05_exercise_mockup.html`：`addFromExample()` 改为**仅 push 到 `referenceStrengths`**（不再同时 push 到 `talents`）；新增 `renderReferences()` 在 step-2 单独展示"参考长处"列表；`source` 字段替代原 `fromExample` 标记；"运行 LLM 汇总"时把 referenceStrengths 合并去重进 talents。

---

## 4. §3 状态机 —— 确认平台既有状态机

**拍板**：ch05 与已完成章节一致，采用平台既有状态机：
```
保存草稿(draft) → 运行 LLM(/run, saved+parsed_output) → 编辑/评级/锁定(saved) → 提交(/submit, submitted)
```
`/submit` 只接受 saved 的成功 LLM 结果，**不调用 LLM**。此前落地文档/回复中"step-2 提交 → assembler 合并 → 喂给 LLM"的时序表述系笔误，已全部改为"运行 LLM 时合并 → saved → 提交"。

**已同步**：
- `docs/ch05_落地级步骤设计.md` §4 step-1 与 step-2 时序：均改为"运行 LLM(/run) → saved → 审阅 → 提交(/submit)"；step-2 时序第 3 步明确"用户点运行 LLM → 后端合并去重送入 LLM → 产出 saved 草稿"。
- `docs/PRD/PRD-ch5.md`：相应正文/交互描述同步。
- `platform/prototype/ch05_exercise_mockup.html`：step-1 按钮分为「运行教练映照」+「提交本步」；step-2 分为「让教练汇总并建议 ◎〇△」+「提交本步」，均默认禁用提交、运行后解锁。

此条同时覆盖 step-1：step-1 也是"五问填写 → 运行 LLM → 审阅 → 提交"，非"填写即提交同步等待 LLM"。

---

## 5. §4 空评级 —— 方案 2（允许为空）

**拍板**：提交**不强制**每项评级。未评级项 `rating:""` 允许保留。

**固定规则（已写入落地 §4 约束 + §10 开放点）**：
- **UI 文案**：未评级项显示「未评级 / 待定」标签（mockup 已加 `.ur` 标记）；
- **profile 形态**：与已评级项一致（`rating:""`），落 `learner_profiles.profile_json`；
- **ch07 处理规则**：ch07 组合时**仅以 `rating=="◎"` 为组合原料**；未评级项不参与组合原料、但作为候选信息保留（不进入 ◎ 优先集合）；
- config step-2 `rating` enum 已含 `""`（无需改），与"允许为空"一致。

---

## 6. 已确认、无需重复讨论（沿用 V3 §5）

V3 §5 的 10 条已确认项（2 步结构、psychologist 角色、无 profile 上游注入、work_purpose 仅 mentor、mentor 只读 submitted、10+ 非硬门槛、commentary/user_manual 不进 profile、单项 locked 原位置保留/整步 submitted 不可编辑、ch05 覆盖 ch3 初始 talents、ch07 producer map=talents(ch5)∩likes(ch6)∩work_purpose(ch4) 且不含 importance）设计侧全部维持，本次未改动其结论。

---

## 7. 本轮同步文件清单

| 文件 | 改动 |
|---|---|
| `config/chapters/chapter_config_ch05.json` | step-1 `instruction` 去 rating 残留 |
| `docs/PRD/PRD-ch5.md` | §3.1.1/§3.1.2/§5.1/§8.3 去 step-1 rating；§3.1.2 prompt 改为后端合并口径 |
| `docs/ch05_落地级步骤设计.md` | §2 时序（状态机 + 后端合并）、§4 schema 分拆、§7 抽屉文案、§10 P1-7、§10 空评级下游语义、去重/持久化规则 |
| `docs/工程实施交接文档.md` | §7.5 维持 step-1 无 rating（无需改） |
| `platform/prototype/ch05_exercise_mockup.html` | `addFromExample` 仅写 referenceStrengths；新增 `renderReferences`；按钮拆「运行 LLM / 提交」；`source` 替代 `fromExample`；未评级「未评级」标记 |

**校验**：config JSON 合法（step-1 字段 `[text, locked, source]`、step-2 `[text, rating, locked, source]`）；全文档旧口径残留 grep = 0（"提交→assembler""点引用即加入 talents""step-1 与 step-2 均为 {text,rating,locked}""rating:null" 等均为 0）。

---

## 8. 待开发侧落实（设计侧不抢活）

- reseed ch05 active config（新 step-1 无 rating schema），跑 `check_config_consistency.py --chapter ch05` 消除 DRIFT；
- assembler 实现 ch05 专用 merge/dedup（读取 `step_1.output.talents` + `step_2.answers.reference_strengths`，去重标 source），对齐 ch04 step-2 特判模式；
- 前端 `renderStepOutput` 补 `talents` 带 ◎〇△ 分支 + 锁定 + 重生成原位置保留 + 未评级标记；step-1 分支只展示 text + locked（无评级控件）；
- `preserve_output` 透传（`output_schema.type=structured` 判定，非 `editable_list`）——属 5.2/5.3 待办；
- ch07 配置/PRD 去 `importance`、gating 改"请先完成第 4/5/6 章"——留 ch07 范围。
