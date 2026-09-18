# What Want 重构 - Session Checkpoint (2026-08-04)

> 此文件由 Codex 在上下文压缩前生成，供下个 session 接管。
> 唯一权威实施依据：`llm_prompt_design/docs/工程实施交接文档.md` v2.0
> 设计侧 Q&A：`llm_prompt_design/docs/重构开放问题_设计侧确认.md`
> 进度文件：`platform/PROGRESS.md`

---

## 0. 当前状态

**附2-1 + 附2-2 完成**（agent_configs seed + DB vs JSON 一致性脚本）：

- ✅ `compaction.py` 新增 `extract_open_questions` + `extract_and_persist_open_questions`
- ✅ `steps.py submit_step` 通过 BackgroundTasks fire-and-forget
- ✅ `agent._force_mentor_compaction` 通过 `asyncio.create_task` 触发
- ✅ 测试 `DISABLE_OPEN_QUESTIONS_EXTRACT=1` 跳过 LLM 调用

**测试**：104 passed（最新全量回归，排除仓库内无权限的 `tests/_tmp`）

## 1. 已完成里程碑

| 阶段 | 状态 |
|---|---|
| M0 数据迁移 | ✅ |
| M1 数据层 + compaction | ✅ |
| M2 schema + exercise | ✅ |
| M3 运行时接入 | ✅ |
| M3.1 / M3.2 灰度 + 推广 | ✅ |
| M3.3 设计侧修改 Verify + 9 步改造 | ✅ |
| Q10 chat/summary 切到 agent | ✅ |
| Q7 mentor 20 轮 compaction | ✅ |
| Q8 open_questions LLM 提取 | ✅ |

handoff 全部 12 项设计侧 Q 已闭环。

**M4.1/M4.2/M4.3 + M5.1 chapter_status 已闭环**（详见 PROGRESS.md §4）：
- M4.1 每章 schema-aligned mock LLM 验证（ch01/02/03/05/06/07/08，test_m4_per_chapter.py 7 测）
- M4.2 ch04 章节内 references 级联（5 步 + step-2→step-1 prompt 验证，test_m4_ch04_cascade.py 2 测）
- M4.3 ch07/ch02 跨章 profile 读（mentor_hooks.references 生效，test_m4_ch07_cross_chapter.py 2 测）

## 2. Q8 实现细节

### `app/services/compaction.py` 新增

```python
OPEN_QUESTIONS_MAX = 3
OPEN_QUESTIONS_LLM_TIMEOUT_S = 8.0

async def extract_open_questions(outputs, profile, *, user_id, chapter_id,
                                 llm_callable=None, max_questions=3) -> list[str]:
    """Cheap LLM extraction of unresolved questions (handoff Q8).
    
    Uses career_counselor role by default (fallback summary). Failure modes:
      - LLM call fails -> warn log, return []
      - LLM returns non-JSON -> warn log, return []
      - Empty inputs -> skip LLM call, return []
    Output: list[str] capped at max_questions.
    """

async def extract_and_persist_open_questions(user_id, chapter_id, outputs=None) -> list[str]:
    """Extract + persist into learner_profiles.open_questions (merge + dedupe)."""
```

### `app/routers/steps.py submit_step`
```python
def submit_step(chapter_id, step_id, background_tasks: BackgroundTasks):
    ...
    profile = _maybe_compact(chapter_id)
    if profile is not None and os.getenv("DISABLE_OPEN_QUESTIONS_EXTRACT") != "1":
        from app.services.compaction import extract_and_persist_open_questions
        background_tasks.add_task(
            extract_and_persist_open_questions,
            os.getenv("DEFAULT_USER_ID", "local"),
            chapter_id,
        )
    return {"ok": True, "status": "submitted", "compacted": profile is not None}
```

### `app/runtime/agent.py _force_mentor_compaction`
```python
def _force_mentor_compaction(user_id, chapter_id):
    # ... existing sync compaction
    try:
        from app.services.compaction import extract_and_persist_open_questions
        asyncio.create_task(extract_and_persist_open_questions(user_id, chapter_id))
    except RuntimeError:
        pass  # no event loop (sync test context)
```

## 3. 待办

handoff 全部 12 项 + 设计侧附2-1/2/3/4 已闭环。

- Q11：learner_profile user_id 跨会话隔离（多用户需求出现再做）
- M4.4 ch07 上游依赖锁定 + 前端 ch04 groups/conversions 渲染分支（推荐并入 M5）
- M5 前端桥接（career-planning mentor 入口）
- M6 验收


## 3.5 M5.6 + M5.7 收尾（2026-08-04 本 session）

**根因**：
- `chapter_configs` 表只有 ch04（其他 7 章没 seed）→ `get_chapter_full_config` 返回空 steps → 前端 loadSteps 拿到 0 → 三章练习不可见
- `llm_roles` 14 行脏数据：9 条 career_counselor UUID 行 `system_prompt='role'`，load_role 实际返回脏串 → career_counselor 真实 LLM 必输出垃圾
- 之前 93 passed 全部 mock 跑，未暴露此 bug

**修复**：
- `python seed_all_chapters.py` -> 7 章补齐
- `DELETE FROM llm_roles` + `python -m scripts.seed_roles` -> 4 条干净 role（career_counselor 拿回设计侧 long-form 1460 字符）
- `scripts/seed_roles.py` 改 UPSERT (by name+provider+enabled=1) + model=`DeepSeek-V4-Flash`

**验证**（已做）：
- `GET /api/book/chapters/ch01` -> `{has_steps: true}`
- `GET /api/book/chapters/ch01/config` -> `steps: [{step_id: step-1, title: "误区自检清单", output_fields: [misconceptions_cleared, external_voices], llm_op.role_id: career_counselor}]`
- `python scripts/smoke_ch01_mock.py` -> `smoke OK: step_runs + learner_profiles populated for ch01`
- 真实 LLM（DeepSeek-V4-Flash 端到端）：沙箱拒网未验，需用户本机浏览器实测

**备份**：
- `backend/data/backups/ww-20260804-115054.db`
- `backend/scripts/seed_roles.py.bak-20260804-115128`
## 3.6 M5.8 第3步（2026-08-04）

**完成**：后端支持结构化 `user_answers`。`render_user_answers` 按 `input_schema` 输出标签化文本；旧 list/string 格式保持兼容；`DraftIn` / `RunIn` 接收 `Any`。

**验证**：`py_compile`、helper 定向断言、后端全量 `93 passed`。

**当前阻塞/注意**：正在运行的旧 uvicorn 进程不会自动加载新代码；前端联调前需由用户重启 backend 8011。

**下一步**：M5.8 第4步先改 `frontend/index.html` 的 `renderStepBody`，随后第5步实现 `?page=roles` 管理界面。

## 3.7 M5.8 第4步（2026-08-04）

**完成**：前端 `renderStepBody` 已改为 `input_schema` 优先；支持 checklist、list_of_items、select/radio、text；ch01/ch02 的结构化答案分别提交为字典/事项数组；步骤角色显示为题目指定的锁定标签；explain 配置显示为说明区。旧 `user_input.questions` 保留 fallback。

**验证**：关键函数和调用点已检查；全文件 Node 语法检查被原文件已有乱码字符串阻断，未声称浏览器验证通过。

**下一步**：实现 M5.8 第5步角色管理界面，然后启动前后端进行浏览器联调。

## 3.8 M5.8 第5步（2026-08-04）

**完成**：前端新增 `?page=roles` 角色管理页，支持去重列表、引用统计、右侧配置抽屉，以及空 prompt dry-run 预览后确认软禁用。角色 API 契约已用 TestClient 验证。

**验证边界**：前后端接口级验证通过；尚未用真实浏览器启动 3011/重启 8011 做视觉与点击验收。原 `index.html` 历史乱码字符串仍会阻断整页 Node 静态语法检查。

**下一步**：用户无需先操作；开发侧应启动/重启服务后完成浏览器验收，并根据实际点击结果修复问题。

## 3.9 M5.8 运行时 seed 闭环修复（2026-08-04）

8011 实测曾返回 ch01/ch02 `input_schema: null`。根因是 seed 脚本跳过已有 active 配置。已把当前 JSON 精确同步到 ch01/ch02 active 记录（version 3），API 现均返回 schema_count=1；回归 `93 passed`。服务 3011/8011 当前运行。

