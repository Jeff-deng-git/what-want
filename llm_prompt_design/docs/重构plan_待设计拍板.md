# What Want 全平台重构 · 实施 plan（v2.0 对齐版）

> 文件：`docs/重构plan_待设计拍板.md`（本文档将被同名覆盖）
> 写于：2026-08-03（v2 修订）
> **唯一权威来源**：`docs/工程实施交接文档.md` v2.0（handoff 自标"唯一必须阅读的文档"，§1.4 已内联全部 7 项决策）
> 关联：`docs/ADR-001-exercises-schema.md`（决策溯源）、`docs/重构plan_设计侧回复.md`（评审记录）
> 受众：Coding Agent（执行）+ 晖哥（确认）

---

## 0. v2 修订说明

v1 列了 4 个待拍板问题。handoff v2.0 §1.4 + §7.0 + §9 红线 8 已经把这 4 个全部闭环，本版本把 plan 重写为可直接执行的版本：

- **Q1（章节标识迁移）** → 决策 4：`04-important → ch04` 一次性迁移 + 清 `CH_ID_ALIAS`
- **Q2（step prompt 装配）** → 决策 1+2+3：Option B + `references` 链 + 类型化 `output_fields`
- **Q3（mentor/summary 落库）** → 决策 7 hybrid：`llm_roles` 存核心 system_prompt + `agent_configs` 存全局脚手架
- **Q4（章末桥接卡时机）** → §8.2 + §8.7：所有 step submitted 后默认展示，B+C 组合

新增 v2 提出的问题见 §7（其中 Q1 端口、Q2 配置转换已澄清/闭环；Q3 step_runs.user_id、Q4 ch04 step-5 是否读 ch3 profile 仍待确认）。

---

## 1. 七项决策（直接来自 handoff §1.4，实施时严格遵守）

| # | 决策 | 实现约束 |
|---|------|---------|
| 1 | 运行时契约 = **Option B（exercises 原生）** | `step_runner` 走 `build_step_prompt`，**彻底去掉 jinja2** |
| 2 | 跨步引用 = `exercises[].references: [{from_exercise, fields}]` | 从同章**已 submitted 的前序 `step_runs.parsed_output`** 注入 |
| 3 | `output_fields` 类型化（oneOf） | `{name, type, readonly?, lockable?}`，type ∈ `markdown\|text\|editable_list\|list\|number\|select\|json\|table`；向后兼容字符串 |
| 4 | chapter_id 统一 `ch01..ch08` | `04-important → ch04` 一次性迁移 + 清 `book.py` 的 `CH_ID_ALIAS` |
| 5 | user_id 常量 `DEFAULT_USER_ID = "local"` | profile 主键保留 user_id；前端不改；单用户本地部署 |
| 6 | 前端托管 = `main.py` 用 `StaticFiles` 挂 `frontend/index.html` 到 `:8011/` | API 改相对路径 `/api`；消除 `http://localhost:8011` 硬编码 |
| 7 | `conversation_summaries` M1 建表 + 实现延迟到 M5 之后 | M1 仅建表；M3 mentor 用 `build_mentor_prompt` 截历史兜底 |

**红线 8（§9 补）**：章节**内**级联用 `references` 从**前序 `step_runs`** 注入；跨**章** mentor 锚点读 `learner_profile`。**两者机制不同**，ch4 的 `groups`/`conversions` 不进 profile（它们是步骤级中间产物）。

---

## 2. Plan（M0 → M6，按依赖顺序）

### M0 · 端口确认 + 数据迁移（开工前置）
- 确认实际运行端口：用户 prompt 写 `localhost:3011`，handoff §1.4 决策 6 + 设计侧回复 §5.3 都指出**真实端口应为 8011**。需先与用户确认哪个是真。
- **章节标识迁移脚本** `platform/backend/scripts/migrate_chapter_ids.py`：
  1. 先 `cp data/ww.db data/ww.db.bak-$(date +%Y%m%d)` 强制备份
  2. `grep -rn "04-important"` 全仓确认无残留引用（包括 jinja2 模板、`index.html`、`seed_ch4.py`、前端 step 引用）
  3. `UPDATE step_runs SET chapter_id='ch04' WHERE chapter_id='04-important'`
  4. `UPDATE chapter_configs SET chapter_id='ch04' WHERE chapter_id='04-important'`（标记旧 config 为 inactive）
  5. 删除 `book.py` 的 `CH_ID_ALIAS = {"ch4": "04-important"}`
