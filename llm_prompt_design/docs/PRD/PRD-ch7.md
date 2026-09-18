# PRD：What Want 平台 · 第七章《找到"真正想做的事"，活出真实的自己》

> 版本：current（2026-08-12 翻新，对齐 chapter_config 新 schema 与 ch04/05/06 契约）
> 实施状态：**开发侧已于 2026-08-14 完成 ch07 全部实施**（含 stale 隔离、ideal_works 白名单、上游门禁双校验）
> 对应章节：原书第七章（想做的事 / 组合收敛章）
> 权威契约：`config/chapters/chapter_config_ch07.json`（运行时唯一消费源）
> 单入口交接：`docs/ch06_落地级步骤设计.md` 同级 `docs/ch07_落地级步骤设计.md`

---

## 1. 需求摘要（原书核心）

第七章是把前几章收集的答案**组合起来**的收敛章。原书核心论点：

1. **放弃"为了将来"的思维**：找到目前最想做的事并认真对待，人才会成长；不要先学"对将来有用的技能"再找想做的事（作者以自己盲目上大学为例）。
2. **"想做的事"即使是假设也没关系**：设立假设 → 行动 → 回顾 → 修正，螺旋上升逐渐接近"真正想做的事"。盲目行动（无假设跳槽十几次）是赌博，不可取。
3. **组合公式**：用"喜欢的事 × 擅长的事"先假设出"想做的事"候选（此阶段**量比质重要**，图 7-2 自由组合）。
4. **工作目的过滤**：用第四章定的"工作目的（work_purpose）"做过滤器——与"想通过工作传递的价值观"直接相关的候选 → **真正想做的事**（作为工作）；无关但仍吸引用户的 → **作为兴趣的想做的事**。
5. **复盘修正**：选定最想先试的假设，行动中回顾、活用，逐步逼近真正想做的事。

---

## 2. 用户旅程与目标

| 阶段 | 用户做什么 | 系统辅助 | 产出 |
|---|---|---|---|
| 进入第七章 | 带着 ch4 工作目的 / ch5 擅长之事 / ch6 喜欢之事 | 导师上下文自动带入三项上游答案 | — |
| Step 1 组合 | 审阅 LLM 生成的 8–15 条"想做的事"候选，增删/改写/锁定 | LLM 交叉组合"喜欢×擅长"，每条标注来源 | `ideal_works`（候选清单） |
| Step 2 筛选定稿 | 用工作目的把候选归入"真正/兴趣"两桶，锁定最想先试的 | LLM 建议分桶、不替用户定性；给下一步行动 | `ideal_works`（带 bucket）+ `next_action` |
| 收尾 | 导出 / 查看自己的"想做的事"清单与复盘计划 | — | 可导出 |

---

## 3. 功能与步骤设计（对齐 config 契约）

### 3.1 步骤结构（2 步级联，与 ch04–ch06 同范式）

| step | 名称 | 角色（既有无新角色） | 输入（跨章） | 输出 |
|---|---|---|---|---|
| step-1 | 组合喜欢×擅长，假设想做的事 | `career_counselor`（职业规划师） | 导师上下文：ch5 `talents`、ch6 `likes` | `ideal_works` + `commentary` |
| step-2 | 用工作目的筛选，定稿真正/兴趣 | `mentor`（导师） | step-1 `ideal_works` + 步骤上下文 + 导师上下文：ch4 `work_purpose`/`values` | `ideal_works`（带 bucket）+ `commentary` + `next_action` |

> 角色映射说明：旧稿曾用 `combination-strategist` / `work-purpose-filter` 两个**新全局角色**，违反"不新增全局角色、章节行为通过 config instruction 注入"的既定规则（ch03 确立）。本章一律映射既有 `career_counselor` / `mentor`，组合/筛选的差异由 `instruction` + `method` 表达，不新建角色。

### 3.2 ideal_works 字段形态（editable_list）

每条候选对象：
- `title`：想做的事标题，建议"一个……的人"句式
- `like_source`（只读）：来自哪条 ch6 喜欢的事（含"方面"），建立与 ch6 的溯源链路
- `strength_source`（只读）：用到哪项 ch5 擅长之事（优先◎级），建立与 ch5 的溯源链路
- `bucket`：枚举 `真正想做的事` / `作为兴趣的想做的事` / `未定`（step-1 默认"未定"，step-2 由用户/LLM 建议定档）
- `locked`：用户锁定后运行时不覆盖

### 3.3 LLM 角色映射（§3.1 细化）

- **step-1 组合（career_counselor）**：读取导师上下文中的 `talents`（含◎〇△评级）与 `likes`（含领域/方面），自由交叉组合 8–15 条候选；每条 `like_source`/`strength_source` 溯源到具体上游项；允许假设、数量优先；不臆造用户未透露的擅长/喜欢。
- **step-2 筛选（mentor）**：读取 `work_purpose` 与 `values`，对候选逐条给分桶建议并说理由；不替用户定档；保留 `locked=true` 项（preserve_output 原样）；输出 `next_action` 复盘计划。

---

## 4. 数据模型与持久化

