# ch05 落地级步骤设计：对「开发终审 V3 设计侧回复」的开发复核（V4）

> 审核日期：2026-08-11  
> 审核范围：仅核对设计侧声明“已同步”的 ch05 最终口径是否已经完整落到运行时 config、最终落地文档、PRD 与 mockup；本文件不修改权威设计，也不进入 ch05 实施。

## 0. 复核结论

V3 的四项产品决策本身已经明确，开发侧认可并将据此实施：

1. step-1 `talents` 为 `{text, locked, source?}`，不含 `rating`；
2. 100 例引用仅写入 `user_answers.reference_strengths`，在 step-2 点击 `/run` 时由后端与已提交的 step-1 `talents` 合并、精确去重并标注来源；
3. 状态机为 `/run → saved → 编辑/评级/锁定 → /submit → submitted`，`/submit` 不调用 LLM；
4. step-2 允许 `rating:""` 的未评级项提交，ch07 仅取 `rating=="◎"` 作为组合原料。

但是，设计侧“已同步”的结论与实际文件仍不完全一致。尤其 `chapter_config_ch05.json` 是运行时 seed 源，若不先修正，前端文案和后端实现仍会被旧口径误导。请先完成下列 P0 的确认与同步；完成后 ch05 即可进入开发。

---

## 1. P0：运行时 config 仍保留已经废弃的「点击即并入 / 提交时合并」数据流

### 1.1 实际冲突

| 来源 | 当前内容 | 与最终拍板的冲突 |
|---|---|---|
| `config/chapters/chapter_config_ch05.json:76` | `reference_strengths` 的 label 仍写“点『引用』即加入你的长处清单 talents”“提交时其项并入 talents” | 最终规则要求：点击引用时**只**写 `reference_strengths`；点击 `/run` 时才由后端合并并生成新的 step-2 `talents` 草稿。 |
| `docs/ch05_落地级步骤设计.md:180` | P1-3 仍写“提交时并入 talents” | 同一文档 `:184` 已写正确的“运行 LLM 时后端合并”规则，形成同文档自相矛盾。 |
| `docs/...开发review_V3_设计侧回复.md:43-71` | 已正式拍板“后端合并” | 与前两处旧表述不一致。 |

### 1.2 请设计侧确认并同步

本项不需要新的产品决策，直接按已拍板的唯一规则修正即可：

- `chapter_config_ch05.json`：将 `reference_strengths.label` 改为不含旧行为的用户可见文案。建议：  
  `从「擅长的事100例清单」引用的长处（已加入本次参考列表；点击「运行 LLM」后会与上一步长处合并分析）`
- `ch05_落地级步骤设计.md:180`：删除或改写 P1-3 中“提交时并入 talents”的旧记录，使其与 `:184` 一致；不要同时保留两种时序作为“历史说明”，避免实施者误读。
- 复核 `config`、PRD、落地文档、mockup 后，全文不再存在“点击引用即加入 talents”“提交时并入 talents”“提交时合并”等旧语义。

### 1.3 开发侧意见

建议 config 的 label 保持用户语言，不暴露 `source`、`parsed_output` 等内部字段；完整的数据流、去重与来源标记应保留在 `instruction` / 落地文档中。这样既避免 UI 误导，也不会让运行时 config 反向诱导错误实现。

---

## 2. P0：`reference_strengths` 的 canonical payload 结构在 config 与 mockup 中不一致

### 2.1 实际冲突

| 来源 | 当前结构 |
|---|---|
| `chapter_config_ch05.json:77-83` | `type:"list_of_items"`，其 item schema 为 `{text: string}`；按平台通用契约应为 `[{"text":"…"}]`。 |
| `platform/prototype/ch05_exercise_mockup.html:367, 528-532` | `referenceStrengths` 是字符串数组，点击引用后直接 `push(t)`，即 `["…", "…"]`。 |

两种 payload 会影响：前端 renderer、`/run` 的 `user_answers`、后端合并去重、保存后的草稿回显和契约测试。若不统一，可能出现前端可选、后端无法按 schema 读取，或再次进入页面时回显失败。

### 2.2 需要设计侧拍板的唯一问题

请明确 `user_answers.reference_strengths` 的 canonical JSON，二选一且全链路统一：

1. **建议方案 A：对象数组**  
   `[{"text":"把复杂问题讲清楚"}, {"text":"让人安心"}]`。  
   与既有 `list_of_items` + `item_schema` 平台配置一致；mockup 改为存对象并按 `.text` 显示。
2. 方案 B：字符串数组  
   `["把复杂问题讲清楚", "让人安心"]`。  
   则 config 不能继续声明 `list_of_items` 的 `{text}` item schema，需改成平台明确支持的字符串列表类型/定义。

### 2.3 开发侧建议

采用**方案 A（对象数组）**。后端可为旧草稿兼容读取字符串数组并规范化，但新的前端、mockup、config、测试和持久化都应只写 canonical 对象数组。该规则还应明确：合并比较使用 `item.text` 经过 trim + 连续空白归一化后的精确值；最终 `parsed_output.talents` 才携带 `source:"100_examples"`。

---

## 3. P0：100 例清单的正式数据载体和交付边界尚未定义

### 3.1 已核验事实

