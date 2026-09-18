# LLM 提示词设计工作总结

> 项目：《如何找到想做的事》交互式自我认知平台
> 整理时间：2026-08-03
> 负责人：WorkBuddy 智能设计助手

---

## 一、背景与目标

平台要让 LLM 充当"自我认知引导教练"，按章节引导用户读完书并完成练习。原方案存在两个问题：

1. **章节 MD 里的图片引用** LLM 读不到图内准确信息（表格、工作表、概念图等），会导致信息缺失。
2. **第四章（已实现 `?chapter=04-important`）的 5 步流程**与书里真实方法有明显偏离，导师（刘老师）对话与用户练习进度完全断裂。

本阶段目标：①把章节知识层准备好（图片文字化）；②设计一套"统一内核 + 章节配置"的 LLM 提示词架构；③修正第四章实现，并设计导师融合方案。

---

## 二、已完成事项

### A. 章节 MD 图片文字化（前置准备，已完成）

- 对 `chapter_md/` 下序 + 第一～八章 + 问题清单全部 MD 做了图片引用处理：
  - **内容图**（表格/工作表/概念图）：读取后用 `【图X-X 文字说明】…` 文字总结替换。
  - **标题/广告图**（封面、推荐徽章、版权页）：直接删除引用。
- 更新前已做备份：`chapter_md.bak_20260802/`（原稿 10 个 MD + images 下 103 张图）。
- 主目录下所有 MD 已无图片引用，LLM 读取时不再漏信息。

### B. LLM 提示词分层架构设计（4 件套，已完成）

设计原则：**不需要每章单独写一套完整 Prompt，也不需要每章一个独立 Agent**——统一一个 Agent 运行时，按 `chapter_id` 动态拼装 `[系统层] + [上下文层] + [任务层] + [示例]`。