浏览器自动化工具因 `failed to write kernel assets` 无法使用，下一步需人工打开页面做视觉/点击验收，或修复浏览器插件运行环境后继续自动验收。

## 3.10 config 路由修复验证（2026-08-04）

Service Dashboard 重启 8011 后，`/api/book/chapters/ch01/config` 与 ch02 config 已恢复：ch01 1 step/1 schema，ch02 1 step/2 schema。根因是 FastAPI router 注册顺序，已在 `app/main.py` 修复。

下一步：用户刷新 3011 页面做视觉验收；若页面仍显示旧内容，使用强制刷新（Ctrl+F5）。

## 3.11 M5.8 收尾与后续主线（2026-08-04）

用户确认当前结构化 UI 虽然较丑但可见，暂不美化，直接推进后续。M5.8 视为功能完成；服务由 Service Dashboard 管理。

后续严格按顺序：
1. M5.3 章末回顾卡（默认可见、CTA 不自动发消息）。
2. M5.4 三入口（顶部常驻、步骤浮层、章末卡）。
3. M5.5 ch07 缺少 ch03/ch04 profile 时整章锁定。
4. M6 验收。

## 3.12 M5.3 章末回顾卡（2026-08-04）

前端已嵌入桥接卡容器与渲染逻辑，CTA 仅切换 tab 并预填 mentor 上下文，不自动发消息。下一步 M5.4 三入口：顶部常驻、步骤浮层、章末卡。

## 3.13 M5.4 三入口（2026-08-04）

三入口全部接入前端：顶部常驻、步骤面板、全页浮层、章末回顾卡。统一调用 `openBridgeChat({step})`，仅切 tab 并预填上下文，不自动发消息。下一步进入 M5.5 ch07 上游依赖锁 UI。

## 3.14 M5.5 ch07 上游依赖锁 UI（2026-08-04）

ch07 页面会在进入时读取 status，未就绪时显示半透明遮罩并提供「前往 ch03 / 前往 ch04」直达按钮。下一步进入 M6 验收。

## 3.15 M6 验收状态（2026-08-04）

机器可验项全部通过；浏览器视觉项（ch04 groups/conversions、桥接卡 B 三入口）已就绪，需要用户在 3011/8011 服务中点击确认。

## 3.16 Review 修复（2026-08-04）

review.md 7 项修复完成；后端全量测试 93 通过；8011 进程仍为旧代码，需用户重启后才会加载。

## 3.17 前端 fetchJson 接入（2026-08-04）

review.md P1-6 闭环：17 处前端 fetch 调用已改为 fetchJson，统一支持 30s 超时和一次重试。

## 3.18 设计侧答复落地（2026-08-04）

`重构开放问题_设计侧确认.md` 5 题 + 附2 跨文档变更已处理：ch03 intersection readonly、ch04 exercises seed 修复、ch07 markdown size guard 回退、agent.run_step 自动 json_mode、ch03/ch07 intersection 差异化渲染。后续待办：agent_configs 表 seed 与迁移。



## 3.19 设计侧 附2 落地（2026-08-04）