- 最终设计、PRD 与 mockup 均要求提供“擅长的事 100 例清单”抽屉；
- `chapter_config_ch05.json` 目前只定义了用户输入字段 `reference_strengths`，未包含 100 条候选内容、分组、稳定 ID 或数据来源；
- 当前后端已有的 `GET /api/book/chapters/{chapter_id}/value-examples` 仅为 ch04 价值观关键词清单服务；对 ch05 不会返回该章的长处 100 例；
- mockup 使用本地 `EXAMPLES` 字符串数组，不能作为正式运行时数据源。

因此，按当前权威文件无法判断生产前端应从哪里获取这 100 条、如何稳定展示，也无法为“引用”建立可追溯的正式输入。

### 3.2 请设计侧确认

请明确以下契约，并写入最终落地文档与运行时 config：

1. **权威数据源**：100 例是否应随 `chapter_config_ch05.json` 发布（推荐），或由单独受版本控制的题库/资源文件发布；不要只存在 mockup 内。
2. **数据结构**：每项至少应包含稳定 `id` 与展示文本 `text`；若有分类/排序/搜索需求，请同时给出 `category`、`order` 等字段。建议：`{id, text, category?}`。
3. **交付内容**：请提供完整、可直接发布的清单，而不是仅写“100 例”这一需求描述；若书中原文不是 100 条，也请明确最终产品采用的实际数量和来源说明。
4. **前端获取方式**：若清单进入 active config，前端读取已加载的 chapter config 即可；若采用独立资源，请明确 API / 文件路径、版本与空数据降级文案。

### 3.3 开发侧意见

建议采用“**ch05 active config 的 `ui_context.strength_examples` + 每项稳定 ID**”的方式。这样 config reseed 后即可同版本生效，避免再次硬编码前端常量或复制 ch04 专用接口。`reference_strengths` 在用户答案中仍保存 `{text}`，不必把展示 ID 传给 LLM；ID 仅用于 UI 去重、列表 key 和日后资源升级。

---

## 4. P1：草稿保存需求已出现，但持久化行为仍需形成可验收契约

### 4.1 已有要求与缺口

`docs/ch05_落地级步骤设计.md:185` 已提出：step-1 每题有“保存此题草稿”与时间戳，并保留“保存全部草稿”。这与此前用户反馈的“保存后重新进入却看不到输入”问题高度相关，开发侧会按可靠持久化而非仅浏览器临时状态实现。

但当前文档尚未明确以下行为：

- 未点击 `/run` 前，5 个问题的草稿保存到哪里、重新进入页面如何加载；
- step-2 已选择但尚未 `/run` 的 `reference_strengths` 是否同样必须保存并回显；
- 单题保存与全量保存的覆盖规则、保存时间戳的定义和失败提示；
- 保存草稿是否创建不参与下游引用、不写 profile 的 draft run，还是使用既有的独立草稿接口。

### 4.2 请设计侧确认的用户可见规则

无需指定后端表结构，但请确认：

1. step-1 的逐题保存、全量保存均需跨刷新和重新进入页面保留，且显示“上次保存于 ……”；
2. step-2 的 100 例引用在 `/run` 前是否也应同样保留；开发侧建议**应保留**，否则用户选择抽屉项后离开会丢失；
3. 草稿不属于 submitted 输出：不可进入下游 step、导师正式上下文或 profile；
4. 保存失败必须给出明确错误，不得显示“已保存”但实际丢失。

### 4.3 开发侧意见

本项不要求新表或新 profile 字段。开发侧可复用既有 step 数据承载草稿，但必须把 draft 与 `/run` 后的 `saved` 结果、`submitted` 正式结果明确隔离，并增加回归测试覆盖“保存 → 刷新/离开 → 回到本步 → 输入完整恢复”。

---

## 5. 已明确、无需重新讨论的实施契约

以下内容已足以直接进入开发，设计侧无需再次选择：

- step-1 `rating` 不存在；step-2 才有 `rating:"◎" | "〇" | "△" | ""`；
- 五问衍生项与 100 例文本相同，保留五问项，`source:null`；手动新增同样 `source:null`；
- 只对 trim + 连续空白归一化后的文本做精确去重，不做语义合并；
- 重生成时 `preserve_output.talents` 中 `locked:true` 项必须原文本、原位置保留；
- `commentary` 和 `user_manual` 不进入 `profile_json`；step-2 submitted 的 `talents` 覆盖 ch03 的初始 `talents`；
- 导师只读取 ch05 本章所有已 submitted step 输出，并结合 ch04 `work_purpose`；不读取草稿、saved 的未提交 LLM 输出或未运行的用户输入；
- ch07 仅把 `rating=="◎"` 的 ch05 正式 `talents` 作为组合原料；未评级项保留在 ch05，不进入 ◎ 集合。

---

## 6. 设计侧回复模板

请按以下格式回填，便于开发侧开始实施：

```md
### V4-1 旧数据流残留
- 处理：已更新 config :76 与落地文档 :180；全文检索旧表述结果：0 处。

### V4-2 reference_strengths schema
- 选择：方案 A / 方案 B。
- canonical JSON：……
- 已同步文件：……

### V4-3 100 例清单数据源
- 权威载体：……
- 字段 schema：……
- 完整清单位置：……
- 前端获取方式 / 空态：……

### V4-4 草稿保存
- step-1 草稿：……
- step-2 引用草稿：……
- 草稿与 submitted 的隔离规则：……
- 已同步文件：……
```

设计侧完成 V4 回填并更新权威文件后，开发侧将进行一次最终一致性检查、reseed ch05 active config，然后开始后端、前端、导师上下文与端到端测试实施。