| # | 交付物 | 类型 / 位置 | 用途 |
|---|---|---|---|
| 1 | `LLM提示词架构图` | Ardot 云端 · fileId `710630790445620`<br>本地 PNG：`../assets/LLM提示词架构图.png` | 给产品/设计团队对齐整体结构（系统层/上下文层/任务层 → 统一 Agent） |
| 2 | `章节任务配置模板` | Ardot 云端 · fileId `710631995475007`<br>本地 PNG：`../assets/章节任务配置模板.png`<br>本地 JSON：`../config/schema/chapter_task_config.schema.json`、`../config/chapters/chapter_config.ch03.example.json` | 字段定义 + 第三章示例规格页（实质为本地两个 JSON） |
| 3 | `chapter_task_config.schema.json` | 本地 `D:\AI_Project\What_Want\llm_prompt_design\config\schema\` | 给编程 Agent 的字段契约（8 字段统一 Schema） |
| 4 | `LLM运行时数据流图` | Ardot 云端 · fileId `710635388127241` | 给编程 Agent 的实现参考（MD/JSON → Loader 拼装 → LLM → 用户） |

**统一 8 字段 Schema**：`chapter_id`、`chapter_title`、`md_source`、`core_concepts`、`guiding_questions`、`exercises`、`output_template`、`few_shot_examples`。

**8 份章节配置初稿**（均在 `../config/chapters/`）：`chapter_config_ch01.json` ~ `chapter_config_ch08.json`，已通过 JSON 校验，含核心概念、引导问题、输出模板、few-shot 示例。

### C. 第四章实现评审与修正（已完成设计 + 代码修正）

**评审结论**：当前架构（统一系统提示 + 章节配置 + Jinja2 跨步引用 + 锁定/提交状态机）合理，不需推翻；但 5 步配置和 prompt 与书中方法偏离。

**修正内容（`D:\AI_Project\What_Want\platform\backend\seed_ch4.py`，已重写并通过 Python 语法校验）**：

| 步骤 | 原实现 | 修正后（对齐书中方法） |
|---|---|---|
| Step 1 | 回答 5 问，LLM 总结 | 一致（书中 5 问唤醒线索 → 输出映照点评 + 5–10 关键词） |
| Step 2 | 只提取扁平关键词 | **形成价值观思维导图**：≥15 关键词 → 相近归组(4~6) → 概括 umbrella value |
| Step 3 | 对步骤1做元反思 | **改回书中核心**：可控性检验 + 5 Why 转化（以他人为中心 → 以自我为中心） |
| Step 4 | 价值观排序 | 保留，强化金字塔逻辑（底层=基础，顶层=最终目的） |
| Step 5 | 仅用排序+点评推导 | **增加 10 个向他人提供价值的经历** → 取高频价值观 = 工作目的 |

**导师（刘老师）融合设计**：她不是独立 Agent，也不是第四章专属角色，而是统一运行时的"全书级常驻导师模式"。上下文注入 `../config/mentor/mentor_config.json`（人设/苏格拉底策略）、跨章压缩档案 `learner_profile`（≤800 tok）、本章 `mentor_hooks`（聚焦点与引用字段）以及最近 8–12 轮对话历史，使其能跨章引用用户原话、指出一致性或矛盾、做苏格拉底式追问。

- 已新建 `mentor_design_spec.md`：全书级导师设计规范（人设、跨章记忆、上下文装配、token 预算、按章钩子契约）。
- 已新建 `../config/mentor/mentor_config.json`：全书级导师配置（人设、苏格拉底策略、跨章示例对话）。
- 已更新 `../config/chapters/chapter_config_ch04.json`：移除原 `mentor` 段，补 `mentor_hooks` 字段。
- 已更新 ch01–ch08 全部 8 份章节配置：注入 `mentor_hooks`（focus + references）。
- 已更新 `../config/schema/chapter_task_config.schema.json`：增加 `mentor_hooks` 可选字段。
- 已更新 3 张 Ardot 图：架构图补全书级导师层 + 策展说明；运行时数据流图升级 Loader 为"上下文装配器（策展 compact+select）"；第四章融合图改全书贯穿视角。
- 已画对照/融合图：`第四章LLM设计修正与导师融合`（Ardot · fileId `710643309154221`）。

---

## 三、生成物清单（位置 / ID）

**Ardot 云端设计文件（用 URL 打开：`https://ardot.tencent.com/file/<fileId>`）**
- `LLM提示词架构图` → `710630790445620`（已导出本地 PNG：`../assets/LLM提示词架构图.png`）
- `章节任务配置模板` → `710631995475007`（已导出本地 PNG：`../assets/章节任务配置模板.png`；实质内容在本地 JSON：`../config/schema/chapter_task_config.schema.json` + `../config/chapters/chapter_config.ch03.example.json`）
- `LLM运行时数据流图` → `710635388127241`（已导出本地 PNG：`../assets/LLM运行时数据流图.png`）
- `第四章LLM设计修正与导师融合` → `710643309154221`（已导出本地 PNG：`../assets/第四章LLM设计修正与导师融合.png`）