- **验收**：DB 内无双标识；全仓 grep 无 `04-important`；备份可回滚

### M1 · 数据层
- `app/db.py` SCHEMA 增三张表：
  - `learner_profiles(user_id PK, profile_json, updated_at)`（决策 5：`user_id='local'`）
  - `conversation_summaries(user_id, chapter_id, summary_json, updated_at, PRIMARY KEY(user_id, chapter_id))`（决策 7：建表）
  - `agent_configs(name PK, config_json, updated_at)`（决策 Q3 hybrid：mentor/summary 脚手架落这里）
- `app/services/compaction.py`（**混合策略 §6.3 已拍板**）：
  - **结构化字段**（`values` / `work_purpose` / `talents` / `likes` / `formula` / `misconceptions_cleared` / `milestones`）→ 规则提取
  - **`open_questions`** → 廉价 LLM 提取/改写
  - 输出 ≤800 tok → `save_profile('local', profile)`
- profile 字段键（§6.2 严格对齐）：
  ```
  misconceptions_cleared, external_voices, internal_external_ratio, reclaim_item,
  likes, talents, importance, work_purpose, values, ranked, intersection,
  success_statement, formula, current_chapter, open_questions, milestones
  ```
- 触发点：① 某章**所有 step submitted** 后；② mentor 对话累计 20 轮（建议值）
- **验收**：profile 序列化后 ≤800 tok；缺字段容错；可重跑

### M2 · 配置 / seed
- 新写 `platform/backend/seed_full.py`（覆盖 `seed_ch4.py`）：
  - **灌 `agent_configs`**（决策 Q3 hybrid）：
    - `name='mentor'` ← 读 `mentor_config.json`：persona 长描述 + `sample_dialogue` + `exercise_informed_dialogue` + `context_budget` + DEFAULT `MENTOR_HOOKS`
    - `name='summary'` ← 读 `summary_config.json`：persona + output_schema + md_cap + per_chapter_focus
  - **灌 `llm_roles`**（仅核心 system_prompt）：
    - 新增 `name='mentor'`（核心人设 + grounding_rules 文本）+ `name='summary'`（核心人设）
    - 各章 `llm_role=assist` 角色（沿用 `psychologist` / `career_counselor` 等，按 ch4 §3.1 提示词）
  - **灌 `chapter_configs`**（决策 1 + 4）：
    - 8 章 `chapter_id='chNN'`（**M0 已迁移**）
    - `config_json` 来自 `chapter_config_chNN.json`，**直接含 `exercises[].references` + 类型化 `output_fields`**
    - **`mentor_hooks` 留 `chapter_configs` 不搬**（决策 Q3 hybrid）
- 校验：seed 完成后用 `jsonschema` 校验每章 config 匹配 `chapter_task_config.schema.json`
- **验收**：DB 三张配置表均填充；seed 可重跑（幂等）；jsonschema 校验通过

### M3 · 运行时接入（灰度，旧路由保留可回滚）
- **新增** `app/runtime/agent.py:run_step()`（决策 1 + 2）：
  ```
  def run_step(chapter_id, step_index, user_input):
      cfg = load_chapter_config(chapter_id)
      exercise = cfg['exercises'][step_index]
      step_role = load_role(cfg['step_role_id'])  # 本章 step 使用的 LLM 角色(psychologist/career_counselor 等)，键名以 schema/M2 为准
      mode = exercise['llm_role']                # assist/guide/none —— 是「辅助模式」不是角色名，决定 LLM 如何协助
      prior = load_prior_outputs(chapter_id, exercise['references'])  # ← 前序 step_runs.parsed_output
      system = role['system_prompt'] + chapter.core_concepts + chapter.guiding_questions
      user = exercise['user_action'] + few_shot + user_input + prior  # prior 由 build_step_prompt 的 ≤3k 护栏裁剪，勿全量注入前序输出
      raw = call_llm(json_mode=...)
      parsed = parse_by_output_fields(raw, exercise['output_fields'])
      save_step_run(parsed)
      if all_steps_submitted(chapter_id):
          compaction.run('local', chapter_id)
      return parsed
  ```
