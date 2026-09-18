# ch04→ch07 stale 一致性 —— 开发侧唯一对接文档（2026-08-14 修正：ch04/ch05 级联 stale 待实施）

> **本文是 ch04 / ch05 / ch06 / ch07 四章 stale 隔离与跨章一致性机制的唯一切面文档。开发侧只需持此一份即可掌握全部相关信息，无需再翻阅四份落地文档。**
> 四章开发实施状态（**2026-08-14 实测，非凭空标注**）：**ch06 / ch07 的 stale 级联已实施**（`app/routers/steps.py:669-689` 硬编码实现，前端 `ch06-stale` 提示已存在）；**ch04 / ch05 的 stale 级联待实施**（开发侧实测：后端无 `mark_downstream_stale`/`clear_chapter_profile_keys`，submit 仍为通用路径，前端 ch04/ch05 无修改入口）。本文对 ch04/ch05 是设计规格，对 ch06/ch07 是已落地追溯。
> 本文是 `docs/ch04_落地级步骤设计.md` §8.6 的**可执行落地版**（设计侧已拍板三件事：级联传播边界 / profile 失效粒度 / 用户提示），给出精确代码位置与算法；并新增 **§8** 覆盖 ch05/ch06/ch07 的上游消费、门禁与映射修正，使开发侧一眼看全局。
> 各章字段级契约（exercises / input_schema / output_schema / 三路上下文）的权威源仍是各自 `config/chapters/chapter_config_ch0X.json`，本文只讲 **stale / 一致性** 这一跨章横切面。
> **例外**：§10 是 2026-08-29 追加的 ch04 step-2「未分组关键词池」字段契约与交互变更（与 stale 无关）。因开发侧交接入口已收敛到本文，故一并纳入，不再另发文档。

> **⚠️ 设计侧交叉验证（2026-08-14，回应开发侧反馈）**：本文「ch04/ch05 待实施」结论已对照实际代码核验，非凭信任标注——
> - 全仓 grep `mark_downstream_stale` / `clear_chapter_profile_keys`：**零命中**（仅本文档三处出现），证实后端无此 helper；
> - `app/routers/steps.py` 的 `submit_step`（611 行起）：**仅 ch06（669-674 行）、ch07（680-687 行）有硬编码 stale 标记块**；ch04/ch05 提交后直接走 `_maybe_compact`，**无任何 stale 逻辑**；
> - ch06/ch07 的 stale SQL 均用 `status IN ('saved','submitted')`（steps.py:673、685），证实「草稿一并置 stale」比仅标 `submitted` 更安全；
> - 前端 `platform/frontend/index.html`：仅 ch06 存在 `class="ch06-stale"` 的「已过期」提示（文案「这一步的历史结果已过期，因为第一步有新的提交。请重新运行第二步」）；**「修改前提醒」弹窗在整包前端不存在**；ch04/ch05 无任何过期提示 / 修改入口。
> **结论**：开发侧 2026-08-14 提出的 5 点修正全部属实，本文已据此收口。后续任何「已实施」状态，均以开发侧实测 / 代码提交记录为准，设计侧不超前标注。

---

## 0. 业务问题（一句话）
ch04 是 5 步强级联（step-1 5问 → step-2 思维导图 → step-3 可控性 → step-4 金字塔 → step-5 工作目的）。用户回退改前序步并重提交后，后续步仍是旧输入推导的结果，但界面照常显示「已完成/已锁定」，且 `values`/`ranked`/`work_purpose` 仍留在 profile 被 ch7/ch8 消费——产生跨章脏数据。需在该重提交发生时，把下游步标过期、把 profile 三键清空。

**现状（实测）**：后端 `step_runs.stale` 列已随 ch06 实施存在（`app/db.py init_db()` 幂等迁移）；`_maybe_compact`（steps.py:541）只在全章 5 步全 `submitted` 且 `stale=0` 时写 profile。因此非末步重提交后 compaction 自动跳过、profile 残留——**必须显式清空三键兜底**。ch04 config 无需改（级联靠既有 `references.from_exercise`）。

