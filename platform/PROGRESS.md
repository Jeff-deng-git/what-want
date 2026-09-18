# What Want 平台 - 重构进度



> 唯一权威实施依据：`llm_prompt_design/docs/工程实施交接文档.md` v2.0

> 设计侧 review 记录：`llm_prompt_design/docs/重构计划_设计侧改动清单.md`

> 设计侧 Q&A：`llm_prompt_design/docs/重构开放问题_设计侧确认.md`

> 下次 session 入口：`platform/CONTEXT_CHECKPOINT.md`

> 旧前四章进度（已冻结）：`platform/PROGRESS.legacy-ch1-ch4.md`



## 0. 当前状态



| 阶段 | 状态 |

|---|---|

| M0 数据迁移 | ✅ |

| M1 数据层 + compaction | ✅ |

| M2 schema + exercise | ✅ |

| M3 运行时接入 | ✅ |

| M3.1 灰度 ch01 | ✅ |

| M3.2 全 8 章推广 | ✅ |

| M3.3 设计侧修改 Verify + 9 步改造 | ✅ |

| Q10 chat/summary 灰度切到 agent | ✅ |

| Q7 mentor 20 轮触发 compaction | ✅ |

| Q8 open_questions 廉价 LLM 提取 | ✅ |
| M4.1 每章 schema-aligned mock LLM 验证 (7 测) | ✅ |
| M4.2 ch04 章节内 references 级联 (2 测) | ✅ |
| M4.3 ch07 跨章 profile 读 (2 测) | ✅ |
| M5.1 后端 chapter_status 端点 (8 测) | ✅ |
| M5.2 ch04 前端 groups/conversions 渲染分支 | ✅ |
| M5.6 前三章 DB seed 补齐 + llm_roles 脏行清理 | ✅ 2026-08-04 |
| M5.7 LLM 模型名 deepseek-chat → DeepSeek-V4-Flash + seed UPSERT | ✅ 2026-08-04（真实 LLM 端到端因沙箱拒网未验） |
| 设计侧 附2-1 agent_configs 表 seed + 迁移 | ✅ 2026-08-04 |
| 设计侧 附2-2 DB vs JSON 一致性脚本 | ✅ 2026-08-04 |
| 设计侧 附2-3 POST /config 端点（version+1 workflow） | ✅ 2026-08-05 |

| M4.1 每章端到端验证 | ✅ |

| M4.2 ch04 章节内 references 级联 | ✅ |

| M4.3 ch07 跨章 profile 读 | ✅ |

| M4.4 ch07 上游依赖锁定 | ⏳ M5.5 一起做 |

| M6 验收 | ✅ 2026-08-04（机器可验项；视觉项交人工） |
| M5.1 后端 chapter_status 端点 (8 测) | ✅ |
| M5.3 章末回顾卡（形态B）| ✅ 2026-08-04 |
| M5.4 三入口 (顶部/步骤/章末/浮层) | ✅ 2026-08-04 |
| M5.5 ch07 上游依赖锁 UI | ✅ 2026-08-04 |
| M5.6 前三章 DB seed 补齐 + llm_roles 脏行清理 | ✅ 2026-08-04 |
| M5.7 LLM 模型名 deepseek-chat → DeepSeek-V4-Flash + seed UPSERT | ✅ 2026-08-04（真实 LLM 端到端因沙箱拒网未验） |
| 设计侧 附2-1 agent_configs 表 seed + 迁移 | ✅ 2026-08-04 |
| 设计侧 附2-2 DB vs JSON 一致性脚本 | ✅ 2026-08-04 |
| 设计侧 附2-3 POST /config 端点（version+1 workflow） | ✅ 2026-08-05 |



## 1. 测试基线



当前 **110 passed**（最新全量回归，排除仓库内无权限的 `tests/_tmp`）：



- `tests/test_assembler.py`：9 passed

- `tests/test_ch01_e2e.py`：2 passed

- `tests/test_all_chapters_e2e.py`：14 passed（含 12 个新增 / 改写断言）

- `tests/test_db_schema.py`：4 passed

- `tests/test_compaction.py`：3 passed

- `tests/test_chat_api.py`：4 passed

- `tests/test_summary_api.py`：3 passed

- `tests/test_m4_per_chapter.py`：7 passed（M4.1：每章 schema-aligned mock + 两层验证）
- `tests/test_m5_chapter_status.py`：8 passed（M5.1：chapter_status 端点 + ch07 上游锁 状态）
- `tests/test_agent_configs.py`：5 passed（设计侧附2-1：agent_configs seed 脚本）
- `tests/test_config_consistency.py`：4 passed（设计侧附2-2：DB vs JSON 一致性脚本）

- `tests/test_m4_ch04_cascade.py`：2 passed（M4.2：ch04 5 步级联 + step-2→step-1 引用）

- `tests/test_m4_ch07_cross_chapter.py`：2 passed（M4.3：ch07/ch02 跨章 profile 读）



## 2. 已闭环里程碑



### M3.3 设计侧修改 Verify + 9 步改造

- ✅ ch07 config `mentor_hooks.references` 补 `importance`

- ✅ `build_step_prompt` 加 chapter_md 注入（md_cap 默认 5000）

- ✅ `build_step_prompt` 按 references 拉 profile 字段

- ✅ `_validate_parsed_against_types` 轻量校验（warn-only）

- ✅ 删 `_run_step_legacy` + `_uses_exercises_schema`

- ✅ 3 个新断言（career_counselor 权威 / md 注入 / type 校验）



### Q10 chat/summary 灰度切到 agent

- ✅ `seed_roles.py` 补 `mentor` + `summary` role（共 4 个）

- ✅ `chat.py send_message` 走 `agent.run_mentor`（USE_AGENT_CHAT=1 默认）

- ✅ `summary.py regenerate_summary` 走 `agent.run_summary`（USE_AGENT_SUMMARY=1 默认）

- ✅ 旧路径保留为可回滚保险



### Q7 mentor 20 轮触发 compaction

- ✅ `agent.py` 加 `MENTOR_COMPACTION_K = 20` + 3 个 helper

- ✅ `run_mentor` 开头 trigger 检查

- ✅ 2 个新断言（trigger 阈值 / profile 刷新）







### M4.1 每章 schema-aligned mock LLM 验证

- ✅ `tests/test_m4_per_chapter.py 7 测（ch01/02/03/05/06/07/08）

- ✅ 两层验证：parsed_output 完整 + profile 落跨章字段

- ✅ 验证章节内 artifact（color_bath_log 等）正确不污染 profile



### M4.2 ch04 章节内 references 级联

- ✅ `tests/test_m4_ch04_cascade.py 2 测

- ✅ 5 步顺序跑通 + step-2 prompt 验证含 step-1 内容



### M4.3 跨章 mentor_hooks.references 验证

- ✅ `tests/test_m4_ch07_cross_chapter.py 2 测

- ✅ ch07/ch02 prompt 验证 profile 内容注入



### Q8 open_questions 廉价 LLM 提取

- ✅ `compaction.py` 加 `extract_open_questions` async + `extract_and_persist_open_questions`

- ✅ `steps.py submit_step` 用 BackgroundTasks fire-and-forget

- ✅ `agent._force_mentor_compaction` 用 `asyncio.create_task` fire-and-forget

- ✅ 测试 `DISABLE_OPEN_QUESTIONS_EXTRACT=1` env gate

- ✅ 4 个新断言（JSON 解析 / LLM 失败 / 非 JSON / 空输入）




### M5.6 前三章 DB seed 补齐 + llm_roles 脏行清理（2026-08-04）

**根因**：
1. `chapter_configs` 表只有 ch04（M3.3 期间单章验证产物），其他 7 章从没 seed。
   `chapter_configs.ch01` 不存在 → `get_chapter_full_config` 走 fallback 返回 `{steps: []}` → 前端
   `loadSteps()` 拿到 0 个 step → 三章练习不可见。
2. `llm_roles` 表 14 行脏数据：9 条 `career_counselor` UUID 行 system_prompt=`'role'`（seed 失败残留），
   `load_role('career_counselor')` 实际返回短串 'role' → career_counselor 步骤真实 LLM 必输出垃圾。
   4 条有效行（mentor / psychologist / summary / career_counselor）受 rowid 顺序影响，部分行被遮蔽。

**修复**：
- `python seed_all_chapters.py` → 7 章补齐（ch04 跳过已存在）
- `DELETE FROM llm_roles` + `python -m scripts.seed_roles` → 4 条干净 role 落库
  - career_counselor 拿回设计侧 long-form（1460 字符）
  - mentor / psychologist / summary system_prompt 完整
  - model = `DeepSeek-V4-Flash`

**备份**：`backend/data/backups/ww-20260804-115054.db`

**验证**（已做）：
- ✅ `GET /api/book/chapters/ch01` → `{has_steps: true}`
- ✅ `GET /api/book/chapters/ch01/config` → `steps: [{step_id: step-1, title: "误区自检清单", output_fields: [misconceptions_cleared, external_voices], llm_op.role_id: career_counselor}]`
- ✅ `python scripts/smoke_ch01_mock.py` → `smoke OK: step_runs + learner_profiles populated for ch01`
  （mock LLM 隔离测试 draft/run/submit 路由；Q8 BackgroundTasks 触发正常）
- ⏳ 真实 LLM 端到端（deepseek API）：沙箱拒网，无法验证。需用户在本地浏览器实测

### M5.7 LLM 模型名 deepseek-chat → DeepSeek-V4-Flash + seed UPSERT（2026-08-04）

**触发**：`deepseek-chat` 真实 API 调用 `APIConnectionError`（模型已 retire）。

**改动**：
- `backend/scripts/seed_roles.py` 默认 `model = "DeepSeek-V4-Flash"`
- main() 由 `if existing: continue` 改为 **UPSERT by (name, provider, enabled=1)**：
  找到 → `UPDATE model + system_prompt + updated_at`；找不到 → INSERT
  （避免 8/3 8/4 重复 INSERT 9 条脏行的 bug 重现）
- `get_chapter_full_config` 转换逻辑保留（exercises → steps 桥接前端旧字段名）

**备份**：`backend/scripts/seed_roles.py.bak-20260804-115128`

**未验证**：
- 真实 LLM（`https://api.deepseek.com/v1` + `DeepSeek-V4-Flash`）：沙箱拒网
  → 用户需在本机浏览器验证 ch01 step-1 全流程（draft → run → submit → LLM 回复）
### M5.8 运行时验收修复：config 路由注册顺序（2026-08-04）

**发现**：Service Dashboard 重启后 8011 正常，但前端显示“该章节暂无步骤配置”；API `/api/book/chapters/{chapter_id}/config` 返回 404。

**根因**：`main.py` 在 `app.include_router(book_router)` 之后才声明 `@book_router.get("/chapters/{chapter_id}/config")`，FastAPI 已完成 router 注册，导致该端点未进入应用。

**修复**：将所有 `include_router(...)` 移到 chapter config 路由声明之后。

**验证**：Service Dashboard 重启后：
- ch01：`steps=1`, `schema=1`。
- ch02：`steps=1`, `schema=2`。
- 3011 静态页面包含 schema 渲染和角色管理代码。

### M5.8 运行时验收修复：input_schema seed 闭环（2026-08-04）

**发现**：运行中的 `GET /api/book/chapters/ch01|ch02/config` 返回 `input_schema: null`。前端代码虽然支持结构化组件，但真实页面仍会 fallback 到旧题目。

**根因**：`seed_all_chapters.py` 对已有 active 记录直接 `skipping`；JSON 源文件已加入 `input_schema`，数据库的 ch01/ch02 active 配置未同步。

**修复**：只更新 ch01/ch02 active `config_json` 为当前权威 JSON，并将 version 从 2 升到 3，不删除历史记录。

**验证**：
- DB ch01/ch02 exercises 均含非空 `input_schema`。
- 运行中 8011 API：ch01/ch02 `schema_count=1`。
- 后端全量回归：`93 passed`。
- 3011/8011 服务保持运行。

**待验**：浏览器工具因本地内核资产路径错误不可用，尚需人工页面视觉与点击验收。

### M6 验收（2026-08-04）

**机器可验证（通过）**：
- 表：`learner_profiles` / `conversation_summaries` / `chapter_configs` / `llm_roles` / `step_runs` 全部存在。
- `llm_roles` 含 `mentor` / `summary`；教练角色含 `career_counselor` / `psychologist`。
- 8 章 `chapter_configs` 已入 DB，ch01/ch02 升级到 version 3（含 input_schema）。
- `chat.py` 走 `agent.run_mentor`，旧路由 `_send_message_legacy` 通过 `USE_AGENT_CHAT` 保留。
- `summary.py` 走 `agent.run_summary`，旧 `_regenerate_legacy` 通过 `USE_AGENT_SUMMARY` 保留。
- 8 章 steps 通过 `/api/book/chapters/{id}/config` 返回。
- ch07 上游依赖锁定逻辑生效：`/api/book/chapters/ch07/status` 返回 `lock_state`。
- 后端全量回归：`93 passed`。

**交还用户验收（机器无法验证）**：
- ch04 `renderStepOutput` 中 `groups` / `conversions` 分支渲染（已存在代码）。
- 章末桥接卡 B（§8）三种入口在浏览器中的实际可见与点击行为。

### 设计侧答复落地（2026-08-04）

依据 `llm_prompt_design/docs/重构开放问题_设计侧确认.md` 全部 5 题答复 + 跨文档变更清单：

- **Q1 ch03 intersection readonly**：配置加 `readonly:true`，前端按章节判断渲染。
- **Q2 ch07 保持单一 intersection**：仅 UI 升级为可编辑矩阵；不新增字段。
- **Q3 ch04 exercises seed 修复**：version 升到 3，5 个 exercises 写入 DB；ch07 lock_state 现在正确显示 ch04 11/5 is_submitted=true。
- **Q4 ch07 markdown 实际 ~15KB**：回退前端 size guard（>200KB `<pre>`），改为正常富文本渲染。
- **Q5 ch07 step name 维持 "三圆组合"**。
- **附2 json_mode**：agent.run_step 按 output_fields 是否为结构化类型自动决定 json_mode（structured_types={editable_list, select, structured, list_of_items, checklist}）。
- **附2 agent_configs 表**：✅ 2026-08-04 由 seed_agent_configs.py 注入 mentor + summary scaffold（5 测）；psychologist / career_counselor 待设计侧补 scaffold JSON。

**验证**：
- ch03/ch04/ch07 config upserted to DB。
- ch04 status: 11 submitted / 5 total。
- ch07 lock_state: ch03 0/1, ch04 11/5 -> lock ready=false（ch03 仍需完成，正常）。
- 后端全量回归：93 passed。
### Review 修复接入（2026-08-04，P1-6 前端 fetchJson 接入）

