# What Want — 进度报告 + 明日计划

> 更新于 2026-07-31（day 4）
> 状态：M1+M2+M3 全部代码完成 + 20 个单元/集成测试通过 + 真实 DeepSeek 端到端跑通 + DB schema 修正 + provider 单一数据源 + 角色管理 UI + 步骤卡内 role 切换
> 测试：`cd platform/backend && python3 -m pytest tests/ -v` → **20 passed**
> 端到端 smoke：`cd platform/backend && bash scripts/smoke.sh` → 5 端点 + 1 LLM 真实调用全通
> 端到端 LLM 跑通：step-1 返回 359 字 commentary + 5 个 top_values（status=saved）

---

## ✅ 增量进展（day 2）

### A. 全章 PDF 提取 (39 页 → 10.6 MB)
- 写 `extract.py` / `lib_drawings.py` / `verify.py` / `compare.py` 完整技能包
- 装 `pymupdf 1.28.0`
- 跑通第 4 章 p95-133 批量提取，4.4 秒
- 验证脚本：2 空白页（p105/108） + 39 内容页

### A.1 PDF 提取 v2 优化（基于用户反馈）
**问题**：Type3 字体被渲染为矢量路径，导致 drawings 图像**重复**了 text 内容
**迭代**：
1. **v1**：drawings 渲染为图 + text 也渲染 → 重复
2. **v2**：仅渲染小"装饰性"drawings，过滤掉被覆盖的 text
3. **v3**（当前）：**text-always** — 默认渲染文字，drawings 不渲染；raster image（图示）按 Y 坐标穿插 → 文字可选中 + 图示位置正确

**当前效果**（实测）：
- 13 张真实图示（按 PDF 中的 Y 位置）
- 434 段文字（全部可选中）
- 蓝色标题 (h1/h2) + 蓝色 span 高亮保留
- 装饰性矢量（蓝色横条等）放弃以避免重复

### B. M2 笔记功能 ✅
- 后端：`POST/GET/PUT/DELETE /api/notes` 支持两种类型（selection / standalone）
- 前端：选中文字弹笔记框 + Tab 切换独立笔记面板
- 修复：循环 import（从 `app.routers` 改为直接 `from app.routers.X import router`）

### C. M3 步骤执行引擎 ✅
- 后端：roles CRUD + steps 5 个端点（draft/run/output/submit/config）
- 服务：`prompt_renderer.py`（Jinja2）+ `step_runner.py`（编排）+ `llm_client.py`（OpenAI 协议）
- 第 4 章配置：`seed_ch4.py` 写入 5 个 step + 2 个默认角色（心理咨询师 + 职业规划师）
- 前端：动态加载步骤配置，按 schema 渲染表单 + LLM 输出
- 修复：JS 引号转义（用 data-act 属性替代内联 onclick）

### D. (skip，没有"阅读对比 + 标记"工具)

---

## ✅ Day 4 增量（2026-07-31，code review + 续开发）

### E. DB schema 修正
- **问题（PROGRESS 未提）**：`chapter_configs` 主键 `PRIMARY KEY(chapter_id)` 与 seed 的 `version+1` 写入冲突；`step_runs` 缺 `error` 列导致解析失败无法持久化
- **修法**：复合主键 `(chapter_id, version)` + `error TEXT` + idempotent 迁移（保留旧数据）
- **测试**：`tests/test_db_schema.py`（2 cases）

### F. provider 单一数据源
- **问题（PROGRESS 未提）**：`llm_client.PROVIDERS` 与复用的 `security/providers.py`（`minimax` vs `minnimax`）两份 provider 列表
- **修法**：删 llm_client 自己的 dict，全部走 `resolve_provider()` 单一源
- **测试**：`tests/test_llm_client.py`（3 cases 覆盖 6 个 provider）

### G. step_runner 错误持久化
- **问题**：JSON 解析失败时抛异常，DB 不写 run 记录
- **修法**：解析失败 → `status='failed'` + `error TEXT` 写库，调用方拿到 `status='failed'` 而不是异常
- **测试**：`tests/test_step_runner.py`（2 cases）