---

## 1. 设计拍板结论（三件事）

| # | 问题 | 拍板 | 理由 |
|---|---|---|---|
| 1 | 级联传播边界 | 重提交 step-k → **所有 step-j（j>k）`stale=1`** | 严格线性链，任一步都依赖前序；1 对多整体失效 |
| 2 | profile 失效粒度 | 清空 **`values` + `ranked` + `work_purpose`** 三键 | 三者须作为同一组一致（ch7 同时读 work_purpose+values、ch8 读 ranked/values）；部分清空会错配 |
| 3 | 用户提示 | step-(k+1)…step-5 显示「已过期，请重新运行并提交」 | 替代「已完成/已锁定」假象 |

---

## 2. 级联算法（伪代码，开发侧实现参考）

```
def get_downstream_steps(chapter_id, step_id) -> list[str]:
    # 按 config exercises[].references.from_exercise 求传递闭包
    cfg = load_chapter_config(chapter_id)
    adj = {ex.step_id: [r.from_exercise for r in ex.references] for ex in cfg.exercises}
    downstream, stack = set(), [step_id]
    while stack:
        s = stack.pop()
        for nxt in adj.get(s, []):
            if nxt not in downstream:
                downstream.add(nxt); stack.append(nxt)
    return sorted(downstream)   # ch04: 重提交 step-1 → {step-2,3,4,5}

def mark_downstream_stale(chapter_id, re_submitted_step_id):
    downstream = get_downstream_steps(chapter_id, re_submitted_step_id)
    if not downstream:
        return  # 末步重提交，无下游
    conn.execute(
        "UPDATE step_runs SET stale=1, updated_at=datetime('now') "
        "WHERE chapter_id=? AND step_id IN (...) AND status IN ('saved','submitted') AND stale=0",
        (chapter_id, *downstream))

def clear_chapter_profile_keys(chapter_id, keys):
    # keys = ["values","ranked","work_purpose"]（ch04 独占写入键）
    profile = load_profile(user_id) or {}
    for k in keys:
        profile.pop(k, None)   # 或置 []/"" ；移除后门禁按 key 缺失判定
    save_profile(user_id, profile)
```

> **与 ch06 行为对齐（2026-08-14 开发侧建议）**：ch06 现网实现将 `saved` 草稿态 **与** `submitted` 一并置 `stale`，比仅标 `submitted` 更安全（避免旧草稿被误提交成「已完成」）。ch04/ch05 统一采用 `status IN ('saved','submitted')`，见上方 SQL。✅ 开发侧确认：ch04 依赖图（step-4 同时依赖 step-2 与 step-3）由本传递闭包算法正确覆盖，无冲突。

**接入点**：`app/routers/steps.py` 的 `submit_step`（约 610 行起）。在「写入新 submitted run」之后、`_maybe_compact` 之前，若 `re_submitted_step_id` 非末步，于**同一 DB 事务**内依次调用 `mark_downstream_stale` + `clear_chapter_profile_keys`。

---

## 3. 后端需改动 / 新增的代码位置（精确）

