# 第二章落地级步骤设计：开发 Review

> 文档状态：待设计侧 review / 回复  
> 创建日期：2026-08-06  
> Review 范围：`ch02_落地级步骤设计.md` 与已完成平台能力之间的衔接  
> 说明：本文件**不把新设计稿与历史交接文档的差异本身视为问题**。本文件只检查：新设计是否覆盖当前已完成的 M5.8 输入 schema、通用步骤运行器、LLM 输出编辑/提交、profile 压缩、导师上下文和现有测试基线。

---

## 0. 给设计侧的回复方式

请不要只回复“可以”或“按设计稿做”。请针对每个“待确认”项给出：

1. 最终用户流程；
2. 最终输入 JSON；
3. 最终 LLM 输出 JSON；
4. 用户可编辑、可锁定字段；
5. 保存草稿、运行 LLM、提交、重新运行规则；
6. 上下游字段和缺失数据行为；
7. 是否纳入本期验收。

可以直接填写本文第 8 节的回复表，也可以在每个问题下补充设计结论。

**开发侧原则：**收到设计侧确认后，再同步 config、Prompt、后端、前端和 E2E；在字段契约确认前不猜测实现。

---

## 1. 当前已完成的平台基线

### 1.1 M5.8 已完成能力

当前平台已经具备以下能力，ch02 新设计可以直接复用：

- `input_schema` 驱动结构化输入控件；
- `list_of_items` 开放列表，可动态增加/删除事项；
- 列表项可以包含 `text`、`select` 等子字段；
- `user_answers` 以 JSON 对象保存到 `step_runs.user_answers`；
- 保存草稿不调用 LLM；
- 运行 LLM 后保存 `parsed_output`，状态为 `saved`；
- 用户提交后状态变为 `submitted`；
- `submitted` 的步骤不能继续编辑；
- 重新运行已提交步骤时创建新的 run，不覆盖历史提交记录；
- `learner_profiles` 可从已提交步骤输出中压缩生成；
- 导师对话可以读取已提交步骤上下文和 learner profile；
- 角色可以通过 `step_role_id` 固定显示，避免用户在步骤内误切换角色。

### 1.2 相关实现文件

| 能力 | 当前实现 |
|---|---|
| ch02 输入配置 | `D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch02.json` |
| 结构化输入渲染 | `D:\AI_Project\What_Want\platform\frontend\index.html:1431` |
| 步骤状态与 API | `D:\AI_Project\What_Want\platform\backend\app\routers\steps.py:180` |
| LLM 运行入口 | `D:\AI_Project\What_Want\platform\backend\app\routers\steps.py:222` |
| 输出编辑 API | `D:\AI_Project\What_Want\platform\backend\app\routers\steps.py:279` |
| 提交和锁定 | `D:\AI_Project\What_Want\platform\backend\app\routers\steps.py:339` |
| Prompt 组装 | `D:\AI_Project\What_Want\platform\backend\app\runtime\assembler.py:375` |
| profile 压缩 | `D:\AI_Project\What_Want\platform\backend\app\services\compaction.py:11` |
| M5.8 设计依据 | `D:\AI_Project\What_Want\llm_prompt_design\docs\M5.8_input_schema_角色管理_设计侧修订稿.md:161` |

### 1.3 当前 ch02 canonical config

当前 ch02 已使用一个 exercise：`内外标准对照`，输入为：

```json
{
  "drive_items": [
    {
      "text": "加班做项目",
      "drive": "external"
    },
    {
      "text": "学新东西",
      "drive": "internal"
    }
  ],
  "notes": "周末想写点东西"
}
```

当前输出字段为：

```json
{
  "internal_external_ratio": {
    "external_pct": 60,
    "internal_pct": 40
  },
  "reclaim_item": "最该收回主动权的一件事"
}
```

当前配置文件：`D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch02.json`

---

## 2. 影响总览

