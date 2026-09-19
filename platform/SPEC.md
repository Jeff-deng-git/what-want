# What Want — 交互式自我认知工作流平台 Spec

> 来源：plan `1-2-d-ai-project-ai-agent-book-obsidian-glowing-moon.md` (已批准) + prototype 验证 (`platform/prototype/index.html`)
> 状态：Ready for agent
> 优先级：M0 → M1 → M2 → M3 → M4 → M5 → M6（重构对齐见 `llm_prompt_design/docs/站点重构与开发计划.md`）

## Problem Statement

用户在读《如何找到想做的事》（八木仁平）一书。书的真正价值取决于读者能否完成"喜欢的事 × 擅长的事 × 重要的事 = 真正想做的事"这套自我认知流程——尤其是从第 4 章起每个章节有 5 个步骤 × 5 个问题的工作流。

当前痛点：
- 书本身只提供问题，没有结构化方式记录答案
- 通用笔记工具缺少 LLM 角色分析能力（心理咨询师 + 职业规划师）
- 每天/隔天使用，手动流程摩擦过大、容易放弃
- 跨步骤的引用（如步骤 3 引用步骤 1 的答案 + 步骤 2 的关键词）纯靠人工无法可靠完成
- 已提炼的关键词容易被新一轮 LLM 提取覆盖，丢失用户已经认同的内容

## Solution

一个单用户、本地部署、local-first 的 Web 平台，提供：
- 章节正文渲染（PDF 提取为 md + 嵌图，文字可选中）
- 双向笔记（选中文字笔记 + 独立面板笔记两种）
- 步骤化反思工作流：每章由 JSON 配置定义 N 个步骤，每步可定制输入问题 + LLM 操作 + 输出 schema
- 跨步骤模板引用（jinja2 风格），让后续步骤自动读取前序步骤输出
- 可锁定输出值：重新生成时保留用户已确定的关键词
- 多个 LLM 角色（默认心理咨询师 + 职业规划师，Web UI 可 CRUD 扩展）
- 三栏 UI（左步骤导航 / 中书 / 右步骤详情），步骤卡默认折叠

## User Stories

### 阅读

1. As a reader, I want to browse all chapters in a list, so that I can pick where to continue.
2. As a reader, I want to see chapter content with images rendered, so that the reading experience matches the original book.
3. As a reader, I want my last scroll position to be restored when I revisit a chapter, so that I can pick up where I left off.
4. As a reader, I want to select text in the book and create a note from it, so that I can capture inspiration tied to specific passages.
5. As a reader, I want to navigate back to the passage my note was attached to, so that I can review notes in context.
6. As a reader, I want a dedicated notes panel to write free-form reflections, so that I can think beyond text selections.

### 步骤工作流

7. As a reader, I want to see all steps of a chapter in a left navigation, so that I have a clear sense of progress.
8. As a reader, I want each step card to show its status (draft / saved / submitted), so that I can see what's done.
9. As a reader, I want step cards to be collapsed by default, so that the page doesn't feel overwhelming.
10. As a reader, I want to expand a step card on click, so that I can focus on one step at a time.
11. As a reader, I want step cards that reference prior steps to be marked with a 🔗, so that I understand the workflow dependencies.
12. As a reader, I want each step to show its inputs (questions) and outputs (LLM analysis), so that I understand what's expected.
13. As a reader, I want my answers to be saved as a draft only when I click "save draft", so that I control when my work is committed.
14. As a reader, I want to submit my answers explicitly, so that I can lock them in once I'm confident.
15. As a reader, I want to manually trigger LLM analysis, so that I control token usage.
16. As a reader, I want to see which prior step outputs feed into a step's prompt, so that I understand what's being analyzed.

### LLM 输出与编辑

17. As a reader, I want LLM output to render inside the step card, so that output is contextual to inputs.
18. As a reader, I want to edit LLM output (e.g., remove irrelevant keywords), so that I have final say.
19. As a reader, I want to lock specific keyword outputs (🔒), so that re-generating won't lose items I've validated.
20. As a reader, I want "regenerate" to replace only unlocked items, so that my locked items survive.
21. As a reader, I want to add new keywords by hand, so that I can extend the LLM output.
22. As a reader, I want to view raw LLM response separately from parsed output, so that I can debug if parsing fails.
23. As a reader, I want each step to record which role analyzed it (psychologist / career counselor / custom), so that I can see the perspective.
24. As a reader, I want to switch roles per step, so that different steps can use different expertise.