| # | 文件:行 | 改动 | 说明 |
|---|---|---|---|
| A | `app/routers/steps.py:610` `submit_step` | **新增** 非末步重提交的级联 stale 事务（写新 run → `mark_downstream_stale` → `clear_chapter_profile_keys`） | ch04 核心新增逻辑；建议抽成通用 helper 供 ch06 复用 |
| B | `app/services/step_runner.py`（或 steps.py） | **新增** `mark_downstream_stale` + `clear_chapter_profile_keys` 两个 helper | 按 §2 算法；ch06 的 step-1→step-2 特例应重构为此通用版 |
| C | `app/db.py init_db()` | **无需改** | `step_runs.stale` 列已随 ch06 存在，ch04 复用 |
| D | `app/routers/steps.py:541` `_maybe_compact` | **无需改**（已带 `AND stale=0`） | 全章非全 latest 时自动跳过，配合本机制 |
| E | `app/routers/steps.py:559` | **无需改**（已带 `AND stale=0`） | 取最新非 stale run |
| F | `app/runtime/agent.py:171` `_load_prior_outputs` | **无需改**（已在 ch06 12 入口内，带 stale=0） | ch04 step 注入上游（references.from_exercise）取非 stale |
| G | ch06 第六轮回复 §4 的 12 个 stale 过滤入口（book.py:160,376 / steps.py:207,226,484,521,740 / agent.py:171 / chat.py:98,117 / services/step_runner.py:48 / context_requirements.py:57-61） | **复用，章节无关** | ch04 的进度/状态/草稿/当前结果/提交/导师上下文读取均被覆盖，无需新增 |
| H | `app/routers/book.py:160,376` | **复用**（已在 12 内） | ch04 章首页进度、章状态接口过滤 stale=0，避免误显「已完成」 |
| I | `app/routers/chat.py:98,117` | **复用**（已在 12 内） | ch04 导师上下文加载过滤 stale=0（含 ch3 `importance` 锚点不受影响） |
| J | `frontend`（步骤 runner UI） | **新增** 修改前提醒弹窗 + 重提交后过期提示 | 依据落地 §8.6 / PRD-ch4 §1.8：① 点击「**有下游消费者**」的已 submitted 步（改了会让本章后续步失效）的「修改」先弹确认（说明下游失效 + 档案清空风险；**末步/无下游消费者弱化或省略**）；② 被改步重提交后，其下游步导航/结果区显示「已过期，请重新运行并提交」；前端通用能力，**ch04 step-1～4、ch05/ch06/ch07 的 step-1 这类「有下游消费者」的步复用**（ch05 已按 §9 选项 A 对齐） |
| K | `frontend`（ch04 step-2 视图） | **新增** 「未分组关键词池」区与双向归属交互 | 与 stale 无关，属 ch04 step-2 字段契约 + 交互变更；**完整清单见 §10**（K1–K8），权威契约为 `config/chapters/chapter_config_ch04.json` step-2；**待开发侧实施** |

> **实施状态（2026-08-14 修正）**：⚠️ 本文 A（级联 stale 事务）、B（两 helper）、J（前端提醒）及「ch05 选项 A」此前被误标为「已由开发侧实现」，**经 2026-08-14 开发侧实测均尚未实现**：后端无 `mark_downstream_stale` / `clear_chapter_profile_keys`，ch04/ch05 的 `submit` 仍为通用路径，前端 ch04/ch05 已提交步骤仅有「对话」按钮、无任何修改入口 / 修改前提醒 / 下游过期提示。现更正为**待开发侧实施**（设计已拍板，本文即实施清单）。C–I 复用结论仍成立（ch06 已铺好共享基础设施），但 ch04/ch05 级联逻辑需新写。

---

## 4. 与 ch06 的差异（避免过度设计）
- ch04 **不需要** ch06 式 canonical 写入规则（方案 A）：ch04 各步产出字段名互不重复（仅 `top_values`→`values` 别名），无同名 `likes` 隐式合并污染，通用 `_flatten_outputs` 即可安全合并。
- ch04 难点是**级联传播（1 对多）**，ch06 是 2 步特例（1 对 1）。**新通用 helper（`mark_downstream_stale` + `clear_chapter_profile_keys`）仅供 ch04/ch05 使用**；**ch06/ch07 已实现的硬编码逻辑保持不动**（开发侧已测试通过，零回归风险），不重构 —— 避免改动已验证章节引入回归。

---

## 5. profile 失效粒度说明（为什么清三键）
- `values` 源自 step-1 `top_values`（step-1 重提交即过期）；
- `ranked` 源自 step-4（step-2/3 重提交即过期）；
- `work_purpose` 源自 step-5（step-4 重提交即过期）。
- 三者经 ch7（work_purpose+values）、ch8（ranked+values）成对/成组消费；统一清空保证下游读到「全缺失」而非「旧值 + 空值」错配。重走全 5 步后 `_maybe_compact` 一次性重写三键为一致版本。