### 附2-1：agent_configs 表 seed + 迁移
- scripts/seed_agent_configs.py 从 llm_prompt_design/config/{mentor,agents}/*.json 读 scaffold，UPSERT 到 agent_configs。
- 实测：mentor=2576 bytes, summary=444 bytes。幂等（重复运行不复制行）。
- 接入点（不阻塞）：后续可让 agent.run_mentor / agent.run_summary 从 agent_configs 拉 scaffold 与 llm_roles core prompt 拼接。
- 待设计侧：psychologist / career_counselor 对应 scaffold JSON 尚未提供。

### 附2-2：DB vs JSON 一致性脚本
- scripts/check_config_consistency.py 对比 8 章 active DB row vs canonical JSON。
- 三态：[OK] / [DRIFT] / [DB-MISS] / [FILE-MISS] / [ERR]。退出码：0=CLEAN, 1=DRIFT/MISS, 2=ERROR。
- 实测当前 8 章 CLEAN。可挂入 CI 防止 ch04 类问题复发。

### 附2-3：POST /config 端点（2026-08-05）
- 已新增 `POST /api/book/chapters/{chapter_id}/config`：读取当前最大 version，写入 version+1，旧版本 active=0，新版本 active=1。
- 已补 `tests/test_book_api.py` 回归：验证 version+1、active 切换与配置内容持久化。

## 3.20 ch01 误区卡独立外部声音（2026-08-05）

- 前端 `renderSchemaField` 将 checklist 渲染为 5 张独立误区卡；每张卡独立勾选、展示 wrong/right，并独立填写外部声音。
- 提交结构保持设计侧约定：`user_answers.misconceptions.external_voices = {"1": "...", "3": "..."}`。
- 兼容旧数据：旧的 `external_voices.general` 会回填到第一个已勾选卡片；未勾选卡片输入不禁用，可继续填写。
- 新增 `tests/test_assembler.py` 回归，确认按误区编号保留外部声音映射。
- 验证：定向 27 passed；全量（排除仓库内无权限的 `tests/_tmp`）104 passed；本次改动 Python 文件定向 `py_compile` 通过；前端内嵌脚本抽取后 `node --check` 通过。
- 备注：全目录 `compileall` 仍被既有 `app/runtime/assembler_clean.py` 语法错误阻断，未修改该无关文件。

## 3.21 ch01 操作提示与导师入口修复（2026-08-05）

- 前端新增 ch01 step-1 右上角 `?` 操作提示弹层，文案按 A 流程对齐：保存草稿 → 运行 LLM → 运行成功后提交；导师入口为可选对话。
- 保留按钮状态机：运行前显示「保存草稿 / 运行 LLM」，LLM 成功后显示「提交」。
- 修复 `openBridgeChatForStep` 的错误 inline onclick 引号；点击后切换右侧对话并预填当前步骤上下文，不自动发送。
- 修复 `sendChat` 使用未定义 `r` 导致发送失败的问题；`fetchJson` 成功返回后直接渲染导师回复。
- 浏览器验收：3011 + 8011 实测通过，问号弹层可见；运行前按钮为「保存草稿 / 运行 LLM」；点击「聊聊这一步」切换到对话面板；无控制台错误。



## 3.22 运行库 chat 清理与 M6 当前边界（2026-08-05）

- 清理运行库中 20 条测试残留的 `mentor: "hi"` 记录；清理前备份：`platform/backend/data/backups/ww-20260805-before-chat-cleanup.db`。
- `tests/test_all_chapters_e2e.py` 的两项 mentor compaction 测试已补 `all_app` 临时数据库 fixture，避免写入真实运行库。
- 验证：`GET /api/chapters/ch01/chat` 返回 `[]`；全量后端测试 `104 passed`（排除 `tests/_tmp`）；3011/8011 浏览器验收无控制台错误。
- M6 mock/机器验收及浏览器交互验收已完成；真实 LLM 端到端仍待用户在本地有效 API Key 下执行，确认 `step_runs` 和 `learner_profiles`。

## 3.23 ch01 保存/运行/摘要错误修复（2026-08-05）

- 根因 1：`saveDraft` 重绘 `stepList` 后没有恢复 `stepBody` 展开状态；已修复为保存/提交后重新展开当前步骤。
- 根因 2：运行库 4 个启用角色使用 `DeepSeek-V4-Flash`，DeepSeek API 实际要求 `deepseek-v4-flash`；已备份并更新 `platform/backend/data/ww.db`，备份为 `platform/backend/data/backups/ww-20260805-before-model-case-fix.db`。
- 根因 3：摘要生成把 `fetchJson` 返回对象再次调用 `.json()`；已改为直接消费解析后的对象，并增强后端错误 detail 展示。
- 相关修复：保存草稿清空旧 `step_runs.error`；当前过期错误已清理，备份为 `platform/backend/data/backups/ww-20260805-before-step-error-clear.db`。
- 验证：浏览器保存后步骤保持展开；摘要真实生成成功；`/api/health` 200；4 个角色模型均为 `deepseek-v4-flash`；前端 `node --check`、后端 `py_compile` 通过。
- 注意：本轮没有再次执行真实运行 LLM；8011 未重启，`steps.py` 的代码热加载待 Service Dashboard 后续托管重载。

## 3.24 ch01 输出与提交后对话入口调整（2026-08-05）

- LLM 输出新增 ch01 结构化渲染：`misconceptions_cleared` 显示为「已识破的误区」列表，`external_voices` 显示为「外部声音」，不再裸展示 JSON。
- 提交后的完成卡改为「我们已经了解了你的信息。如果需要，你可以和导师聊聊你的想法。」+「对话」按钮；按钮只切换右侧 Chat Tab。
- `bridgeCardSlot` 已移入步骤侧栏，修复原 DOM 顺序导致 Chat Pane 被 CSS Grid 自动放到左侧的问题。
- 验证：模拟 submitted + JSON 浏览器回归通过；Chat Pane left=917、Side Panel left=916；前端 `node --check`、后端 `py_compile`、`git diff --check` 通过。
- 本轮没有再次执行真实 LLM，也没有修改运行库提交状态。

## 3.25 全章 Mock / 浏览器 E2E 回归与共享组件修复（2026-08-05）

- 按真实 `chapter_config_ch01..ch08.json` 执行后端临时数据库 Mock E2E：8 章 12 步全部通过，角色路由、draft → run(mock) → submit、ch04 五步和 profile 落库通过。
- 按 webapp-testing / Playwright 执行浏览器全章回归：所有 Tab、步骤展开、schema 输入、保存草稿保持展开、Mock LLM 输出、提交完成卡、对话 Tab、刷新恢复均通过；无应用 console 错误、500 或失败请求。
- 修复 `platform/frontend/index.html` 的共享输入收集 bug：`list_of_items` 行字段收集改为 `Array.from(querySelectorAll(...)).map(...)`，ch02 不再因 `querySelectorAll(...).map is not a function` 阻断。
- 修复共享 `renderStepOutput`：按 `output_fields.type` 渲染 `editable_list` / `list` / `text` / `markdown` / `table`；ch02、ch05、ch06、ch08 不再显示裸 JSON，新增表格样式并对输出文本做 HTML 转义。
- 验证：前端脚本抽取后 `node --check` 通过，`git diff --check` 通过；3011/8011 HTTP 正常，未停止或手动重启服务。
- 当前边界：浏览器 run/submit 使用网络 mock，后端 Mock 使用临时数据库；真实 LLM 受控 smoke test 仍待用户在有效 API Key 环境执行。

## 4. 下个 Session 开局建议

1. 读 `CONTEXT_CHECKPOINT.md`（本文件）
2. 读 `PROGRESS.md` §0 / §1
3. 跑后端全量测试：`python -m pytest tests --ignore=tests/_tmp -q`（当前 Hermes Python 环境未预装 pytest；需使用项目测试环境）
4. 进入 M6 受控真实验收：先确认有效 API Key，再在 3011 上执行 ch01 五卡片 → 草稿 → 运行 LLM → 提交，核对 `step_runs` / `learner_profiles`


## 3.27 M5.14 结构化 LLM 输出与空响应保护（2026-08-05）
- 根因已确认：DeepSeek `deepseek-v4-flash` 首次请求在 `max_tokens=1500` 下可能以 `finish_reason=length` 结束，仅返回 `reasoning_content`，最终 `message.content` 为空；此前代码将其当作成功空字符串。
- 当前修复：结构化步骤 prompt 明确要求 JSON object；agent 与 prompt 共用结构化类型判定；LLM client 对 reasoning length 做一次 4k–6k token 受控重试，并对最终空 content 抛出明确异常；steps router 失败 upsert、返回 502、submit 拒绝非 saved/空输出。
- 真实验证：直接调用当前 `agent.run_step('ch01', 'step-1', ...)` 成功返回非空 JSON，keys 为 `misconceptions_cleared`、`external_voices`；未写入 live `step_runs`，未停止/重启 3011/8011。
- 隔离验证：空响应状态机（run 502 → submit 409）、JSON mode prompt、retry max_tokens 1500→4000、ch01 mock draft→run→submit→profile 均通过。
- 注意：当前 shell 无 pytest；历史 104 passed 仍有效。live DB 之前的空 smoke row 保留未动，恢复须使用已有 backup 并先确认后续数据。
## 3.28 M5.15 pytest 全量回归与异步警告修复（2026-08-05）
- 用户环境已安装 pytest；全量回归 `108 passed`。
- `agent.py` 的 `create_task()` 同步场景悬空 coroutine 已修复；回归输出不再出现 `RuntimeWarning: coroutine ... was never awaited`。
- 当前剩余 113 条 warning 不影响测试通过：主要是 FastAPI `on_event` 弃用、book 正则 FutureWarning，以及 Windows pytest 临时目录清理权限异常。
## 3.29 M6 只读浏览器验收与 live 无效运行修复（2026-08-05）
- Playwright CLI 只读验证 root/ch01：API 请求全为 200；favicon 修复后 console 无 error/warning。
- 前端空输出不再显示 `{}`；live DB 先备份到 `platform/backend/data/backups/ww-20260805-before-invalid-run-repair.db`，再修复 3 条历史空 `saved/submitted` 运行，标记为 `failed`。
- 未执行真实 UI run/submit，未重启 3011/8011；当前最后一步仍需用户确认数据范围后，在 Service Dashboard 重载最新后端代码，再做一次真实 ch01 UI 验收。
## 3.30 M5.16 ch01 失败状态呈现与提交后对话入口修复（2026-08-05）
- 历史 `failed` step run 仍保留在后端审计数据，但前端不再将其当作当前输入回填；进入页面显示干净输入，并在展开步骤时给出可理解的重试提示。
- `submitted` 步骤在当前卡片内显示完成确认和「对话」CTA，点击后带入当前步骤上下文并切换 Chat Tab；已提交输入与操作区锁定。
- Chrome + Playwright 模拟 failed/submitted 两种状态通过；前端 `node --check` 与 `git diff --check` 通过。
- 本轮没有重启 3011/8011，也没有修改 live DB；前端刷新即可读取改动。

## 4. 当前下一步
1. 用户刷新 `http://localhost:3011/?chapter=ch01`，确认历史失败状态不再显示问号和默认勾选。
2. 在已提交步骤内点击「对话」，确认直接进入右侧 Chat Tab。
3. 继续按 M6 计划推进真实 API Key 场景的受控验收；后端若有新代码，再通过 Service Dashboard 重载 8011。

## 3.31 P0-3 step_runs 状态机护栏（2026-08-05）
- 修复 `_persist_run` 按章节最新行覆盖已提交 step 的问题：draft/saved 只更新同一 `run_id`，failed/submitted 后续运行插入新行。
- 新增 ch01 回归：提交后再次运行必须保留原 submitted 行并生成新的 saved 行。
- 定向 `4 passed`，全量 `109 passed, 115 warnings`。
- 下一项进入 REVIEW P0-1：SQLite 连接线程与忙等待配置。

## 3.32 P0-4 `/run` 输入 schema 服务端校验（2026-08-05）
- `/run` 现在在 LLM 调用前执行 `_validate_user_answers`；非法输入返回 422，不落库、不消耗 LLM。
- 新增 ch01 非法误区 id 回归；定向 `5 passed`，全量 `110 passed, 117 warnings`，无跳过。
- 已确认 P0-1/P0-2 当前代码已有修复。
- 由于修改后端代码，下一步需要用户通过 Service Dashboard Reload/Restart `8011`；禁止终端手动启动或停止。

## 3.33 P0-5 提交后输出锁定护栏（2026-08-05）
- `steps.py` 的输出编辑端点现在拒绝 `submitted` 运行，返回 `409`，保持提交结果不可变。
- 新增 ch01 回归测试 `test_ch01_submitted_output_cannot_be_edited`；修复重复/缺失的 `pytest.mark.asyncio`，空 LLM 响应测试已恢复执行。
- ch01 定向 `6 passed, 0 skipped`；全量 `111 passed, 119 warnings`。
- warning 仍为 FastAPI `on_event` 弃用、book 正则 FutureWarning 和 Windows pytest 临时目录清理权限提示；未影响测试退出码。
- 后端代码已更新但 `8011` 尚未重载；需用户通过 Service Dashboard Reload/Restart `8011` 后，再做只读在线验证：已提交步骤调用 `PUT /output` 应返回 `409`。

## 4. 当前下一步
1. 用户在 `http://localhost:4005` Reload/Restart What Want backend `8011`。
2. 重载完成后，验证已提交 ch01 步骤的 `PUT /output` 返回 `409`，不修改 live DB。
3. 继续 REVIEW 中剩余的 P0/P1 护栏，并保持每项都有回归测试和全量回归。
## 3.34 P0-5 在线护栏验收（2026-08-05）
- 用户已通过 Service Dashboard 重载 `8011`。
- ch01 step-1 当前 live run 为 `submitted`，有有效输出。
- 使用当前输出原值调用 `PUT /api/chapters/ch01/steps/step-1/output`，返回 `409 submitted step output is locked`。
- 前后核对 run id、状态、输出内容均未变化，确认没有写入 live DB。
- P0-5 已完成代码、测试和在线验证；下一步继续 REVIEW 剩余 P0/P1 护栏。
## 3.35 REVIEW P0/P1 复核与 M6 真实验收边界（2026-08-05）
- 当前 REVIEW 中 P0-1～P0-5 均已完成代码、测试；P0-5 已在线返回 `409 submitted step output is locked`。
- 附2-1～附2-4 已落地：结构化 json_mode、agent_configs seed、`POST /api/book/chapters/{chapter_id}/config` version+1、DB/JSON 一致性检查脚本。
- P1-3 已使用 `created_at + rowid` 作为同秒消息的稳定排序；P1-2/P1-4 按 REVIEW 原结论暂缓，待数据规模达到阈值再做索引/元数据优化。
- 当前后端回归基线为 `111 passed, 119 warnings`，无新的高风险代码项应猜测修改。
- 下一步是 M6 真实 API Key 验收：用户在 `3011` 执行一次 ch01 `保存草稿 → 运行 LLM → 提交`，开发侧再核对 live `step_runs` / `learner_profiles`；不直接消耗 API 配额。
## 3.36 M6 真实 ch01 验收前测试数据隔离（2026-08-05）
- 已按用户确认先备份 `platform/backend/data/ww.db` 到 `platform/backend/data/backups/ww-20260805-before-real-ch01-reset.db`；源库与备份 SHA-256 一致。
- 已清理 1 条 ch01 `step_runs`、4 条 `ch01/ch1` 对话、1 条 `local` profile；其他章节 29 条运行记录保留。
- 在线复核：`8011` health=200，ch01 `current_run=null`，ch01 chat=0 条。
- 当前可以开始干净真实验收：在 `3011` 执行 ch01 `保存草稿 → 运行 LLM → 提交`；完成后核对 live `step_runs` / `learner_profiles`。
## 3.37 M6 上下文完整性审计结论（2026-08-05）
- ch01 的“LLM 复述”根因不是正文未注入，而是 output_fields/output_template 没有要求 `commentary`；ch01 PRD 要求三类输出，但交接文档 §7.1 当前只列两类，需后续统一文档契约。
- 导师看不到外部声音的根因已确认：`mentor_hooks.references=[]` 时 assembler 只放 profile 占位，没有真正注入 `learner_profiles`。
- “聊聊这一步”当前只显示前端 banner，没有把真实 step 输出传给 `/chat/send`。
- `agent.run_step` 默认 user_id 为空，导致后续章节 step prompt 也可能拿不到 profile；不能只修 ch01。
- ch04 `top_values` 未映射到 profile `values`，会影响 ch08 的跨章引用；ch04 mentor `formula` 当前没有明确 producer，需要设计侧确认，开发侧不猜。
- 章节内 references 缺少运行前完整性校验，后续需覆盖 ch04 级联及所有声明 references 的步骤。
- 后续修复范围覆盖全章上下文链路；ch07/ch08 作为跨章引用重点验收样本，不是唯一修复对象。
- 代码补丁、测试与设计文档同步已完成；当前 live ch01 配置已通过 version+1 端点发布，后续进入真实 UI 验收与未决设计项处理。

## 3.38 M6 上下文完整性修复完成（2026-08-05）
- ch01 配置已新增 `commentary` 输出契约；prompt 明确要求基于本章正文逐条解释误区、给出正确认知，并区分外部声音与用户自评。
- `build_mentor_prompt` 现在始终注入完整 compact profile；bridge CTA 保存 `step_id`，后端读取最新 submitted step output 后注入 mentor prompt。
- compaction 现在合并既有 profile，`top_values` 映射为 profile `values`；因此前序章节字段不会被后续章节覆盖丢失。
- `references` 在运行前检查 submitted 来源和字段，缺失时返回 `409 Step context incomplete`；ch04 五步测试已按 submitted 状态验证。
- 前端 commentary 与 `misconceptions_cleared` / `external_voices` 同时渲染；ch01、ch02/ch03 profile、ch04 级联、ch07/ch08 跨章引用均有回归覆盖。
- 定向测试 `33 passed`；全量测试 `120 passed, 123 warnings`；前端脚本 Node 语法检查通过。
- 已通过 `POST /api/book/chapters/ch01/config` 发布 live DB version `4`；未停止/重启 `3011/8011`，未删除现有真实验收数据。
- 已同步 `PRD-ch1.md`、`platform/SPEC.md`、工程实施交接文档，明确 commentary、profile 合并、references 护栏和 bridge step context 契约。
- 未决：ch04 `mentor_hooks.references=[formula]` 没有明确 producer，继续保留为设计侧确认项，不自行猜测替换。

## 3.39 M6 ch01 重测前数据清理（2026-08-05）
- 用户确认后已备份 live DB：`platform/backend/data/backups/ww-20260805-before-ch01-reset-203809.db`。
- 备份 SHA-256：`d67600e83b93ba9da561173e8387b2677c35ebad8f25890a1f221fadf9d0c77c`。
- 已删除 1 条 ch01 `step_runs`、4 条 ch01/ch1 对话、1 条 `local` profile；其他章节 29 条运行记录保留。
- 在线复核通过：`8011` health=200，ch01 current run=null，ch01 chat=0，active config 字段包含 `commentary`。
- 未停止/重启 `3011/8011`；下一步由用户通过 Service Dashboard Reload/Restart `8011` 后进行干净 ch01 UI 验收。

## 3.40 M6 ch01 反馈修复与 version 5（2026-08-05）

- 输入阶段隐藏「聊聊这一步」；仅当本步成功生成 `parsed_output` 后显示，避免用户在没有 LLM 结果时提前进入导师对话。
- ch01 `commentary` 改为用户绑定的本章分析：按每个勾选误区分别解释，结合对应外部声音和用户想法，不再输出泛化章节摘要或重复用户输入。
- mentor prompt 注入完整 compact profile 和最近提交步骤上下文；导师必须用自己的话结合用户问题解释原则，禁止“书中说 / 作者说 / 本章写到”等照本宣科表达。
- 上下文完整性规则适用于所有章节：章节内 `references` 读已提交前序 step 输出，跨章引用读合并后的 `learner_profiles`；缺失来源或字段时拒绝生成。
- 定向测试 `31 passed`；全量测试 `123 passed, 123 warnings`。
- 已通过 `POST /api/book/chapters/ch01/config` 发布 live DB version `5`；未停止或手动重启 `3011/8011`。

### 当前接管动作

1. 用户通过 Service Dashboard Reload/Restart `8011`，刷新 `3011`。
2. version 5 需要新的 ch01 run 才能验证；在清理当前 ch01 测试数据前先取得用户确认。
3. 验收顺序：填写误区卡 → 运行 LLM → 检查逐条 commentary → 提交 → 进入「对话」确认导师结合误区和外部声音、避免书面直引。

## 3.41 M6 A方案上下文契约与 live version 6（2026-08-05）

- 当前任务：修复 ch01 LLM 只复述输入、导师追问发散/照本宣科；A 方案已实现。
- ch01 step prompt 现在逐条装配 `checked_ids` 与 `external_voices`，每条包含误区、错误认知、本章原则和四步分析 contract；未勾选误区不进入分析。
- mentor prompt 现在携带 active focus、对应外部声音、本章原则、conversation stage 和 focus turn count；最多连续追问同一焦点两轮，行动问题先给行动，澄清/收束时不再追问。
- live DB：ch01 config 已发布 version `6`；mentor role 已通过 API 更新；agent config scaffold 已 seed。未清理 ch01 数据，未停止或重启 `3011/8011`。
- 验证：定向 `33 passed`；全量 `125 passed, 123 warnings`；API 复核 live few-shot 不含 `??`，mentor role 不含损坏的 `????`。
- 全章实施教训：所有 ch02–ch08 都必须把前一步的真实 submitted output 或合并 profile 作为后一步输入；ch07/ch08 只是重点验收，不是唯一范围。每条 references 必须有 producer/consumer/缺失阻断测试。

### 当前接管动作

1. 用户通过 Service Dashboard Reload/Restart `8011`，刷新 `3011`。
2. 用新的 ch01 run 验收逐条 commentary；已有历史数据保留，不要把历史 run 当作本轮结果。
3. 进入「对话」验证刘老师引用当前误区和外部声音，围绕本章理解收束，不使用「书中说」等照本宣科表达。
4. 继续 ch02 之前，按同一契约检查其输入是否明确引用 ch01 输出/profile，并先补对应 API/E2E 测试。

## 3.42 M6 A方案验收前 ch01 数据已清理（2026-08-05）

- 用户确认需要清理后，已在线备份 live SQLite：`platform/backend/data/backups/ww-20260805-223529-before-ch01-reset-v6.db`。
- 备份 SHA-256：`17fe573c003081d279dc27ac032556f9c78c010072750ad01106ff0eafa29d6e`。
- 已删除 ch01 `step_runs` 1 条、ch01/ch1 对话 18 条、`learner_profiles.user_id='local'` 1 条；其他章节 29 条 step_runs 保留。
- 在线复核：ch01 step_runs=0、ch01 chat=0、local profile=0、chapter_configs=14；配置未删除。
- 未停止或重启 `3011/8011`。用户下一步 reload `8011`、刷新 `3011`，从干净 ch01 开始验证 A 方案。

## 3.43 M6 ch01 清单正文对齐与 live version 7（2026-08-05）

- 已确认右侧误区自检清单由 `chapter_config_ch01.json.input_schema.items` 静态渲染，不是 LLM 摘要；旧配置与第一章正文 3–5 条错位。
- 已按正文五个 POINT 修正 1–5 卡片、错误认知、正确认知、core concepts、guiding questions 和两处 few-shot。
- `PRD-ch1.md` 五误区表已同步；测试新增精确标题/正确认知断言。
- live config 已通过 version+1 端点发布 version `7`，API 回读 5 条卡片均与正文一致。
- ch01 数据已在 version 7 发布前清理，未删除其他章节数据；用户下一步刷新 `3011`，验证卡片和 LLM 分析使用新的编号语义。

## 3.44 M6 ch02 E2E 与跨章上下文实测（2026-08-05）

- 浏览器测试环境已就绪：Python Playwright `1.62.0` 显式使用 `D:\Programs\playwright-browsers\chromium-1234\chrome-win64\chrome.exe`；不依赖 Playwright 自动下载的 headless shell。
- ch02 真实流程已通过：步骤表单序列化、草稿保存、LLM 运行、结构化输出渲染、提交锁定、完成卡和对话 CTA 均正常；所有请求无失败，页面无 console error。
- Chat bridge 实测请求为 `POST /api/chapters/ch02/chat/send`，body 含 `step_id: step-1`。后端回复实际引用了 ch01 profile 中的外部声音，同时引用当前 ch02 `internal_external_ratio` 与 `reclaim_item`，证明前序 profile 和当前 submitted step context 均已成为导师真实输入。
- ch01–ch08 页面烟测通过：8 个章节均可加载，摘要/对话/步骤/笔记四个 Tab 均可切换；共 12 个步骤卡均可展开，未发现页面错误或网络失败。
- 回归基线：上下文/跨章定向测试 `32 passed`；全量 `125 passed, 123 warnings`。warning 仅为已知弃用、正则 FutureWarning 和 Windows pytest 临时目录权限提示。

### 当前 live 状态

- 本轮在 live DB 留下 ch02 `step-1` 的 1 条 `submitted` E2E run 和 2 条 ch02 对话消息；profile 已刷新到 `current_chapter=ch02`。
- 这些是验收数据，不应被后续章节验收误认为用户真实输入；开始 ch03 前需决定保留作跨章演示，或先做带备份的受控清理。
- 本轮未停止、kill 或手动重启 `3011/8011`；服务仍由 Service Dashboard 管理。

### 接管动作

1. 继续 ch03 前，读取其配置的 `references` 与输入 schema，列出每个 producer/consumer 和缺失时的阻断行为。
2. 为 ch03 补页面 E2E 与上下文完整性测试，再实现或修正页面，不把上一章节的提示文案当作真实上下文。
3. 每个章节完成后重复：浏览器真实路径、接口回归、全量 pytest、live 数据范围记录、Git 检查点。

## 3.45 M6 ch02 E2E 数据已清理（2026-08-05）

- 用户确认清理本轮 ch02 验收数据；清理前先完成 live SQLite 在线备份：`platform/backend/data/backups/ww-20260805-before-ch02-reset.db`。
- 备份 SHA-256：`c803c2be37eefe5015925f5177dc455d64e0fb4c089bf6226ec53b305a065ee5`。
- 精确删除 1 条 ch02 `step_runs` 和 2 条 ch02 `chapter_chat`；目标记录删除后均为 0，未影响其他章节记录。
- profile 清理只移除 ch02 运行产生的 `internal_external_ratio`、`reclaim_item`，并把 `current_chapter` 恢复为 `ch01`；ch01 profile 字段保留。
- `3011/8011` 未停止或重启，服务继续由 Service Dashboard 管理。

## 3.46 M6 ch01 教训推广为全章节 few-shot 门禁（2026-08-05）

- 已确认 ch01 的 `??` few-shot 问题应作为跨章节工程门禁，而不是一次性修复；同类损坏可能在 JSON、备份、DB 发布或读取链路复发。
- 新增 `test_all_chapter_few_shots_are_not_corrupted`：遍历 ch01–ch08 canonical chapter config 的所有 `few_shot*` 字段，禁止 `??` 和 Unicode replacement character `�`。
- 本轮门禁测试通过 `13 passed`；ch01 原有的正文绑定、commentary 和 few-shot 语义断言没有删除。
- live `check_config_consistency.py` 已确认 ch01–ch08 全部 `[OK]`；全量后端回归为 `126 passed, 123 warnings`。
- 后续章节的统一交付门槛：
  1. 先做 JSON/DB active config 一致性和 few-shot 编码检查；
  2. 明确每个 producer/consumer，缺失上下文必须阻断；
  3. 用真实 submitted output/profile 做 API 与页面 E2E；
  4. 运行全量 pytest 后再进行 live 验收和数据清理。
- 这条门禁目前已记录在开发侧进度与 checkpoint；若后续设计侧需要正式验收条款，再同步到工程实施交接文档/SPEC，而不改变其作为唯一权威设计依据的地位。

## 3.47 M6 ch03 三要素结构化输入与 Venn 实测（2026-08-06）

- 已确认 ch03 原 live config 的 `input_schema=[]` 是真实缺口：前端只渲染一个总文本框，无法保证「喜欢/擅长/重要」分别成为后续输入。
- canonical config 和 live version `3` 已补齐三组 `list_of_items`（各 3–5 项）以及 `commentary` + 三要素 + `intersection` 输出契约。
- 前端新增仅作用于 ch03 的实时 Venn 预览；三组输入值通过原有 `collectSchemaAnswers` 结构提交，未改变其他章节协议。
- 浏览器实测通过：三组输入、草稿、LLM、结构化输出、提交和 profile compaction 全部成功；五个输出键齐全，无页面错误或网络失败。
- 提交后的 profile 同时包含 ch03 的 `likes/talents/importance/intersection` 与 ch01 `misconceptions_cleared`，证明跨章 profile 未被覆盖丢失。
- live 发布前备份：`platform/backend/data/backups/ww-20260806-before-ch03-config-publish.db`；SHA-256：`fd3e621d1cb27ec35affedcacb8b6623e88cfa9f0e858719cb7f4d8a2a35972d`。

### 当前接管动作

1. ch03 live 当前保留 1 条本轮 `submitted` E2E run 和更新后的 profile；若进入下一轮真实验收，先确认是否备份并清理这批测试数据。
2. 对话验证必须同时检查：ch01 误区锚点、ch03 三要素结果、本章公式，以及导师不照本宣科且围绕三要素收束。
3. ch04 开发继续沿用“先契约/测试，后页面”的顺序，重点验证 step-1 → step-2 → step-3 → step-4 → step-5 的真实 submitted output 引用链。


### 3.48 ch03 导师对话重复发送修复（2026-08-06）

- 已确认重复对话来自前端 POST 自动重试，不是 ch03 测试数据本身：sendChat 的 chat/send 请求在超时/网络异常时会由 fetchJson 再发一次，后端无幂等保护。
- 已修复为 chat POST 使用 retry: 0，并加入前端契约测试，防止通用 fetchJson 变更后回归。
- 验证结果：定向 21 passed；全量（忽略既有无权限 tests/_tmp）130 passed, 123 warnings；ch03 live 页面烟测无控制台错误/请求失败；ch01-ch08 配置一致性 CLEAN。
- 未停止或重启 3011/8011，未修改 live DB；当前 ch03 测试数据仍按上一 checkpoint 保留，真实验收前需先备份并经确认后清理。
- 下一步：创建 Git 检查点；随后进入 ch04，先验证 step-1→step-5 的真实 submitted output 引用链，再做页面级级联 E2E。

### 3.49 ch04 输出契约对齐与五步级联验收（2026-08-06）

- ch04 五步级联机制保持 `references -> submitted step_runs.parsed_output`，新增测试逐步验证：step-2←step-1.top_values、step-3←step-2.groups、step-4←step-2.groups+step-3.conversions、step-5←step-4.ranked。
- 修复 Step 3 输出字段契约：使用 `value/type/converted_to/why_chain`，前端显示可控性状态和 5 Why 链，并兼容历史 `rewritten` 数据。
- 修复 Step 5 输出契约：增加 `reasoning`，并让前端同时渲染 `work_purpose` 与 `experience_map`。
- live config 已发布 version 4；发布前备份路径为 `platform/backend/data/backups/ww-20260806-before-ch04-config-publish.db`，SHA-256 为 `3098369fa448a476ae1e0229bab90eb19ddf39958dba14cf4a1d18040d2c1359`。
- 未停止或重启 3011/8011，未清理任何 live 数据；ch04 当前仍无提交步骤，真实验收需由用户确认输入后再进行。
- 下一步：创建 Git 检查点；随后继续检查 ch05 的输入结构、profile 引用和页面输出，不复用 ch04 的假设。

### 3.50 ch05 产品/架构评审：流程确定，字段契约进入 backlog（2026-08-06）

- 产品经理 Agent 与系统架构 Agent 已完成评审；ch05 采用交接文档的一步八角度方案，不采用 PRD 中旧的两步五问/使用说明书方案。
- 暂不修改 ch05 live config：输入 key、payload 结构、talents item 内部字段和证据绑定尚未被权威文档确定，离线期间不能猜测并发布。
- backlog 项：8 个角度稳定 ID/顺序；顶层 answers/grid_answers/angles 形状；talent/evidence/source_angles/locked 等内部字段；用户编辑和锁定结果的持久化格式；PRD 与交接文档的同步方式。
- 当前 ch05 页面基线已实测确认：1 个步骤、1 个总文本框、无结构化字段；该问题已记录，不作为完成状态。
- 继续工作：核对 ch06 及后续章节，优先处理不依赖 ch05 未决 schema 的实现与测试。



### 3.51 ch07 field-level cross-chapter context gate (2026-08-06)

- Product and architecture review confirmed that unresolved ch05/ch06/ch08 input schemas must not be guessed. The confirmed ch07 ch03/ch04 producer fields were implemented as a server-side gate.
- Changed: `platform/backend/app/runtime/context_requirements.py`, `platform/backend/app/routers/book.py`, `platform/backend/app/routers/steps.py`, `platform/backend/app/routers/chat.py`, `platform/backend/app/runtime/agent.py`, `platform/backend/app/services/compaction.py`, and `platform/frontend/index.html`.
- Updated tests: `tests/test_m5_chapter_status.py`, `tests/test_m4_per_chapter.py`, and `tests/test_all_chapters_e2e.py`; ch07 is no longer treated as an independent chapter in the E2E fixture.
- Validation: full `133 passed, 127 warnings`; config consistency is CLEAN; after the 8011 restart live status correctly locks ch07 for missing ch04 `work_purpose`; browser smoke has no console/request failures.
- Current live data still contains historical ch04 step runs, but the profile is missing `work_purpose`, so ch07 remains correctly locked. Back up and confirm the cleanup scope before the next real acceptance run.
- Next: continue read-only audits of ch05/ch06/ch08; after field contracts are confirmed, synchronize PRD, canonical config, DB active config, renderer, validation, prompt, and E2E together.

### 3.52 Step prompt audit evidence persistence (2026-08-06)

- `platform/backend/app/runtime/agent.py` supports `return_details=True`; `platform/backend/app/routers/steps.py` persists the actual assembled prompt in `step_runs.rendered_prompt` instead of a placeholder.
- `tests/test_all_chapters_e2e.py` verifies that the real ch07 prompt contains the ch04 `work_purpose` value.
- Full regression: `133 passed, 127 warnings`.
- Because this change happened after the latest 8011 reload, live verification is pending the next Service Dashboard reload; do not manually kill or restart the services.

## 4. 当前接管点：ch02 四阶段重构已实现（2026-08-06）

### 当前代码状态

- ch02 canonical config 与 PRD 已切换到最终设计：一个 exercise、四阶段语义流、`drive_items` + `note`、后端 item-count ratio、`commentary`/`reclaim_item` 输出、ch01 两个 profile 引用。
- ch02 专属前端 renderer 已接入 `platform/frontend/index.html`，不影响其他章节通用 renderer。
- 后端已实现 ch02 输出 contract、ratio 权威覆盖、reclaim-only 编辑、new draft、最新 submitted 选择和严格提交校验。
- live DB ch02 config 已通过 POST version+1 发布到 version `4`；当前服务进程仍需 Service Dashboard reload 才能加载本轮后端代码。

### 验证证据

- `tests/test_ch02_e2e.py`、M4 ch02：专项通过。
- `pytest --ignore=tests/_tmp -q`：`138 passed, 137 warnings`。
- 真实 `3011` 页面加载和 ch02 阶段 1 smoke 通过；Playwright 拦截写接口的完整四阶段前端回归通过，无 console/page error。
- 默认 pytest 的唯一阻断是既有 `platform/backend/tests/_tmp` 无权限目录，未触碰该目录。

### 下一步

1. 用户通过 Service Dashboard reload/restart `8011`，刷新 `3011`。
2. 在不清理其他章节数据的前提下，用户确认是否清理 ch02 live 测试数据；确认后再做真实 ch02 端到端验收。
3. 验收重点：ratio 是否为后端件数派生、commentary 是否结合事项/备注、reclaim 编辑后提交锁定、导师只读 submitted profile、重新做本章保留旧 submitted。
4. 验收通过后创建/确认 Git 检查点；继续 ch03 或按计划审阅下一章。
5. ch05/ch06/ch08 的未决 schema 继续 backlog，禁止根据旧 PRD 猜测实现。

### 经验固化

- 配置源文件不是运行时配置；每章改 schema 必须同时发布 DB active version，并验证回读。
- 前一步输出只有在 submitted + compaction 后才是后一步正式上下文；draft/saved 不得进入导师或下游章节。
- LLM 输出的派生数值不能作为事实来源；后端按用户最终输入重新计算并在 run/edit/submit 三个边界覆盖。
- 单体通用 runner 无法表达复杂章节阶段流；优先用章节专属 renderer，避免改坏其他章节。
- 所有章节必须在 API 单测通过后再做浏览器 E2E；浏览器测试必须覆盖刷新、失败、重跑、提交锁定和上下文审计。

## 当前接管点：ch02 第二次运行超时假失败已修复（2026-08-07）

- 现象：首次运行成功后返回修改，再次点击“运行 LLM”时浏览器提示 `signal is aborted without reason`。
- 证据：数据库记录显示后端实际请求可能在浏览器 90 秒超时后继续完成；一次真实请求最终约 117 秒后保存成功，说明前端 AbortController 先于后端完成。
- 修复：`platform/frontend/index.html` 的 LLM `POST /run` 改为 `timeout: 180000, retry: 0`；成功后 ch02 明确进入阶段 2。
- 回归：前端契约 `2 passed`；ch02 后端专项 `5 passed`；真实浏览器 `POST /run` 返回 `200` 且无页面错误；拦截式回归确认只发送一次 POST 并显示阶段 2。
- 不需要用户重启 `3011/8011`；刷新前端即可验证。当前 live 数据保留本轮 ch02 测试 run，后续如需真实验收，先单独确认清理范围。
- 通用教训：所有章节的长耗时 LLM POST 禁止盲目 retry；验收必须覆盖“首次运行 → 返回修改 → 再次运行 → 页面阶段状态”。

## 当前接管点：ch02 provider 超时与测试文案隔离修复（2026-08-07）

- 新错误是后端真实 provider timeout，不是前端 AbortController：`500 Step run failed: Request timed out.`。
- `AsyncOpenAI` 默认内部重试 2 次，step 默认 SDK timeout 30 秒；已改为 step 120 秒、SDK `max_retries=0`，timeout 映射为 504。
- 失败 run 现在保存本次最新 `user_answers` 并清空旧 Prompt/输出，避免上一次输入被误带入失败结果。
- Prompt 新增用户输入边界：用户填写内容仅作为原始证据，不作为系统/开发者指令或已验证事实；调试/测试/运行状态词不能被当成现实事实。
- 已承认上一轮真实浏览器回归向 live ch02 写入过测试文案；当前只读全库扫描未发现“超时恢复/超时修复/回归/测试”残留。后续不得对 live DB 写测试文案。
- 专项验证 `24 passed`；全量 `140 passed, 2 failed`，失败为既有 ch03 dirty config 与旧测试断言不一致。
- 下一步：用户通过 Service Dashboard 重启 `8011`，刷新 `3011`，重新测试 ch02；不需要清理当前数据，除非用户明确要求清理范围。


## ??????ch02 ??????? chat ??????2026-08-08?

- ch02 ????????????????? run ???? `user_answers`????????? `failed` ?????????????????
- ??????? `500 Internal Server Error: mentor unavailable: LLM provider timed out after 30s`???? mentor provider timeout ??? 120 ??router ?? 504???????? 180 ????? POST?
- ?????`tests/test_chat_api.py` ? `tests/test_ch02_e2e.py` ? 11 ???????????? 3 ????
- ??????????? Service Dashboard reload/restart `8011`????? `3011`????????????? ch02 ????????????????? 30 ??????
- ???????????????????????????????????????????? user input?run status?error message ??????


## 当前接管点：全局选区笔记高亮漂移已修复（2026-08-08）

- 用户发现正文高亮与右侧笔记“定位原文”不一致。代码审计确认是 innerText 偏移、DOM 文本节点偏移不一致，以及重复原文使用 indexOf 首次命中的双重问题。
- 已在 platform/frontend/index.html 统一选区 Range、DOM 文本坐标、旧锚点回溯；新增安全笔记浮层，点击高亮即可查看当初笔记。
- 旧 live 笔记未删除；已验证 ch02/ch03/ch04/ch05，包含 ch03 跨 Markdown 列表换行的旧笔记。
- 用户动作：不需要重启 8011；刷新前端或通过 Service Dashboard Reload 3011 后验证：点击高亮查看浮层、右侧笔记“定位原文”、跨段落旧标注。
- 后续注意：新建选区笔记应生成 source_anchor.version=2；任何正文渲染结构变化都必须保留旧锚点兼容测试。

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
## 3.58 ch03 三圆交集预览布局修复（2026-08-09）

- 用户反馈：三圆重叠区中的清单文字互相覆盖，截图中无法完整阅读；要求缩小字体或参考 mockup。
- 采用方案：对齐 `platform/prototype/ch03_exercise_mockup.html` 的“三栏陈列 + 独立交集卡片”，不再把用户清单文字塞进重叠圆形。
- 实现文件：`D:\AI_Project\What_Want\platform\frontend\index.html`。
- 具体行为：三组清单分别渲染为独立卡片，文字 `overflow-wrap/word-break`，列表可滚动；交集区明确标注为 AI 语义总结；保留实时计数与阶段 2 的 `intersection` 回填。
- 契约边界：不修改 API、数据库、配置或 `user_answers`；未加入 mockup 中逐项 `note` 字段。
- 验证：内联脚本语法通过；Playwright mock draft 回归通过，覆盖 3 栏、长输入、实时刷新、交集 renderer；`CH03_VENN_E2E=PASS`，控制台错误和请求失败均为空。
- 用户动作：刷新 `3011` 查看最新布局；不需要重启 `8011`，不需要清理 live 数据。

## 3.59 ch03 导师对话超时修复（2026-08-09）

- 根因已确认：前端 180 秒 AbortController 与后端导师调用的多次 provider 尝试叠加，超时后浏览器显示 `signal is aborted without reason`；历史日志同时出现 reasoning-only、自动扩大 `max_tokens` 和 provider timeout。
- 已完成修复：LLM client 增加跨尝试总 timeout budget 和 `LLMTimeoutError`；导师调用至少 4000 `max_tokens`、关闭 reasoning retry 和 SDK retry；chat 路由返回 504；前端对 504 显示友好提示并转义错误文本。
- 已验证：相关后端测试 `12 passed`；前端内联脚本语法检查通过。验证使用工作区隔离 pytest 临时目录，避开历史系统临时目录权限问题。
- 待用户操作：通过 Service Dashboard Reload `8011`，刷新 `3011` 后复测导师对话；不要手动 kill/restart 服务。
- ch03 当前有 3 条 user + 3 条 mentor 聊天记录，共 6 条。数据库清理尚未执行，等待用户明确“全部清理”或“仅清理 mentor”。
## 3.60 ch03 旧聊天记录清理完成（2026-08-09）

- 已按用户确认删除 ch03 前 4 条历史聊天记录，删除范围由 4 个明确消息 ID 限定。
- 未删除第 5、6 条最新对话；通过 8011 API 复核当前剩余 `2` 条：`1 user + 1 mentor`。
- 本次清理未触碰其他章节数据，也未停止或重启 3011/8011。

## 3.61 当前接管点：ch04 五步重构已实现，历史数据已清理（2026-08-10）

### 已完成

- `platform/backend/app/routers/steps.py` / `runtime/agent.py` / `runtime/assembler.py`：真实 step 路径透传 `preserve_output`；锁定列表项按原位置恢复，锁定项删除受到后端保护。
- `runtime/assembler.py`：step-2 过滤用户删除的继承关键词；普通 step 只使用 `step_context.references`；锁定编辑注入 prompt。
- `platform/backend/app/routers/chat.py`：ch04 导师只读取所有已提交 step 的筛选上下文，未提交 step 不进入 prompt。
- `platform/backend/app/services/compaction.py`：`values` / `ranked` 加入下游必保字段。
- `platform/frontend/index.html`：ch04 五个 step 专用 renderer 与编辑交互已接入；step-5 textarea 按行提交为 `experiences`。
- `platform/backend/tests/test_ch04_dev_contract.py`：新增 6 个开发契约测试，并覆盖 100 例价值观接口。

### 数据/配置状态

- ch04 active config 当前为 DB version `5`，与 canonical JSON 一致。
- ch04 测试历史已清理：`step_runs=0`、`chapter_summaries=0`、`chapter_chat=0`、`conversation_summaries=0`。
- 未删除 ch04 配置版本，也未触碰其他章节数据。

### 验证证据

- ch04 契约测试：`6 passed`。
- 相关回归：`33 passed, 1 failed`；唯一失败是既有 ch05 role 期望不一致，不属于本轮 ch04 改动。
- 前端语法检查通过；Playwright 已验证 ch04 5 step 可见、五问采集、step-2 关键词、100 例入口返回 100 项、preserve 构造、step-5 十行经历，控制台无错误（100 例请求用新后端响应 mock 验证）。
- 8011 live 进程仍需 Service Dashboard Reload 才会加载本轮后端代码；不手动停止/重启 3011/8011。

### 下一步

1. 用户通过 Service Dashboard Reload `8011`，刷新 `3011`。
2. 从干净 ch04 数据开始走 step-1→step-5：先验证 step-1 提交，再逐步运行/编辑/锁定/重生成/提交。
3. 真实运行通过后，再补 ch04 导师分层上下文 live 验收；若出现阻塞，记录到本文件与 `PROGRESS.md`，不要绕过。

## 3.62 当前接管点：ch04 step-2 关键词池 reasoning 截断已修复（2026-08-11）

### 已完成

- 已确认 502 根因：`deepseek-v4-flash` 的旧 `max_tokens=1500` 不足以覆盖 reasoning token + JSON 正文，导致 provider 返回 `finish_reason=length` 和空 content。
- `platform/backend/scripts/seed_roles.py`：`psychologist` / `career_counselor` 默认预算改为 `4000`；既有角色刷新时同步 `description`、`temperature`、`max_tokens`，避免 seed 源与 DB 生效值再次漂移。
- `platform/backend/tests/test_seed_roles.py`：新增回归，确保已有 role 再次 seed 时会恢复到 `4000`。
- 活动 DB 已只更新 deepseek 的 `psychologist` 与 `career_counselor` 两条记录到 `4000`；未触碰用户 profile、已提交 step 或其它章节数据。

### 验证证据

- 定向测试：`8 passed`（`test_seed_roles.py` + `test_llm_client.py`）。
- 同一失败 step-2 输入的真实 `/run` 验证成功：新 run `45228ee7-c631-4cfc-90ad-d3d1e9c5c730` 状态为 `saved`，`parsed_output.groups=4`。
- 未停止、启动或重启 `3011/8011`；本修复不需要 Service Dashboard 重启，因为步骤角色由 DB 按请求加载。

### 下一步

1. 用户刷新 ch04 页面，确认 step-2 显示最新分组结果并完成编辑 / 锁定 / 提交。
2. 继续走 ch04 step-3 至 step-5；若仍出现 `finish_reason=length`，记录角色、prompt 大小、response usage，再决定是否需要将客户端重试上限扩展至 `6000`。
3. Git 提交时只纳入本次 seed 同步、回归测试与对应进度记录，不混入工作区已有无关修改。

## 3.63 当前接管点：ch06 设计复核完成，等待设计侧确认（2026-08-12）

### 已完成

- 已对照 ch06 最终落地文档、PRD、canonical config、后端 steps/assembler/chat、前端 renderer、题库 API 与全书测试夹具。
- 已确认 `chapter_config_ch06.json` 的两步主方向与设计一致：step-1 领域级 `likes`，step-2 结构化 `likes` + 可选 `reference_talents`，导师钩子为 `talents`/`likes`。
- 已新增 `llm_prompt_design/docs/ch06_落地级步骤设计_待设计确认.md`，列明实现缺口与 5 项最小待确认问题。

### 硬边界

- 当前实施目标仍是 ch05；不能把当前工作区描述为 ch05/ch06 一起完成。
- ch06 当前配置升级与为其迁移的测试属于 pending，待设计回复后单独实施、单独验证、单独 Git 保存。
- 本轮没有改 ch06 生产代码、数据库、ch07 代码，也没有清理用户数据或停止/重启 3011/8011。

### 已发现缺口

- ch06 缺少后端专属 output normalize/validate、step-2 `reference_talents` 合并契约和 locked 原位保护测试。
- ch06 缺少专属前端 renderer；嵌套 `likes` 当前会退化为 JSON，且 `passion_examples` 尚未从 step API 的 `ui_context` 传到页面。
- ch06 导师仍需切换到 submitted-only 的本章多 step 上下文；草稿时间戳、保存失败恢复、30 问交互和 100 例引用 seed 载体仍未形成完整实现契约。
- ch07 后续需补 ch06 `likes` 上游门禁及嵌套 likes 消费/flatten 规则；不在本轮扩大实现范围。

### 验证状态

- 已完成只读代码/文档审计。
- ch06 DB active config 一致性尚未完成验证；项目 Python 解释器调用遇到 `Access is denied`，不能无证据声称已 reseed。
- ch06 真实 LLM/API E2E 与浏览器 E2E 尚未执行。

### 下一步

等待设计侧回复并同步 ch06 权威文件；回复明确后，再开始 ch06 独立实施。ch05 任务可继续按 ch05 计划推进。

## 4. 当前接管点：ch06 实施完成，回归全绿，待 live 浏览器验收（2026-08-14）

### 结论

- 设计侧第六轮回复已闭环，无未决问题，按最终设计实施。
- 权威依据：`llm_prompt_design/docs/ch06_落地级步骤设计.md`、`ch06_落地级步骤设计_待设计确认6_设计侧回复.md`、`config/chapters/chapter_config_ch06.json`。
- ch06 实施基线 commit：`0bae105`。

### 已完成

- 后端两步级联：step-1 领域级 `likes` 仅作级联输入、永不入 profile；step-2 提交后结构化 `likes` 显式覆盖 `learner_profile.likes`。
- `step_runs.stale` 幂等迁移，所有关键读取路径过滤 `stale=0`；step-1 重提交置旧 step-2 stale 并清空 profile。
- ch07 上游统一为 `ch04(work_purpose,values)`、`ch05(talents)`、`ch06(likes)`，移除 ch03/importance。
- ch06 输出 normalize/validate、step-2 三类候选合并（step-1 领域 / passion_seeds / reference_talents）已实现。
- 前端 ch06 专属 renderer 已实现：5 问、30 问抽屉、100 例抽屉、嵌套卡片编辑、stale 提示、Markdown commentary。

### 验证

- ch06 契约测试 `4 passed`；ch07 门禁与全章链路定向回归 `54 passed`；后端全量回归 `166 passed`（2026-08-14 复跑）。
- 前端内联脚本语法通过；DB `stale` 列存在；ch06 config version 2 active。

### 未完成

- live E2E 已全部通过（2026-08-14）：草稿恢复、30 问、100 例、step-1/step-2 真实 LLM、编辑锁定提交、stale 重提交与恢复；章节状态 2/2、进度 100%。期间修复两个真实缺陷（source 自由格式规范化、30 问查看按钮加载），见 commit `d76cc0e`。
- 用户已确认清理（2026-08-14）：ch06 `step_runs` 5→0、30 问答案 note 已删、`profile.likes=[]`、`current_chapter=ch03`；live API 复核 ch06 0/2、进度 0%，用户可从空白开始测试。

### 约束

- 不手动 kill/stop/restart `3011/8011`，由 Service Dashboard 管理。
- 只提交 ch06 实施相关文件，不执行 `git add .`；发布前 DB 备份位于 `C:\Users\deng_\AppData\Local\Temp\ww.db.pre-ch06-20260813-231006.bak`。


## 5. 当前接管点：ch04/ch05 问题清单已对齐 ch06（方案A，2026-08-14）

- 已完成：前端通用 30 问抽屉（`bankOpenThirty` 等）接入 ch04 `value_questions`（1–30）与 ch05 `talent_questions`（31–60）；ch04 100 例抽屉改读 `ui_context.values_examples`；后端 `_build_ui_context` 补 `values_examples`。
- reseed：ch04 v6、ch05 v3 已发布；ch04/ch05 DRIFT CLEAN。
- 验证：后端全量 `170 passed`；浏览器只读验收通过（抽屉 30 题、100 例、collect 与 prompt 注入）；未触动 ch04/ch05 用户数据。
- 待认：ch07 config DRIFT（文件 2 exercises vs DB 1）未擅动，需用户/设计侧确认是否 reseed。
- 回滚备份：`platform/backups/index.html.pre-ch04ch05-questionbank-20260814-154428.html`；`C:\Users\deng_\AppData\Local\Temp\ww.db.pre-ch04ch05-reseed-20260814-154428.bak`。


## 6. 当前接管点：ch07 正式实施完成，待上游完成后 live 验收（2026-08-14）

- 实现：`ideal_works` 白名单、ch07 专属 normalize/validate、step-1/step-2 提交钩子与内部 stale 传播、assembler CH07 契约、chat 上下文、前端 ch07 渲染器与锁屏整改。
- reseed：ch07 v2 已发布，全部章节配置一致性 CLEAN。
- 验证：`test_m7_ch07_cascade.py` 5 passed；后端全量 `175 passed`；浏览器只读验收通过。
- 待用户完成 ch04/ch05/ch06 后再走 ch07 live 流程；ch07 当前无 step 数据。


## 7. 当前接管点：ch08 全书流程图页实施完成（2026-08-16）

- 实现：`flowchart_state` 表 + GET/PUT `/api/book/chapters/{id}/flowchart-state`；当前节点推导与上游软提示；`has_steps` 排除 flowchart 页型；前端 ch08 流程图渲染器与真实跳转（focus 深链接自动开 30 问抽屉）。
- reseed ch08 v2；全部章节配置一致性 CLEAN。
- 验证：`test_m8_ch08_flowchart.py` 4 passed；后端全量 `186 passed`；浏览器只读验收通过。
- 待认：mentor_hooks.references 保留全书上下文需产品侧确认；带★问题子集为后续平台特性。