### 角色管理

25. As an admin, I want to view the list of LLM roles, so that I can see available perspectives.
26. As an admin, I want to create a new role with custom name / description / system prompt / model / provider, so that I can add expertise as needed.
27. As an admin, I want to edit an existing role's prompt, so that I can tune its behavior.
28. As an admin, I want to delete a role, so that I can remove unused ones.
29. As an admin, I want to test a role's connectivity before using it in a step, so that I don't waste tokens on broken configs.
30. As an admin, I want to enable/disable a role, so that disabled ones don't appear in step selectors.

## Implementation Decisions

### 模块划分

- **Backend (FastAPI)**
  - `app/routers/book.py` — 章节内容 + 图片
  - `app/routers/notes.py` — 笔记 CRUD（两种类型）
  - `app/routers/steps.py` — 步骤运行 + 输出编辑
  - `app/routers/roles.py` — LLM 角色 CRUD
  - `app/routers/state.py` — 阅读位置
  - `app/services/step_runner.py` — 步骤执行引擎（LLM + 解析；jinja2 模板已弃用，由 `app/runtime` 取代）
  - `app/services/prompt_renderer.py` — 模板变量渲染（legacy，jinja2 弃用后不再使用）
  - `app/services/llm_client.py` — LLM 调用封装（复用 ai-agent-book `security/providers.py`）
  - `app/data/chapter_configs/` — 每章步骤定义 JSON

- **Frontend（单页原生 JS SPA，非框架）**
  - `index.html`（仓库根目录，约 1516 行，无构建步骤）：章节网格 + 阅读双/三栏 + 右侧 tab 面板（摘要/对话/步骤/笔记）+ 题库 + 浮动角色头像
  - 三栏/双栏由 `GET /api/book/chapters/{id}` 的 `has_steps` 切换（有 active chapter_config → 三栏，否则两栏）
  - 已实现 `renderStepOutput`（按 output 字段名分支渲染，待补 `groups`/`conversions` 分支）；API base 已改为同源 `location.origin`（默认），支持 `?api=` 或 `window.API_BASE` 覆盖；后端在 `/` 以 `FileResponse` 直接托管前端（M3 已落地）
  - 注：原 Next.js 组件拆分方案未落地，本重构以单文件 SPA 为准（详见 `llm_prompt_design/docs/站点重构与开发计划.md` §2.1）

### 数据模型（SQLite）

来自 plan。关键表：
- `book_notes` — 笔记（type: selection | standalone）
- `llm_roles` — LLM 角色（name, system_prompt, provider, model, temperature, max_tokens, enabled）
- `step_runs` — 步骤运行（user_answers JSON, referenced_outputs JSON, role_id, rendered_prompt, llm_response, parsed_output JSON, status）
- `chapter_configs` — 章节步骤定义（version, config_json, active）；`config_json` 现承载新 `exercises[]` schema（见 §JSON Schema）
- `learner_profiles` — 跨章压缩学习者档案（user_id, profile_json, updated_at）；字段键见 `llm_prompt_design/config/schema` 的 `learner_profile` 段（work_purpose / talents / likes / values / misconceptions_cleared …），≤800 token 压缩存档，按 user_id 隔离
- `conversation_summaries` — 长程对话回填摘要（id, chapter_id, user_id, summary_json, turn_from, turn_to, created_at）；建表但实现延迟到 M5 后
- `reading_state` — 阅读位置（chapter_id, last_step_id, scroll_position）

新增约束：
- `parsed_output` 中的列表元素可包含 `locked: bool`（用于 editable_list）
- `step_runs.status ∈ {draft, saved, submitted, failed}`
- 锁定元素不可通过 `DELETE` API 删除，只能通过 `PUT` 修改 lock 状态

### API 契约（关键）