| 事项 | 对现有平台影响 | 当前判断 |
|---|---|---|
| 一个 exercise、内部四阶段 | 低 | 可复用当前步骤 runner，但需要补充 UI 状态说明 |
| `list_of_items` 输入 | 低 | M5.8 已支持 |
| 每项增加备注 | 低至中 | 通用 renderer 可扩展 item 字段，但需补 schema 和校验 |
| ratio 系统派生 | 中 | 需要后端生成/校验逻辑和测试 |
| `commentary` 正式输出 | 低至中 | 需要补 `output_fields`、Prompt 契约和测试 |
| `reclaim_item` 文本编辑 | 中 | 后端已有输出编辑 API，前端需要补 text 编辑态 |
| 整步提交锁定 | 低 | 当前运行时已经支持，但设计稿需明确这是整步锁定 |
| ch01 上下文摘要 | 中至高 | 若新增 `external_voices_summary`，需要 producer、profile 和 Prompt 链路 |
| ch02 → ch04 回响 | 中 | 需要正式定义引用字段和 Prompt 规则 |
| 新增数据库表 | 无 | 当前设计不需要新增表或列 |
| 浏览器 E2E | 中 | 需要补完整四阶段和异常态验收 |

---

## 3. 当前设计已经覆盖的部分

以下内容在新设计稿中已经足够明确，开发侧不认为是阻塞项：

### 3.1 章节结构

- ch02 只有一个练习单元；
- 练习单元内部有填写、LLM 分析、用户确认、档案沉淀四个阶段；
- 不新增独立 step；
- 阶段0阅读正文不需要单独落库。

### 3.2 用户输入方向

- 用户列出当前正在投入的事项；
- 每件事项标记为外部驱动或内部驱动；
- 用户可以补充说明；
- 事项范围不局限于工作，可以包含学习、关系、消费等。

### 3.3 LLM角色方向

- 使用心理咨询师 `psychologist`；
- LLM 是辅助者，不是裁判；
- 重点发现用户标注与备注之间的潜在矛盾；
- `reclaim_item` 在用户确认前只能是草稿。

### 3.4 现有数据承载方式

- 原始事项放 `step_runs.user_answers`；
- LLM 输出放 `step_runs.parsed_output`；
- 只有最终提交结果进入 `learner_profiles`；
- 不需要为 ch02 新增表或数据库列。

---

## 4. 需要设计侧补充的关键契约

### 4.1 阶段与平台状态的对应关系

新设计稿写了四个阶段，但没有完全映射到当前平台状态。请确认是否采用以下映射：

| 设计阶段 | 平台状态 | 用户动作 | 是否形成正式上下文 |
|---|---|---|---|
| 阶段1：用户填写 | `draft` | 保存草稿 | 否 |
| 阶段2：LLM分析 | `saved` | 运行 LLM，生成分析草稿 | 否 |
| 阶段3：用户确认 | `saved` → `submitted` | 编辑 `reclaim_item`，点击“确认并保存/提交” | 是 |
| 阶段4：沉淀档案 | `submitted` | 系统 compaction | 是 |

请明确：

- “运行 LLM”是否绝不代表提交；
- “提交/确认并保存”是否是唯一使 ch02 输出进入下游上下文的动作；
- LLM 运行成功后是否必须显示提交按钮；
- 用户未确认 `reclaim_item` 时能否离开页面；
- 提交后是否显示“我们已经了解了你的信息”和“对话”入口；
- 用户点击“重新做本章”时，是否创建新 draft 而不覆盖历史 submitted run。

当前前端已经有运行、提交和提交后完成提示的基础逻辑：`D:\AI_Project\What_Want\platform\frontend\index.html:1540`

### 4.2 `drive_items` 最终输入 schema

当前 M5.8 schema 是：

```json
{
  "drive_items": [
    {
      "text": "写下这件事",
      "drive": "external|internal"
    }
  ],
  "notes": "全局备注"
}
```

新设计稿描述为“事项文本 + 驱动类型 + 备注”，但没有明确备注属于事项还是全局字段。

请确认最终结构：

#### 方案 A：保留全局备注

```json
{
  "drive_items": [
    {
      "id": "item-1",
      "text": "加班做项目",
      "drive": "external"
    }
  ],
  "notes": "最近总体感受"
}
```

#### 方案 B：每件事项独立备注

```json
{
  "drive_items": [
    {
      "id": "item-1",
      "text": "加班做项目",
      "drive": "external",
      "note": "爸妈说稳定体面，但我经常想辞职"
    }
  ],
  "notes": "可选的整体补充"
}
```

开发侧建议采用方案 B，因为 LLM 需要知道哪条备注对应哪件事项；否则多个事项的备注无法稳定绑定。

还请确认：

- 是否需要稳定的 item `id`；
- 最少事项数量是 1 还是 2；
- 最多事项数量是否为 10；
- `text` 和 `drive` 是否必填；
- 是否允许事项重复；
- 是否允许用户在运行 LLM 后修改输入并重新运行；
- 示例事项是否只是 placeholder，还是会被当作真实数据提交。