- **持久键**：`ideal_works`（ch07 唯一新增键），落 `learner_profiles.profile_json`。
- **新增键落库方式**：`ideal_works` 当前**不在** `compaction.py` 白名单，需开发侧在 `PROFILE_FIELDS` / `STRUCTURED_FIELDS` / `MANDATORY_DOWNSTREAM_FIELDS` 三处加入（仅新增一个已存在 `profile_json` 内的键，**ideal_works 自身零新增表/列**），并 reseed 消除 DRIFT。
- **`stale` 列沿用（ch06 第六轮拍板）**：ch07 全部 step-run 读取须带 `AND stale=0`，沿用 ch06 在 `step_runs` 表新增的 `stale INTEGER NOT NULL DEFAULT 0` 列（后端 `init_db()` 幂等补列）；ch07 step-1 重提交时旧 step-2 `stale=1` 且 `profile.ideal_works=[]`（见落地文档 §10）。
- **下游（ch8 施展魔法）**：ch8 将消费 `ideal_works` 作为"想做的事"成品，沿用 `mentor_hooks.references` 跨章读取即可。
- **状态机**：与 ch02–ch06 同构（`/run` → saved 草稿 → 编辑/锁定 → `/submit` 后 `edit_output` 返回 409，不再调 LLM）。草稿持久化契约见落地文档 §8.6。

> 一致性声明：旧稿曾把产出写成 `intersection`——该键已被 **ch03** 占用（三清单字面交集、早期"想做的事"假设），复用会与 ch03 冲突，故本章改用独立键 `ideal_works`。旧稿 `passions[]` / `purpose` 亦为旧口径，本章统一为 `likes` / `work_purpose`。

---

## 5. 跨章依赖（与 ch04/05/06 真实产出对齐）

| 上游章 | 真实产出键（config 字段名） | ch07 用途 | 注入路径 |
|---|---|---|---|
| ch04 重要的事 | `work_purpose`（工作目的）、`values`（核心价值观） | step-1 组合 + step-2 过滤"真正/兴趣"的判断依据 | `step_context.references` + `mentor_hooks.references` |
| ch05 擅长的事 | `talents`（含 `rating`◎〇△、`locked`、`source`） | step-1 组合原料，优先◎级 | `mentor_hooks.references` |
| ch06 喜欢的事 | `likes`（含 `field`/`aspects`/`linked_strengths`/`sources`/`locked`） | step-1 组合原料，拆到"方面"连接擅长 | `mentor_hooks.references` |

- **字段名一致性（已核对，无黑话）**：ch07 消费的 `talents` / `likes` / `work_purpose` / `values` 与 ch04/05/06 实际 emit 的键**完全一致**（ch04 经 top_values→values 别名产出 `values`，无 `importance`——`importance` 属 ch03 早期假设，ch07 不引用）；不再使用旧稿 `passions[]` / `purpose`。
- **ch05/ch06 早已预告下游**：ch05 step-2「第七章将以◎级为主结合『喜欢的事』」、ch06「第七章以『喜欢×擅长组合、用工作目的（含价值观）筛选』」——与本章设计一致，无矛盾（注：ch07 不消费 `importance`，用 `work_purpose`/`values` 过滤，非"三者交集"旧稿）。
- **100 例清单**：ch07 是组合章，无独立 100 例抽屉；其组合原料来自 ch5 `strength_examples`、ch6 `passion_examples`，经导师上下文带入，不另接接口。

---

## 6. 设计判断（关键决策留痕）

1. **为何 2 步而非 1 步**：原书明确"先组合假设、后工作目的筛选"两段；且 ch04–ch06 普遍为 2 步级联，本章保持一致的可编辑分段体验。
2. **为何不用 `intersection`**：该键属 ch03（字面交集），复用会覆盖 ch03 早期假设，造成跨章数据冲突。
3. **为何新增 `ideal_works` 而非复用 `success_statement`**：`success_statement` 语义偏"单句成功陈述"，承载候选清单牵强；`ideal_works` 语义直白、与书词汇一致，仅多一个白名单键。
4. **角色不新增**：组合/筛选差异由 config `instruction`/`method` 表达，遵守 ch03 既定规则。

---

## 7. 开放点与待办

- **开发侧**：① `compaction.py` 白名单加入 `ideal_works` 三处 + reseed；② assembler 实现 ch07 step-1 用 `talents`×`likes` 组合、step-2 用 `work_purpose` 分桶；③ 运行时 gate（双校验，仿 ch06 §8.7）：进入 ch7 前 `context_requirements` 校验 ch04 step-5 / ch05 step-2 / ch06 step-2 均 `submitted & stale=0` 且对应 profile 键非空（`len(likes)>0` 为 ch06 完成判定），任一缺失整章锁定；④ `ideal_works` 嵌套渲染器（同 ch5 `talents`/ch6 `likes` 自定义渲染）；⑤ 契约测试覆盖 ch07（含 stale 隔离：上游重提交后 ch07 门禁回退、step-2 读 step-1 取最新非 stale）；⑥ 草稿真实持久化 + 失败提示；⑦ `ideal_works` 整体导出 UI（用户导出"想做的事清单"）；⑧ **`stale` 列迁移**：`init_db()` 幂等补 `step_runs.stale INTEGER NOT NULL DEFAULT 0`，全量 step-run 读取路径加 `AND stale=0`（含 `context_requirements.get_upstream_context_status`、`references.from_exercise` 解析、`book.py` 进度/状态接口）。
- **题库/资源**：ch7 无独立题库；组合原料依赖 ch5/ch6 已完成。
- **需求覆盖核对**：对照原书第七章，放弃为将来 / 假设可接受 / 组合 / 工作目的过滤 / 螺旋上升 均已覆盖；图 7-2（自由组合）在 mockup 中央区呈现。