```
GET    /api/book/chapters
GET    /api/book/chapters/{id}
GET    /api/book/chapters/{id}/content       # md with image paths rewritten
GET    /api/book/chapters/{id}/state
PUT    /api/book/state

GET    /api/notes?chapter_id=X
POST   /api/notes
PUT    /api/notes/{id}
DELETE /api/notes/{id}

GET    /api/roles
POST   /api/roles
PUT    /api/roles/{id}
DELETE /api/roles/{id}
POST   /api/roles/{id}/test

GET    /api/chapters/{cid}/steps/{sid}
POST   /api/chapters/{cid}/steps/{sid}/draft
POST   /api/chapters/{cid}/steps/{sid}/run
PUT    /api/chapters/{cid}/steps/{sid}/output
POST   /api/chapters/{cid}/steps/{sid}/submit
```

### JSON Schema：章节任务配置（`exercises[]`，非 legacy `steps[]`）

> 权威 schema：`llm_prompt_design/config/schema/chapter_task_config.schema.json`。以下为精简示例；jinja2 `prompt_template` / `output_schema` 已废弃。

```jsonc
{
  "chapter_id": "ch04",
  "chapter_title": "找到指引人生的指南针：重要的事",
  "md_source": "chapter_md/第四章-...md",
  "core_concepts": [ "..." ],
  "guiding_questions": [ "..." ],
  "exercises": [
    {
      "step_id": "step-1",
      "name": "回答5个问题，找出价值观关键词",
      "method": "书中精选5问唤醒价值观线索",
      "instruction": "逐题长文作答 5 问",
      "user_action": "用户逐题作答；LLM 只映照与归纳，不做判断",
      "llm_role": "assist",
      "references": [],
      "output_fields": [
        { "name": "top_values", "type": "editable_list", "lockable": true },
        { "name": "commentary", "type": "markdown" }
      ],
      "few_shot_examples": [ { "user": "...", "assistant": "..." } ]
    },
    {
      "step_id": "step-2",
      "references": [ { "from_exercise": "step-1", "fields": ["top_values"] } ],
      "name": "形成价值观思维导图",
      "output_fields": [ { "name": "groups", "type": "editable_list", "lockable": true } ]
    }
  ],
  "output_template": "完成五步后请呈现...",
  "few_shot_examples": [ { "user": "...", "assistant": "..." } ],
  "mentor_hooks": { "focus": "...", "references": ["formula"] }
}
```

> 完整字段与类型枚举见 `llm_prompt_design/config/schema/chapter_task_config.schema.json`；8 章配置见 `llm_prompt_design/config/chapters/`。

### 关键机制

- **跨步依赖（references）**：`exercises[].references: [{from_exercise, fields}]` 声明本步需注入哪些**前序已 submitted 步骤**的 `parsed_output` 字段；统一运行时 `app/runtime/agent.build_step_prompt` 据此注入（解决 ch4 五步级联）。jinja2 `{{ step_X.field }}` 已废弃（M0 后 legacy 模板不再使用）。受 ≤3k assembler 护栏约束，仅按需注入、不全量。
- **上下文完整性**：运行声明 `references` 的步骤前，必须确认来源 step 存在最新 `submitted` 输出且声明字段非空；缺失时返回 `409 Step context incomplete`，不得在缺输入时继续生成。跨章字段统一从按 `user_id` 隔离的 `learner_profiles` 读取，章节 compaction 必须合并既有 profile，不得用当前章覆盖前序字段。
- **mentor 档案与桥接**：mentor prompt 始终注入 compact `learner_profiles`；`mentor_hooks.references` 仅决定优先字段，空数组也不能抑制完整档案。步骤桥接入口保存 `step_id`，`/chat/send` 将其传给后端，由后端读取最新 submitted `step_runs.parsed_output` 作为真实上下文。
- **锁定 + 重提取**：editable_list 元素的 `locked: true` 阻止删除 + 在下次 LLM 调用时被传入 prompt（"以下关键词请保留，不要替换"）。
- **步骤状态机**：`draft → saved → submitted`。只有 `submitted` 状态的步骤可被后续步骤引用。
- **章节版本**：`chapter_configs` 表带 version 字段，JSON 修改自动 version+1，方便回溯。

