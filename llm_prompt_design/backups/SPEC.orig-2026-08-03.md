# What Want — 交互式自我认知工作流平台 Spec

> 来源：plan `1-2-d-ai-project-ai-agent-book-obsidian-glowing-moon.md` (已批准) + prototype 验证 (`platform/prototype/index.html`)
> 状态：Ready for agent
> 优先级：M1 → M2 → M3（按阶段交付）

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
  - `app/services/step_runner.py` — 步骤执行引擎（jinja2 + LLM + 解析）
  - `app/services/prompt_renderer.py` — 模板变量渲染
  - `app/services/llm_client.py` — LLM 调用封装（复用 ai-agent-book `security/providers.py`）
  - `app/data/chapter_configs/` — 每章步骤定义 JSON

- **Frontend (Next.js)**
  - `app/book/page.tsx` — 章节列表
  - `app/book/[chapter_id]/page.tsx` — 章节阅读页（三栏布局）
  - `components/BookReaderLayout.tsx` — 三栏容器
  - `components/BookMarkdownReader.tsx` — md 渲染 + 选中弹出
  - `components/BookNotesPanel.tsx` — 笔记列表 + 编辑
  - `components/NoteEditor.tsx` — 笔记编辑弹窗
  - `components/StepNav.tsx` — 左步骤导航（含 🔗 标识）
  - `components/StepRunner.tsx` — 步骤卡（折叠/展开 + 输入 + 输出 + 编辑）
  - `components/StepOutputView.tsx` — 按 output_schema 动态渲染输出
  - `components/RoleManager.tsx` — 角色 CRUD UI
  - `lib/api.ts` — 前端 API 客户端

### 数据模型（SQLite）

来自 plan。关键表：
- `book_notes` — 笔记（type: selection | standalone）
- `llm_roles` — LLM 角色（name, system_prompt, provider, model, temperature, max_tokens, enabled）
- `step_runs` — 步骤运行（user_answers JSON, referenced_outputs JSON, role_id, rendered_prompt, llm_response, parsed_output JSON, status）
- `chapter_configs` — 章节步骤定义（version, config_json, active）
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

### JSON Schema：步骤定义

```jsonc
{
  "chapter_id": "04-important",
  "title": "第四章",
  "pdf_pages": [95, 96],
  "content_md_path": "book/chapters_md/04.md",
  "steps": [
    {
      "step_id": "step-1",
      "title": "回答5个问题",
      "description": "请认真思考每个问题",
      "user_input": {
        "questions": [
          { "id": "q1", "text": "你尊敬的人？", "type": "long_text" }
        ]
      },
      "llm_op": {
        "role_id": "psychologist",
        "prompt_template": "请基于：\n{{ step_1.answers }} 分析...",
        "output_schema": {
          "type": "structured",
          "fields": [
            { "name": "commentary", "type": "markdown" }
          ]
        }
      }
    }
  ]
}
```

> 完整 JSON 示例 + prototype 验证片段见 plan 文件与 `platform/prototype/index.html`。

### 关键机制

- **跨步模板变量**：`{{ step_X.field }}` 引用前序步骤输出。PromptRenderer 用 jinja2 渲染。
- **锁定 + 重提取**：editable_list 元素的 `locked: true` 阻止删除 + 在下次 LLM 调用时被传入 prompt（"以下关键词请保留，不要替换"）。
- **步骤状态机**：`draft → saved → submitted`。只有 `submitted` 状态的步骤可被后续步骤引用。
- **章节版本**：`chapter_configs` 表带 version 字段，JSON 修改自动 version+1，方便回溯。

### 端口与项目布局

- 前端 `:3011` / 后端 `:8011`（避开 ai-agent-book 的 3010/8010）
- 项目根：`D:\AI_Project\What_Want\platform\`
- 复用：`D:\AI_Project\ai-agent-book\site\apps\backend\app\security\providers.py` (LLM provider + 加密)

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
- 章节 5-8 的具体工作流（等 ch4 跑通再做）
- 移动端响应式（只做桌面）
- 性能优化、压测
- 公网部署

## Further Notes

- **Prototype 文件**：`platform/prototype/index.html` — 设计参考源。所有 UI 决策的视觉证据。
- **Plan 文件**：`~/.claude/plans/1-2-d-ai-project-ai-agent-book-obsidian-glowing-moon.md` — 14 项决策 + 风险登记。
- **验证策略**：每个里程碑（M1/M2/M3）后用浏览器手测 + curl 验证 API。
- **变更管理**：JSON chapter_configs 修改需手动 version+1；锁定状态在 parsed_output 中持久化。
- **重启 prototype**：`cd platform/prototype && python3 -m http.server 8080`

## Milestones

- **M1**：骨架 + 章节阅读（C 三栏布局）+ 阅读位置。验证：`/book/04-important` 三栏可见。
- **M2**：笔记 CRUD（两种类型）。验证：选中文字能记笔记，独立面板能记笔记。
- **M3**：步骤执行引擎 + LLM 分析 + 角色 CRUD。验证：第 4 章 5 步完整跑通，跨步引用、锁定机制工作。
---

# Phase A2 + C（2026-08）设计

> 本节是 mockup-v4 验收 + 3 子 agent 审阅后的权威设计。ch5-8 需求确认后追加细节。
> 相关文件：plan `~/.claude/plans/what-want-plan-c-users-deng-claude-plan-cozy-tower.md`、mockup `platform/prototype/mockup-v4.html`、交接 `D:\AI_Project\What_Want\HANDOFF.md`

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
                                       ch1-3: 摘要|对话|笔记
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
- `GET /api/chapters/{id}/chat`（时间正序）/ `POST /send {content}` / `DELETE`（清空）
- system prompt：固定"刘老师·职业规划导师"人格 + 本章 MD + 引导规则（只基于本章/循序渐进/引用用户原话）
- 历史：最近 10 条压平进 user 文本（因 `call_llm` 只接受单 system+user）
- **待改进（架构审阅建议）**：给 `call_llm` 加 `messages` 参数去掉压平 workaround；对话注入用户已提交步骤/题库答案（个性化）

### 题库
- `GET /api/questions`（可 `?category=`）/ `GET /{q_order}` / `GET /{q_order}/answer` / `POST /{q_order}/answer`

### 续读 + 进度
- `GET /api/book/last-reading` → 最近 reading_state + 章节信息
- `GET /api/book/chapters` 每章加 `has_steps / progress_pct / submitted_steps / total_steps / last_read_at`
- 进度：ch4+ = `COUNT(DISTINCT step_id WHERE submitted)/total`；无 config = null（前端显示已读/未读）

## 已知遗留（审阅发现，待修/待确认）

| 状态 | 项 |
|------|-----|
| 🔴 待修 | `book.py get_chapter()` has_steps 别名 bug（ch4 步骤工作流消失） |
| 🔴 待修 | 题库解析丢 2 题（88≠90）+ Q88 被 100 例表格污染 |
| 🔴 待修 | `tests/test_notes_api.py` 缺失 |
| 🔴 待修 | chat 同秒消息排序错乱 |
| 🔴 待修 | 前端 step-4 readonly 无排序箭头（用户已定：readonly+箭头） |
| ⏳ 待确认 | ch5-8 每章是否配工作流 config |
| ⏳ 待确认 | 问题清单是否加"已答 N/90"反馈 + 3×100 例清单入口 |
| ⏳ 待确认 | 导师对话是否注入用户步骤/题库答案 |