**已完成**：
- `frontend/index.html` 的 17 个调用点全部接入 `fetchJson`：
  - `load()` 直接转发到 `fetchJson`。
  - `loadSteps` / `loadCurrentRuns` / `loadSummary` / `loadChatHistory` / `loadNotes` / `loadRoles` / `loadRoleRefs` 已使用 `fetchJson`。
  - `saveDraft` / `runStep` / `submitStep` / `saveChipEdits` / `generateSummary` / `sendChat` / `clearChat` 已使用 `fetchJson`，超时分别 30s/90s/60s 不等。
  - `createNote` / `updateNote` / `deleteNote` / `saveQAnswer` / `editRolePrompt` / `newRole` / `saveRoleDrawer` / `previewEmptyRoles` / `bulk-disable-empty` 已使用 `fetchJson`。

**验证**：
- 后端全量回归：`93 passed`。
- 前端静态扫描：所有 `await fetch(\`${API}\`...)` 已替换为 `fetchJson`（fetchJson 内部 `fetch` 调用除外）。

### Review 修复（2026-08-04，review.md P0/P1/P2 7 项）

**已完成**：
- **P0-1** SQLite：`connect(check_same_thread=False, timeout=10.0)`。
- **P0-3** step 状态机：`save_draft` 拒绝覆盖 `submitted`；`_get_or_create_run_id` 仅复用 `draft`/`saved` 行。
- **P0-4** `user_answers` schema 校验：`_validate_user_answers` + `_current_input_schema`，校验失败返回 422。
- **P0-5** mentor 历史预算：assembler 新增 `_truncate_history_to_budget(1800)`，`build_mentor_prompt` 调用前置。
- **P2-3** legacy 模型名：`chat.py` / `summary.py` 的旧路径 `deepseek-chat` 改为 `DeepSeek-V4-Flash`。
- **P1-5** LLM client：`call_llm_with_retry` 包装 `call_llm`，对连接/超时/5xx 自动重试 1 次。
- **P1-6** 前端：`fetchJson(url, opts, {timeout=30s, retry=1})` 工具函数，支持 30s 超时和一次重试。

**验证**：
- 后端全量回归：`93 passed`。
- 当前 8011 进程为旧代码，需在 Service Dashboard 重启后才会加载 sqlite / 校验 / 历史预算修复。

### M5.5 ch07 上游依赖锁 UI（2026-08-04）

**完成**：
- `frontend/index.html` 在 `renderReader` 进入 `ch07` 时调用 `/api/book/chapters/ch07/status`。
- 当 `lock_state.ready=false` 时，在 `#bookContent` 上方插入 `.gated-overlay` 半透明遮罩，列出 ch03/ch04 进度并提供「前往 ch03 / 前往 ch04」直达按钮。
- ready=true 时不插入遮罩，走正常步骤流程。

**验证边界**：
- status API 当前返回 `ready=false`，ch03/ch04 进度可见。
- 未做浏览器视觉验收。

### M5.4 三入口（2026-08-04）

**完成**：
- 顶部常驻：「与导师聊聊本章」按钮。
- 步骤面板内每条 step 的「聊聊这一步」按钮。
- 全页浮层按钮（在 `renderReader` 时挂载，不重复创建）。
- 章末回顾卡 CTA（已在 M5.3 实现）。
- 统一调用 `openBridgeChat({step})`，CTA 仅切 tab + 预填上下文，不自动发消息。

**验证边界**：
- 关键函数与调用点已检查；未声称浏览器实际渲染验证通过。

### M5.3 章末回顾卡（形态B，2026-08-04）

**完成**：
- `frontend/index.html` 新增 `bridge-card-slot` 容器，默认放在 summary pane 之上、章节内容区之外。
- `renderBridgeCard()` 基于 `chapterSteps + currentRunByStep` 汇总 `submitted` 步骤数、已识破误区、外部声音片段。
- CTA `把这一章放进对话` 调用 `openBridgeChat()`：仅切换 tab 并预填 mentor 提示，不自动发消息（满足 §8.7 验收）。
- 提交或保存草稿后会重新渲染回顾卡。

**验证边界**：
- 静态函数定义与调用点检查通过。
- 真实视觉与点击验证待浏览器（前端浏览器工具当前不可用）。

### M5.8 收尾状态确认（2026-08-04）

设计侧确认后，M5.8 的后端治本、input_schema 数据闭环、结构化 user_answers、前端结构化渲染、角色锁定和角色管理页均已实现。运行时补修了两个问题：seed 跳过导致 schema 未入库、FastAPI config 路由注册顺序错误；Service Dashboard 重启后 ch01/ch02 config API 已验证正常。

UI 美化暂不纳入当前主线，用户确认先推进后续功能。

**当前主线顺序**：M5.3 章末回顾卡 → M5.4 三入口 → M5.5 ch07 上游锁 UI → M6 验收。

### M5.8 input_schema 与角色管理（第5步完成，2026-08-04）

**本阶段完成**：
- `frontend/index.html` 新增 `?page=roles` 角色管理页。
- 列表使用 `group_by_name=true`，显示 name、provider/model、prompt 预览和启用状态。
- 每个角色异步读取 `/api/roles/{id}/refs`，展示引用步骤数量和位置 tooltip。
- 配置按钮打开右侧抽屉，可编辑 name、description、provider、model、temperature、max_tokens、system_prompt。
- 一键禁用空 prompt 先调用 dry-run，弹出 name/provider/prompt 预览确认框，确认后调用 `confirm=true`；后端执行软禁用，不删除内容。

**验证**：
- 角色列表 API：4 条角色返回正常。
- 引用 API：返回对象格式已适配前端 `refs` 字段。
- 空 prompt dry-run：返回 `200`、候选列表为空，未执行破坏性操作。
- 页面脚本标签配对正常；整页 Node 检查仍受原文件历史乱码字符串影响，需浏览器实际加载验证。

**下一步**：
- 重启 backend 8011 后进行浏览器验收：ch01/ch02 练习渲染、角色管理页、抽屉保存和空 prompt 确认流程。
- 验收通过后进入 M6 收尾。

### M5.8 input_schema 与角色管理（第4步完成，2026-08-04）

**本阶段完成**：
- `frontend/index.html` 按 `input_schema` 优先渲染结构化输入：checklist、list_of_items、select/radio、text。
- ch01 支持误区勾选、补充说明和 explain；ch02 支持事项动态增删及 external/internal 选择。
- 草稿和运行统一提交结构化 `user_answers`；无 schema 的旧步骤继续使用旧题目数组。
- 步骤内角色改为题目指定的静态锁定标签，不再提供角色下拉。

**验证边界**：
- 新增函数与关键调用点已检查；原文件已有乱码字符串导致整页 `node --check` 不能作为全文件通过依据，需浏览器实际加载验证。

**下一步**：
- M5.8 第5步：角色管理页、引用统计、编辑抽屉、空 prompt 确认后软禁用。



**本阶段完成**：
- `app/runtime/assembler.py` 新增 `render_user_answers`：兼容旧列表/字符串输入，并按 `input_schema` 将新字典答案渲染为可读 prompt。
- `app/routers/steps.py` 的 `DraftIn` / `RunIn.user_answers` 改为 `Any`，支持 checklist、list_of_items 等结构化答案。
- 语法检查与 helper 定向验证通过。
- 后端全量回归：`93 passed`。

**下一步**：
- M5.8 第4步：前端按 `input_schema` 渲染 ch01/ch02 练习、静态角色锁定标签与解释区。
- M5.8 第5步：角色管理页、引用统计、编辑抽屉、空 prompt 确认后软禁用。

### 设计侧 跨文档变更全量覆盖（2026-08-04）

依据 `重构开放问题_设计侧确认.md` §"设计侧跨文档变更清单" + Q1-Q5 + 附1/附2：

| 项 | 内容 | 落点 | 状态 |
|---|---|---|---|
| A-1 | chapter_task_config.schema.json 加 exercises[].input_schema[] / step_role_id / allow_role_override | 设计侧直接改 schema | ✅ 已合入 |
| A-2 | 8 章 chapter_config_ch0N.json 的 output_fields 字符串 → 类型化对象 | 设计侧改 JSON；M2 不再转 | ✅ 已合入（实测 8 章全 dict） |
| B-1 | seed_roles.py career_counselor 改 ch7/ch8 场景版；psychologist 更名心理教练师 | 设计侧直接改 | ✅ 已合入；开发侧 verify |
| B-2 | PRD-ch7.md / PRD-ch8.md 删 7 细分角色运行时；mentor 子节点独立 | 设计侧直接改 PRD | ✅ 已合入 |
| C-1 | platform/SPEC.md 11 处同步（Next.js→SPA、learner_profiles/conversation_summaries、exercises schema、references 改、端口 3011 等） | 设计侧直接改 SPEC | ✅ 已合入；开发侧无需动 |
| D | 工程实施交接文档 v2.0 仍为唯一权威 | — | ✅ 始终遵循 |
| Q1 | ch03 intersection 加 readonly:true，前端按 chapter 判断 | DB v2 + 前端分支 | ✅ 已落地 |
| Q2 | ch07 单字段 intersection，前端按 chapter 渲染可编辑矩阵 | DB 不变 + 前端分支 | ✅ 已落地 |
| Q3 | ch04 chapter_config 补 5 个 exercises，version 升到 3 | DB v3 + ch07 lock 修复 | ✅ 已落地 |
| Q4 | ch07 md 实际 ~15KB（设计侧复核），回退前端 size guard 走富文本 | 前端 renderMarkdown 还原 | ✅ 已落地 |
| Q5 | ch07 step name 维持"三圆组合"，UI 升级由前端做 | 不改 | ✅ 不需改 |
| 附1 | 跨章同名 intersection 语义不同（ch03 readonly vs ch07 editable），前端按 chapter 区分 | 已与 Q1+Q2 一致 | ✅ 已覆盖 |
| 附2-1 | json_mode 未按 output_fields 类型生效 | agent.run_step line 193 json_mode=has_structured | ✅ 已合入 |
| 附2-2 | agent_configs 决策悬空（表无 seed） | scripts/seed_agent_configs.py UPSERT mentor + summary | ✅ 2026-08-04 |
| 附2-3 | ch04 修复须走 /config 端点（version+1 workflow），勿直 UPDATE 绕过 versioning | `POST /api/book/chapters/{id}/config` | ✅ 已合入 |
| 附2-4 | DB vs JSON 一致性脚本防 ch04 类问题复发 | scripts/check_config_consistency.py | ✅ 2026-08-04 |

**附2 backlog 已清零**：附2-3 POST /config 端点已完成。
## 3. 已拍板待办（不阻塞当前进度）



| # | 议题 | 拍板 | 触发 |

|---|---|---|---|

| Q11 | learner_profile user_id 跨会话隔离 | **决策 5**：现在不加 user_id 列；DEFAULT_USER_ID="local"；step_runs 不含 user_id；learner_profile.user_id 固定 'local'。多用户需求出现时再迁移（届时同步改 schema + migration + 所有 router 加 user_id）。已记入 ADR-001 / handoff §1.4 | 等多用户需求 |

| M4 | 逐章实现（按 §7）：8 章 step 落 profile；ch4 前端 groups/conversions 分支 | 待启动 | M3.3 ✅ |

| M5 | 前端桥接卡（章末回顾卡 + 三入口） | 待启动 | 等 M4 |

| M6 | 验收（§10 清单） | 待启动 | 等 M5 |
| 附2-3 | POST /api/book/chapters/{id}/config 端点（version+1 upsert workflow） | 已完成；后续配置修复统一走该端点 | ✅ 2026-08-05 |



## 4. M4 范围与计划（2026-08-03 启动）



按 handoff §7 逐章实施指南 + §10 验收清单逐章做：



### 通用规则

- 每章按 `chapter_config_chNN.json` 的 `exercises[]` 渲染前端 step 区块

- LLM 走 `agent.run_step` → `build_step_prompt`（已实现）

- `output_fields` 按类型化对象 `{name, type, lockable, readonly}` 渲染（前端待补 groups/conversions 分支）

- 章节内级联 = `exercises[].references` 走前序 step_runs.parsed_output（已实现）

- 跨章 = `mentor_hooks.references` 走 learner_profiles（Q2 已实现）



### 每章交付清单

- [x] chapter_config_chNN.json 已填 exercises + step_role_id + few_shot_examples + mentor_hooks（8 章都齐）

- [x] 端到端跑通：draft → run → submit → parse → profile 落字段（**M4.1 通过 test_m4_per_chapter.py 7 测**）

- [x] type 校验不阻塞（Q6 已实现）

- [x] reference 级联正确传递（章节内）（**M4.2 通过 test_m4_ch04_cascade.py 2 测**）

- [x] mentor 锚点正确读取 profile 字段（跨章）（**M4.3 通过 test_m4_ch07_cross_chapter.py 2 测**）



### 阻塞项

- ch4 step-2/3 前端需补 `groups`(editable_list) / `conversions`(list) 渲染分支（handoff §7.0 阻塞项）



### M4 完成情况（2026-08-04 启动）



#### M4.1 每章 schema-aligned mock LLM 验证（7 passed）

- `tests/test_m4_per_chapter.py 7 测全过：ch01/02/03/05/06/07/08

- mock LLM 按每章 output_fields 返回 schema-aligned JSON

- 验证两层：① 所有 declared output_fields 落 step_runs.parsed_output；

  ② PROFILE_FIELDS 白名单字段落 learner_profiles，章节内 artifact 留 step_runs

- ch04 端到端验证在 `test_m4_ch04_cascade.py



#### M4.2 ch04 章节内 references 级联（2 passed）

- `tests/test_m4_ch04_cascade.py 2 测全过

- step-1 → step-2 → step-3 → step-4 → step-5 顺序 5 步全过

- step-2 prompt 验证包含 step-1.top_values 内容（不放测试代理走抓取 user 字段）



#### M4.3 跨章 mentor_hooks.references 验证（2 passed）

- `tests/test_m4_ch07_cross_chapter.py 2 测全过

- ch07 step-1 prompt 包含 4 个 hook 字段（work_purpose/talents/likes/importance）

- ch02 step-1 prompt 读取 ch01 misconceptions_cleared（验证 mentor_hooks 跨章复用为 step references）



#### M4.4 ch07 上游依赖锁定（前后端）

- 前端 .gated-hint 类已存在，但检测逻辑需要补充

- 后端 chapter_status 端点待加（返回 ch03/ch04 是否 submitted）

| M5.1 后端 chapter_status 端点 (8 测) | ✅ |
| M5.3 章末回顾卡 (形态 B) | ⏳ |
| M5.4 三入口 (顶部常驻 / 步进浮层 / 章末卡) | ⏳ |
| M5.5 ch07 锁 UI | ⏳ |
| M5.6 前三章 DB seed 补齐 + llm_roles 脏行清理 | ✅ 2026-08-04 |
| M5.7 LLM 模型名 deepseek-chat → DeepSeek-V4-Flash + seed UPSERT | ✅ 2026-08-04（真实 LLM 端到端因沙箱拒网未验） |
| 设计侧 附2-1 agent_configs 表 seed + 迁移 | ✅ 2026-08-04 |
| 设计侧 附2-2 DB vs JSON 一致性脚本 | ✅ 2026-08-04 |
| 设计侧 附2-3 POST /config 端点（version+1 workflow） | ✅ 2026-08-05 |
| M6 验收 | ⏳ 等 M5 |