- **`assembler.py` 新增** `build_step_prompt(role_system, chapter_cfg, exercise, prior_outputs, user_input)`，受 ≤3k 护栏约束
- `chat.py` 改调 `run_mentor(chapter_id, user_id='local', content, history)`；删硬编码 system + `md[:12000]` + `HISTORY_LIMIT=10`
- `summary.py` 改调 `run_summary(chapter_id)`；删 `SUMMARY_SYSTEM` 常量
- 旧 `step_runner.run_step_legacy()`（jinja2 路径）保留，`WW_LEGACY_STEPS=1` env 切换
- **验收**：路由全部走新路径；旧路径仍可启动；同一 chapter 不同 step 输出与现有 pytest 不冲突

### M4 · 逐章 step（按 §7 实施指南）
- ch01-08 全部按 `chapter_config.exercises` 跑通
- 关键差异：
  - **ch04**（5 步级联，决策 2）：`references` 链 step-2←step-1.top_values → step-3←step-2.groups → step-4←step-2.groups+step-3.conversions → step-5←step-4.ranked
  - **ch07**（上游依赖，§7.7）：进入时检查 ch3 的 `likes/talents/importance` + ch4 的 `work_purpose`；缺失则**整章锁定**（半透明遮罩 + 「请先完成第 3/4 章」卡 + 直达按钮），参照 PRD-ch4 §1.6 gating
  - **ch08**（终点章，§7.8）：mentor_hooks.references=`[values, work_purpose, talents, likes]`，profile 综合引用最广
- **M4 前必读**：PRD-ch2 / PRD-ch5 / PRD-ch6 / PRD-ch8（handoff §6 我未读的 4 份）
- **验收**：端到端跑 ch01-08 各 1 step submit → profile 字段逐步累加；ch4 5 步级联链路通

### M5 · 前端桥接卡 + 配置改造
- **决策 6 落地**：`main.py` 加 `StaticFiles` 挂 `frontend/` 到 `:8011/`；前端把所有 `http://localhost:8011` 改为相对路径 `/api`
- `renderStepOutput` 按 `output_fields` 类型分支（决策 3）：
  - `markdown` → 直接渲染
  - `text` → 文本
  - `editable_list` + `lockable=true` → 复用现有 `renderEditableList`（chip + 🔒）
  - `editable_list` + `readonly=true` → chip + ▲▼ 排序（step-4 ranked 既有）
  - `list` → 只读列表
  - `table` → `experience_map` 行渲染
  - `json` → 折叠 JSON
  - 关键补：**`groups`**（umbrella+keywords 卡片组）+ **`conversions`**（other/self + why_chain）
- **章末桥接卡 B**（§8）：
  - 触发：进入章末视图（§8.2 满足条件 = 本章所有 step submitted）；同时「回顾」链接可触发
  - 内容：读 `learner_profiles` 中该章 `mentor_hooks.references` 指向字段（回退 `output_fields`）
  - profile 空时显示**空态卡**（"完成本步后，这里会浮现你的人物画像"），**不重算 LLM**
  - CTA「和刘老师聊聊这一步 ▸」→ 切对话 tab，预填 `chapter_id + step_id`，**不自动发送**
- 三种入口连通：① 顶部 sticky「问刘老师」/ ② 步进浮层 / ③ 章末卡（§8.5）
- **验收**：Step 2 / Step 3 不再裸 JSON；三种入口均可用；profile 空时不报错

### M6 · 验收（按 handoff §10）
- pytest 全绿（现有 7 文件 + 新增 `runtime/test_assembler.py` / `services/test_compaction.py`）
- 冒烟脚本 `scripts/smoke.sh`：seed → 8 章各 1 step submit → profile 字段校验 → mentor / summary 调用成功
- §10 验收清单逐项打钩（数据层 / 配置 / 运行时 / 逐章 / 前端 5 块）

---

## 3. 复用 vs 重写（handoff §4）