---

## 6. 回归用例（契约测试必覆盖）
1. step-1 重提交 → step-2/3/4/5 的 `submitted` run 全部 `stale=1`；`profile.values/ranked/work_purpose` 缺失；ch7 门禁回退锁定（work_purpose 缺失）。
2. step-2 重提交（step-1 已 current）→ step-3/4/5 `stale=1`；profile 三键清空。
3. step-3 重提交 → step-4/5 `stale=1`；profile 三键清空。
4. step-4 重提交 → step-5 `stale=1`；profile 三键清空。
5. **末步 step-5 重提交（前 4 步均非 stale）→ `_maybe_compact` 正常重写三键，不触发清空**（安全路径）。
6. step-1 重提交事务中途失败（如清空失败）→ 整体回滚，新 step-1 run 不残留、下游未标 stale、profile 未改。
7. stale 后重走全 5 步并全提交 → `_maybe_compact` 写出新的 `values/ranked/work_purpose`，ch7 门禁解锁。
8. `stale=1` 历史 run 不进导师上下文 / summary / ch7 / ch8 / compaction（由 12 过滤入口 + `_maybe_compact` stale=0 保证）。
9. **前端提醒（J，待开发侧实施）**：ch04 当前连「修改 / 重新填写」入口都无（已提交步骤仅有「对话」按钮）。J 实际范围 = ① 先补 ch04 step-1～4、ch05 step-1 的修改入口；② 点击修改先弹确认提醒（含下游失效 / 档案清空风险）；③ 上游重提交后，ch04 step-2～5、ch05 step-2 显示「已过期，请重新运行并提交」，且 ch7 门禁回退锁定；重走全步并提交后提示消失、档案键重写。保留作契约测试基线。
10. **ch05 选项 A 回归（2026-08-14 拍板，待实施）**：ch05 step-1 重提交 → step-2 `stale=1` + `profile.talents` 缺失；ch7 门禁因 `talents` 缺失回退锁定；重走全 2 步并提交 → `_maybe_compact` 重写 `talents`，ch7 解锁。该行为将复用 §2 新增通用 helper（仅 ch04/ch05 使用），无新增逻辑。

---

## 7. 设计文档改动点（设计侧已落地，供追溯）
- `docs/ch04_落地级步骤设计.md` §8.1（stale 列复用说明）、§8.5（改动范围补级联 stale）、**新增 §8.6 级联 stale 隔离与 profile 失效（权威口径）**、§10 开发侧待办（新增级联 stale 条目）。
- 备份：`docs/backups/pre-ch04-stale-2026-08-14_ch04_落地级步骤设计.md`、`pre-ch04-stale-2026-08-14_PRD-ch4.md`。
- config / schema / 白名单**无需改**（级联靠既有 `references.from_exercise`；三键已在 `compaction.py` 白名单与 `PROFILE_FIELD_ALIASES`）。

> 实施边界：本机制只影响 ch04 级联与 ch04 自有 profile 键，**不改变全局 `compact_profile` 语义、不碰 ch03/ch05/ch06/ch07 的字段或契约**。ch04 重提交导致的 ch7/ch8 过期由「profile 三键清空 + 下游门禁缺失判定」双重兜底拦截。

---

## 8. 跨章联动总览（ch04→ch07 的 stale 一致性与上游映射 —— 开发侧唯一需知的全局视角）

> 本节把 ch04/05/06/07 在 stale 维度如何串起来讲清。开发侧改任何一章的 stale 行为，都请从本节对照，避免破坏下游门禁。

### 8.1 共享 stale 基础设施（章节无关，四章共用）
- **数据列**：`step_runs.stale INTEGER NOT NULL DEFAULT 0` —— 由 `app/db.py init_db()` 幂等 `ALTER TABLE ... ADD COLUMN` + `try/except` 引入（ch06 落地），ch04/05/07 复用，无重复迁移。
- **12 个消费侧过滤入口**（全部筛 `status='submitted' AND stale=0`）：`book.py:160,376` / `steps.py:207,226,484,521,740` / `agent.py:171` / `chat.py:98,117` / `services/step_runner.py:48` / `context_requirements.py:57-61`。
- **compaction 闸门**：`steps.py:541 _maybe_compact` 仅当全章所有 step 均 `submitted` 且 `stale=0` 才写 profile（任一步 stale 即跳过），自带过期兜底。