#### M4.5 前端 groups/conversions 渲染分支

- handoff §7.0 阻塞项



## 5. 关键代码改动汇总



- `app/runtime/assembler.py` —— build_step_prompt 新签名（chapter_md / profile / md_cap）

- `app/runtime/agent.py` —— run_step / run_mentor / run_summary + Q7 trigger helpers

- `app/services/compaction.py` —— compact_profile + Q8 extract_open_questions

- `app/routers/steps.py` —— Option B 路由 + type 校验 + BackgroundTasks Q8

- `app/routers/chat.py` —— 灰度切到 agent.run_mentor

- `app/routers/summary.py` —— 灰度切到 agent.run_summary

- `scripts/seed_roles.py` —— 4 个 role（psychologist / mentor / summary / career_counselor）
- `scripts/seed_agent_configs.py` —— agent_configs scaffold UPSERT（mentor + summary）
- `scripts/check_config_consistency.py` —— DB vs JSON 8 章一致性对比

- `llm_prompt_design/config/chapters/chapter_config_ch07.json` —— 补 importance

- `tests/` —— 39 passed



## 6. 备份与防回归



`llm_prompt_design/backups/` 6 个备份 + 设计侧 2026-08-04 改动另存于 `重构开放问题_设计侧确认.orig-2026-08-04.md`：

- `seed_roles.orig-2026-08-03.md` (2415B)

- `seed_roles.q10-2026-08-03-pre-mentor-summary.py` (5959B)

- `PRD-ch7.orig-2026-08-03.md` (30093B)

- `PRD-ch8.orig-2026-08-03.md` (29961B)

- `SPEC.orig-2026-08-03.md` (17198B)

- `chapter_config_ch07.orig-2026-08-03.json` (2653B)



## 7. 协作边界



- plan / progress / checkpoint 由开发侧维护；设计侧只 review 不直接改

- 本轮例外：设计侧改了 `seed_roles.py` 和 PRDs（内容源头），由开发侧 verify 通过

- 设计侧 Q&A 文档归设计侧维护（开发侧只提问不复答）


## 8. M5.9 ch01 独立误区卡与配置版本端点（2026-08-05）

### 已完成

- `platform/frontend/index.html`：ch01 checklist 改为 5 张独立误区卡；每张卡独立勾选与外部声音输入，提交时按误区编号生成 `external_voices` 映射。
- `platform/backend/app/main.py`：新增 `POST /api/book/chapters/{chapter_id}/config`，按 version+1 写入新配置并切换 active。
- 回归覆盖：新增配置端点版本切换测试、外部声音编号映射序列化测试。

### 验证

- 定向测试：`27 passed`。
- 全量测试：`104 passed`（使用 `tests --ignore=tests/_tmp`；该目录当前被系统拒绝访问，无法由 pytest 收集）。
- 本次改动 Python 文件定向 `py_compile` 通过；前端内嵌脚本抽取后 `node --check` 通过。
- 全目录 `compileall` 被既有 `app/runtime/assembler_clean.py` 语法错误阻断，未修改该无关文件。

### 下一步

- M6 人工验收：在 Service Dashboard 管理的 3011 页面确认 ch01 五卡片勾选、独立填写、保存草稿、运行 LLM、提交后的 payload 与 profile 展示。


## 9. M5.10 ch01 操作提示与导师入口修复（2026-08-05）

### 已完成

- `platform/frontend/index.html`：新增右上角 `?` guideline 弹层，文案与 A 流程一致，不在运行前假设「提交」已出现。
- 保留两阶段按钮状态：运行前「保存草稿 / 运行 LLM」；运行成功后显示「提交」。
- 修复「聊聊这一步」入口的 inline onclick 引号错误。
- 修复导师发送逻辑中错误引用未定义 `r` 的问题。

### 验证

- 内嵌脚本抽取后 `node --check` 通过。
- 3011/8011 浏览器实测：问号弹层可见、文案正确；运行前按钮为「保存草稿 / 运行 LLM」；点击「聊聊这一步」切换到对话面板；无控制台错误。





## 10. M5.11 运行库对话数据清理与 M6 自动验收（2026-08-05）

### 已完成

- 清理运行库中由测试残留的 20 条 `mentor: "hi"` 对话记录；清理前备份为 `platform/backend/data/backups/ww-20260805-before-chat-cleanup.db`。
- 修复 `tests/test_all_chapters_e2e.py` 的 mentor compaction 测试，统一使用 `all_app` 临时数据库 fixture，避免测试再次污染真实 `platform/backend/data/ww.db`。

### 验证

- `GET /api/chapters/ch01/chat` 返回空数组，运行库不再显示测试用「Hi」气泡。
- 全量后端测试：`104 passed`（`tests --ignore=tests/_tmp`）。
- 浏览器实测：3011/8011 当前服务正常；ch01 guideline、五张误区卡、导师入口和按钮状态机均通过；无控制台错误。

### 当前边界

- M6 的 mock/机器验收与浏览器交互验收已完成。
- 真实 LLM 端到端（保存草稿 → 运行 LLM → 提交，并确认 `step_runs` / `learner_profiles`）仍需在本地配置有效 API Key 后由用户执行；本轮不主动消耗 API 配额。

## 11. M5.12 ch01 保存/运行/摘要错误修复（2026-08-05）

### 已完成

- 修复 `platform/frontend/index.html` 保存草稿后重绘步骤列表导致当前步骤折叠的问题；保存和提交后会恢复当前步骤展开状态。
- 修复摘要生成继续把 `fetchJson` 返回对象当作 `Response` 调用 `.json()` 的问题；同时让 `fetchJson` 保留后端错误 detail，运行失败时不再丢失具体原因。
- 移除 `runStep` 中已失效的 `Response.ok/text` 分支，统一使用 `fetchJson` 的成功/异常语义。
- 修正 DeepSeek 模型 ID 大小写：seed、旧版 mentor/summary 路径和当前运行库 4 个启用角色统一为 `deepseek-v4-flash`。
- 清理 ch01 当前草稿行中由旧模型错误留下的过期 `step_runs.error`；修复保存草稿逻辑后续会同步清空该字段。

### 验证

- 浏览器保存草稿实测：步骤仍保持展开，状态显示「草稿」，五张误区卡输入保留。
- 浏览器摘要生成实测成功，`/api/chapters/ch01/summary` 已有摘要缓存；本次测试产生一次真实摘要请求。
- `8011 /api/health` 返回 `200`；角色接口显示 4 个启用 DeepSeek 角色均使用 `deepseek-v4-flash`。
- 前端内嵌脚本 `node --check` 通过；相关 Python 文件 `py_compile` 通过；`git diff --check` 无新增空白错误。
- 浏览器控制台仅剩既有 `/favicon.ico` 404，无应用脚本错误。

### 当前边界

- 本轮未再次点击真实「运行 LLM」，避免重复消耗 API；此前 500 根因已由运行库 `step_runs.error` 明确确认并修复。
- `8011` 未停止或手动重启；`steps.py` 的代码级保存错误清理将在 Service Dashboard 下次托管重载后生效，当前运行库中过期错误已手动清除。

## 12. M5.13 ch01 输出与提交后对话入口调整（2026-08-05）

### 已完成

- `platform/frontend/index.html` 为 ch01 结构化 LLM 输出增加正常分段渲染：分别显示「已识破的误区」列表和「外部声音」，不再展示裸 JSON。
- 提交后的完成提示从「把这一章放进对话」改为「我们已经了解了你的信息。如果需要，你可以和导师聊聊你的想法。」并提供「对话」按钮。
- 将提交后完成提示卡移入右侧步骤侧栏，修复其作为三列网格子元素导致 Chat Tab 掉到左侧栏的问题。
- 「对话」按钮只切换右侧 Chat Tab，不再把桥接卡放入网格第三列。

### 验证

- 使用模拟 submitted + JSON 输出的浏览器回归：输出显示为分段列表；完成提示文案正确；点击「对话」后 Chat Tab 位于右侧栏。
- 浏览器几何检查：Chat Pane `left=917`，Side Panel `left=916`，未出现左侧掉栏。
- 前端内嵌脚本 `node --check` 通过；后端相关 Python `py_compile` 通过；`git diff --check` 通过。

### 当前边界

- 本轮未再次执行真实 LLM；浏览器回归使用网络 mock，不修改运行库提交状态。
- 原交接文档 §8.7 的三入口能力保留；本轮仅按用户最新产品确认调整章末完成卡文案与入口行为。

## 13. M6 全章 Mock / 浏览器 E2E 回归与共享组件修复（2026-08-05）

### 本轮发现与修复

- 使用 webapp-testing / Playwright 按真实配置遍历 ch01–ch08，发现共享 `collectSchemaAnswers` 在 list_of_items 分支对 `querySelectorAll()` 直接调用 `.map()`，导致 ch02 运行前端报错；已改为 `Array.from(...).map(...)`。
- 同一轮发现 `renderStepOutput` 对 ch02 表格、ch05 `talents`、ch06 `likes`、ch08 `success_statement/color_bath_log` 会退化为裸 JSON；已按交接文档 §4.3 的 `output_fields.type` 增加通用 `editable_list` / `list` / `text` / `markdown` / `table` 渲染，并保留 ch01、ch04 groups/conversions 专用分支。
- 新增结构化表格样式；所有新增文本、表格单元格和列表输出经过 HTML 转义。

### 验证

- 后端临时数据库 Mock E2E：8 章、12 个步骤全部通过；draft → run(mock LLM) → submit、角色路由、ch04 五步提交和 profile 当前章节均通过，12 条 `step_runs` 均为 `submitted`。
- 浏览器全章 E2E：ch01–ch08 全部通过；覆盖 Tab 切换、步骤展开、真实 schema 控件、保存草稿保持展开、Mock LLM 输出、提交完成卡、对话切换、刷新状态恢复。
- 浏览器 E2E 无应用 console 错误、无 500、无失败请求；结构化输出不再出现裸 JSON `<pre>`。
- 前端内嵌脚本抽取后 `node --check` 通过；`git diff --check` 通过；3011/8011 HTTP 探测正常，服务未停止或手动重启。

### 当前边界

- 本轮所有浏览器 run/submit 请求均为网络 mock，后端 Mock 使用临时数据库；未再次调用真实 LLM，也未修改运行库提交状态。
- 真实 API Key 场景仍需用户在 Service Dashboard 页面执行一次受控 ch01 运行，确认真实 `step_runs` / `learner_profiles` 结果。

## 13. M5.14 结构化 LLM 输出与空响应保护（2026-08-05）
### 已完成
- `platform/backend/app/runtime/assembler.py` 增加结构化输出判定，并在 `output_fields` 含结构化类型时明确要求模型只返回一个 JSON object；`platform/backend/app/runtime/agent.py` 复用同一判定决定 `json_mode`，避免 DeepSeek JSON mode 因 prompt 未出现 `json` 被 400 拒绝。
- `platform/backend/app/services/llm_client.py` 增加 content 兼容提取与 `LLMEmptyResponseError`；当 provider 首次以 `finish_reason=length` 结束且只有 reasoning content 时，仅重试一次并将 `max_tokens` 提升到 4k–6k；仍无最终 content 则明确失败，不再保存空成功结果。
- `platform/backend/app/routers/steps.py` 增加失败运行 upsert；运行失败返回 502 并落库 `failed`，提交只接受 `saved` 且同时存在非空 `llm_response`/`parsed_output` 的运行，失败时清理旧输出，避免空结果进入提交和 profile compaction。
- 新增/补充结构化 prompt、空 content、reasoning length retry、空响应运行/提交回归覆盖。
### 验证
- 目标 Python 文件 `py_compile` / `compileall` 通过。
- 隔离回归通过：JSON prompt + `json_mode=True`、空 content → 502、失败运行 → submit 409、reasoning length 首次 1500 → 二次 4000。
- `scripts/smoke_ch01_mock.py` 通过；运行时设置 `DISABLE_OPEN_QUESTIONS_EXTRACT=1`，未触发额外真实请求。
- 受控真实 ch01 agent smoke 通过：返回非空 JSON，字段包含 `misconceptions_cleared`、`external_voices`；只读取 live DB 配置，不写 `step_runs`，未停止或重启 `3011/8011`。
- 当前命令行未安装 `pytest`，因此本轮未重新执行 pytest；历史全量回归记录仍为 `104 passed`。
### 当前边界
- 真实 smoke 只验证了当前源代码直接调用；Service Dashboard 管理的 `8011` 未重启，代码由 Dashboard 后续托管重载后生效。
- live DB 中此前真实 smoke 产生的空 ch01 submitted row 未在本轮覆盖或恢复；已有备份 `platform/backend/data/backups/ww-20260805-before-real-ch01-smoke.db`，恢复前需确认不覆盖其后的用户数据。
- 当前 ch01 配置将 `external_voices` 声明为 `markdown`；受控真实输出的类型为字符串。前端仍兼容按误区 ID 对象、数组和字符串渲染；不擅自改变设计配置。
## 14. M5.15 pytest 全量回归与异步警告修复（2026-08-05）
- 修复 `platform/backend/app/runtime/agent.py` 中同步场景触发 `_force_mentor_compaction()` 时产生悬空 coroutine 的问题：先获取 running loop，再创建 `extract_and_persist_open_questions` task。
- 全量测试命令：`python -m pytest tests --ignore=tests/_tmp -q`。
- 结果：`108 passed, 113 warnings, 14.65s`；此前的 `coroutine was never awaited` 警告已消失。
- 剩余警告为 FastAPI `on_event` 弃用提示、`book.py` 正则 FutureWarning，以及 pytest 在 Windows 清理临时目录时的 `PermissionError`；pytest 退出码仍为 0，未发现测试失败。
## 15. M6 只读浏览器验收与 live 无效运行修复（2026-08-05）
### 已完成
- 使用 Playwright CLI 对 `http://localhost:3011/` 与 ch01 做只读探查：页面加载成功，角色/章节/内容/摘要/chat/notes/config/state/step API 全部返回 200。
- 修复 `platform/frontend/index.html` 对空 `parsed_output` 的防御展示：不再渲染裸 `{}`，改为提示“本次运行没有有效输出，请重新运行 LLM”。
- 为前端增加内嵌 favicon 声明，消除根页面 `/favicon.ico` 404；浏览器 console 验收达到 `0 errors / 0 warnings`。
- 先创建 `platform/backend/data/backups/ww-20260805-before-invalid-run-repair.db`，再将 live DB 中 3 条 `saved/submitted + 空 LLM 输出` 记录标记为 `failed`，不删除记录、不修改 profile。
### 验证边界
- 后端全量 pytest：`108 passed, 113 warnings`；未 awaited coroutine warning 已在 M5.15 修复。
- 本轮浏览器验收未点击“运行 LLM/提交”，避免对已有 live 用户数据产生新写入；真实 ch01 agent 已在前一阶段直接调用验证成功。
- `3011/8011` 均未停止或手动重启；Service Dashboard 后续重载后才会加载最新后端代码。
### 下一步
- M6 最后一项：在确认 live DB 数据范围和 Service Dashboard 重载窗口后，由用户在页面执行一次新的 ch01 `draft → run LLM → submit`，核对真实 `step_runs` 与 `learner_profiles`；不直接恢复旧备份覆盖后续数据。
## 14. M5.16 ch01 失败运行清理与提交后即时对话入口（2026-08-05）

