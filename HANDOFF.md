# What Want — 交接文档（跨 session / 跨天接续）

> 每次 session 开始先读本文件。更新于 2026-08-01。
> 本文件是**交接快照**，权威设计看 `platform/SPEC.md`，进度日志看 `platform/PROGRESS.md`。

## 一句话现状

What Want 是一个单用户 local-first 互动阅读平台（FastAPI + SQLite + 单文件静态 HTML 前端），围绕《如何找到想做的事》做"喜欢×擅长×重要"自我认知工作流。M1-M3 + 多章阅读 + Phase A2 前端重构 + Phase C 后端新 API **代码已全部落地**，当前处于**修审阅 bug + 端到端验收**阶段。

## 启动命令

```bash
# 后端
cd /d/AI_Project/What_Want/platform/backend && python3 -u run.py   # :8011
# 前端
cd /d/AI_Project/What_Want/platform/frontend && python3 -m http.server 3011
# 测试
cd /d/AI_Project/What_Want/platform/backend && python3 -m pytest tests/ -v   # 期望 39+ passed
# 题库 seed
cd /d/AI_Project/What_Want/platform/backend && python3 seed_questions.py
# 浏览器
start http://localhost:3011/
```

## 已完成（本轮 2026-08-01）

- **Phase C 后端**：3 新表（chapter_summaries / chapter_chat / questions）+ summary.py + chat.py + questions.py + seed_questions.py + book.py 加 last-reading/progress/has_steps + main.py 注册。**39 pytest 通过**（含 1 个已知红测试见下）。
- **Phase A2 前端**：index.html 整文件重写为 mockup-v4 体系（书卷气 CSS / landing / 单页 reading / 右侧 tab 面板 / 摘要 / 对话 / 目录下拉 / 笔记定位 / 角色浮窗 / 滚动恢复 / 题库页）。**已写完未浏览器验收**。
- mockup-v4（验收过的设计）在 `platform/prototype/mockup-v4.html`。

## 🔴 已知待修 bug（3 子 agent 审阅确认，用户已批"全部修"）

| # | 问题 | 位置 | 修法 |
|---|------|------|------|
| 1 | **ch4 步骤工作流消失**：`get_chapter('04-important').has_steps=False`（list 是 True），前端渲染成 2 栏 3 tab | `backend/app/routers/book.py` `get_chapter()` | 查 `_chapters_with_configs()` 前先 `CH_ID_ALIAS.get(ch["id"], ch["id"])` |
| 2 | **题库 88≠90**：解析器遇分类 header 丢上一类最后一题 | `backend/seed_questions.py` | 分类切换前先把 current append 进去；重 seed |
| 3 | **Q88 被污染**：3×100 例清单 markdown 表格灌进 sub_questions（306 行） | `backend/seed_questions.py` | 加表格行过滤（`^\|`）；重 seed |
| 4 | **`tests/test_notes_api.py` 缺失**（PROGRESS 记录有 4 用例） | `backend/tests/` | 重建（notes CRUD 4 用例） |
| 5 | **chat 同秒消息排序错乱**（红测试 `test_chat_send_persists_both`） | `backend/app/routers/chat.py` | 排序键用 `created_at DESC, rowid DESC` 或加自增 seq |
| 6 | **step-4 排序箭头回归**：新前端 `renderEditableList` 无 ▲▼，且 readonly 下没法排序 | `frontend/index.html` | readonly 下恢复 ▲▼ 上下箭头（用户已定：readonly+纯排序） |

## 其他已确认决策（用户 2026-08-01）

- **章节 HTML 自带样式**：全局统一样式，**不保留**章节 `<head><style>`（renderContent 只取 body 是正确行为）
- **step-4 交互**：readonly（不能增删锁）+ ▲▼ 上下箭头排序
- **git 治理**：允许 `git init`（在 `D:\AI_Project\What_Want` 根）——但上次被中断，未执行
- 绑 0.0.0.0 + 无鉴权：单用户 local 定位，有意为之，接受

## 待用户确认（ch5-8，确认后补进 SPEC）

1. **ch5-8 工作流 config**（用户已确认需要）：每章都需要 config，但可能和 ch4 不同（需读完对应章节后确定）
2. **问题清单答题页 + LLM 分析**（用户已确认需要）：附录的问题清单入库后，需要专门的答题页和基于回答的 LLM 分析功能，**可后做**
3. **导师对话注入已提交步骤答案做个性化引导**（用户已确认需要）：具体注入哪些、注入格式（system prompt 一段 vs 消息列表）需要进一步调研和设计，**后做**
4. 导师人格 prompt 是否需要编辑入口
5. 顶部进度条显示/隐藏（当前 `display:none` 隐藏了）

## 审阅发现的低优先项（不急）

- `book_images.py` 路径穿越（拒绝含 `..` 的 filename）
- chat 用户消息先落库、LLM 失败残留孤儿消息（成功后再落库）
- `call_llm` 加 `messages` 参数去掉对话压平 workaround
- summary/chat 喂 MD 前 12000 字，长章只覆盖前 1/3（接受为当前约束）
- `llm_client.encrypt_key/decrypt_key` 死代码可删
- step-5 模板 `{{ step_4.output.ranked | join('、') }}` 的 dict 渲染债（未决）

## 目录速查

- 内容源：`chapter_html/*.html`（阅读）、`chapter_md/*.md`（LLM 机器读）
- 题库源：`chapter_md/问题清单.md`（3 组×~30 题 + 3×100 例清单）
- 后端：`platform/backend/app/`
- 前端：`platform/frontend/index.html`
- 设计参考：`platform/prototype/mockup-v4.html`