### 8.2 各章 stale 行为一览
| 章 | 步结构 | stale 行为 | profile 失效 |
|---|---|---|---|
| ch04 | 5 步强级联 | 重提交 step-k → 所有 step-j(j>k) `stale=1` | 清空 `values`+`ranked`+`work_purpose` 三键（同事务） |
| ch05 | 2 步（step-2 `references` step-1 `talents`）| step-1 重提交 → step-2 `stale=1`（**与 ch06/ch07 同构，复用 §2 通用 helper `mark_downstream_stale`，仅 ch04/ch05 使用，零新增代码**）；并 `clear_chapter_profile_keys(['talents'])` 使 ch7 因 `talents` 缺失回退锁定 —— **待开发侧实施** | `talents`（ch05 权威写方；step-1 重提交即清空，重跑全 2 步后重写；ch3 初始 `talents` 已被本章覆盖，无残留冲突） |
| ch06 | 2 步 | step-1 重提交 → step-2 `stale=1` + `profile.likes=[]`（方案 A，已实施） | `likes` 由专属 canonical 逻辑（方案 A）显式写最新非 stale 版 |
| ch07 | 2 步（组合） | ① 进入门禁双校验；② step-1 重提交 → 旧 step-2 `stale=1` + `profile.ideal_works=[]` | `ideal_works` 新增键，compaction 白名单三处扩展，零新增表/列 |
| ch08 | 独立流程图页（`page_type:flowchart`，无 `exercises`）| **无内部 stale 级联**（不写 profile、不持有 profile 键）；进入时读 ch04–ch07 完成态（含 `stale=0` 校验）做软提示；上游任意章 `stale=1` 时标注「数据可能已过期，建议重跑」 | **无 profile 写入**：流程图导航态存独立表 `flowchart_state`，与 `learner_profile` 完全解耦，零新增 profile 键/列、无 DRIFT |

- **前端通用 UX（J）触发准则 =「被改步有下游消费者」**：改某步会令本章后续步失效才弹提醒。**适用**——ch04 step-1～4（严格链，每步都有下游）、ch05/ch06/ch07 的 step-1（step-2 均依赖 step-1）。**不适用（末步 / 无下游消费者，改了不影响后续）——ch04 step-5、ch05/ch06/ch07 的 step-2**。**ch05 step-1 已按选项 A 拍板（2026-08-14）对齐 ch06/ch07**：同样弹「修改前提醒」+ 重提交触发级联 + 清 `talents`**（设计已定，待开发侧实施）**，详见 §9。

### 8.3 上游映射修正（context_requirements 权威口径）
- **旧（已废弃）**：`context_requirements.py` 错挂 ch03 + `importance` 为 ch04/05/06 上游。
- **新（已实施）**：`ch04 → (work_purpose, values)` ／ `ch05 → (talents)` ／ `ch06 → (likes)`；彻底移除 ch03、弃用 `importance`。
- **ch07 跨章注入**：`step_context.references = mentor_hooks.references = [talents, likes, work_purpose, values]`；assembler 注跨章 profile 进 step prompt 时**只读 `step_context.references`**（存在时绝不回退 `mentor_hooks`）——这是 ch07 相对 ch03/ch05「仅 mentor_hooks」惯例的首例扩展。
- **ch04 自身**：仍引 ch03 的 `importance`（仅 `mentor_hooks`，不进 step prompt），不受本次映射修正影响。

