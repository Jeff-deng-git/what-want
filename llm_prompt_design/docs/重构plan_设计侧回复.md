# 设计侧回复：评审 `重构plan_待设计拍板.md`

> 文件：`docs/重构plan_设计侧回复.md`
> 写于：2026-08-03 ｜ 受众：Coding Agent + 评审 agent + 晖哥
> 关联：`docs/重构plan_待设计拍板.md`（被评文档）、`docs/站点重构与开发计划.md`（v1.1，权威）、`docs/ADR-001-exercises-schema.md`（已采纳）

---

## 0. 总评

这份 plan 文档**结构清晰、现状审计准确、与交接文档/设计总览高度一致**，可直接作为实施蓝本。

但需要注意一个时间线问题：**它是基于我们上午那轮 7 项架构拍板（v1.1 + ADR-001）之前写的**。因此它的 4 个"待拍板"里：

- **Q1 / Q2 / Q4 我们已经拍板了**（对应 v1.1 §3.4 / §3.1–3.3 / M5），无需再等设计答复；
- **Q2 的"跨步引用机制"描述有错误**，必须按 §2 修正，否则 ch4 级联会断；
- **Q3（mentor/summary 落库）是我们 v1.1 里没显式定的**，本文给出正式拍板（方案 A，细化）。

**行动建议**：Coding Agent 以 `站点重构与开发计划.md` v1.1 为权威主线，本回复 + ADR-001 作为补充；被评文档的 M1–M6 与我们的里程碑一致，可直接复用，但 Q2 机制必须替换。

---

## 1. Q1 章节标识迁移 → 已拍板（方案 B，一致）

与我们 v1.1 §3.4 / ADR-001 §2.4 完全一致：统一 `ch01..ch08`，一次性迁移 `04-important → ch04`，随后删除 `book.py` 的 `CH_ID_ALIAS`。

**补充（务必）**：迁移脚本 `migrate_chapter_ids.py` 执行前，先 `grep -rn "04-important"` 全仓（含 jinja2 模板、前端 `index.html`、`seed_ch4.py`、任意硬编码引用），确认无残留后再做；并强制先备份 `ww.db`。

---

## 2. Q2 step 模式 prompt 装配 → 已拍板，但机制描述**错误（关键）**

### 2.1 已拍板部分
- **Option B（exercises 原生）**：重写 `step_runner` 走 `build_step_prompt`，彻底去掉 jinja2（ADR-001 §2.1）。
- **跨步引用用 `exercises[].references`**（ADR-001 §2.2）：`build_step_prompt` 从同章**已 submitted 的前序 `step_runs.parsed_output`** 注入。

### 2.2 ❌ 必须修正的错误
你写的：
> "跨步引用由'按 `output_fields` 拉 `learner_profile`'实现，不再用 `{step_X.output.x}` 模板语法"

这是**错的**，会让 ch4 级联直接断掉。原因：

- ch4 级联：step‑2 要 step‑1 的 `top_values`；step‑3 要 step‑2 的 `groups`；step‑4 要 step‑2 `groups` + step‑3 `conversions`；step‑5 要 step‑4 `ranked`。
- 其中 **`groups` 与 `conversions` 是步骤级中间产物，不进 `learner_profile`**（profile 只收最终合成字段，见 §5.4）。从 `learner_profile` 拉不到 `groups`/`conversions`，级联断裂。
- ✅ 正确做法：用 `exercises[].references: [{ "from_exercise": "step-2", "fields": ["groups"] }]`，`build_step_prompt` 从**前序 `step_runs.parsed_output`** 取这些字段注入。`chapter_config_ch04.json` 已作为 canonical 样例补完 5 步级联。

### 2.3 你的 prompt 拼装骨架——方向对，但需补两点
```
system = role.system_prompt + core_concepts + guiding_questions   # ✅ 字段名已核对 schema 存在
user   = exercise.user_action + few_shot_examples + user_answers + output_fields + 【prior_outputs】
```
- 补 **`prior_outputs`**：来自 `references` 声明的"前序 step_runs 输出"，**不是** profile。
- `json_mode` 判定：依据 `output_fields[].type` 是否含结构化类型（`editable_list`/`list`/`table`/`select`/`number`/`json`），而非"是否为 list"。纯 `markdown`/`text` 字段走非结构化输出。

---

## 3. Q3 mentor / summary 落库 → 需补决策（推荐 方案 A，并细化范围）