### ch01 练习输出与导师表达约束

- ch01 自检步骤的 `output_fields` 固定为 `commentary`、`misconceptions_cleared`、`external_voices`。`commentary` 是基于本章正文、绑定用户勾选和外部声音的逐条分析，不是泛化章节摘要，也不能只复述用户输入；`misconceptions_cleared` 与 `external_voices` 才进入 `learner_profiles`。
- 前端在输入阶段不显示步骤对话入口；仅在 LLM 成功产生 `parsed_output` 后显示「聊聊这一步」。当 `commentary` 已存在时，不再把同一批用户输入重复渲染成第二个分析模块。
- mentor 必须结合 compact profile 与最近提交步骤上下文，用自己的话解释章节原则；禁止“书中说 / 作者说 / 本章写到”等逐字引用式表达，不写整章摘要，不替用户判断。

### 端口与项目布局

- 前端为单文件 `index.html`（仓库根目录，无独立端口），由后端在 `/` 以 `FileResponse` 托管；API base 已改为同源 `location.origin`（M3 已落地）
- 项目根：`platform/`（本仓库根目录下的 `platform/`）
- 复用：ai-agent-book 项目的 `app/security/providers.py`（LLM provider + 加密），已复制进本仓库 `app/security/providers.py`

### 复用策略

- ai-agent-book 的 `providers.py`、`db.py`、`MarkdownReader.tsx` 模式 → **复制** 到本项目（不是 fork），减少耦合
- PDF 提取用 pymupdf（已装 1.28.0），不用 book-to-skill skill（步骤配置我们自己写）
- 不复用 ai-agent-book 的 auth、terminal、annotations 等无关模块

## Testing Decisions

### 测试 seam

API + DB 为主要 seam。前端组件不写单元测试（用 prototype HTML 视觉验证 + M3 端到端走通流程）。

### 测什么

- **API contract tests**：每个端点输入输出字段、错误码
- **DB CRUD tests**：notes、step_runs、roles 的增删改查、约束
- **Step runner 集成测试**（mock LLM）：
  - draft / run / edit / submit 流程
  - 跨步模板变量渲染
  - 锁定元素在重提取时保留
  - LLM 输出 JSON 解析失败时回退 raw
- **Prompt renderer 单元测试**：jinja2 各种变量引用 + 缺失变量报错

### 不测什么

- 前端 UI 组件（prototype 视觉验证代替）
- LLM 输出质量（用户的领域，靠用户判断）
- 性能 / 压测（单用户用不到）

### 测试工具

- Backend: pytest + httpx (async client) + pytest-asyncio
- Mock LLM: monkeypatch `llm_client.call_llm` 返回固定字符串
- DB: 内存 SQLite (`sqlite:///:memory:`)

## Out of Scope

- 多用户支持 / 登录
- 笔记反链图谱（V2）
- 跨章节 profile 聚合（V2）
- ~~章节 5-8 的具体工作流（等 ch4 跑通再做）~~ → 已设计：8 章工作流已在 `llm_prompt_design/config/chapters/chapter_config_chNN.json` 完成，进入重构 M4 实现
- 移动端响应式（只做桌面）
- 性能优化、压测
- 公网部署

## Further Notes

- **Prototype 文件**：`platform/prototype/index.html` — 设计参考源。所有 UI 决策的视觉证据。
- **Plan 文件**：`~/.claude/plans/1-2-d-ai-project-ai-agent-book-obsidian-glowing-moon.md` — 14 项决策 + 风险登记。
- **验证策略**：每个里程碑（M1/M2/M3）后用浏览器手测 + curl 验证 API。
- **变更管理**：JSON chapter_configs 修改需手动 version+1；锁定状态在 parsed_output 中持久化。
- **重启 prototype**：`cd platform/prototype && python3 -m http.server 8080`

## Milestones（重构后对齐 `llm_prompt_design/docs/站点重构与开发计划.md` §4）