### 8.4 方案 A：跨章问题清单统一（30问 + 100例 固化 config）
- **30问**：ch04 `value_questions` / ch05 `talent_questions` / ch06 `passion_questions`（`input_schema` 可选字段，q_order 区间 价值观 1–30 / 才能 31–60 / 热情 61–90），答案走 questions 服务 + `book_notes`，**不进 profile、不流下游**。
- **100例**：ch04 `ui_context.values_examples` / ch05 `ui_context.strength_examples` / ch06 `ui_context.passion_examples`（各 100 项），固化进各自章节 config，前端读已加载章节 config 即生效，**不再依赖 `chapter_md/问题清单.md`**。
- 纯增量、向后兼容、与既有字段/流程零冲突（详见 `docs/问题清单跨章统一_方案A_变更清单与开发侧待办.md`）。

### 8.5 交付后验证清单（回归基线）
1. `check_config_consistency.py --chapter ch04/ch05/ch06/ch07` 应**无 DRIFT**（已 reseed，新增 `ui_context.*_examples` / `*_questions` / `ideal_works` 均已进 DB）。
2. 契约测试覆盖：`test_m4_ch04_cascade` / `test_m4_ch05_cascade` / ch06 既有 / ch07 新增（含 stale 隔离、上游重提交后门禁回退、step-2 读最新非 stale）。
3. 全链路 smoke：ch04 走完 5 步 → ch07 解锁；ch04 step-1 重提交 → ch07 门禁回退锁定 → 重走 ch04 全 5 步 → ch07 重新解锁；ch06 step-1 重提交 → ch07 门禁同样回退；**ch05 step-1 重提交 → ch07 门禁同样因 `talents` 缺失回退（选项 A，2026-08-14 拍板，待实施）**。

### 8.6 本文与四份落地文档的关系
- 本文是 **stale / 一致性横切面的唯一文档**；四份 `ch0X_落地级步骤设计.md` 仍是各章字段级契约与 LLM 角色索引（设计侧维护，仅供追溯与后续设计变更）。
- 开发侧**待实施**（设计已拍板，2026-08-14 修正此前误标的「已实施」状态）；后续若改动 stale 行为，以本文为入口，并同步回对应落地文档 §10 的「实施状态」区块。

---

## 9. ch05 step-1 与 ch06/ch07 对齐（2026-08-14 已拍板，待实施）

- **现象**：四章 config 均为 step-2 `references` step-1（ch05/06/07 同构的 2 步），但 §8.2 仅 ch06/ch07 标注「step-1 重提交 → step-2 `stale=1`」且前端弹提醒；ch05 标「无自有 stale 级联」、前端免提醒。
- **矛盾点**：`config/chapters/chapter_config_ch05.json` step-2 仍 `references` step-1 `talents`；step-1 答案变更后 step-2 合并基线变化，且 step-2 产出的 `talents` 流到 ch7（与 ch06 `likes`、ch07 `ideal_works` 风险同构）。若无级联 / 无提醒，ch05 step-1 改后 ch7 可能读到陈旧 `talents`。
- **✅ 已拍板（2026-08-14）：采用选项 A——ch05 对齐 ch06/ch07**。`ch05 step-1` 现在与 `ch06/ch07 step-1` 同构：
  1. 点击 step-1「修改」→ 弹「修改前提醒」（说明下游 step-2 失效 + `talents` 清空、ch7 门禁回退风险）。
  2. 重提交 step-1 → `mark_downstream_stale` 将 step-2 `stale=1` + `clear_chapter_profile_keys(['talents'])` 清空 `talents`（**复用 §2 通用 helper，仅 ch04/ch05 使用，零新增代码**）；ch7 因 `talents` 缺失回退锁定。
  3. 重走全 2 步并提交 → `_maybe_compact` 重写 `talents`，ch7 解锁。
- 同步：ch05 落地文档 §2 / §8.7 / §10 已补 stale 级联与提醒说明；§8.2 上表 ch05 行已更新为级联行为。
- ⚠️ **上述 ch05 选项 A 行为尚未实现**（2026-08-14 开发侧实测：ch05 `submit` 仍为通用路径、前端 step-1 无修改入口/提醒），待开发侧按本文 §3 J + §2 helper 实施。

