# 问题清单跨章统一（方案A）变更清单与开发侧待办

> 生成时间：2026-08-13
> 范围：ch04 / ch05 / ch06 对「30 问 + 100 例清单」的处理口径统一为 ch06 标准
> 决策来源：用户拍板「方案A」——四五六章统一为 ch06 标准（30问 + 100例全部固化进 config，前端读 config 即生效）

---

## 1. 背景与决策

- 原状：ch04 / ch05 / ch06 对「问题清单（30 问 + 100 例）」的处理口径逐章加深——ch04 最浅（仅 PRD/落地规划性描述，config 未接）、ch05 仅接了 100 例（`ui_context.strength_examples`）、ch06 最全（30问 `passion_questions` + 100例 `passion_examples` 均固化）。
- **实测事实**（以 config 为唯一权威核实，非文档）：方案A 落地前，ch04 的 step-1 `input_schema` 既无 30问 字段、也无 100例 数据源（旧文档称"数据源 `chapter_md/问题清单.md`"属规划残留，并未固化）；ch05 仅有 100例（strength_examples），30问 未接。
- 用户拍板方案A：统一为 ch06 标准，30问 + 100例 全部固化进各自章节 config，前端读已加载的章节 config 即生效，不再依赖 `chapter_md/问题清单.md` 或单独题库接口（30问 仍走 questions 服务 + `book_notes` 持久化，但字段已写入 `input_schema`，属配置即生效）。

---

## 2. 本次 config 改动（设计侧已落地，SCHEMA PASS，已备份）

| 文件 | 改动 | 性质 |
|---|---|---|
| `config/chapters/chapter_config_ch04.json` | step-1 `input_schema` 新增可选字段 `value_questions`（`list_of_items`，item=`{question_id:number(q_order 1–30), question?:text, answer:text}`）；顶层新增 `ui_context.values_examples`（100 项，价值观名+描述） | 纯增量 |
| `config/chapters/chapter_config_ch05.json` | step-1 `input_schema` 新增可选字段 `talent_questions`（`list_of_items`，item=`{question_id:number(q_order 31–60), question?:text, answer:text}`） | 纯增量（100例 `ui_context.strength_examples` 方案A 前已固化，未动） |
| `config/chapters/chapter_config_ch06.json` | 未改（作为基准：已有 `passion_questions` + `ui_context.passion_examples`） | 基准 |
| `config/chapters/chapter_config_ch07.json` | 未改（`step_context`/`mentor_hooks` 引用 `[talents, likes, work_purpose, values]`，与本次字段无关） | 零影响（已实测） |

- q_order 全局区间（seed_questions.py 实测）：价值观 1–30、才能 31–60、热情 61–90。
- 校验：`config/schema/chapter_task_config.schema.json` Draft7 校验 **PASS**；ch04/ch05 无重复字段；ch07 未受影响。

---

## 3. 本次文档同步改动（设计侧已改）

| 文件 | 改动要点 |
|---|---|
| `docs/ch04_落地级步骤设计.md` | §3 step-1 补 `value_questions`（30问可选发现辅助）描述；§7「100 例清单」数据源改为 config `ui_context.values_examples`；§10/§11 把"题库注入方式"更新为方案A 收口口径（100例已固化 config 即生效、30问经 `value_questions`）；删除/更正"数据源 `chapter_md/问题清单.md`"旧表述 |
| `docs/ch05_落地级步骤设计.md` | §3 step-1 补 `talent_questions`（30问可选发现辅助）描述；注明 100例 已固化 `ui_context.strength_examples` |
| `docs/PRD/PRD-ch4.md` | step-1 `input_schema` JSON 片段补 `value_questions`；§1 新增"配套资源（方案A 收口）"说明 `values_examples` / `value_questions` 来源 |
| `docs/PRD/PRD-ch5.md` | step-1 `input_schema` JSON 片段补 `talent_questions`；§1.5 配套资源注明 30问/100例 已固化进 config |

---

## 4. 备份清单（`docs/backups/`，后缀 `pre-A-2026-08-13`）

- `chapter_config_ch04.json.pre-A-2026-08-13`
- `chapter_config_ch05.json.pre-A-2026-08-13`
- `ch04_落地级步骤设计.md.pre-A-2026-08-13`
- `ch05_落地级步骤设计.md.pre-A-2026-08-13`
- `PRD-ch4.md.pre-A-2026-08-13`
- `PRD-ch5.md.pre-A-2026-08-13`

> 回滚：任一文件异常，用对应 `.pre-A-2026-08-13` 覆盖即可。

---

## 5. 冲突安全分析（用户重点要求：不影响已有功能、不产生冲突）

- **纯增量**：新增 `value_questions` / `talent_questions` 均为 step-1 `input_schema` 的**可选**字段（`required:false`），存 `user_answers` / `step_run`，**不进入 `learner_profile`**，不新增/不改任何 output 字段、不改动 `step_context` / `mentor_hooks` / `ui_context.references`。
- **100例 数据源变更**：`ui_context.values_examples` / `strength_examples` / `passion_examples` 均为 schema 已有可选键，仅扩充内容（ch04 由"无"变"100项"），不影响其他章节。
- **ch07 零影响（实测）**：ch07 `step_context.references` / `mentor_hooks.references` 均为 `[talents, likes, work_purpose, values]`（章节产出键），与本次 30问/100例 输入字段无关；assembler 跨章注入只读 `step_context.references`，存在时绝不回退 `mentor_hooks`，故不存在字段泄漏。
- **compaction 白名单无需改**：30问/100例 均不落 `learner_profile`，白名单（`PROFILE_FIELDS` / `STRUCTURED_FIELDS` / `MANDATORY_DOWNSTREAM_FIELDS`）不受影响。
- **结论**：方案A 为向后兼容的纯配置增量，不破坏既有功能、不与任何现有字段/流程冲突。

---

## 6. 开发侧待办 / 需注意（请开发处理，设计侧不动代码）

1. **reseed**：重新发布 ch04、ch05 active config，消除 `check_config_consistency.py --chapter ch04/ch05` 的 DRIFT（新增 `ui_context.values_examples` / `value_questions` / `talent_questions` 需进 DB）。
2. **30问 接入**：`value_questions` / `talent_questions` / `passion_questions`（ch06）答案走 questions 服务接入 + `book_notes` 持久化；前端运行 step-1 前按 `q_order`（价值观 1–30 / 才能 31–60 / 热情 61–90）取回填入对应 `input_schema` 字段。**不进入产出（`top_values`/`talents`/`likes`）、不流下游。**
3. **100例 抽屉改读 config**：ch04 前端「100 例清单」抽屉数据源由 `chapter_md/问题清单.md` 改为已加载章节 config 的 `ui_context.values_examples`；ch05 已是 `ui_context.strength_examples`；ch06 已是 `ui_context.passion_examples`。**不再另接 `chapter_md` 读取路径。**
4. **引用落点**：ch04 100例 引用项写入 step-2 `supplemental_keywords`（既有设计，未变）；ch05/ch06 引用项写入各自既有的 `reference_strengths` / `reference_talents`。
5. **契约测试（可选）**：`check_config_consistency.py` 可扩展覆盖 `ui_context.values_examples` 与题库 `q_order` 漂移（ch03/ch04 同性质问题）。
6. **回归验证**：跑 `test_m4_ch04_cascade` / `test_m4_ch05_cascade`（及 ch06 既有测试），确认新增字段不改变既有 5 步 / 2 步级联与 `preserve_output` 行为；确认 ch07 进入时 `step_context` / `mentor_hooks` 引用仍仅 `[talents, likes, work_purpose, values]`。