### H. 后端测试覆盖
- 新增 `tests/conftest.py` + 5 个测试文件 / **20 个测试全部通过**
- `test_db_schema.py` (2) · `test_llm_client.py` (3) · `test_step_runner.py` (2) · `test_notes_api.py` (4) · `test_roles_api.py` (2) · `test_prompt_renderer.py` (5) · `test_book_api.py` (6)
- 同时修复一个 bug：`get_chapter_content` 走 styled 路径时未校验 chapter_id → 未知章节也返回 200

### I. 前端角色管理 UI（PROGRESS 漏写）
- 右侧 Tab 列表从 `[步骤, 笔记]` → `[步骤, 笔记, 角色]`
- 角色 CRUD：list / new / edit / delete 全部用现有 `/api/roles` 后端
- 步骤卡内 role select：从写死 `step.llm_op.role_id` 改为读 select 当前值

### J. smoke 脚本 + 端到端真跑
- `scripts/smoke.sh` — 启 backend → curl 5 端点 + 1 LLM 真实调用 → kill
- 端到端验证：DEEPSEEK_API_KEY（35 字符）有效，`deepseek-chat` 模型可用，step-1 返回 359 字 commentary + 5 个价值观关键词

---

## 🔄 当前服务（运行时）

| 端口 | 服务 | 状态 |
|------|------|------|
| 8011 | 后端 FastAPI | 手动启（`python3 -u run.py`） |
| 3011 | 前端 | 手动启（`python3 -m http.server 3011`） |

> PROGRESS day 2 说"前后端当前已跑"是过时的；现在按"按需启停"。

---

## ⏭️ 接下来

### 1. 关键词锁定 UI 完整端到端
- 前端 `regenKw` 已传 `preserve_output`，但浏览器手测未跑（`/api/chapters/.../run` 端到端未走通 step-2/step-4）
- 建议：用 seed_ch4 已有的 5 步数据，按用户场景（锁定 1 个 → 重提取 → 检查保留）跑一次

### 2. 跨步引用 step-1 → step-2 → step-4 → step-5
- 后端 Jinja2 模板已支持 `{{ step_1.output.commentary }}` 等
- 端到端未跑：未在 step-1 submitted 后实际跑 step-2 看关键词模板是否带 commentary 进去

### 3. 步骤 5 的 `{{ step_4.output.ranked | join('、') }}` join 行为
- Jinja2 filter `join` 在 `prompt_renderer.py` 用的是 StrictUndefined，可能让 array → list 转换失败；待 step-4 跑通后验证

### 4. 其他章节（ch5-8）
- v2 任务，等 ch4 step-1→5 全跑通再做

---

## 📂 文件清单（增量部分）