当前配置是 `min_items: 1`、`max_items: 10`：`D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch02.json:63`

### 4.3 `internal_external_ratio` 的唯一来源

新设计稿前后对 ratio 的来源描述不完全一致。请确认最终采用以下哪一种：

- [ ] 用户自己填写比例；
- [ ] 用户为每件事项填写权重，后端计算；
- [ ] 后端按事项数量计算；
- [ ] 不输出数字比例，只展示外部/内部事项分布；
- [ ] 其他：请说明。

如果采用系统派生，请补充正式算法。例如：

```text
external_pct = external_item_count / total_item_count * 100
internal_pct = internal_item_count / total_item_count * 100
```

并确认最终 JSON：

```json
{
  "internal_external_ratio": {
    "external_pct": 60,
    "internal_pct": 40,
    "method": "item_count"
  }
}
```

还需要确认：

- 两个比例是否必须相加为 100；
- 只有 1 件事项时是否允许生成比例；
- LLM 是否可以看到后端计算结果；
- LLM 是否禁止改写这个数字；
- ratio 是直接由后端写入 `parsed_output`，还是只写入 profile；
- 前端展示为表格、数字还是比例条。

当前后端只做输出类型 warning，不会自行补算 ratio，也不会因为 ratio 缺失阻止提交：`D:\AI_Project\What_Want\platform\backend\app\routers\steps.py:118`

### 4.4 LLM 输出字段契约

设计稿阶段2要求：

```json
{
  "commentary": "整体映照和矛盾分析",
  "internal_external_ratio": {
    "external_pct": 60,
    "internal_pct": 40
  },
  "reclaim_item": "最该收回主动权的一件事"
}
```

请确认三个字段的正式属性：

| 字段 | 类型 | 用户可编辑 | 用户可锁定 | 进入 profile | 备注 |
|---|---|---:|---:|---:|---|
| `commentary` | 待确认 | 否 | 否 | 否 | LLM 分析正文 |
| `internal_external_ratio` | 待确认 | 否 | 否 | 是 | 系统计算还是 LLM 输出 |
| `reclaim_item` | 待确认 | 是 | 是 | 是 | 用户确认后的正式产出 |

目前 canonical config 未声明 `commentary`，只有 `internal_external_ratio` 和 `reclaim_item`：`D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch02.json:25`

请确认：

- `commentary` 是否加入 `output_fields`；
- 类型是 `markdown` 还是 `text`；
- 是否需要按事项逐条分析，还是只给整体分析；
- `commentary` 是否必须引用用户备注；
- LLM 缺少某项输出时能否提交；
- LLM 返回非法 JSON 时是否进入失败状态而不是生成空成功结果。

当前后端的输出解析是 best effort：`D:\AI_Project\What_Want\platform\backend\app\routers\steps.py:105`

---
## 5. `reclaim_item` 编辑与锁定

### 5.1 类型选择

当前 config 定义为 `text`，新设计稿部分内容又将其描述为“一个 editable_list 项目”。请确认最终类型：

- [ ] `text`：用户编辑一整句话；
- [ ] `editable_list`：用户编辑一个只有 1 项的列表；
- [ ] 结构化对象：包含事项 ID、候选文本、理由、状态等字段；
- [ ] 其他：请说明。

开发侧倾向使用 `text`，因为用户实际确认的是一句“我最想收回主动权的事”，不是维护一个列表。

### 5.2 LLM 候选与用户最终确认

请确认是否采用以下语义：

```text
LLM 输出候选
    ↓
用户可以修改 / 拒绝 / 重写
    ↓
用户点击“确认并保存”
    ↓
reclaim_item 成为正式提交输出
```

需要明确：

- LLM 能否返回多个候选；
- 用户是否必须从候选中选择；
- 用户能否完全手写一条新内容；
- LLM 是否必须附带候选依据；
- 用户不认可 LLM 候选时，是否允许空值提交；
- `reclaim_item` 是否必须引用对应的 `drive_items[].id`。

### 5.3 当前运行时的锁定粒度

当前提交后是整步锁定：

- `submitted` 后不能再编辑输出；
- 再次运行会创建新的 run；
- 历史 submitted run 保留。

相关实现：`D:\AI_Project\What_Want\platform\backend\app\routers\steps.py:279`

请确认产品是否接受“整步锁定”，还是需要真正的字段级锁定：

- [ ] 整步提交即全部锁定；
- [ ] 只锁定 `reclaim_item`，ratio/commentary 可重新生成；
- [ ] 每个候选项独立锁定；
- [ ] 其他：请说明。