**复用**：
- FastAPI app 结构 / `app/db.py` 连接 / Pydantic 模型基类
- 前端 `index.html` 三栏布局外壳 / 选区笔记 / 目录 / 进度保存 / 摘要 tab
- `chapter_md/` 八章正文
- seed 脚本模式（`seed_ch4.py` → `seed_chapters.py`）
- `SPEC.md` 步骤运行器模式（⚠️ 已于 2026-08-03 对齐重构；原版备份 `llm_prompt_design/backups/SPEC.orig-2026-08-03.md`；**无需再改 SPEC**，冲突以 SPEC 当前版为准）

**重写 / 新增**：
1. M1：3 张新表 + compaction
2. M2：`agent_configs` + `seed_full.py` + jsonschema 校验
3. M3：`build_step_prompt` + `run_step` 接入，旧路由灰度保留
4. M5：决策 6（前端托管）+ `renderStepOutput` 类型分支 + 章末卡
5. M4：按 §7 把 ch1-8 全实现

---

## 4. 边界与红线（handoff §9）

1. ≤3k token 护栏：先截历史，再退化「仅档案+钩子」，**绝不**全量注入 step_runs
2. 配置真相在 DB：`config_loader` 读 DB；JSON 仅 seed 源
3. `learner_profiles` 按 `user_id='local'` 隔离
4. LLM 按 `llm_role` 仅辅助，**不**替用户下结论
5. 保留 `step_runs`，新增 3 张表，**不破坏旧结构**
6. 灰度可回滚（M3）
7. chapter_id 统一 `ch01..ch08`（M0）
8. **章节内级联走 references → 前序 step_runs；跨章 mentor 锚点才读 profile**

---

## 5. 与评审历史的关系

- `docs/重构plan_设计侧回复.md` §5 列了 6 项补充点，全部已被 handoff v2.0 内联：
  - `user_id='local'` → 决策 5
  - 前端 `:8011/` 托管 → 决策 6
  - 端口真实 8011 → 决策 6（**与用户 prompt 的 3011 冲突，见 §7 Q1**）
  - profile 字段边界（`groups`/`conversions` 不进 profile）→ 红线 8
  - 未读 PRD → 已在 §2 M4 标注
  - `conversation_summaries` 延迟实现 → 决策 7
- `重构plan_待设计拍板.md`（v1）保留作为历史，M1-M6 与本文档一致，仅 Q2 机制描述被红线 8 取代

---

## 6. 关键文件路径速查

| 用途 | 路径 |
|------|------|
| 唯一权威 | `llm_prompt_design/docs/工程实施交接文档.md` |
| 决策溯源 | `llm_prompt_design/docs/ADR-001-exercises-schema.md` |
| 配置契约 | `llm_prompt_design/config/schema/chapter_task_config.schema.json` |
| 8 章配置 | `llm_prompt_design/config/chapters/chapter_config_chNN.json` |
| 导师配置 | `llm_prompt_design/config/mentor/mentor_config.json` |
| 摘要配置 | `llm_prompt_design/config/agents/summary_config.json` |
| 8 章 PRD | `llm_prompt_design/docs/PRD/PRD-chN.md` |
| 运行时骨架 | `platform/backend/app/runtime/` |
| 现有 DB schema | `platform/backend/app/db.py` |
| 待改造 routers | `platform/backend/app/routers/{chat,summary,steps}.py` |
| 待改造 step runner | `platform/backend/app/services/step_runner.py` |
| 前端 | `platform/frontend/index.html` |

---

## 7. v2 仍待确认的问题（4 项）

### Q1 · 真实端口到底是 3011 还是 8011？—— ✅ 已澄清（按 8011 推进）
- **根因（2026-08-03 实测 `app/config.py`）**：后端监听端口 `BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8011"))` → **后端真实端口 = 8011**。你记忆里的 `3011` 来自 `config.py` 里另一行 `FRONTEND_ORIGIN = "http://localhost:3011"` —— 这是个**陈旧的默认环境变量**（前端源地址），并非后端端口，也不是真实运行端口。前端 `index.html` 本身硬编码的就是 `localhost:8011`。
- **结论**：按 **8011** 推进，无需确认。决策 6（后端 `StaticFiles` 挂 `frontend/` 到 `:8011/`，API 改相对 `/api`）落地后，`FRONTEND_ORIGIN` 这个变量将不再需要（同端口同源），M5 顺手把 `config.py` 的 `FRONTEND_ORIGIN` 默认值从 `3011` 改为 `http://localhost:8011` 或直接删掉该变量，消除历史误导。
- **开工前动作**：`python platform/backend/run.py` 起服务，`curl http://localhost:8011/api/health` 应返回 `{"ok": true}`；前端访问 `http://localhost:8011/`。