---

## 10. ch04 step-2「未分组关键词池」契约变更（2026-08-29 拍板，**待开发侧实施**）

> ⚠️ 本节与 stale 无关，是 ch04 step-2 的**字段契约 + 前端交互**变更，因交接入口收敛到本文而纳入。
> **字段级权威源仍是 `config/chapters/chapter_config_ch04.json` step-2**（config 已改并过 schema 校验），本节只是实施清单；两者冲突时以 config 为准。

### 10.1 变更背景（含一次设计侧纠错）

- **纠错**：原书第四章明确为「**每组 4～6 个**关键词」（原书图 4-8 八木仁平例：审美意识 7 / 热爱 5 / 成果 4 / 好奇心 7 / 简单 3，实际浮动 3~7）。而 config step-2 `instruction` 原写「把相近的归入一组（**4~6 组**）」——把「每组词数」误写成「组数」，**是 config 写错**，不是落地文档写错。2026-08-29 已改回「每组 4~6 个」，并明确 **4~6 是软建议（允许 3~7），不是硬门禁**。
- **新拍板交互**：用户锚定关键词池后**由 LLM 做初步分组，用户可全权修改**。关键词的归属调整一律走「组内 ↔ 未分组」双向移动，不允许凭空手输新词（否则会漏归类 / 重复计数）。

### 10.2 契约变更点（config 已改，权威）

| 位置 | 变更 |
|---|---|
| step-2 `instruction` / `method` | 「4~6 组」→「**每组 4~6 个**」+「4~6 为建议值，实际可 3~7，不拦截」 |
| step-2 `input_schema` `supplemental_keywords.label` | 补充词**一律先进「未分组」区，不会自动进组** |
| step-2 `user_action` | 3 条 → 5 条（补：删整组回池 / 新补充词先入池 / 4~6 为软提示） |
| step-2 `output_fields` | **新增** `ungrouped`（`type:list`, `readonly:true`），与 `groups` 并列 |

`ungrouped` 语义（**请开发侧严格按此实现**）：

- **只读字段**：用户不能直接编辑，只能通过对 `groups` 的增删**间接维护**；**LLM 不得覆盖**（`preserve_output` 不涉及本字段）。
- **三个来源**：① 从某组删除的关键词；② 删除整个分组时的全组关键词；③ 新补充的关键词（含从「100 例价值观清单」引用的）。
- **提交门禁**：`ungrouped` 非空 = 尚有未归组词 → 禁用提交并提示「还有 N 个关键词未归组」；清空才放行。
- **不进 `profile_json`**：不在 `compaction.py` 的 `PROFILE_FIELDS` 白名单，与 `groups` 同为**章内中间产物、不跨章传播**（进 profile 的仍只有 `values` / `ranked` / `work_purpose` 三键）。
- 写入 `groups[].keywords[]` 时**不应包含** `ungrouped` 中的词，避免重复计数。

### 10.3 前端待办清单（K1–K8，**待开发侧实施**）

| # | 位置 | 改动 |
|---|---|---|
| K1 | ch04 step-2 视图 | 新增常驻「**未分组关键词池**」区（建议顶部），带计数徽标；空态显示「✓ 全部关键词都已归组」 |
| K2 | 分组卡片 · 关键词 | 每个关键词加 `✕` = **移回未分组池**（不是删除）；「＋ 加关键词」改为「**＋ 从未分组池添加**」，点击在卡片内展开选词浮层列出池内词，**废除 `prompt()` 手输入** |
| K3 | 未分组池 · 关键词 | 池内 `✕` = **彻底从关键词池删除**（与 K2 的「移回池」语义不同，UI 需可区分） |
| K4 | 分组卡片 · 底部 | 软提示：`3 个 · 建议 4~6 个，还差 1 个`（橙）/ `在建议区间（4~6）内`（绿）/ `超出建议区间`（红）——**纯提示，不拦截提交** |
| K5 | 提交按钮 | `ungrouped` 非空 → 置灰 + 红字门禁提示；清空后自动解禁 |
| K6 | step-2 前置区 | 「让咨询师分组」**之前**补充的词进「**补充关键词暂存区**」（可 `✕`、计入 N/15 计数）；触发分组时暂存词一并进入未分组池 |
| K7 | 删除分组 | 删除整个分组时，组内关键词**全部回未分组池**，不丢弃 |
| K8 | 100 例抽屉 | 从抽屉引用的词按 K6 / K1 路径进未分组池，**不直接进组** |