### Skills 目录
- `D:\AI_Project\What_Want\platform\.claude\skills\pdf-styled-extract\`
  - `SKILL.md` — 描述 + 工作流
  - `extract.py` — 主提取器（含 raster images + Y 坐标排序）
  - `lib_drawings.py` — drawing 分类（默认 skip_all_text=False）
  - `verify.py` — sanity check
  - `compare.py` — 生成对比页
  - `README.md` — 使用说明

### 后端（M3 新增 + Day 4 修）
- `D:\AI_Project\What_Want\platform\backend\app\routers\roles.py`
- `D:\AI_Project\What_Want\platform\backend\app\routers\steps.py`
- `D:\AI_Project\What_Want\platform\backend\app\services\prompt_renderer.py`
- `D:\AI_Project\What_Want\platform\backend\app\services\step_runner.py`  ← 错误持久化
- `D:\AI_Project\What_Want\platform\backend\app\services\llm_client.py`  ← 单一 provider
- `D:\AI_Project\What_Want\platform\backend\app\db.py`  ← 复合 PK + 迁移
- `D:\AI_Project\What_Want\platform\backend\app\routers\book.py`  ← 404 校验
- `D:\AI_Project\What_Want\platform\backend\seed_ch4.py`
- `D:\AI_Project\What_Want\platform\backend\scripts\smoke.sh`  ← 端到端

### 后端测试（Day 4 新增）
- `D:\AI_Project\What_Want\platform\backend\tests\__init__.py`
- `D:\AI_Project\What_Want\platform\backend\tests\conftest.py`
- `D:\AI_Project\What_Want\platform\backend\tests\test_db_schema.py`
- `D:\AI_Project\What_Want\platform\backend\tests\test_llm_client.py`
- `D:\AI_Project\What_Want\platform\backend\tests\test_step_runner.py`
- `D:\AI_Project\What_Want\platform\backend\tests\test_notes_api.py`
- `D:\AI_Project\What_Want\platform\backend\tests\test_roles_api.py`
- `D:\AI_Project\What_Want\platform\backend\tests\test_prompt_renderer.py`
- `D:\AI_Project\What_Want\platform\backend\tests\test_book_api.py`

### Frontend（Day 4 加角色 Tab + 步骤卡 role select）
- `D:\AI_Project\What_Want\platform\frontend\index.html`  ← Tab 列表 + loadRoles/newRole/editRole/delRole + 步骤卡 role select

### 数据
- 第 4 章 markdown：`book/chapters_md_styled/styled_p{95-133}.html`
- 第 4 章图示：`book/chapters_md_styled/images/page{N}_fig{i}.png`
- DB：`data/ww.db`（5 张表 + chapter_configs 复合 PK + step_runs.error 列）
- 默认角色：心理咨询师 + 职业规划师（deepseek-chat）
- 端到端证据：1 条 step-1 run（status=saved, commentary 359字, top_values 5 个）

---

## 🐛 已知问题

### 已修复
1. **PDF 重复渲染** — text+drawings 双渲染 → v3 默认 text-only
2. **图示位置错误**（图全部在末尾）→ Y 坐标排序穿插
3. **路由循环 import** → 直接子模块导入
4. **JS 引号转义** → data-act 属性
5. **chapter_configs 主键冲突** → 复合 PK + 迁移
6. **step_runs 缺 error 列** → schema 加列 + ALTER 兜底
7. **llm_client.PROVIDERS 与 security/providers 不一致** → 删 llm_client 自己的 dict
8. **JSON 解析失败不写库** → try/except + status='failed'
9. **get_chapter_content 未知章节返回 200** → 加 CHAPTERS 校验

### 进行中
- 关键词锁定 UI 端到端（regenKw 已有 + 后端 merge_with_locked 已实现，待浏览器手测）
- 跨步引用端到端 step-1→2→4→5（后端模板就绪，待按场景跑）

### 设计层面（已决策）
- 牺牲矢量装饰条（保留文字可选中 + 真实图示）
- 单用户、local、无 auth
- LLM 角色可扩展，2 个默认已 seed

---

## 🎯 启动命令

```bash
# 后端
cd /d/AI_Project/What_Want/platform/backend && python3 -u run.py

# 前端
cd /d/AI_Project/What_Want/platform/frontend && python3 -m http.server 3011

# 浏览器
start http://localhost:3011/?chapter=04-important

# 测试
cd /d/AI_Project/What_Want/platform/backend && python3 -m pytest tests/ -v