我们的 v1.1 §M2 原写"把 `mentor_config.json`/`summary_config.json` 拆出角色灌入 `llm_roles`"——这偏 **方案 B**，会导致 `llm_roles.system_prompt` 膨胀，且 `MENTOR_HOOKS`/示例/few-shot 无处干净放置。

**✅ 设计侧正式拍板：方案 A（新增 `agent_configs` 表），并做如下细化（hybrid）：**

| 表 | 职责 | 存什么 |
|----|------|--------|
| `llm_roles` | 模型路由 + 核心 persona | `provider` / `model` / 简短 `system_prompt`（核心人设 + grounding_rules） |
| `agent_configs(name PK, config_json)` | **全局** mentor/summary 脚手架 | persona 长描述、`sample_dialogue`、`exercise_informed_dialogue`、`context_budget`、DEFAULT `MENTOR_HOOKS` |
| `chapter_configs.mentor_hooks` | **每章** 导师钩子 | `focus` / `references`（指向 profile 字段）/ `entry_prompt` —— 已在各章 config 中，**不搬** |

`assembler.build_mentor_prompt` = `llm_roles.system_prompt` + `chapter.mentor_hooks` + `agent_configs.sample_dialogue/few_shot` + `profile` + `history`，全部受 ≤3k 护栏。

> 我会同步把 v1.1 §M2 的 seed 描述改为这个 hybrid，避免两份文档矛盾。

---

## 4. Q4 章末桥接卡触发时机 → 已拍板（B+C 组合，一致）

与 v1.1 §M5 一致。补充明确两点：

1. **卡内容来源**：`learner_profile` 中 `mentor_hooks.references` 指向的字段（回退 `output_fields`）；profile 为空时显示**空态卡**（"完成本步后，这里会浮现你的人物画像"），不报错、不重算 LLM。
2. **触发**：进入章末视图即默认展示（方案 C 的默认展开），任一步 `submitted` 后填充（方案 B 的动态填充）；**不自动弹窗、不强制对话**；CTA「和刘老师聊聊这一步 ▸」带入 `chapter_id + step_id` 预填，**不自动发送**。

---

## 5. 该文档缺失 / 需对齐的点（我们 v1.1 已覆盖，请对齐）

1. **user_id 来源（全文未提）**：已拍板 `DEFAULT_USER_ID = "local"`（v1.1 §3.5）。M1–M4 所有 `learner_profiles` / `step_runs` 读写默认该值，前端无需改。
2. **前端托管（未提）**：已拍板 §3.6——后端 `main.py` 用 `StaticFiles` 挂 `frontend/index.html` 到 `:8011/`，前端 `API` 改相对路径 `/api`，消除硬编码 `http://localhost:8011`。
3. **端口混乱**：你 §6 写 "localhost:3011 无监听"，但我们的代码审计与 `index.html` 硬编码都是 `http://localhost:8011`。**请先确认真实运行端口再开工**（很可能是 8011）。
4. **⭐ profile 字段边界（关键）**：你的 M1 字段映射没把 `groups`/`conversions` 列入 profile（这点是**对的** ✅），但要在 Q2 机制里强调——`groups`/`conversions` 是**步骤级**，只活在前序 `step_runs`，经 `references` 注入；**只有最终合成字段**进 profile：`work_purpose`/`ranked`/`values`/`likes`/`talents`/`importance`/`intersection`/`misconceptions_cleared`/`internal_external_ratio`/`reclaim_item`/`success_statement`。这直接决定 `compaction.py` 的提取规则。
5. **未读 PRD**：你 §6 标注 ch2/ch5/ch6/ch8 PRD 未读——M4 前必须读，交接文档 §7 已列逐章 step→文档映射。
6. **`conversation_summaries`**：M1 建表，但**实现延迟到 M5 之后**（v1.1 §3.7），不是现在就用。

---

## 6. 结论 / 行动

- **Q1 / Q2 / Q4 已闭环**（以 ADR-001 + v1.1 为准）；Q2 机制描述必须按 §2 修正（从 `references`/前序 `step_runs` 注入，而非 profile）。
- **Q3 现拍板**：`agent_configs` 表存全局 mentor/summary 脚手架 + `llm_roles` 只存核心 system_prompt（hybrid）。
- **文档关系**：`站点重构与开发计划.md` v1.1 为权威主线；本回复 + ADR-001 为补充。建议 Coding Agent 以 v1.1 + ADR-001 + 本回复进入 M0→M6。
- 我会把 v1.1 §M2 的 seed 描述改为 hybrid（agent_configs），并补 README 索引。