### Q2 · ch1-3/5-8 配置的 `output_fields` 字符串写法，M2 是否批量转对象？—— ✅ 已闭环（无需再问）
- **现状（2026-08-03 复核）**：**8 章 config 的 `output_fields` 已全部是类型化对象**，不再是字符串数组。这是 T-A 步骤（把 ch01–03、ch05–08 七份转类型化）已完成的事实，Python 结构校验 8 章均 `all typed? True`；ch04 为 canonical。
- **结论**：决策 3（推荐对象写法）**已由设计侧落地**，M2 的 seed 只需用 `jsonschema` 校验，无需再做转换。原"抽样看过仍是字符串"的判断已过时，请勿据此让 coding agent 重转。
- 类型映射已固化：ch1 `misconceptions_cleared`=editable_list(lockable)+`external_voices`=markdown；ch2 `internal_external_ratio`=table+`reclaim_item`=text(lockable)；ch3 四字段=editable_list(lockable)；ch5 `talents`/ch6 `likes`/ch7 `intersection`=editable_list(lockable)；ch8 `success_statement`=text(lockable)+`color_bath_log`=table。

### Q3 · step_runs 是否加 `user_id` 列？
- **冲突点**：决策 5 说 `DEFAULT_USER_ID='local'` 写到 profile；handoff §9 红线 5 说"不破坏 step_runs"——但当前 `step_runs` 表无 `user_id` 列
- **选项**：
  - **A · 不加列**：保持兼容，`step_runs` 视为当前 user 的数据；M3 加 ALTER 防御性兼容（与现有 `init_db()` 一致）
  - **B · 加列**：M1 加 `step_runs.user_id TEXT NOT NULL DEFAULT 'local'`，索引 `(user_id, chapter_id, step_id)`
- **建议 A**（红线 5 优先；多用户能力靠 profile 表主键预留即可，step_runs 单一用户场景不需要）

### Q4 · ch04 step-5 是否需要读 ch03 profile 的 likes/talents？
- **现状**：handoff §7.4 ch04 表写 step-5 references=`step-4.ranked`，**没有 references profile**；但 ch4 是工作目的，理论上应参考 ch3 的 likes/talents 才能定得准
- **选项**：
  - **A · 不读 profile**：step 模式严格按 references 链（决策 2 边界清晰），ch3 引用交给 ch7/ch8 的 mentor 锚点
  - **B · 扩展 references 支持 profile**：schema 加 `from_source: "profile"` 选项
- **建议 A**（决策 2 红线 8 明示"两者机制不同"；ch4 step-5 只看 ranked + step-4 之前的 step 数据，符合设计边界；ch3 的引用确实重要，但可由 ch4 mentor 钩子或 ch5/6/7 自然衔接）

---

## 8. 防跑偏最后清单（handoff §11 + §7.9）

- ❌ 不要重写 role system prompt → 从 `PRD-chN §3.1` + `config/*` 取
- ❌ 不要全量注入章节 MD → 按 `assembler` 切片（`md[:md_cap]` + 钩子选段）
- ❌ 不要新增 output 字段名 → 必须与 `chapter_config.output_fields` 一致
- ❌ 不要跨用户共享档案 → `learner_profiles` 按 `user_id='local'` 隔离
- ❌ 不要从 `learner_profile` 拉 `groups`/`conversions`（红线 8）
- ❌ 不要新增 jinja2 模板（决策 1：彻底去掉）
- ❌ 不要把 mentor `persona/hooks` 塞 `llm_roles.system_prompt`（决策 Q3 hybrid：分 `agent_configs`）

---

## 9. 等 Q1-Q4 答复后开工顺序

拿到答复（即便只确认"按你建议执行"）→ M0（端口确认 + 04-important 迁移）→ M1（数据层）→ M2（seed）→ M3（runtime）→ M4（逐章）→ M5（前端）→ M6（验收）。