如果选择字段级锁定，影响会从 config 调整扩大到前端输出编辑器、后端合并逻辑和重新生成 API。

### 5.4 前端编辑能力补充

当前前端对 `editable_list` 有 chip 编辑能力，但 ch02 的 `reclaim_item` 如果是 `text`，需要明确是否新增：

- 运行结果下方的 textarea；
- “保存修改”按钮；
- “确认并提交”按钮；
- 保存修改后状态是否仍为 `saved`；
- 提交前是否允许返回修改原始 `drive_items`。

设计稿需要补一张“LLM运行成功后的状态图或页面草图”，否则当前 M5.8 的通用 runner 无法判断这个文本字段的编辑位置。

---

## 6. ch01 上下文与导师上下文

### 6.1 ch02 练习是否读取 ch01

新设计稿有两种表述：

- 阶段1不读任何上游；
- 为保持连续性，注入 ch01 外部声音摘要。

请确认最终范围：

| 场景 | 是否读取 ch01 | 读取字段 | 具体用途 |
|---|---:|---|---|
| 阶段1用户填写 |  |  |  |
| 阶段2 LLM分析 |  |  |  |
| 阶段3确认 reclaim_item |  |  |  |
| ch02导师对话 |  |  |  |

当前运行时的一个重要事实：`mentor_hooks.references` 会被 `build_step_prompt` 用作 step Prompt 的 profile 字段选择：`D:\AI_Project\What_Want\platform\backend\app\runtime\assembler.py:394`

因此，如果 ch02 config 保留：

```json
"mentor_hooks": {
  "references": ["misconceptions_cleared"]
}
```

那么 ch02 step Prompt 可能会读取 ch01 profile。这一点需要在设计稿中明确，而不能只写“导师对话引用”。

### 6.2 是否新增 `external_voices_summary`

如果需要新增摘要字段，请补充完整链路：

```text
ch01.external_voices
    → 谁生成 summary
    → summary 的 JSON 结构
    → learner_profiles 保存
    → ch02 哪个阶段读取
    → Prompt 如何注入
    → 缺失时如何处理
```

当前 profile 压缩白名单已经有：

```text
misconceptions_cleared
external_voices
internal_external_ratio
reclaim_item
```

但没有 `external_voices_summary`：`D:\AI_Project\What_Want\platform\backend\app\services\compaction.py:11`

如果本期不希望扩大 ch01 影响，建议先使用现有 `external_voices`，不要新增 summary 字段。

### 6.3 导师 Prompt 的字段优先级

请确认刘老师在 ch02 对话中是否必须同时看到：

- ch01 的误区和外部声音；
- ch02 的原始 `drive_items`；
- ch02 的 `internal_external_ratio`；
- ch02 已确认的 `reclaim_item`；
- ch04 或其他章节 profile。

尤其要确认：

- 对话是否只能读取已提交结果；
- ch02 草稿是否可以被导师看到；
- `reclaim_item` 是否需要被特别置顶；
- 如果用户尚未提交 ch02，导师应该如何提示。

---

## 7. ch02 → ch04 的正式引用契约

新设计稿提出 ch02 的两个产出可以供 ch4 刘老师引用：

- `reclaim_item`；
- `internal_external_ratio`。

请确认这一条是否属于本期必须实现的正式跨章链路：

```text
ch02 submitted output
    → learner_profiles
    → ch04 mentor prompt
    → 回响提示
```

如果是，请补充：

| 项目 | 需要确认 |
|---|---|
| producer | ch02 的哪一个 submitted run |
| 字段 | `reclaim_item`、`internal_external_ratio` 是否都引用 |
| consumer | ch04 mentor、ch04 step、还是两者 |
| 展示方式 | 直接显示字段，还是由导师自然语言回响 |
| 缺失处理 | 没有 ch02 时是否只提示、不阻断 ch04 |
| 优先级 | 是否高于 ch04 当前其他 profile 字段 |
| 测试 | 是否增加 ch02 → ch04 Prompt 断言 |

如果只是设计建议而不是本期验收内容，请明确标注为 backlog，避免开发侧误认为必须同步实现。

---

## 8. 错误态、边界态和重新运行

请在设计稿中补充以下场景：

### 8.1 输入边界

- 空事项列表；
- 只有 1 件事项；
- 事项超过最大数量；
- 事项没有文本；
- 事项没有驱动类型；
- 所有事项都标成外部；
- 所有事项都标成内部；
- 事项重复；
- 只有全局备注、没有事项。