### 已完成

- `platform/frontend/index.html`：历史 `failed` 运行不再作为当前运行展示，避免进入步骤页时出现误导性的「失败」状态、旧测试勾选和问号输入；展开步骤时仅提示「上次运行没有完成」，回到干净输入状态。
- 已提交步骤在当前步骤内显示「我们已经了解了你的信息。如果需要，你可以和导师聊聊你的想法。」及「对话」按钮，不再必须滚动到步骤栏顶部寻找章末卡。
- 已提交步骤锁定输入控件并移除保存/运行/提交操作，避免提交后继续修改已锁定结果。

### 验证

- 前端内嵌脚本 `node --check` 通过，`git diff --check` 通过。
- 使用 Chrome + Playwright 只读模拟两种状态：失败运行不回填 `????` 或勾选；已提交运行显示即时 CTA、隐藏操作区、输入不可编辑，点击「对话」切换 Chat Tab；无页面错误。
- 本轮未停止、手动启动或重启 `3011/8011`，未修改 live DB。刷新 `3011` 即可读取前端改动。

### 当前边界

- 用户此前真实 ch01 流程已走通；本轮修复的是进入页面时的历史失败数据呈现和提交后的导航体验。
- 后续仍按计划推进真实 API Key 场景的受控验收与下一阶段功能，不再通过逐个手动点击发现共享 UI 回归。

## 15. P0-3 step_runs 状态机护栏（2026-08-05）

### 已完成

- `platform/backend/app/routers/steps.py`：`_persist_run` 改为按 `run_id` 更新 draft/saved，失败或已提交运行使用新 id 插入，不再按章节最新行覆盖已提交历史。
- `platform/backend/tests/test_ch01_e2e.py`：新增提交后再次运行回归，验证原记录仍为 `submitted`、新运行独立落库为 `saved`。

### 验证

- 定向测试：`4 passed`。
- 全量后端回归：`109 passed, 115 warnings`；warning 仍为 FastAPI `on_event` 弃用、book 正则 FutureWarning 和 Windows pytest 临时目录清理权限提示。
- 测试未触碰 live DB；未停止、手动启动或重启 `3011/8011`。

### 下一步

- 继续处理 REVIEW 中剩余的 P0 并发/事务护栏，保持每项都有复现测试和全量回归。

## 16. P0-4 `/run` 输入 schema 服务端校验（2026-08-05）

### 已完成

- `platform/backend/app/routers/steps.py`：`POST /api/chapters/{chapter_id}/steps/{step_id}/run` 在调用 LLM 前复用 `_validate_user_answers`，非法 checklist id、list_of_items 行或 select 值直接返回 `422`，不写入运行记录、不触发 LLM。
- `platform/backend/tests/test_ch01_e2e.py`：新增非法误区 id 的 422 回归测试。
- 同时确认 REVIEW P0-1（SQLite `check_same_thread=False` + `timeout=10.0`）和 P0-2（chat 两条消息在同一事务中落库）当前代码已具备，无需重复改动。

### 验证

- 定向测试：`5 passed`。
- 全量后端回归：`110 passed, 117 warnings`；无跳过测试。
- 本轮未修改 live DB；`8011` 尚未重载，后端改动需通过 Service Dashboard Reload/Restart 后才会在线生效。

### 下一步

- 用户通过 `http://localhost:4005` Reload/Restart What Want backend `8011`，随后做一次只读 API 验证和必要的真实 UI 回归。
- 之后继续 REVIEW 中剩余的 P0/P1 护栏，不绕过阻塞条件。

## 17. P0-5 提交后输出锁定护栏（2026-08-05）

### 已完成

- `platform/backend/app/routers/steps.py`：`PUT /api/chapters/{chapter_id}/steps/{step_id}/output` 查询当前运行状态；已提交运行拒绝编辑并返回 `409`，避免提交结果被覆盖。
- `platform/backend/tests/test_ch01_e2e.py`：新增已提交输出不可编辑回归；同时修复测试装饰器错位，确保空 LLM 响应测试实际执行。

### 验证

- ch01 定向回归：`6 passed, 0 skipped`。
- 全量后端回归：`111 passed, 119 warnings`；无测试失败或跳过。
- 剩余 warning 主要为 FastAPI `on_event` 弃用、`book.py` 正则 FutureWarning，以及 Windows pytest 临时目录清理权限提示；不影响退出码 0。
- 未停止、手动启动或重启 `3011/8011`，未修改 live DB。

### 下一步

- 用户通过 `http://localhost:4005` 对 What Want backend `8011` 执行 Reload/Restart，使最新输出锁定代码在线；随后验证已提交步骤调用 `PUT /output` 返回 `409`。
- 在线护栏验证完成后，继续 REVIEW 中剩余的 P0/P1 项。
## 18. P0-5 在线护栏验收（2026-08-05）

- 用户已通过 Service Dashboard 重载 What Want backend `8011`。
- 只读读取确认 ch01 step-1 当前运行状态为 `submitted`，存在有效 `parsed_output`。
- 使用当前原值调用 `PUT /api/chapters/ch01/steps/step-1/output`，在线返回 `409`：`submitted step output is locked`。
- 前后核对确认 run id、状态和输出内容均未变化；本次验证未改写 live DB。

### 阶段结论

- P0-5 提交后输出锁定护栏已完成代码、回归测试和在线验证。
- 继续进入 REVIEW 中剩余的 P0/P1 护栏，保持每项都有复现测试、全量回归和必要的在线验收。
## 19. REVIEW P0/P1 清单复核与 M6 边界确认（2026-08-05）

- 复核 `platform/REVIEW.md` 与当前代码/测试：P0-1～P0-5 均已有实现、回归测试，并完成本轮 P0-5 在线验收。
- 附2-1～附2-4 已完成：结构化 `json_mode`、`agent_configs` seed、`POST /api/book/chapters/{chapter_id}/config` version+1、DB/JSON 一致性脚本。
- P1-5/P1-6 已完成；P1-3 当前使用 `created_at + rowid` 明确稳定排序。
- P1-2/P1-4 仍按原 REVIEW 标记为数据规模达到阈值后再处理，当前不应为了“继续开发”而提前引入索引或元数据表。

### 当前边界

- 本轮没有新的高风险代码项需要猜测式修改。
- 后端自动回归基线保持 `111 passed, 119 warnings`；`8011` 已加载 P0-5 最新代码并完成在线验证。
- 下一步进入 M6 真实 API Key 场景：由用户在 `3011` 执行一次受控 ch01 `保存草稿 → 运行 LLM → 提交`，再核对 live `step_runs` 与 `learner_profiles`。
## 20. M6 真实 ch01 验收前测试数据隔离（2026-08-05）

### 已完成

- 用户确认清理范围后，先备份 live DB：`platform/backend/data/backups/ww-20260805-before-real-ch01-reset.db`。
- 备份与源库大小均为 `688128` 字节，SHA-256 校验一致。
- 在单个 SQLite 事务中清理：
  - `step_runs` 中 `chapter_id='ch01'`：删除 1 条；
  - `chapter_chat` 中 `chapter_id IN ('ch01','ch1')`：删除 4 条；
  - `learner_profiles` 中 `user_id='local'`：删除 1 条。
- 其他章节的 29 条 `step_runs` 保留，未做全库清理。

### 在线复核

- `GET /api/health`：`200`。
- `GET /api/chapters/ch01/steps/step-1`：`current_run=null`。
- `GET /api/chapters/ch01/chat`：返回 0 条消息。
- 未停止或重启 `3011/8011`；服务在线读取到清理后的状态。

### 下一步

- 用户在 `3011` 执行干净的 ch01 `保存草稿 → 运行 LLM → 提交`，开发侧随后核对新的 `step_runs` 与 `learner_profiles`。
## 21. M6 上下文完整性审计：ch01 暴露的全章问题（2026-08-05）

### 已确认根因

1. **ch01 LLM 输出契约不足以要求分析**
   - 当前 `chapter_config_ch01.json` 只声明 `misconceptions_cleared` 与 `external_voices`，`output_template` 也只要求清单和旧观念。
   - `build_step_prompt` 虽然注入本章 MD，但没有强制输出“逐条基于书中内容解释为什么是误区”的 `commentary`。
   - ch01 PRD §5.1 已要求 `commentary + misconceptions_cleared + external_voices`，与工程交接文档 §7.1 当前的“两字段”表述不一致；后续需同步 PRD、SPEC、交接文档和配置，不能只改 prompt。

2. **导师 profile 上下文未真正注入**
   - ch01 提交后 `learner_profiles` 确实保存了误区和外部声音。
   - 但 `assembler.build_mentor_prompt` 在 `mentor_hooks.references=[]` 时只注入“current chapter”占位，不注入 profile 内容；因此导师看不到刚提交的外部声音。
   - 这不是前端加载失败，而是后端上下文装配逻辑丢失。

3. **“聊聊这一步”当前只显示假上下文提示**
   - `frontend/index.html` 的 `openBridgeChat` 只显示“已加载输出作为上下文”的前端 banner，没有将真实 step 输出发送给 `/chat/send`。
   - 需要将 `chapter_id + step_id`（并由后端读取最新 submitted 输出）真正传入导师 prompt。

4. **step prompt 默认没有 user_id，后续章节也可能拿不到 profile**
   - `agent.run_step(..., user_id=None)` 在 router 调用时没有补 `DEFAULT_USER_ID`。
   - 因此 ch02/ch03 等依赖 `mentor_hooks.references` 的 step prompt 可能没有读取 `learner_profiles`，不是 ch01 特有问题。

5. **ch04 → ch08 profile 字段映射缺失**
   - 交接文档规定 ch04 step-1 的 `top_values` 汇入 profile 的 `values`。
   - 当前 `compaction.py` 只按同名字段提取，未执行 `top_values → values` 映射；ch08 的 `mentor_hooks.references=[values,...]` 可能因此拿不到价值观。

6. **章节内 references 缺少完整性护栏**
   - `agent._load_prior_outputs` / `_format_references` 对未提交来源或缺失字段只放入提示文字或静默跳过，没有阻止 LLM 在缺上下文时继续生成。
   - 后续 ch04 五步级联等场景需要在运行前校验来源 step 和字段；缺失时明确返回上下文错误，不允许“看似成功但少了输入”。

7. **配置中存在待澄清的跨章引用缺口**
   - ch04 `mentor_hooks.references=[formula]`，但当前 8 章 exercise output 中没有明确的 `formula` 生产者。
   - 该项必须进入设计文档同步/拍板清单，开发侧不自行猜测替换成其他字段。

### 全章影响范围

- 影响章节内级联：ch04 step-2～step-5，及未来所有声明 `exercises[].references` 的步骤。
- 影响跨章 step/profile：ch02、ch03、ch05、ch06、ch07、ch08。
- 影响导师连续性：所有章节；ch07/ch08 由于引用字段最多，作为重点验收样本，但不是唯一范围。

### 计划修复

- ch01 输出增加结构化 `commentary`，并同步 prompt、前端渲染、profile 落库边界和测试。
- mentor prompt 始终注入 compact profile；hook references 同时输出字段可用性/缺失状态。
- bridge 入口传递 `step_id`，后端从最新 submitted run 读取真实 step context。
- `run_step` 默认使用 `DEFAULT_USER_ID`；compaction 增加 `top_values → values` 显式映射。
- 增加章节内 references 完整性校验、跨章 profile producer/consumer 静态检查，以及 ch02/ch03/ch04/ch07/ch08 回归覆盖。

### 设计文档待同步

- `llm_prompt_design/docs/PRD/PRD-ch1.md`
- `platform/SPEC.md`
- `llm_prompt_design/docs/工程实施交接文档.md`
- `llm_prompt_design/config/schema/chapter_task_config.schema.json`（若 commentary 契约需要 schema 约束）
- 各章配置与 `platform/backend` seed/DB version+1 数据

## 22. M6 全章上下文链路修复与 ch01 配置发布（2026-08-05）

### 已完成

- ch01 `output_fields` 统一为 `commentary`、`misconceptions_cleared`、`external_voices`；`output_template` 强制要求基于本章正文逐条解释误区、给出正确认知、区分外部声音，并禁止只复述用户原话或替用户判断。
- mentor prompt 在 `mentor_hooks.references=[]` 时仍注入完整 compact `learner_profile`；步骤桥接保存 `step_id`，`/chat/send` 发送并由后端读取最新 submitted `step_runs.parsed_output`。
- ch04 `top_values → values` 映射已保留；章节 compaction 改为合并既有 profile，避免 ch02/ch03/ch05/ch06/ch07/ch08 覆盖前序字段。
- 章节内 `references` 在运行前校验来源 step 与字段；缺失时返回 `409 Step context incomplete`，不再在缺上下文时生成“看似成功”的输出。
- 前端 `renderStepOutput` 同时渲染 commentary、误区清单和外部声音，commentary 经过 Markdown 渲染并避免提前 return。
- 新增全章上下文完整性回归：跨章 mentor 引用图、ch04 五步级联、profile 合并、bridge step context、ch01 分析契约。
- 已通过 `python -m pytest tests --ignore=tests/_tmp -q`：`120 passed, 123 warnings`；前端内嵌脚本 `node --check` 通过。
- 已通过 `POST /api/book/chapters/ch01/config` 发布 live DB version `4`；未停止或重启 `3011/8011`，现有真实 ch01 数据未清理。

### 设计文档同步

- 已同步 `PRD/PRD-ch1.md`、`platform/SPEC.md`、`工程实施交接文档.md`：明确 commentary 契约、profile 合并、references 完整性和 bridge step context。

### 未决项

- ch04 `mentor_hooks.references=[formula]` 仍没有明确 producer；保持显式缺口，等待设计侧确认，不自行替换字段。
- pytest 仍有既有 FastAPI `on_event` 弃用、book 正则 FutureWarning 和 Windows 临时目录权限 warning；不影响退出码，本轮未扩大范围修复。

## 23. M6 ch01 重测前数据清理（2026-08-05）

- 用户确认后，使用 SQLite 在线备份保存 live DB：`platform/backend/data/backups/ww-20260805-before-ch01-reset-203809.db`。
- 备份 SHA-256：`d67600e83b93ba9da561173e8387b2677c35ebad8f25890a1f221fadf9d0c77c`。
- 清理范围：ch01 `step_runs` 1 条、ch01/ch1 对话 4 条、`learner_profiles.user_id='local'` 1 条。
- 其他章节 29 条运行记录保留；未删除章节配置，live ch01 config 仍为 version `4`。
- 在线复核：`8011` health=200、ch01 `current_run=null`、ch01 chat=0 条，输出字段仍为 `misconceptions_cleared` / `external_voices` / `commentary`。
- 下一步：用户通过 Service Dashboard Reload/Restart `8011`，刷新 `3011`，执行干净 ch01 流程；本次未停止或重启任何服务。

