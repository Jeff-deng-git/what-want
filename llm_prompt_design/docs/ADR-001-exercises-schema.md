# ADR-001：练习（exercises）运行时契约设计

> 文件：`docs/ADR-001-exercises-schema.md`
> 状态：**已采纳（Accepted）** ｜ 日期：2026-08-03
> 关联：`docs/站点重构与开发计划.md` §3（原 7 项待拍板，现已全部拍板）
> 关联：`config/schema/chapter_task_config.schema.json`（已落地）

## 1. 背景 / 问题

通读 `platform/` 实际代码后发现三个阻断 coding agent 的设计断层：

1. **配置契约不兼容**：现有 `step_runner.py` 消费 legacy `{ steps[].llm_op.prompt_template(jinja2), output_schema }`；新设计是 `{ exercises[] }`。两者必须二选一统一。
2. **ch4 五步级联无 schema 载体**：step‑2 要 step‑1 的 `top_values`，step‑3 要 step‑2 的 `groups`，step‑4 要 step‑2/3，step‑5 要 step‑4。legacy 用 jinja2 `{{ step_X.output }}` 注入，新 `exercises` schema 没有字段声明这种"前序依赖"。
3. **`output_fields` 缺类型/渲染元数据**：前端 `renderStepOutput` 按字段名硬编码分支，没有 `groups`/`conversions` 分支，且分不清"可编辑 chip 列表" vs "只读 markdown" vs "readonly 排序项"。

## 2. 决策（已拍板）

### 2.1 ★ 运行时配置契约：选 **Option B（exercises 原生）**
- 以 `exercises[]` 为运行时契约；重写 `step_runner` 走 `build_step_prompt`（persona + instruction + worksheet + few_shot + 前序输出注入），**彻底去掉 jinja2**。
- 前端 `renderStepBody` / `renderStepOutput` 改为读 `exercises[].output_fields` + 类型元数据。
- 放弃 Option A（seed 期转译保留 jinja2）——它无法真正实现"配置驱动 assembler"，且 few_shot 拼进 jinja2 易碎。

### 2.2 ★ 跨步引用：新增 `exercises[].references`
```json
"references": [
  { "from_exercise": "step-1", "fields": ["top_values"] }
]
```
- `build_step_prompt` 据此从同章**已 submitted** 的 `step_runs.parsed_output` 取前序字段注入 user prompt。
- 简化写法：省略 `fields` 即注入该步全部 output。
- 受 ≤3k assembler 护栏约束：仅按需注入、不全量。

### 2.3 ★ output 字段类型元数据：`output_fields` 升级为 oneOf
```json
"output_fields": [
  { "name": "groups",      "type": "editable_list", "lockable": true },
  { "name": "conversions", "type": "list" },
  { "name": "ranked",      "type": "editable_list", "lockable": true },
  { "name": "commentary",  "type": "markdown" }
]
```
- `type` 枚举：`markdown | text | editable_list | list | number | select | json | table`。
- `readonly`：用户不可编辑（如 step‑4 ranked 的只读项）。
- `lockable`：用户可锁定阻止 LLM 覆盖（如 groups 分组）。
- **向后兼容**：`output_fields` 仍接受纯字符串（等价 `{name, type:unknown}`），已有 ch01‑03/ch05‑08 配置无需立即改写，M0/M2 由 coding agent 批量转对象。

### 2.4 chapter_id 统一为 `ch0N`
- 新配置 `ch01..ch08` 为唯一规范；legacy `04-important` 经一次性迁移 `migrate_chapter_ids.py` 改为 `ch04`，随后删除 `book.py` 的 `CH_ID_ALIAS`。迁移前强制备份 `ww.db`。

### 2.5 user_id 常量
- 单用户本地部署：常量 `DEFAULT_USER_ID = "local"`。`config_loader.load_profile/save_profile`、`agent.run_mentor/run_summary/run_step` 默认取该值；schema 保留 `user_id` 主键以便将来多用户。前端无需改。

### 2.6 前端托管
- **选 (a)**：后端 `main.py` 用 `StaticFiles` 挂载 `frontend/index.html` 到 `:8011/`，前后端同端口同源，消除硬编码 `http://localhost:8011` 跨域问题；API 改相对路径 `/api`。

### 2.7 `conversation_summaries`
- M1 **建表**（成本极低）；**实现延迟到 M5 之后**作为可选增强。M3 的 mentor 先用 `build_mentor_prompt` 截历史兜底。

## 3. 后果 / 影响

- `chapter_config_ch04.json` 已作为 canonical 样例：5 步全部补 `references` 级联 + 类型化 `output_fields`。
- 其余 7 份 config 的 `output_fields` 仍为字符串（schema 兼容），M0 由 coding agent 批量转对象。
- `agent.run_step` / `assembler.build_step_prompt` 必须在 M3 实现，否则级联无法落地。
- 前端 `renderStepOutput` 必须新增 `groups`（umbrella+keywords 卡片组）与 `conversions`（原值→转化值+why_chain 列表）两个分支，并据 `type` 分支渲染 —— 这是 handoff §7.4 的阻塞项，随本 ADR 解除。

## 4. 反面方案（为何不选 A / 不选 jinja2）

- jinja2 `{{ step_X.output }}` 把"跨步数据流"写死在模板字符串里，既不可被审计，也无法受 assembler 护栏约束；本次重构主旨是"配置驱动、不写死 prompt"，A 与之相悖。
- 字符串 `output_fields` 无法表达 `editable_list`/`readonly`/`lockable`，导致前端只能按字段名硬编码 —— 正是当前 `groups`/`conversions` 渲染缺失的根因。