- **M0 契约冻结**：7 项架构决策拍板（Option B / references / output_fields 类型化 oneOf）；schema + 8 章 config canonical 化。
- **M1 数据层**：`learner_profiles` / `conversation_summaries` 建表 + 跨章压缩（≤800 token）。
- **M2 配置/seed**：8 章 config + mentor/summary 灌 DB（统一 `seed_chapters.py`）；chapter_id 统一 `ch01..ch08` 迁移。
- **M3 运行时接入**：`chat/summary/steps` 改调 `app/runtime/agent.run_*`，去硬编码 system prompt；`build_step_prompt` 支持 references + ≤3k 护栏。
- **M4 逐章+前端**：8 章 step 跑通、groups/conversions 渲染分支、ch7 上游锁定、mentor/summary 配置驱动。
- **M5 章末桥接卡 B**：回顾卡 + 三种刘老师入口（顶部常驻/步进浮层/章末 CTA）。
- **M6 验收测试**：`test_runtime_step` / `test_compaction` + 现有测试适配新 schema。
---

# Phase A2 + C（2026-08）设计

> 本节是 mockup-v4 验收 + 3 子 agent 审阅后的权威设计。ch5-8 需求确认后追加细节。
> 相关文件：plan `~/.claude/plans/what-want-plan-c-users-deng-claude-plan-cozy-tower.md`、mockup `platform/prototype/mockup-v4.html`（本地原型，不入库）、交接 `HANDOFF.md`（本地交接件，不入库）

## 设计语言（书卷气）

- `--paper:#f6efde / --paper-edge:#ebe1c8 / --paper-light:#faf4e3 / --ink:#2a2620 / --ink-soft:#6b6354 / --accent:#7a4d2b / --accent-bg:#f1e8d2 / --rule:#d9cfb6`
- 中文衬线字体栈：`"Source Han Serif SC","Noto Serif SC","Songti SC","SimSun",serif`
- 纸纹背景（径向渐变 vignette），全局统一样式（**不保留章节 HTML 自带 `<style>`** —— 用户 2026-08 决策）

## 信息架构（单页状态驱动）

```
LANDING (/)                     READING (?chapter=X)
  Hero + 续读卡 + 章节网格         顶部 sticky bar（☰目录/面包屑/前后章）
                                  ├─ 左步骤nav（仅 ch4+ 有 config 时，190px）
                                  ├─ 中正文（章节 HTML）+ 底部"与导师对话" CTA
                                  └─ 右侧 tab 面板（340px）
                                       ch1-3: 摘要|对话|笔记（M2 灌入 exercises 后自动出现"步骤"tab）
                                       ch4+:  摘要|对话|步骤|笔记
```

- 布局判定：`GET /api/book/chapters/{id}` 的 `has_steps`（有 active chapter_config → 3 栏，否则 2 栏）
- "与导师对话"按钮 = 同页面右侧 tab 切到"对话"，正文始终可见
- 右下浮动角色头像：切换默认分析角色（localStorage `ww_default_role`）+ ⚙ prompt 配置入口

## 右侧 tab 面板

| tab | 内容 | 数据源 |
|-----|------|--------|
| 摘要 | 完整摘要 / 核心概念◆ / 关键流程编号 + `⟳ 重新总结` | `GET/POST /api/chapters/{id}/summary[/regenerate]`，DB 缓存 `chapter_summaries` |
| 对话 | 导师"刘老师"多轮，每章独立历史，× 退出回摘要，清空按钮 | `GET/POST/DELETE /api/chapters/{id}/chat`，DB `chapter_chat` |
| 步骤 | 完整 runner（问题/角色select/关键词chip/运行/提交）| `steps.py` 现有 API |
| 笔记 | 选区+独立笔记，点"定位"滚回原文高亮 | `notes.py` 现有 API + `source_anchor` 存 `{offset,len}` |

## 目录下拉（☰）

- 全部卷章列表（当前高亮）+ 本章 h2 锚点
- 点章节 `location='?chapter=X'`；点 h2 `scrollIntoView`；点空白关闭

## 后端新 API（Phase C）