## 24. M6 ch01 反馈修复、上下文契约收口与 version 5 发布（2026-08-05）

### 用户反馈根因与修复

1. **“聊聊这一步”出现过早**：输入阶段没有可供导师使用的 LLM 结果，前端现在仅在成功产生 `parsed_output` 后显示该入口；不会在填写外部声音时提前出现。
2. **LLM 输出重复且缺少针对性分析**：ch01 的 `commentary` 现在必须针对每个勾选误区，结合对应的 `external_voices` 和用户想法，用本章正文解释误区如何形成及可继续观察的方向；前端有 `commentary` 时不再重复渲染同一份结构化输入。
3. **导师照本宣科**：mentor prompt 明确要求先回应用户具体经历和外部声音，用自己的话解释书中原则；禁止“书中说 / 作者说 / 本章写到”等逐字引用式表达，不写整章摘要，不替用户下结论。

### 全章教训

- 前一步输出必须作为后一步的真实输入：章节内级联读取已提交 `step_runs.parsed_output`，跨章读取合并后的 `learner_profiles`，不能只依赖前端提示或 profile 占位符。
- 该规则适用于 ch02/ch03/ch04/ch05/ch06，也适用于 ch07/ch08 的跨章节综合引用；ch07/ch08 只是验收重点，不是唯一适用范围。
- 缺失 references 来源或字段时必须阻止生成并返回上下文错误，避免“流程成功但上下文不完整”。

### 验证与发布

- 定向回归：`31 passed`。
- 全量回归：`python -m pytest tests --ignore=tests/_tmp -q` → `123 passed, 123 warnings`。
- 已通过 `POST /api/book/chapters/ch01/config` 发布 live DB version `5`；未停止或手动重启 `3011/8011`。
- warning 仍为既有 FastAPI `on_event` 弃用、book 正则 FutureWarning 和 Windows pytest 临时目录权限 warning，不影响退出码。

### 下一步

- 用户通过 Service Dashboard Reload/Restart `8011` 后刷新 `3011`；由于 version 5 只影响后续运行，重新验收前需先确认是否清理当前 ch01 测试数据。

## 25. M6 A方案：ch01 证据绑定与导师收敛闭环（2026-08-05）

### 已完成

- `build_step_prompt` 为 ch01 每个已勾选误区构造独立证据块：误区编号、错误认知、本章原则、对应 `external_voice` 和四步分析要求。
- ch01 `commentary` 契约要求逐条引用用户外部声音短语，解释其造成的卡点，用本章原则重构，并给出观察方向或低成本行动；禁止泛化摘要、只复述输入和照本宣科表达。
- `build_mentor_prompt` 增加 active focus、外部声音、本章原则、对话阶段和追问轮数状态；导师最多连续追问同一焦点两轮，用户问“怎么做”时先给行动，明确切换前不得自行换误区。
- live mentor role 已通过 `PUT /api/roles/{role_id}` 同步 `mentor_config.json` 的 1.1 规则；`seed_agent_configs.py` 已同步 mentor/summary scaffold。
- 已通过 `POST /api/book/chapters/ch01/config` 发布 live DB version `6`；API 复核确认 active ch01 few-shot 不含字面量 `??`。
- 定向测试 `33 passed`；全量测试 `125 passed, 123 warnings`。

### 全章教训固化

- 前一步输出必须成为后一步的真实输入：章节内级联只读取已提交 `step_runs.parsed_output`，跨章连续性读取合并后的 `learner_profiles`；前端提示、占位 profile 或自然语言暗示都不算上下文传递。
- 该规则覆盖 ch02–ch08；ch07/ch08 仅是跨章引用的重点验收样本，不是唯一适用章节。
- 每个依赖字段都必须有 producer、consumer 和缺失时的阻断测试；缺失来源或字段时返回上下文错误，不让 LLM 在不完整输入上“看似成功”。
- 运行中的 `8011` 需要由用户通过 Service Dashboard Reload/Restart 重新加载后端代码；本轮未停止、kill 或手动重启 `3011/8011`，也未清理现有 ch01 数据。

### 下一步

- 用户 reload `8011` 并刷新 `3011`，用新的 ch01 数据验证：逐条 commentary 是否绑定输入、导师是否围绕当前误区收束且不照本宣科。
- 后续章节开发沿用同一上下文契约，先补 producer/consumer 与 E2E 测试，再实现页面。

## 26. M6 A方案验收前 ch01 数据隔离（2026-08-05）

- 用户指出不清理数据无法验证；已执行受控清理。
- SQLite 在线备份：`platform/backend/data/backups/ww-20260805-223529-before-ch01-reset-v6.db`。
- 备份 SHA-256：`17fe573c003081d279dc27ac032556f9c78c010072750ad01106ff0eafa29d6e`。
- 清理范围：ch01 `step_runs` 1 条、ch01/ch1 对话 18 条、`learner_profiles.user_id='local'` 1 条。
- 保留范围：其他章节 29 条运行记录、全部 14 条 chapter_configs、live ch01 version 6。
- 当前未停止或重启 `3011/8011`；下一步用户通过 Service Dashboard Reload/Restart `8011`，刷新 `3011`，执行干净 ch01 流程。

## 27. M6 ch01 误区清单正文对齐与 version 7 发布（2026-08-05）

- 根因确认：右侧误区卡不是 LLM 总结，而是 `chapter_config_ch01.json.input_schema.items` 经 `renderSchemaField` 原样渲染；旧配置的 3–5 与正文不一致，1–2 也不是正文精确标题。
- 已按第一章正文五个 POINT 修正页面数据源：1「必须是能坚持一生的事」、2「找到想做的事时会有命中注定的感觉」、3「必须是对别人有益的事」、4「必须多行动才能找到」、5「想做的事不能成为工作」。
- 同步修正 `core_concepts`、guiding questions、exercise/top-level few-shot，避免 LLM 继续使用旧误区定义。
- `PRD-ch1.md` §1.1 五误区表已按正文同步；新增回归断言锁定 5 个卡片标题和正确认知。
- 定向测试 `29 passed`；全量测试 `125 passed, 123 warnings`。
- 已通过 `POST /api/book/chapters/ch01/config` 发布 live DB version `7`；API 回读确认 5 张卡与正文一致、无损坏字符。
- ch01 数据此前已清理，当前可直接从干净状态验收；刷新 `3011` 即可看到新卡片。

## 28. M6 ch02 页面 E2E 与全章节浏览器烟测（2026-08-05）

### 验证结果

- Playwright 使用 Python `1.62.0`，显式浏览器路径为 `D:\Programs\playwright-browsers\chromium-1234\chrome-win64\chrome.exe`；完整 Chrome 可正常启动，不依赖额外下载的 headless shell。
- 使用真实页面路径完成 ch02：切换「步骤」→填写两条内外驱动事项→保存草稿（`200`）→运行 LLM（`200`）→渲染结构化表格和「收回主动权」→提交（`200`，`compacted=true`）。
- 提交后输入控件全部锁定，完成提示和「对话」按钮显示；点击后切换 Chat Tab，并将 `bridgeStepId=step-1` 保留到发送请求。
- 导师发送请求携带 `step_id=step-1`，返回 `200`；回复同时引用了 ch01 已保存的外部声音和当前 ch02 step 输出，确认跨章 profile 与当前 submitted step context 都进入了导师上下文。
- ch01–ch08 浏览器烟测全部通过：8/8 页面加载、4/4 Tab 切换、12 个步骤卡均可展开（ch04 为 5 个步骤），无 console error、无 request failure。
- 定向上下文回归：`32 passed`；全量后端回归：`125 passed, 123 warnings`。剩余 warning 为 FastAPI `on_event` 弃用、章节编号正则 FutureWarning，以及 Windows pytest 临时目录清理权限提示，均未影响退出码。

### 本轮 live 测试数据

- ch02 `step-1` 当前保留 1 条 `submitted` 测试 run，包含两条 E2E 事项和结构化输出。
- ch02 对话当前保留 2 条消息；`learner_profiles.user_id='local'` 已合并 ch01 profile 与 ch02 输出，`current_chapter='ch02'`。
- 以上数据仅用于本轮验收，清理前需用户确认；未停止、kill 或手动重启 `3011/8011`。

### 下一步

- 继续 ch03 的输入契约梳理：先确认其 producer/consumer，补前一步真实 submitted output 的 API/E2E 阻断测试，再实现页面行为。
- 沿用本轮验收模板覆盖 ch04–ch08，尤其验证章节内级联和跨章 profile 不被历史 run 或占位数据污染。

## 29. M6 ch02 E2E 数据清理（2026-08-05）

- 用户确认清理后，先在线备份 live SQLite：`platform/backend/data/backups/ww-20260805-before-ch02-reset.db`。
- 备份大小 `733184` bytes，SHA-256：`c803c2be37eefe5015925f5177dc455d64e0fb4c089bf6226ec53b305a065ee5`。
- 仅删除本轮精确生成的 ch02 数据：1 条 `step_runs`、2 条 `chapter_chat`；未批量删除其他章节数据。
- 从 `learner_profiles.user_id='local'` 移除本轮 ch02 的 `internal_external_ratio`、`reclaim_item`，恢复 `current_chapter='ch01'`；ch01 的 `misconceptions_cleared`、`external_voices`、`open_questions` 保留。
- 清理后复核：目标 run=0、目标 chat=0、ch02 输出字段不存在；未停止、kill 或手动重启 `3011/8011`。

## 30. M6 全章节 few-shot 完整性门禁（2026-08-05）

### 已固化的教训

- ch01 暴露的 `few-shot` 损坏不是 ch01 特例：配置编码、备份恢复、DB 发布和页面/LLM 读取之间任一环节都可能把内容变成 `??` 或 Unicode replacement character。
- 因此每章验收前都必须检查 canonical JSON 的所有 `few_shot_examples`，并结合 DB vs JSON consistency 检查 active config；不能只在页面上看到结果后再人工判断。
- ch01 的输入绑定、逐条分析、真实 submitted context、跨章 profile、导师收敛规则也全部视为 ch02–ch08 的通用验收契约；ch07/ch08 只是重点跨章样本，不是唯一适用章节。

### 自动化门禁

- `tests/test_context_integrity.py::test_all_chapter_few_shots_are_not_corrupted` 现在遍历 ch01–ch08 所有 `few_shot*` 字段，发现 `??` 或 `�` 立即失败。
- 本轮新增门禁验证通过：`13 passed`；现有 ch01 专项内容断言继续保留。
- live `check_config_consistency.py` 通过：ch01–ch08 全部 `[OK]`，DB active config 与 canonical JSON 一致；全量后端回归：`126 passed, 123 warnings`。
- 后续每章开发固定执行：配置完整性/编码门禁 → producer/consumer 上下文测试 → 页面 E2E → 全量 pytest → live 数据范围复核。

## 31. M6 ch03 三要素结构化输入与 Venn E2E（2026-08-06）

### 已完成

- 根因确认：ch03 live version 2 的 `input_schema=[]` 使前端退化成一个总文本框，不符合三圆练习设计。
- canonical config 已补齐 `likes`、`talents`、`importance` 三个 `list_of_items` 输入，每组 `min_items=3`、`max_items=5`。
- 输出契约已统一为 `commentary`、`likes`、`talents`、`importance`、`intersection`；`intersection` 为只读文本，三要素进入 learner profile。
- 前端新增 ch03 实时 Venn 预览，输入数量变化会更新三组计数和交集状态；不改变已有 API payload 或其他章节渲染。
- 已通过 `POST /api/book/chapters/ch03/config` 发布 live version `3`；API 回读确认三组输入和五个输出字段一致。
- 真实浏览器 E2E 通过：三组各 3 项 → 保存草稿 `200` → 运行 LLM `200` → 五字段结构化输出 → 提交 `200`、`compacted=true`；无 console error、无 request failure。
- 提交后 profile 已包含 ch03 的 `likes`、`talents`、`importance`、`intersection`，同时保留 ch01 `misconceptions_cleared`。
- 发布前 live SQLite 备份：`platform/backend/data/backups/ww-20260806-before-ch03-config-publish.db`；SHA-256：`fd3e621d1cb27ec35affedcacb8b6623e88cfa9f0e858719cb7f4d8a2a35972d`。

### 当前 live 状态

- ch03 当前保留本轮结构化 E2E 的 1 条 `submitted` run，profile 已更新到 `current_chapter='ch03'`；这是测试数据，后续真实验收前需单独确认是否清理。
- 之前遗留的 ch03 failed run 被草稿保存复用并转为本轮成功 run，未另增一条运行记录。
- 权威交接文档和 `PRD-ch3.md` 已同步 `commentary` 输出、三组结构化输入和实时 Venn 要求。

### 下一步

- 对 ch03 的导师对话做一次带三要素/profile 的上下文验证，再决定是否清理本轮 live 数据。
- 继续 ch04：先验证五步 `references` 的 producer/consumer 和缺失阻断，再做页面级级联 E2E；不要把 ch03 输出只当作页面展示。


## 3.48 ch03 导师对话重复发送修复（2026-08-06）

- 根因确认：前端 /api/chapters/{chapter_id}/chat/send 是 POST，但调用通用 fetchJson 时只覆盖了 timeout，继承了默认 retry=1；请求超时或网络异常后会再次提交，而后端在 LLM 成功后没有幂等键，导致同一组 user/mentor 消息重复落库。
- 最小修复：platform/frontend/index.html 的 sendChat 将该 POST 明确设置为 retry: 0；不改变 GET 请求的通用重试，也不改 live 数据或服务端口。
- 新增防回归契约：platform/backend/tests/test_context_integrity.py 检查 chat POST 永不继承自动重试。
- 验证：聊天/上下文定向测试 21 passed；全量回归（忽略已有无权限的 tests/_tmp）130 passed, 123 warnings；ch03 浏览器烟测打开步骤后 Venn 存在，无 console error/request failure；ch01-ch08 配置一致性 CLEAN。
- 环境说明：直接运行 pytest -q 仍会被既有 tests/_tmp 的 WinError 5 阻断，未擅自删除该目录；pytest 的临时目录清理仍有 Windows 权限 warning，不影响退出码。
- 经验推广：所有会触发 LLM 或写入数据库的 POST 都不能复用无差别自动重试；后续章节 E2E 需同时检查“请求次数=1”和“数据库消息/step run 数量=1”。

## 3.49 ch04 输出契约对齐与五步级联验收（2026-08-06）