### 8.2 LLM 异常

- LLM 返回空字符串；
- LLM 返回 Markdown 代码块包裹的 JSON；
- LLM 返回非法 JSON；
- 缺少 `commentary`；
- 缺少 `internal_external_ratio`；
- 缺少 `reclaim_item`；
- ratio 与后端计算结果不一致；
- LLM 分析没有引用用户备注，只输出通用章节摘要。

当前后端对空结果和异常有 failed 状态处理，但对“字段缺失”目前主要是 warning，设计侧需要确认哪些情况必须阻止提交。

### 8.3 用户重新运行

请确认以下场景：

- 用户修改了 drive_items 后再次运行；
- 用户已经编辑了 reclaim_item 后再次运行；
- 用户已提交后点击重新做本章；
- 用户重新运行时是否保留旧 commentary；
- 用户重新运行时是否保留旧 reclaim_item；
- 用户是否可以比较前后两次分析；
- 下游章节读取哪一个版本。

---

## 9. 开发影响拆分

### 9.1 只需要配置和 Prompt 调整

如果设计侧确认以下方案，整体影响较小：

- 保留一个 exercise；
- 保留 `list_of_items` + 全局 `notes`；
- ratio 由后端按事项数量派生；
- `commentary` 加入 `output_fields`；
- `reclaim_item` 使用 `text`；
- 提交后整步锁定；
- 不新增 `external_voices_summary`；
- ch02 → ch04 回响暂时只作为导师 Prompt 的 profile 引用。

需要调整的主要文件：

- `D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch02.json`
- `D:\AI_Project\What_Want\llm_prompt_design\docs\PRD\PRD-ch2.md`
- `D:\AI_Project\What_Want\llm_prompt_design\docs\ch02_落地级步骤设计.md`
- `D:\AI_Project\What_Want\llm_prompt_design\config\mentor\mentor_config.json`（如导师 Prompt 需更新）

### 9.2 需要后端代码调整

以下决定会增加后端实现：

- ratio 由系统派生并必须写入 parsed output；
- 后端必须校验 commentary/ratio/reclaim_item 是否齐全；
- ratio 和 LLM 返回值不一致时以后端结果为准；
- ch02 → ch04 使用显式跨章字段契约；
- 新增 `external_voices_summary` producer/consumer；
- 字段级锁定而不是整步锁定。

可能涉及：

- `D:\AI_Project\What_Want\platform\backend\app\routers\steps.py`
- `D:\AI_Project\What_Want\platform\backend\app\runtime\agent.py`
- `D:\AI_Project\What_Want\platform\backend\app\runtime\assembler.py`
- `D:\AI_Project\What_Want\platform\backend\app\services\compaction.py`
- `D:\AI_Project\What_Want\platform\backend\app\runtime\context_requirements.py`

### 9.3 需要前端代码调整

以下决定会增加前端实现：

- 每个事项增加 `note` 子字段；
- `reclaim_item` 使用可编辑文本框；
- ratio 使用专用可视化，而不是普通 table；
- 提交前显示字段级确认状态；
- 字段级锁定；
- 重新运行时保留用户编辑项并提示差异。

主要涉及：

- `D:\AI_Project\What_Want\platform\frontend\index.html`

### 9.4 必须新增的测试

至少需要补充：

1. ch02 输入 schema 的最终 JSON 验证；
2. ratio 派生算法；
3. ratio 不被 LLM 错误覆盖；
4. commentary/ratio/reclaim_item 缺失时的提交行为；
5. reclaim_item 文本编辑和提交锁定；
6. 重新运行不覆盖历史 submitted run；
7. ch01 上下文是否进入 ch02 step Prompt；
8. ch02 mentor 是否读取已提交的 reclaim_item；
9. ch02 → ch04 引用是否成立；
10. 空输入、单条输入、全外部、全内部、非法 JSON 等异常情况。

---

## 10. 建议的最终验收流程

设计侧确认后，开发侧建议按以下顺序验收：