> **可直接对照的原型**：`platform/prototype/ch04_exercise_mockup.html`（step-2 视图已按 K1–K8 全部实现，2026-08-29 验证通过）。
> 原型备份：`platform/prototype/backups/ch04_exercise_mockup.html.bak.2026-08-29T1500`（改动前完整版）。

### 10.4 后端 / 数据影响

- **零新增表 / 列 / 迁移**：`ungrouped` 随 `groups` 一起存 `step_runs.parsed_output`，随 step-2 的 run 走。
- **无需改 `compaction.py`**：`ungrouped` 不进 profile，白名单无需扩展。
- **建议（待开发侧确认）**：在 `submit_step` 侧同步校验 `parsed_output.ungrouped` 为空，非空返回 4xx —— 前端门禁可被绕过，后端加一道更稳。若开发侧认为不必要，请回设计侧沟通，不要静默省略。
- 与既有待办的关系：`preserve_output`（重新生成分组时透传锁定项）**仍待实施**（本文此前 P0-2）；本轮新增的 `ungrouped` **不参与** `preserve_output` 透传（只读字段）。

### 10.5 回归用例（契约测试建议覆盖）

1. 从「审美意识」组删「热衷」→ 该词出现在未分组池、池计数 +1、提交按钮禁用。
2. 在另一组点「＋ 从未分组池添加」选「热衷」→ 词进入该组、池计数 -1、浮层保持展开便于连续添加。
3. 池清空 → 提交按钮解禁、池区显示「✓ 全部关键词都已归组」。
4. 池内 `✕` → 关键词彻底移除；「组 → 池 → 删除」整链路计数正确、无残留。
5. 删除整个分组 → 组内全部词回池，门禁重新禁用。
6. 分组前从 100 例选词 → 进暂存区、N/15 计数 +1、暂存区可 `✕`；点「让咨询师分组」后暂存词进入未分组池。
7. 某组词数为 3（低于建议区间）→ 显示橙色软提示，但**提交不被拦截**。
8. 点「重新生成分组」→ 锁定组保留；`ungrouped` 中的词不被 LLM 覆盖、位置不丢。

### 10.6 设计侧已完成的校验（可复核）

- `config/chapters/chapter_config_ch04.json` 通过 `config/schema/chapter_task_config.schema.json` 校验：**SCHEMA_OK**；`type:list` 已在 schema enum 内，**未改 schema**。
- 全文「4~6 组」残留 **0** 处，「每组 4~6 个」4 处。
- 原型用 **jsdom 冒烟**跑通 step-1 → step-2 全流程：**36 项断言全绿、零运行期错误**（脚本 `C:/Users/deng_/.workbuddy/binaries/node/workspace/ch04_smoke.js`，该工作区已装 jsdom）。仅靠 `node --check` 查不出退化成 `alert()`、样式作用域失效、空指针这类问题，故一律跑 jsdom。
- 同步改的三份文件：`config/chapters/chapter_config_ch04.json`、`docs/ch04_落地级步骤设计.md`（§4 UX 行为扩到 9 条）、`platform/prototype/ch04_exercise_mockup.html`。
- 备份：`config/backups/chapter_config_ch04.json.bak.2026-08-29T1450` 与 `.bak.2026-08-29T1520`；`docs/backups/ch04_落地级步骤设计.md.bak.2026-08-29T1450` 与 `.bak.2026-08-29T1520`；`platform/prototype/backups/ch04_exercise_mockup.html.bak.2026-08-29T1500`。