- 只读核对发现实现与权威 PRD 的错位：Step 3 前端/测试沿用旧字段 `rewritten`，而设计要求 `value/type/converted_to/why_chain`；Step 5 canonical config 缺少 `reasoning`，前端原有 `work_purpose` 分支还会提前返回，吞掉 `experience_map`。
- canonical config 修复：Step 5 输出字段为 `work_purpose`、`reasoning`、`experience_map`；Step 3 保持设计规定的 `conversions` 结构。已通过正式接口发布 ch04 live version 4。
- 前端修复：Step 3 按「他人/不可控」与「自我/可控」显示转换结果，并渲染 `why_chain`；兼容历史 `rewritten`；Step 5 显示工作目的、推理过程和经历映射；用户文本统一转义。
- 测试增强：ch04 五步级联测试现在逐步断言 step-2/3/4/5 的 prompt 分别包含真实前序 submitted output，而不是只验证请求成功；上下文契约测试锁定 Step 5 字段和前端渲染标记。
- 验证：ch04 定向 + context 20 passed；全量回归（忽略既有无权限 `tests/_tmp`）131 passed, 123 warnings；浏览器渲染烟测确认 `converted_to`、`why_chain`、`experience_map` 正常显示且无 console/request 错误；ch01-ch08 config consistency CLEAN。
- live 发布前备份：`platform/backend/data/backups/ww-20260806-before-ch04-config-publish.db`；SHA-256：`3098369fa448a476ae1e0229bab90eb19ddf39958dba14cf4a1d18040d2c1359`。
- 经验推广：每章开发必须先用权威文档逐字段对比 canonical config、DB active config、前端 renderer、mock/test fixture；字段名称或嵌套结构不一致时，即使 API 200 和页面可打开，也不能视为完成。

## 3.50 ch05 产品/架构评审：流程确定，字段契约进入 backlog（2026-08-06）

- 已调用产品经理 Agent 与系统架构 Agent 并行评审 ch05 的交接文档/PRD/config 冲突；两者结论一致：唯一权威交接文档要求 ch05 保持 1 个 exercise / `step-1`，8 个角度分别填写 1–2 项，LLM 仅辅助归纳 `talents`，不替用户判断。
- 当前实现确实不符合该流程：`input_schema=[]`，前端退化为一个总文本框；后端空 schema 不校验 8 角度完整性；现有 E2E 只提交 `["a sample answer"]`，不能证明上下文完整。
- 按离线期间安全边界，本轮不改生产配置、不发布猜测字段：以下事项进入 backlog，等待设计侧明确后一次性落地：8 个稳定机器字段名与顺序、顶层 payload 形状、`talents` item schema、角度到 talent 的证据绑定、talents 编辑/锁定后的回写格式。
- 已确定且不会回退的产品决策：1 步九宫格流程、8 角度输入意图、输出顶层字段 `talents`、`editable_list` + `lockable=true`、mentor hook 引用 `work_purpose`。
- 继续推进策略：不让 ch05 的未决字段阻塞后续章节；先核对 ch06 的权威输入/输出/跨章 profile 引用，发现同类冲突时同样记录 backlog，不离线猜测。



## 3.51 M6 ch07 field-level cross-chapter context gate (2026-08-06)

- Product and architecture agents reviewed ch06-ch08. The handoff requires one exercise per chapter; ch06/ch08 structured input fields remain unresolved and stay in backlog instead of being guessed from the old PRDs.
- Confirmed ch07 producer/consumer contract: ch03 -> `likes`, `talents`, `importance`; ch04 -> `work_purpose`. Missing any field or incomplete upstream submission keeps the chapter locked.
- Added one readiness helper shared by status, step draft/run/submit routes, and mentor runtime. The frontend lock now shows missing profile fields instead of relying on a visual overlay only.
- Profile compaction gives higher preservation priority to structured fields and ch07 downstream requirements. If the profile still cannot retain required fields, readiness remains false.
- E2E fixtures now execute the real order ch03 -> ch04 -> ch05/ch06 -> ch07 -> ch08 and assert that submitted upstream runs without profile fields still return 409.
- Validation: targeted 35 passed; full `pytest --ignore=tests/_tmp -q` returned `133 passed, 127 warnings`; `scripts/check_config_consistency.py` returned `CLEAN` for ch01-ch08.
- Live validation after the 8011 restart: ch07 status returned `ready=false` because ch04 `work_purpose` is missing; browser smoke confirmed lock overlay, zero step cards, disabled chat input, visible missing field, and no console/request failures. Live data was not cleaned.
- Backlog remains: ch05 eight-angle input and `talents` item schema; ch06 decomposition input and `likes` item schema; ch07 `intersection` item schema and ch08 consumer field alignment; ch08 seven-day table schema and save/run/submit rules; final PRD/config synchronization.

## 3.52 Step prompt audit evidence persistence (2026-08-06)

- Architecture review found that `step_runs.rendered_prompt` stored only a placeholder, so it could not prove whether profile, chapter text, or prior outputs reached the LLM.
- `agent.run_step` can now return the raw response plus the final system/user prompts; the step route persists the actual assembled prompt while preserving raw-return compatibility for existing callers.
- Full E2E now asserts that the ch07 `step_runs.rendered_prompt` is not a placeholder and contains the real ch04 `work_purpose` value.
- Validation: full `pytest --ignore=tests/_tmp -q` returned `133 passed, 127 warnings`. This latest change was made after the most recent 8011 reload and still needs live verification after the next Service Dashboard reload.

## 3.53 ch02 四阶段重构落地与契约回归（2026-08-06）

### 已实现

- canonical config `chapter_config_ch02.json` 已对齐设计侧最终契约：
  - `drive_items` 最少 2、最多 10；每项包含 `text`、`drive`、可选 `note`；顶层 `notes` 可选。
  - 输出正式包含只读 `commentary`、后端派生的只读 `internal_external_ratio`、可编辑 `reclaim_item`。
  - `mentor_hooks.references` 同时引用 `misconceptions_cleared` 与 `external_voices`。
- 后端步骤 API：
  - draft 模式允许不完整输入；run 模式严格校验嵌套 required 和最少事项数。
  - ch02 非法 JSON、缺少 `commentary`/`reclaim_item` 会进入 `failed`，不能提交。
  - ratio 始终按 `drive_items[].drive` 件数由后端生成，覆盖 LLM 返回值，格式为 `external_pct/internal_pct/method:item_count`。
  - `PUT /output` 对 ch02 只允许修改 `reclaim_item`；commentary 和 ratio 保持只读。
  - submitted 后支持 `new_run=true` 创建新 draft；历史 submitted 保留；并修复同秒 run 只按 `created_at` 排序导致旧 run 被读回的问题。
  - compaction 按每个 step 最新 submitted run 读取，避免重做后旧提交污染 profile。
- Prompt：ch02 明确要求逐项结合事项、drive、note 分析，不替用户重标、不复述输入、不照本宣科，且保留 ch01 profile 上下文。
- 前端：新增 ch02 专属四阶段 renderer；阶段 1 填写、阶段 2 映照/比例、阶段 3 编辑并提交、阶段 4 归档/对话/新建草稿；其他章节仍走原通用 renderer。
- PRD `PRD-ch2.md` 已同步新阶段流、比例派生和输出字段要求。

### 配置发布与验证

- 通过现有配置发布 API 将 ch02 新配置发布为 live version `4`；未新增数据库表或字段。
- 真实 `3011` 页面 smoke：步骤卡可展开、四阶段按钮可见、初始有 2 条空事项、无 console error。
- Playwright 拦截 ch02 写接口完成前端流程：填写 → 运行 → 比例/Markdown 输出 → 编辑 reclaim → 提交 → 完成态/对话入口；无 console/page error，未污染 live 数据。
- 专项 `tests/test_ch02_e2e.py`：5 passed；ch02 M4 回归：1 passed。
- 全量回归：`pytest --ignore=tests/_tmp -q` → **138 passed, 137 warnings**。
- 默认 `pytest -q` 仍会被仓库既有无权限目录 `tests/_tmp` 阻断；该目录未修改、未清理。warning 主要是 FastAPI `on_event` 弃用、章节正则 FutureWarning、Windows 临时目录权限提示。

### 待用户动作 / backlog

- 代码变更尚未在当前 8011 进程加载；请通过 Service Dashboard Reload/Restart `8011`，再刷新 `3011` 做一次真实 ch02 数据流验收。未手动 kill/restart 服务。
- ch02 live 测试数据未清理；清理前需用户明确确认。
- 继续章节前，沿用本轮规则：先对照权威设计稿同步 config/DB/Prompt/renderer/test，再做 API 回归和浏览器 E2E；ch05/ch06/ch08 未决 schema 仍保持 backlog，不离线猜测。

## 32. ch02 重跑超时假失败修复（2026-08-07）

### 根因

- ch02 第二次运行时，浏览器端 `fetchJson` 的 LLM 请求上限为 90 秒；真实 provider 请求可能超过该窗口（本次观测约 117 秒）。
- 浏览器在 90 秒时触发 `AbortController`，用户看到 `signal is aborted without reason`；8011 后端请求并未立即停止，随后仍可能完成并把 run 保存为 `saved`，因此这是前端假失败，不是数据丢失。
- `runStep` 使用通用 `retry=1` 会对非幂等的 LLM `POST /run` 进行盲目重试，provider 慢或 5xx 时可能产生重复调用。

### 修复

- `platform/frontend/index.html`：ch02/全章节 LLM 运行请求等待上限改为 `180000ms`，并对 `POST /run` 设置 `retry: 0`。
- `runStep` 成功后显式把 ch02 阶段切回阶段 2（AI 分析），避免用户从阶段 2 返回修改后重新运行成功，却停留在阶段 1 误以为没有生成分析。
- `platform/backend/tests/test_context_integrity.py`：新增前端契约断言，锁定长耗时窗口、禁止 LLM POST 自动重试、成功后阶段跳转。

### 验证

- 前端契约测试：`2 passed`。
- ch02 后端专项：`5 passed`（使用工作区独立 `--basetemp`，避开机器既有 pytest 临时目录权限问题）。
- 真实浏览器回归：`POST /api/chapters/ch02/steps/step-1/run` 返回 `200`，约 42.9 秒完成，无弹窗、无 console/page error。
- 拦截式前端回归：LLM POST 只发送 1 次，成功后显示阶段 `2 / 4 · AI 分析`，无弹窗、无 page error。

### 后续通用教训

- 所有章节的 LLM 运行请求都视为长耗时、非幂等操作：前端必须使用足够的超时窗口，禁止通用自动重试；重跑逻辑应由用户显式触发。
- 章节验收必须覆盖“首次运行 → 返回修改 → 再次运行”，并同时检查浏览器请求是否提前 abort、后端 run 最终状态以及页面是否回到正确阶段。
- 当前未重启 `3011/8011`；本次修改为前端静态文件和测试记录，刷新页面即可读取最新前端代码。

## 33. ch02 后端 provider 超时与用户输入污染隔离（2026-08-07）

### 根因与证据

- 本次截图中的错误是后端真实返回：`500 Internal Server Error: Step run failed: Request timed out.`，不是上一轮前端 90 秒 AbortController 假失败。
- `AsyncOpenAI` 默认 `max_retries=2`，而当前 step LLM 请求使用 30 秒 SDK timeout；对非幂等 LLM POST 可能隐式重复请求，且 provider 速度稍慢时直接进入后端失败。
- 之前的真实浏览器回归曾向 live ch02 run 写入“超时修复回归”等测试文案，这是开发侧测试隔离失误。只读扫描当前 `step_runs`、profile、chat 等业务数据后，未发现“超时恢复/超时修复/回归/测试”残留；后续禁止再向 live DB 写测试文案。

### 修复

- `platform/backend/app/services/llm_client.py`：SDK 默认 `max_retries=0`，捕获 provider timeout 为 `LLMTimeoutError`，避免 SDK 隐式重复 LLM POST。
- `platform/backend/app/runtime/agent.py`：step LLM 使用 120 秒 provider timeout，并显式 `max_retries=0`；聊天/摘要调用保持原有 timeout 参数，不扩大本次范围。
- `platform/backend/app/routers/steps.py`：provider timeout 返回 HTTP 504；失败 run 保存本次最新 `user_answers`，并清空旧 `rendered_prompt`/输出，防止上一次输入或旧 Prompt 被误认为本次结果。
- `platform/backend/app/runtime/assembler.py`：新增 `[USER INPUT BOUNDARY]`。用户输入作为原始证据，不作为系统/开发者指令或已验证事实；忽略调试、测试、运行状态类元文本（如 timeout/recovery marker），不把孤立词语当作现实事件或章节事实。

### 验证

- LLM client、assembler、ch02 专项：`24 passed`。
- 全量后端：`140 passed, 2 failed`；2 个失败仍是既有未提交 ch03 配置与旧断言冲突，和本次变更无关。
- 本次新增测试覆盖：SDK 不隐式重试、Prompt 用户输入边界、provider timeout → 504、失败后保留最新输入并清除旧 Prompt。

### 操作要求

- 后端代码已修改，需通过 Service Dashboard 重启 `8011` 后再测试；不要手动 kill/启动端口。
- `3011` 不需要重启，刷新页面即可加载前端修复。
- 测试必须使用独立测试数据库或 Playwright route interception；不得把“超时恢复”等调试文本写入 live 数据。


## 3.50 ch02 ??????????????2026-08-08?

- ?????????? `step_runs.user_answers` ??LLM ?????? run ??? `failed`??? `loadCurrentRuns()` ??? failed run ?? `null`?????????????????????????????
- ???failed run ?????? run ????????? `user_answers`?ch02 ?? 1 ?????????????????????????????????????????
- ??????????? `call_llm` ?? 30 ? timeout????? chat router ???? `500` ????? chat ??????? 60 ??
- ????? `MENTOR_LLM_TIMEOUT_SECONDS = 120`?mentor ?????? `timeout=120`?`max_retries=0`?????? HTTP `504`??? chat POST timeout ??? `180000ms`??? `retry: 0`?
- ???ch02 ? chat ???? `11 passed`????????chat timeout?chat ????? `3 passed`??? pytest ?????? Windows ???????????? basetemp ???
- ???????? `failed` step run ???????????????LLM ???????? provider timeout?router status??? AbortController timeout ? POST retry ???


## 3.54 全局选区笔记锚点与高亮回溯修复（2026-08-08）

- 根因：选区保存使用 book.innerText + indexOf(source_text)，恢复/定位使用 DOM 文本节点累加；结构换行计数不一致，且重复原文总是命中第一次，导致高亮漂移或“定位原文”错误。
- 修复：前端改为基于 Selection Range 直接生成统一文本坐标，新增锚点版本 version: 2；保存、恢复高亮、定位原文共用同一套 DOM 文本坐标。
- 旧数据兼容：旧锚点优先按原文精确匹配；对 Markdown 列表/段落换行差异使用空白归一化并保留原文位置映射；重复文本按旧偏移选择最近匹配，不删除数据库笔记。
- 交互：点击正文高亮直接显示对应笔记浮层，可从浮层跳转右侧笔记；右侧“定位原文”使用同一解析逻辑。
- 验证：前端脚本语法检查通过；Playwright 真实页面回归 ch02/ch03/ch04/ch05 通过，旧笔记高亮与原文匹配、浮层显示、跨换行笔记定位均通过，无 console/page error。
- 影响范围：仅 platform/frontend/index.html；不改后端接口、不清理 live DB；刷新或 Reload 3011 后生效。
- 可复用教训：所有需要从正文回溯的用户标注必须保存可版本化、可解释的 DOM 坐标；禁止用渲染文本的 innerText 与简单 indexOf 作为唯一锚点。