# Smoke (含真实 LLM，需 DEEPSEEK_API_KEY)
cd /d/AI_Project/What_Want/platform/backend && bash scripts/smoke.sh
```

---

## 💡 关键技术教训

1. **Type3 字体 PDF** — 文字提取出来是黑色，但视觉是蓝色（颜色由矢量路径提供）；不要试图从 text 提取颜色，要靠 drawings 或 CSS 模拟
2. **drawings 双渲染陷阱** — 矢量图像可能包含完整文字，必须用 Y 坐标排序区分先后
3. **Python 包导入路径** — `app.routers.X` 比 `from app.routers import X` 更安全（避免循环）
4. **HTML 内联 onclick 的引号** — 用 `data-act` 属性 + 事件委托，不要拼接字符串
5. **SQLite 复合 PK 与 version+1 写入** — 单列 PK 会让多次 seed 撞主键；复合 PK 让版本成为表内自变量
6. **SQLite migration 必须幂等** — 旧 DB 已用新 schema 跑过时，旧的 `__old` 残表要 DROP IF EXISTS，否则 INSERT 会撞主键
7. **pytest-asyncio + module reload** — `reload()` 必须在 fixture 体外先 import，否则 `import app` 在函数内会触发 UnboundLocalError
8. **CSS block layout + 继承 line-height** — 块级子元素继承父元素的 `line-height`，会把 text-glyph 的 leading 算进 box height，撑出 ~20px 假行间距。**修复**：父容器用 `display: flex; flex-direction: column`，flex 按内容高度测盒子不受影响。`(platform/frontend/index.html .step-runner .llm-out)`
9. **CSS Grid `align-content: normal` 在固定行高下不会拉伸** — 但 `display: grid` 的容器如果有 `line-height` 继承，子元素网格项会撑高。改 flex 列布局后立即恢复正常

---

## ✅ 增量进展（day 5 — 2026-08-02，前端步骤面板 UI 精修）

### 触发的用户反馈（按时间顺序）
1. **步骤面板 UI 回退** — 用户截图显示步骤卡片样式回退、点 textarea 输入框会折叠、UI 太丑字体过大
2. **关键词 chip 点击 🔒/× 无效** — 用户反馈 step-2 点击 chip 没任何反应，无法锁定/解锁
3. **关键词窗口空白太多** — 用户指出 label 和 chip 之间、chip 和按钮之间有大块空白
4. **2 列没对齐 / 圆圈编号太丑** — 用户反馈 chip 在 flex-wrap 下两列不对齐，圆形 rank 编号难看
5. **chip 上下空间太多** — 用户反馈 chip 网格垂直方向空旷
6. **关键词 panel 层次感调整（明天）** — 用户反馈整个 panel 一种背景没层次、保存修改按钮突兀要放到底部、4 步统一黄色需调整

### 已完成的 commit

| Commit | 主题 | 关键改动 |
|--------|------|---------|
| `babfb08` | fix(steps): restore card-style step UI + stop click-input from folding body | 把 `expandStep` 移到 `.ttl` div（原来挂在 `.st-card` 上导致 textarea 点击冒泡触发折叠）；把 stepBody 内容用 `<div class="step-runner">` 包裹（原来没包裹，`.step-runner .q / .chip / .actions` 全部 CSS 不生效） |
| `a1eb46c` | polish(steps): textarea height, role spacing, nav font, chip redesign + lock-click fix | chip-click bug：把 `toggleChipLock` 挂到整个 chip（除 ×），🔒 退化为视觉指示器；textarea min-height 48 → 92px；role-line 间距 8 → 16px；左步骤 nav 字体 serif → sans-serif；chip 加 hover、🔒×× 重设计 |
| `64043d8` | polish(chips): replace circle rank badges + grid 2-col alignment + tighter chrome | rank 圆形徽章 → 朴素 tabular-nums 文字 + 左侧 accent 书脊；chip-row flex-wrap → CSS Grid `1fr 1fr` 真两列对齐；llm-out padding + chip-row margin + chip padding 全部收紧 |
| `0939b34` | polish(chips): shorten labels to 1 line + tighten vertical chrome | label 文案缩短让单行显示；actions margin-top 10 → 10；chip-row margin 4x2 → 4x0 |
| `156512f` | polish(chips): fix 42px mystery gap via flex-column on .llm-out | **根因**：`.llm-out { display: block }` + 子元素继承 `line-height: 1.4` 导致块级盒子被 leading 撑高 42px（上下对称）。**修复**：`.llm-out { display: flex; flex-direction: column }`。额外收紧 padding/margin |

### Playwright 验证（每次 commit 后都跑过）
- ✅ Step-2 chip 点击文本区能切换 locked / unlocked（class toggle + PUT /output 200）
- ✅ 5×2 chip grid 两列严格对齐（左列 1/3/5/7/9，右列 2/4/6/8/10）
- ✅ 步骤 nav 用 sans-serif 后文字清晰可读
- ✅ llm-out 高度 345 → 259px（-86px），label→chip 间隙 50 → 4px，chip→按钮 52 → 6px

### 设计语言备忘
- **书卷气**：paper #f6efde / ink #2a2620 / accent #7a4d2b / paper-edge 米色 / paper-light 浅米
- **字体**：正文 + 标题 serif（Source Han Serif / Songti），UI 控件 sans-serif（PingFang SC / 微软雅黑）
- **已接受的 hook findings**（book-aesthetic 有意保留）：
  - `.chapter-content h2` 的 3px accent 左边线 — 章节正文 h2 视觉锚点
  - `.st-card` 的 3px paper-edge 左边线 — paper-edge 不是 accent 色，hook 误报
  - `.note-card .src` 的 2px accent 左边线 — 引文视觉标记

---

## 📋 明日 Todo List（day 6 — 2026-08-03）

### 高优先级 — 步骤面板层次感重构（用户当前请求）
- [ ] **`.llm-out` 视觉层次**：目前 accent-bg（黄色）整片铺底，和 step card 背景没区分 → 改用 paper-light bg + 细 border，让 chip / commentary 区域作为 card 浮在 step card 上
- [ ] **`保存修改` 按钮位置**：当前在 `.llm-out` 内部（黄色框中），突兀 → 移到 `.llm-out` 外部、跟 `角色 select` / `重新提取` / `提交` 同一行（统一 action 区）
- [ ] **4 步统一层次**：step 1/2/3/4 的内容区域都改成一致的"card-on-card"视觉（paper-light + 细 border + 内部 padding），避免出现一片黄、一片白的混乱
- [ ] **`.st-card` 折叠态**：当前是 paper-edge 左边线 → 考虑去掉左边线，单纯用 border + padding，让 step card 更克制
- [ ] **`.llm-out` 内的 label 和 chip 之间**：视觉再加点区分（label 上方加细分割线 / 改 label 颜色 / 标签做成 chip 样式）

### 中优先级 — 收尾 + 测试
- [ ] **重构后的步骤面板 Playwright 验证**：所有 4 步展开，截图比对层次感
- [ ] **45+ pytest 仍通过**：跑一遍 `pytest tests/ -v` 确保没破坏后端
- [ ] **impeccable hook 跑一次**：`/impeccable audit platform/frontend/index.html` 看新设计是否还有 side-tab / overused-font 等 finding

### 低优先级 — 之前一直 pending
- [ ] **ch5-8 章节内容理解 + workflow config**（用户确认需要，详情一章一章渗透）
- [ ] **问题清单答题页 + LLM 分析**（用户确认需要）
- [ ] **导师对话注入已提交步骤答案做个性化引导**（用户确认需要）

### 不动（hook 误报 / 用户已接受）
- ❌ `.chapter-content h2 { border-left: 3px solid var(--accent) }` — 保留
- ❌ `.st-card { border-left: 3px solid var(--paper-edge) }` — paper-edge 不是 accent，保留
- ❌ `.note-card .src { border-left: 2px solid var(--accent) }` — 保留

---

## 关键决策回顾（来自 grill-me）

| # | 决策 | 当前实现 |
|---|------|---------|
| 1-2 | 单用户 / 三栏 / 阅读 + 报告 + 参考 | ✅ |
| 3 | 每天使用 | ✅ 状态持久化 |
| 4-5 | 草稿 + 提交 + 两种笔记 | ✅ |
| 6-8 | 两角色 + Web UI + 灵活 | ✅ seed 2 角色 + UI 已补 |
| 9-11 | 灵活 step + jinja2 模板变量 | ✅ |
| 12-14 | C 三栏 + 默认折叠 + 锁定机制 | ✅ UI 已实现，锁定 UI 端到端已跑（day 5） |
| 15 | 步骤面板 UI 精修（day 5） | ✅ 5 个 commit 落地 |
| 16 | 步骤面板层次感重构（day 6 待做） | 📋 见上方 Todo List |

---

## 关键决策回顾（来自 grill-me）

| # | 决策 | 当前实现 |
|---|------|---------|
| 1-2 | 单用户 / 三栏 / 阅读 + 报告 + 参考 | ✅ |
| 3 | 每天使用 | ✅ 状态持久化 |
| 4-5 | 草稿 + 提交 + 两种笔记 | ✅ |
| 6-8 | 两角色 + Web UI + 灵活 | ✅ seed 2 角色 + UI 已补 |
| 9-11 | 灵活 step + jinja2 模板变量 | ✅ |
| 12-14 | C 三栏 + 默认折叠 + 锁定机制 | ✅ UI 已实现，锁定 UI 端到端未跑 |