### DB 新表
```sql
chapter_summaries(chapter_id PK, summary_json, updated_at)
chapter_chat(id PK, chapter_id, role CHECK(user|mentor), content, created_at)
questions(id AUTOINC PK, q_order, question, sub_questions JSON, category, created_at)
```
- 题库答案**复用 `book_notes`**：`chapter_id='questions' AND note_type='standalone' AND source_anchor=q_order`（PONYTAIL 免建表）
- 题库源 `chapter_md/问题清单.md`：3 组×~30 题（价值观/才能/热情）+ 3×100 例清单（词表，不入库仅源参考）。解析器用**顺序计数**（OCR 数字不可靠），分类 header 切换，**过滤 markdown 表格行**

### 摘要
- `GET /api/chapters/{id}/summary` → `{summary:{summary,core_concepts[],key_process[]}|null, updated_at}`
- `POST /api/chapters/{id}/summary/regenerate` → 调 LLM（`call_llm(deepseek, json_mode=True)`），喂 MD 前 12000 字，JSON 输出

### 对话
- `GET /api/chapters/{id}/chat`（时间正序）/ `POST /send {content, step_id?}` / `DELETE`（清空）
- system prompt：固定"刘老师·职业规划导师"人格 + 本章 MD + 引导规则（只基于本章/循序渐进/引用用户原话）
- 历史：最近 10 条压平进 user 文本（因 `call_llm` 只接受单 system+user）
- 对话注入按 `user_id` 隔离的 compact `learner_profiles`；从步骤入口进入时，额外注入指定的最新 submitted step output。历史仍按最近 10 条压平进 user 文本。

### 题库
- `GET /api/questions`（可 `?category=`）/ `GET /{q_order}` / `GET /{q_order}/answer` / `POST /{q_order}/answer`

### 续读 + 进度
- `GET /api/book/last-reading` → 最近 reading_state + 章节信息
- `GET /api/book/chapters` 每章加 `has_steps / progress_pct / submitted_steps / total_steps / last_read_at`
- 进度：ch4+ = `COUNT(DISTINCT step_id WHERE submitted)/total`；无 config = null（前端显示已读/未读）

## 已知遗留（审阅发现，待修/待确认）

| 状态 | 项 |
|------|-----|
| ⏳ 待回归 | `book.py get_chapter()` has_steps 别名 bug（ch4 步骤工作流消失）— 疑似已修，需回归确认 |
| 🔴 待修 | 题库解析丢 2 题（88≠90）+ Q88 被 100 例表格污染 |
| ✅ 已补 | `tests/test_notes_api.py` 缺失 — 已补（重构 M6 适配新 schema） |
| 🔴 待修 | chat 同秒消息排序错乱 |
| 🔴 待修 | 前端 step-4 readonly 无排序箭头（用户已定：readonly+箭头，待 M4 实现） |
| ✅ 已设计 | ch5-8 每章工作流 config — 已在 `llm_prompt_design/config/chapters/chapter_config_chNN.json` 完成（8 章全） |
| ⏳ 待确认 | 问题清单是否加"已答 N/90"反馈 + 3×100 例清单入口 |
| ✅ 已实现 | 导师对话读取 compact `learner_profile`；步骤桥接额外注入最新 submitted step output，缺失 step context 不伪造“已加载”状态 |

### M6 上下文完整性与导师收敛补充（2026-08-05）

- ch01 的 `external_voices` 在用户答案和 LLM 输出中按误区编号保存为对象，例如 `{"1":"...","3":"..."}`；不得把多条外部声音合并成一个无编号字符串。
- ch01 `commentary` 必须逐条绑定已勾选误区及其对应声音，完成“声音压力 → 用户卡点 → 本章重构 → 观察/行动”四步；不得只生成章节摘要或复述输入。
- mentor 运行时必须接收当前 active focus、对应声音、本章原则和已提交 step context；导师先回应再提问，同一焦点最多连续追问两轮，用户问行动时先给行动，未明确切换不得自行换焦点。
- 全章节统一上下文原则：章节内 `references` 读取已 submitted 的 `step_runs.parsed_output`，跨章 `mentor_hooks.references` 读取合并后的 `learner_profiles`；缺失 producer、字段或提交状态时必须阻止生成并返回上下文错误。