**本地工程文件（`D:\AI_Project\What_Want\llm_prompt_design\`）**
- `config/schema/chapter_task_config.schema.json` — 字段契约（已扩展 `mentor_hooks`）
- `docs/mentor_design_spec.md` — 全书级导师设计规范
- `config/mentor/mentor_config.json` — 全书级导师配置
- `config/chapters/chapter_config_ch01.json` ~ `chapter_config_ch08.json` — 8 章配置初稿（均含 `mentor_hooks`）
- `config/chapters/chapter_config_ch04.json` — 已按书里方法 + 全书级导师钩子更新

**本地后端代码（已改写，仍在 platform 仓库内）**
- `D:\AI_Project\What_Want\platform\backend\seed_ch4.py` — 第四章 5 步配置（需重跑生效）

---

## 四、后续需要做什么

**工程侧（交给编程 Agent 或你自己）**
1. **重跑 seed**：`cd D:\AI_Project\What_Want\platform\backend && python seed_ch4.py`，让新第四章配置写入 DB（每次跑自动升版本，旧版 `active=0`）。
2. **前端改造**：`renderStepOutput` 需支持新结构 `groups[]`（umbrella + keywords + locked）以及 `conversions[]`（可控性检验 + 5Why 链），避免 Step2/Step3 退化成裸 JSON。
3. **`chat.py` 导师融合（尚未写代码）**：扩展为读取 `learner_profiles` + 应用 `mentor_hooks` + 装载最近 8–12 轮历史，实现刘老师全书级苏格拉底对话。设计已就绪，代码待写。
4. **学习者档案存储与压缩任务（尚未写代码）**：新建 `learner_profiles` 表与 compaction 任务（step 提交或计数触发廉价 LLM 压缩）。设计已就绪，代码待写。
5. **验证**：本地起服务，走一遍第四章 5 步，确认 Step2 分组、Step3 5 Why、Step5 经历→目的 的链路通顺。

**设计/内容侧（可继续迭代）**
6. **其他 7 章（ch01–ch03, ch05–ch08）**：目前配置是初稿，引导问题按方法论推断，需你审一遍是否贴合各章实际练习。
7. **是否补 `序(ch00)` 配置**：序言偏开场动机，与正文章节性质不同，待定。
8. **统一拼装 Loader**：目前各章 prompt 由 `seed_ch4.py` 内的 template 直接拼，尚未抽象成"系统层 + MD + JSON"的统一 Loader（架构图里画的是目标态，代码侧可进一步解耦）。
9. **各章摘要生成 LLM Agent**：目前各章"摘要生成"也是常驻全书的 LLM 能力，但疑似写死在 `summary.py` / `chat.py` 路由中。需确认是否像 mentor 一样提升为全书级、纳入"统一 Agent 运行时 + 配置驱动"架构，而非硬编码（见 `mentor_design_spec.md` 的同类思路）。

---

## 五、怎么用这些生成物

| 角色 | 用什么 | 怎么用 |
|---|---|---|
| **你 / 产品 / 设计** | 4 张 Ardot 图 | 用 fileId URL 打开，审阅整体结构、字段契约、第四章修正方向，对齐认知 |
| **编程 Agent** | `../config/` 下的 schema + 8 份 JSON + `../assets/` 下的数据流图 | 照 schema 写 Loader：按 `chapter_id` 读对应 JSON + 章节 MD → 拼成纯文本 prompt → 发给 LLM。LLM 不直接读文件，只消费拼好的文本 |
| **运行时** | `../config/chapters/chapter_config_chNN.json` + `../config/mentor/mentor_config.json` + 各章 `.md` | 作为真实数据，由 Loader 在应用侧读取注入 |
| **第四章落地** | `D:\AI_Project\What_Want\platform\backend\seed_ch4.py`（已修正） | 重跑脚本写入 DB；再补前端 `groups[]` 渲染与 `chat.py` 导师融合 |

**关键认知**：Ardot 图是"方案蓝图"（不参与运行）；JSON 是"数据契约 + 运行时数据"；`seed_ch4.py` 是第四章的具体实现种子。三者分工明确，LLM 只在最末端看到拼好的 prompt。

---

## 附：本次未改动的部分（供核对）

- 前端 `index.html`：未改动。
- `steps.py` / `prompt_renderer.py` / `step_runner.py`：只读未改（新 prompt 模板变量名已核对可正确引用）。
- `chat.py`：仅做了设计规划，未写代码。
- `DEFAULT_ROLES`（psychologist / career_counselor 双角色）：保留原设计，未动。
- 8 份 `chapter_config_ch*.json` 与 `chapter_task_config.schema.json`：已更新。
- 新增 `mentor_design_spec.md` 与 `mentor_config.json`：设计规格与配置已就绪。