## 3.55 ch03 四阶段实施与契约回归（2026-08-09）

### 本轮完成

- 后端 `steps.py` 已实现 ch03 专属 `ui_context` 返回：根据 `ui_context.references` 从 profile 过滤 `external_voices`，映射 ch01 静态误区标签，过滤空值并按误区编号升序返回；前端不读取完整 `learner_profile`。
- ch03 步骤分析与导师上下文已分层：`step_context.references=[]`，步骤分析不读取前章 profile；`mentor_hooks.references=["misconceptions_cleared", "external_voices"]`，仅供导师对话使用；`ui_context` 只用于右栏回响展示，不写入 `user_answers`、不进入分析 Prompt、不是 LLM 分析证据。
- `external_voices` 缺失数据硬规则已固定：完全为空/缺失时整块隐藏回响区，不显示任何占位文案；部分缺失时只渲染已存在的声音，不补占位、不造假。
- ch03 输出契约已在后端和前端同时收紧：`importance`、`talents`、`likes` 均要求 3–5 个非空字符串；`intersection` 和 `commentary` 必须存在；提交后整步锁定，重新运行创建新 run 并保留历史 submitted run。
- 前端 ch03 四阶段流程已接入：三组输入 → AI 分析 → 可编辑三组结果并确认提交 → 归档/对话入口；commentary 支持 Markdown 渲染，intersection 只读。
- 两个旧测试夹具已按新契约修正：全章节 E2E 增加 ch03 专属 contract mock，M4 ch03 mock 改为三组各 3 项。

### 验证证据

- `py_compile`：ch03 相关测试文件通过。
- 定向回归：`2 passed`。
- 后端全量回归：`149 passed, 8428 warnings`。
- 配置一致性：ch03 `[OK]`，ch01/ch02/ch05–ch08 均 `[OK]`；脚本另发现既有 ch04 DB/file drift（`exercises`、`mentor_hooks`），本轮未擅自修复。
- 当前探测：`3011/8011` 均未监听，因此真实浏览器 E2E 尚未执行；未手动停止、启动或重启服务。

### 下一步

- 用户通过 Service Dashboard 启动或 Reload `3011/8011` 后，执行 ch03 浏览器 E2E：页面加载、三组输入、引导问题、空/部分/完整 `ui_context`、保存草稿恢复、运行 LLM、分析结果编辑、提交锁定、对话入口和无 console/request error。
- 真实验收不得写入调试词或测试提示；如需清理 live ch03 数据，先单独确认备份与清理范围。
- ch04 的配置 drift 单独进入 backlog，不与 ch03 实施混修。
## 3.56 ch03 浏览器端 E2E 验收（2026-08-09）

- Service Dashboard 恢复 `3011/8011` 后，真实页面加载成功：前端返回 `200`，后端 OpenAPI 返回 `200`。
- 使用 Playwright 进行隔离式页面回归：读取真实章节配置和 `ui_context`；拦截 draft/run/output/submit 写请求，不向 live DB 写入测试输入或测试 LLM 输出。
- 验收覆盖：
  - `external_voices` 全空：回响区整块隐藏；
  - `external_voices` 部分存在：只显示已有声音；
  - 完整回响：误区编号、标签和原文正常显示；
  - 三组各 3 项输入、计数器、Venn 预览和引导问题；
  - 保存草稿；
  - 运行 LLM 后进入阶段 2，commentary、三组归纳和 intersection 正常渲染；
  - 阶段 3 修改三组结果并确认提交；
  - 阶段 4 显示归档提示、锁定结果和“对话”入口；
  - 点击“对话”切换导师面板并显示本章上下文提示。