```text
1. 清理 ch02 测试数据
        ↓
2. 进入 ch02，确认初始页面没有历史失败/测试输出
        ↓
3. 填写 2–3 件事项并标记 external/internal
        ↓
4. 保存草稿，确认只保存输入、不调用 LLM
        ↓
5. 运行 LLM，确认 commentary 结合每件事项和备注
        ↓
6. 确认 ratio 与后端计算一致
        ↓
7. 编辑 reclaim_item
        ↓
8. 提交，确认整步锁定
        ↓
9. 刷新页面，确认输出和 submitted 状态保留
        ↓
10. 进入导师对话，确认只引用已提交 ch02 数据
        ↓
11. 进入 ch04，确认回响规则（若本期实现）
        ↓
12. 检查 step_runs、learner_profiles 和 Prompt 审计证据
```

---

## 11. 设计侧最终回复表

请直接填写右侧“设计侧确认”列。

| 编号 | 决策项 | 设计侧确认 |
|---|---|---|
| 1 | ch02 是否保持 1 个 exercise，内部 4 阶段 |  |
| 2 | 阶段与 `draft/saved/submitted` 的映射 |  |
| 3 | 最少事项数量 |  |
| 4 | 最大事项数量 |  |
| 5 | 每件事项是否有独立 `id` |  |
| 6 | 备注是 item 级还是全局级 |  |
| 7 | `drive_items` 最终 JSON |  |
| 8 | ratio 的计算方式 |  |
| 9 | ratio 的最终 JSON |  |
| 10 | ratio 是否由后端计算 |  |
| 11 | LLM 是否可以修改 ratio |  |
| 12 | `commentary` 是否是正式 output field |  |
| 13 | `commentary` 类型 |  |
| 14 | `commentary` 是否允许编辑 |  |
| 15 | `reclaim_item` 类型 |  |
| 16 | `reclaim_item` 是否必须引用事项 ID |  |
| 17 | LLM 候选是否允许用户拒绝/重写 |  |
| 18 | 锁定粒度：整步还是字段级 |  |
| 19 | ch02 阶段1是否读取 ch01 |  |
| 20 | ch02 阶段2是否读取 ch01 |  |
| 21 | 读取 `external_voices`、`misconceptions_cleared` 还是摘要 |  |
| 22 | 是否新增 `external_voices_summary` |  |
| 23 | ch02 导师读取哪些已提交字段 |  |
| 24 | ch02 → ch04 是否本期实现 |  |
| 25 | ch04 读取哪些字段 |  |
| 26 | 缺少 ch02 时 ch04 的行为 |  |
| 27 | 缺字段 / 非法 JSON 是否阻止提交 |  |
| 28 | 重新运行时如何处理用户编辑 |  |
| 29 | 本期必须实现的 E2E 场景 |  |
| 30 | 本期明确不实现、进入 backlog 的内容 |  |

---

## 12. 开发侧建议的低影响落地方案

以下不是最终设计结论，只是为了帮助设计侧快速评估影响：

```text
ch02 一个 exercise
  ├─ input_schema: drive_items[text + drive] + notes
  ├─ 保存草稿：draft
  ├─ 运行 LLM：saved
  │    ├─ commentary: markdown，只读
  │    ├─ ratio: 后端按事项数量计算，只读
  │    └─ reclaim_item: text，可编辑
  ├─ 用户编辑 reclaim_item
  ├─ 确认并提交：submitted，整步锁定
  ├─ profile: ratio + reclaim_item
  └─ 导师：只读已提交 profile 和 ch01 已确认上下文
```

如果设计侧确认这一路径，预计不需要重构通用框架，主要是：

- 更新 ch02 config；
- 更新 Prompt 和 few-shot；
- 增加 ratio 派生；
- 增加 reclaim_item 文本编辑；
- 增加 ch02 专项 E2E。

---

## 13. 参考文件

- 新设计稿：`D:\AI_Project\What_Want\llm_prompt_design\docs\ch02_落地级步骤设计.md`
- 当前 M5.8 设计基线：`D:\AI_Project\What_Want\llm_prompt_design\docs\M5.8_input_schema_角色管理_设计侧修订稿.md`
- 当前 ch02 config：`D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch02.json`
- 当前 ch02 PRD：`D:\AI_Project\What_Want\llm_prompt_design\docs\PRD\PRD-ch2.md`
- 当前步骤 API：`D:\AI_Project\What_Want\platform\backend\app\routers\steps.py`
- 当前 Prompt 装配器：`D:\AI_Project\What_Want\platform\backend\app\runtime\assembler.py`
- 当前 profile compaction：`D:\AI_Project\What_Want\platform\backend\app\services\compaction.py`
- 当前前端 runner：`D:\AI_Project\What_Want\platform\frontend\index.html`
- 当前测试基线：`D:\AI_Project\What_Want\platform\backend\tests`