- 结果：`E2E=PASS`，无 console error、page error、request failure；截图保存于 `D:\AI_Project\What_Want\_artifacts_ch03\`。
- 本轮没有向 live DB 写入测试数据，也没有清理现有数据。
- ch03 实施与页面验收完成；ch04 配置 drift 仍保持独立 backlog，不能混入本轮修复。
## 3.57 ch03 阶段1输入布局与 mockup 对齐修复（2026-08-09）

- 根因：ch03 阶段1此前错误复用了通用 `renderSchemaField/renderSchemaRow`，并用 `repeat(3, 1fr)` 将三组输入压缩为右栏内三列；在整页 viewport 大于 760px 时，媒体查询不会触发，导致每列约 100px、placeholder 截断、删除按钮脱离输入行。
- 修复：在 `platform/frontend/index.html` 增加 ch03 专属输入卡 renderer，改为纵向三张卡片；每张卡显示栏目说明、`n / 3+` 计数；每个输入行全宽并在行内提供删除按钮；“添加一项”固定在对应卡片底部。
- 栏目说明已接入：重要的事「你真正在乎的状态」、擅长的事「天生不痛苦就能做好的」、喜欢的事「你一做就忘记时间的领域」。
- 数据契约保持不变：仍为三组 `list_of_items`，每项只有 `text`；没有加入 mockup 中的逐项备注字段。
- 验证：前端内联脚本语法通过；Playwright E2E 通过（空/部分/完整 ui_context、9 个输入行、卡片宽度、添加/删除、保存、运行、阶段2/3/4、对话入口）；无 console/page/request error；修复后截图保存于 `D:\AI_Project\What_Want\_artifacts_ch03\stage1-layout-fixed.png`。
- Impeccable detector 仍报告 `index.html` 中既有的侧边强调线 warning；本次新增 ch03 输入卡未新增 detector warning。
- 用户动作：刷新 `3011` 页面即可看到前端修复；不需要重启 `8011`，不需要清理数据库。
## 3.58 ch03 三圆交集预览改为 mockup 三栏陈列（2026-08-09）

- 根因：旧版把三组清单文字直接放进三个重叠圆形，右侧窄栏中长文本会互相覆盖，无法完整阅读。
- 修复：`platform/frontend/index.html` 将预览改为三栏独立陈列，三组清单各自拥有可换行的滚动列表；交集结论移动到独立语义卡片，不再叠加在几何图形上。
- 保持契约：仍保留三组实时计数、输入变化实时刷新，以及阶段 2 的 AI `intersection` 回填；没有修改 API、数据库或 `user_answers` 格式。
- 验证：前端内联脚本语法通过；mock draft Playwright 回归覆盖三栏、长文本换行、实时刷新和阶段 2 renderer；`CH03_VENN_E2E=PASS`，无 page error、无 request failure。
- 截图：`D:\AI_Project\What_Want\_artifacts_ch03\venn-columns-preview.png`、`D:\AI_Project\What_Want\_artifacts_ch03\venn-columns-regression.png`。
- 用户动作：刷新 `3011` 即可查看；不需要重启 `8011`，不需要清理数据库。

## 3.59 ch03 导师对话超时与前端中止错误修复（2026-08-09）

### 根因

- 导师请求由前端 `fetchJson()` 使用 `AbortController` 控制，前端等待上限为 180 秒；超时后浏览器主动 abort，因此界面会显示 `signal is aborted without reason`。
- 后端导师调用原先先以角色配置的 `max_tokens=600` 请求；DeepSeek reasoning 消耗完 token、没有正文时会自动再发一次更大的请求。两次请求的总耗时可能超过前端窗口。
- 后端导师超时虽然配置为 120 秒，但未限制多次 provider 尝试共享同一总预算，且没有把超时明确映射为 504。

### 修复

- `platform/backend/app/services/llm_client.py`：增加一次调用的总 timeout budget；多次 reasoning 尝试共享同一个 deadline；新增 `LLMTimeoutError`；支持按调用关闭 reasoning retry，并默认关闭 SDK 自动 retry。
- `platform/backend/app/runtime/agent.py`：导师调用使用至少 4000 `max_tokens`，关闭 reasoning 二次 retry，显式使用 120 秒 timeout 和 `max_retries=0`；step LLM 也显式设置 timeout 与 `max_retries=0`。
- `platform/backend/app/routers/chat.py`：将导师超时转换为 HTTP 504，避免前端把后端超时误报成普通 500。
- `platform/frontend/index.html`：保留 HTTP status，504 显示“导师响应超时，请稍后再试”，并对错误文案进行 HTML 转义。

### 验证

- `python -m pytest -q -p no:cacheprovider --basetemp=<workspace-temp> tests/test_llm_client.py tests/test_chat_api.py`：`12 passed`。
- 前端内联脚本语法检查通过。
- 直接使用系统默认临时目录时，pytest 会被历史目录权限阻断；验证改用工作区隔离 `--basetemp`，不是业务代码失败。
- 需要通过 Service Dashboard Reload `8011` 后，再用 `3011` 刷新页面验证真实导师对话。

### 数据清理待确认

- 当前 `ch03` 聊天记录共 6 条：3 条 `user`、3 条 `mentor`。
- 删除操作尚未执行；需先明确删除全部 6 条，还是仅删除 3 条 `mentor` 记录。仅删导师记录会保留孤立的用户消息。
## 3.60 ch03 旧聊天记录按用户指定范围清理（2026-08-09）

- 用户确认删除 ch03 前 4 条记录：2026-08-06 的两轮重复问题及其两条导师回复。
- 通过 4 个明确消息 ID 执行删除，仅影响 `chapter_id='ch03'` 的这 4 行；没有使用整章清空接口，也没有影响第 5、6 条记录。
- 清理后通过 `GET /api/chapters/ch03/chat` 核对：当前剩余 2 条，分别为 2026-08-09 的 1 条 user 消息和 1 条 mentor 消息。

## 3.61 ch04 五步重构、上下文完整性与历史数据清理（2026-08-10）

### 本轮完成

- 后端真实 `agent.run_step` 路径透传 `preserve_output`；锁定的 `top_values` / `groups` / `ranked` 按原位置合并回 LLM 输出，锁定项只能先解锁再删除。
- `build_step_prompt` 注入锁定编辑并过滤 step-2 已删除的上游关键词；`mentor_hooks.references` 不作为普通 step 的 profile 输入。
- ch04 导师上下文改为仅读取已提交 step 的筛选摘要：step-1 五问与 `top_values`、step-2 `groups`、step-3 `conversions`、step-4 `ranked`、step-5 经历与工作目的/经验地图；未提交 step 排除。
- `compaction.MANDATORY_DOWNSTREAM_FIELDS` 补齐 `values` / `ranked`，避免 ch04 下游字段被预算裁剪。
- 前端新增 ch04 专用五步 renderer：五问输入、关键词池 N/15、100 例入口、可编辑分组/转化/金字塔/工作目的、锁定/删除/重生成，以及 step-5 多行经历按行转换为 `experiences`。
- 新增 `tests/test_ch04_dev_contract.py`，覆盖锁定位置、锁定删除保护、step-2 关键词过滤、profile 保留、导师已提交上下文和 100 例接口。

### 数据与配置

- ch04 active config 已从 DB v4 发布为 v5；`check_config_consistency.py --chapter ch04` 返回 `CLEAN`。
- 按用户确认清理 ch04 历史：`step_runs` 24→0、`chapter_summaries` 1→0、`chapter_chat` 0→0、`conversation_summaries` 0→0；未删除 `chapter_configs` 或其他章节数据。

### 验证

- ch04 新增契约测试：`6 passed`。
- `test_context_integrity.py`、`test_config_consistency.py`、`test_m4_ch04_cascade.py`、`test_m4_per_chapter.py`：`33 passed, 1 failed`；唯一失败是既有 ch05 角色期望与当前 ch05 配置不一致，与本轮 ch04 改动无关，未擅自修复。
- 前端内联脚本语法检查通过；Playwright 浏览器验收覆盖 ch04 5 个可见 step、五问采集、step-2 补充关键词、100 例入口（100 项）、preserve_output 构造、step-5 10 行经历采集，控制台错误为 0（100 例接口用新后端响应 mock 验证；live 8011 仍待 Reload）。
- 当前运行中的 `8011` 进程尚未加载本轮后端代码；需通过 Service Dashboard Reload `8011`，再刷新 `3011` 进行真实 LLM 流程验收。不要手动 kill/restart 服务。

## 3.62 ch04 step-2 推理 token 耗尽 502 修复（2026-08-11）

- 现象：用户在 ch04 step-2「关键词池」运行 LLM 时收到 `502 Bad Gateway: LLM returned an empty response (finish_reason=length)`。
- 根因已用同一份失败输入不落库复测确认：`deepseek-v4-flash` 在旧 `max_tokens=1500` 下将全部 completion token 消耗在 `reasoning_content`，未留下 JSON 正文；这不是关键词输入、前序 step、API key 或网络问题。
- 对照验证：同一 prompt 在 `max_tokens=4000` 下返回 `finish_reason=stop`、有效 `groups` JSON；实际使用约 3165 个推理 token 后再输出结果。
- 修复：`scripts/seed_roles.py` 将 `psychologist` 与 `career_counselor` 的预算提升为 `4000`，并修正 seed 对既有 `llm_roles` 行未同步 `description` / `temperature` / `max_tokens` 的缺陷。
- 运行时生效：已定向更新活动 DB 中上述两条 deepseek 角色记录为 `4000`；`load_role()` 每次请求读取 DB，故无需重启或停止 `8011`。
- 回归：`python -m pytest tests/test_seed_roles.py tests/test_llm_client.py -q -p no:cacheprovider --basetemp D:\AI_Project\What_Want\.pytest-token-budget-ch04-20260811` → `8 passed`。
- 真实验证：通过 `POST /api/chapters/ch04/steps/step-2/run` 重放刚才失败输入，返回 `status=saved`、`role_id=psychologist`、`groups=4`；未提交 step、未写 profile。
- 用户动作：刷新 ch04 页面即可看到最新 saved 输出；可继续审阅、编辑、锁定并自行点击「提交」。

## 3.63 ch06 设计复核与 ch05/ch06 范围隔离（2026-08-12）

### 本轮完成

- 读取并对照 `llm_prompt_design/docs/ch06_落地级步骤设计.md`、`docs/PRD/PRD-ch6.md`、`config/chapters/chapter_config_ch06.json`、后端 steps/assembler/chat、前端 renderer、题库 API 与全书测试夹具。
- 确认当前 ch06 配置已进入最终设计的两步方向：step-1 `psychologist` 输出领域级 `likes`，step-2 `career_counselor` 通过同章 submitted 级联并可选引用 ch05 `reference_talents`，输出结构化 `likes`。
- 明确 ch06 不是 ch05 的附带实施；当前 ch05 是实施目标，ch06 配置/测试迁移属于独立 pending 范围，后续应单独实施和单独保存 Git 版本。
- 新增开发侧 review 文档：`llm_prompt_design/docs/ch06_落地级步骤设计_待设计确认.md`。

### 当前发现

- ch06 后端尚无专属 normalize/validate、step-2 `reference_talents` 合并块和锁定项契约；通用 warning 校验不足以保证 canonical 输出。
- ch06 前端尚无 `renderCh06StepBody`；当前通用 renderer 无法正确编辑嵌套 `likes` 卡片。
- `/step` 的 `ui_context` 尚未把 config 中的 `passion_examples` 传给前端。
- ch06 导师路由尚未切换到本章多 step submitted-only 上下文；草稿时间戳、失败恢复和 ch06 专项契约测试仍待补齐。
- 设计侧需要确认 5 项：嵌套字段 canonical JSON、100 例引用 seed 载体、30 问写入/调用规则、ch04 `work_purpose` 可选依赖的 executable contract、step-2 few-shot 是否删除「书里说」表达。

### 验证边界

- 本轮未修改 ch06 生产代码、配置、数据库或 ch07 代码；未执行 reseed、用户数据清理或服务重启。
- ch06 DB active config 一致性和真实页面/LLM E2E 尚未验证；曾尝试调用项目 Python 解释器时遇到 `Access is denied`，因此不声称 DB 已发布或 ch06 已完成。

### 下一步

- 等设计侧回复并同步 ch06 权威设计文件后，再单独实施 ch06；在此之前继续保持 ch05 与 ch06 的 Git/交付边界分离。

## 3.64 ch06 两步级联实施完成，回归全绿，待 live 浏览器验收（2026-08-14）

### 设计闭环

- 第六轮设计侧回复已固化两条最终口径：summary 保留 `values`/`work_purpose` 角度但不消费 `likes`；ch06 `likes` 采方案 A（step-1 永不入 profile，step-2 提交时显式覆盖 `profile.likes`）。
- 开发侧复核补充的 12 项 stale 覆盖清单（§4 #1–#12）已全部纳入实施。

### 本轮实现

- 后端：`step_runs.stale` 幂等补列；ch06 step-1/step-2 级联门禁、输出 normalize/validate、step-2 专属 `profile.likes` 写入；step-1 重提交后旧 step-2 置 stale 且清空 profile；ch07 上游改为 `ch04(work_purpose,values) + ch05(talents) + ch06(likes)` 并移除 ch03。
- 所有 step-run 读取路径统一 `status='submitted' AND stale=0`，包括导师上下文、compaction、章节进度/状态、当前 run 选取与提交。
- 前端：新增 ch06 专属 renderer（5 问、热情 30 问抽屉、喜欢的事 100 例抽屉、ch05 擅长引用、嵌套 likes 卡片编辑/锁定/删除/添加、stale 历史提示、Markdown commentary）。
- 新增契约测试 `tests/test_m6_ch06_cascade.py`，覆盖两阶段契约、候选合并、normalize/validate、profile 只接受 step-2 与 stale 失效。

### 验证

- ch06 契约测试：`4 passed`。
- ch07 门禁与全章链路定向回归：`54 passed`。
- 后端全量回归：`166 passed`。

### live 浏览器验收中发现并修复的两个问题（2026-08-14）

- 「查看已填 30 问」按钮只展开抽屉不加载已保存答案（抽屉为空）；改为复用 `ch06OpenThirty`，展开时加载并合并已保存答案。
- 真实 DeepSeek 返回的 `source` 常为自由格式（如 `Q1/Q3`、`q2 和 q61`），严格校验导致 step-1 运行整体失败；新增 `_ch06_source_tokens` 规范化提取 q1-q5 / q61-q90 令牌，step-1 合并为 `q1,q3` 形式、step-2 拍平去重，无有效令牌时置空不阻断。
- 修复后：ch06 契约测试 `5 passed`，后端全量回归 `167 passed`；前端脚本语法通过。
- 修复后 live 全部通过：页面加载、旧 failed 徽标与重试提示、草稿保存/刷新恢复、30 问抽屉保存/恢复、100 例抽屉默认隐藏且 100 条、step-1 真实 LLM 运行（11 个领域 + commentary）与提交、step-2 100 例引用/运行（11 张结构化卡片）/编辑方面/锁定/提交、profile.likes 结构化写入且首项 locked=true。
- stale 机制 live 通过：重新填写并提交 step-1 后，旧 step-2 置 `stale=1`、`profile.likes=[]`、页面显示「已过期，请重新运行第二步」；重跑 step-2 提交后恢复结构化 likes 且 `stale=0`。控制台错误 0、dialog 0。
- 章节状态接口对重复提交的 step_id 去重（此前 step-1 重提交会显示 3/2）；ch06 状态现为 `submitted 2/2`、进度 100%。
- DB 状态：`stale` 列存在；ch06 config version 2 active；live 验收数据已按用户确认清理（2026-08-14）。

### 待办

- 用户已确认清理：ch06 `step_runs` 5→0、30 问答案 note 已删、`profile.likes=[]`、`current_chapter=ch03`；live API 复核 ch06 0/2、进度 0%。清理前备份：`C:\Users\deng_\AppData\Local\Temp\ww.db.pre-ch06-clean-20260814-135151.bak`。
- 发布前备份：`C:\Users\deng_\AppData\Local\Temp\ww.db.pre-ch06-20260813-231006.bak`。


## 3.65 ch04/ch05 ?? ch06 ?????????A?2026-08-14?

### ??
- ??????`llm_prompt_design/docs/问题清单跨章统一_方案A_变更清单与开发侧待办.md`（设计侧已完成 config/doc 同步，开发侧落地运行侧）。

### 实施
- 前端新增通用 30 问抽屉助手（`bankLoadQuestions` / `bankOpenThirty` / `bankSaveThirty`）：按 q_order 区间与分类加载（价值观 1–30、才能 31–60、热情 61–90），答案经 questions 服务写入 `book_notes`，不进产出、不流下游。
- ch04 step-1：`value_questions` 不再误渲染为单行 textarea，改为「回答/查看 价值观 30 问」抽屉；`collectCh04Answers` 收集 `value_questions` 列表。
- ch05 step-1：`talent_questions` 同样改为「擅长的事 30 问」抽屉；`collectCh05Answers` 收集 `talent_questions` 列表。
- ch04 step-2 100 例抽屉改读 `ui_context.values_examples`（config 内 100 项），移除旧 `/value-examples` 接口与 20 项硬编码回退；引用落点仍为 step-2 `supplemental_keywords`（既有设计未变）。
- 后端 `_build_ui_context` 补白名单：新增 `values_examples`，与 `strength_examples`/`passion_examples` 一致。
- reseed：通过 `POST /api/chapters/{id}/steps/step-1/config` 发布 ch04 v6、ch05 v3；`check_config_consistency --chapter ch04/ch05` 均 CLEAN。

### 验证
- 新增 `tests/test_question_bank_uniformity.py`（ch04/ch05/ch06 字段与 100 例契约）。
- 后端全量回归：`170 passed`；前端 `node --check` 通过。
- 浏览器只读验收（不写用户数据）：ch04 30 问加载 30 条 q1–q30、100 例抽屉读 config 共 100 项（首项「发现／找出新的东西」）；ch05 30 问 q31–q60、`collectCh05Answers` 正确收集 `talent_questions`；assembler 将两章 30 问答案注入 step-1 prompt。控制台错误 0。
- ch04/ch05 用户数据未触动（只读、未写草稿）。

### 待认
- ch07 仍存在 config DRIFT（文件 2 个 exercises vs DB active 1 个），属设计侧已更新的 ch07 落地文档，本轮未擅动；是否 reseed ch07 待用户/设计侧确认。
- 备份：`platform/backups/index.html.pre-ch04ch05-questionbank-20260814-154428.html`；DB `C:\Users\deng_\AppData\Local\Temp\ww.db.pre-ch04ch05-reseed-20260814-154428.bak`。


### 数据清理（2026-08-14，用户确认）
- ch04/ch05 全部录入数据已清除：`step_runs` 5→0（ch04 提交/草稿/失败各数据与 ch05 旧 failed）、`chapter_chat` 8→0；`chapter_summaries`/`conversation_summaries` 本就为 0。
- profile 无 ch04/ch05 产出需回滚（work_purpose/values/ranked 缺失，`talents` 仍为 ch03 种子未动）。
- 保留：阅读高亮笔记 8 条（book_notes，非 step 录入数据）未动。
- 验证：live API ch04 `0/5`、ch05 `0/2`，进度 0%；浏览器复核两章全部步骤均显示「待开始」。
- 备份：`C:\Users\deng_\AppData\Local\Temp\ww.db.pre-ch04ch05-clean-20260814-155823.bak`。


## 3.66 ch07 正式实施：想做的事两步级联（2026-08-14）

### Review 结论
- 基于 `ch07_落地级步骤设计_review.md`、落地设计、PRD-ch7 与 config 做了实施前一致性确认：设计文档与 config 一致，ch06 第六轮的 stale 迁移、ch07 上游门禁（ch04/ch05/ch06 + stale=0）已在前轮预先落地，无阻塞问题；剩余均为开发侧待办。

### 实施
- 后端：`ideal_works` 加入 compaction 白名单（PROFILE/STRUCTURED/MANDATORY 三处）；新增 ch07 专属 normalize/validate（title 非空、bucket 三枚举、locked 布尔、step-2 next_action）与提交钩子：step-1 提交置旧 step-2 stale 且 `profile.ideal_works=[]`；step-2 提交显式覆盖写入 profile；assembler 新增 CH07 STEP-1/2 CONTRACT（组合证据、分桶建议、保留 locked、不照本宣科）；chat 上下文接入 ch07 submitted ideal_works。
- 前端：新增 ch07 专属渲染器（title 编辑、bucket 三选一、锁定/删除/新增、like/strength 溯源、commentary 与 next_action、导出清单）；step-2 重跑保留 locked；铁门障印口径更新为 ch04/ch05/ch06 三按钮 + 缺失字段按章展示。
- reseed：ch07 config 发布 v2（2 个 exercises）；`check_config_consistency` 全部 8 章 CLEAN（ch07 DRIFT 已消除）。

### 验证
- 新增 `tests/test_m7_ch07_cascade.py`：配置契约、normalize/validate、step-2 prompt 含 step-1 与 profile、完整级联 + 门禁 + 内部 stale 传播 + canonical 写入，`5 passed`。
- `test_m4_per_chapter` 白名单同步 `ideal_works`；后端全量回归 `175 passed`；前端 `node --check` 通过。
- 浏览器只读验收：锁屏遮罩 + 三章直达按钮（ch04 0/5、ch05 0/2、ch06 0/2）；渲染器 fake run 验证两步按钮、bucket 选择、next_action、locked 卡片、step-2 门禁；控制台错误 0。
- live 真实 LLM 流程需等用户完成 ch04/ch05/ch06 后再走；现有契约测试已用 mock 覆盖全链路。

### 待认
- 待用户完成上游三章后做 ch07 live 端到端验收；目前 ch07 无任何 step 数据，不需清理。


## 3.67 ch04 级联 stale 隔离实施（2026-08-14，回滚标签 pre-ch04-stale-cascade-20260814）

- 后端：新增通用 `_downstream_step_ids`（传递闭包）、`_mark_downstream_stale`（saved+submitted）、`_clear_chapter_profile_keys`；ch04 提交时对非末步同事务内置下游 stale 并清空 `values/ranked/work_purpose`；末步仍走 `_maybe_compact` 重写三键。
- 主线 `get_chapter_full_config` 补传 `references` 到前端步骤配置（此前转换时丢失，前端无法计算下游）。
- 前端 ch04：新增「修改本步」入口（仅 step-1~4）+ 确认提醒（下游失效 + 档案三键清空）；下游步骤显示「这一步的结果已过期，请重新运行并提交」。
- 契约测试 `tests/test_m4_ch04_stale.py`（传递闭包/各步重提交级联/末步安全路径/重走全链恢复，5 passed）；后端全量 `180 passed`；前端 `node --check` 通过。
- 浏览器只读验收：闭包 step-1→{2,3,4,5}、step-4→{5}、step-5→{}；step-1 已提交视图含「修改本步」而 step-5 不含；step-2 过期提示渲染；控制台错误 0。


## 3.68 ch05 选项 A 与 ch06/ch07 前端提醒对齐（2026-08-14）

- 后端：ch05 step-1 提交复用通用 helper：置 step-2 stale（saved+submitted） + 清空 `profile.talents`；重走全 2 步后 `_maybe_compact` 重写 talents，ch7 门禁因缺失回退/解锁。
- 前端 J 全量对齐：ch05 step-1 已提交视图新增「修改本步」+ 确认（step-2 失效 + talents 清空 + ch7 门禁回退）；ch05 step-2 过期提示。
- ch06/ch07 step-1 的「重新填写第一步」改为先确认再建草稿（分别提示喜欢清单 / 想做的事清单清空风险）。
- 契约测试 `tests/test_m5_ch05_stale.py`（2 passed）；后端全量 `182 passed`；前端 `node --check` 通过。
- 浏览器只读验收：ch05 step-1 含「修改本步」/步-2 不含；step-2 过期提示渲染；ch06/ch07 重填按钮均走确认包装；控制台错误 0。


## 3.69 ch08 全书可视化流程图页实施（2026-08-16）

### 实施
- 后端：新增 `flowchart_state` 表（元组为 user_id+chapter_id+decision_point_id，与 profile 完全解耦）；新增 GET/PUT `/api/book/chapters/{id}/flowchart-state`（状态读取 + 当前节点推导 + 上游 ch04–ch07 完成态软提示，含 stale_dirty 标记）；`has_steps` 判定改为排除 page_type=flowchart，ch08 不再显示步骤页签。
- 前端：新增 ch08 流程图渲染器（四阶段、6 个决策点 + 终点，分支按钮、备注保存、当前节点高亮、hint_only 提示）；「否/找不到」真实跳转到对应章，并通过 `focus` 参数自动打开目标章的 30 问抽屉（value/talent/passion_questions）；顶部软提示展示未完成上游章与「前往」按钮。
- 无 LLM 步骤、不写 `learner_profile` 任何键、不触发 compaction；mentor_hooks.references 保留全书上下文（含 ideal_works，设计默认，可调）。
- reseed：ch08 v2 已发布；全部章节配置一致性 CLEAN。

### 验证
- 新增 `tests/test_m8_ch08_flowchart.py`（4 passed：建表、状态往返、当前节点推导（含 jump 停留）、分支/节点校验、不写 profile）。
- 同步既有测试：`test_all_chapters_e2e` 移除 ch08 step 链（14 runs，current_chapter=ch07）；`test_m4_per_chapter` ch08 改为 flowchart 契约检查；`test_context_integrity` ch08 引用补 ideal_works。
- 后端全量 `186 passed`；前端 `node --check` 通过。
- 浏览器只读验收：流程图渲染、6 决策点 + 终点、当前节点 dp-1 高亮、软提示展示 ch04/05/06/07、20 个分支按钮、侧栏无步骤页签（摘要/对话/笔记），控制台错误 0。

### 待认
- 设计 §7.4 mentor_hooks.references 保留为全书上下文（含 ideal_works）需产品侧最终确认；如不需可清空。
- 「带★的问题」子集为平台级后续特性（当前按设计全部30问即★）。
