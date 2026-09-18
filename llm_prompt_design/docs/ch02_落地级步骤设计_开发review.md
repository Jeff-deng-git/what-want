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
| 1 | ch02 是否保持 1 个 exercise，内部 4 阶段 | **是**。1 个 exercise「内外标准对照」= 1 个 step 容器；4 阶段是 UI 状态切换（填写→AI分析→确认锁定→沉淀），不拆独立 step。阶段0 阅读正文不落库。 |
| 2 | 阶段与 `draft/saved/submitted` 的映射 | **采纳 4.1 表**：阶段1 填写=`draft`（保存草稿）；阶段2 运行 LLM=`saved`（生成分析草稿，不提交）；阶段3 编辑 reclaim_item 后「确认并保存/提交」=`saved→submitted`；阶段4 沉淀= `submitted` 后 compaction。运行 LLM **绝不代表提交**；唯一使 ch02 输出进入下游的动作是「确认并提交」。 |
| 3 | 最少事项数量 | **2**。提交校验：事项数 < 2 拦截并提示「至少列 2 件事才能对照」。需将 config `min_items` 由 1 改为 2。 |
| 4 | 最大事项数量 | **10**（保持现状 `max_items: 10`）。 |
| 5 | 每件事项是否有独立 `id` | **否**。reclaim_item 是 AI 从整体凝练的一整句话，不绑定具体 item id；LLM 也无需引用 item id。免 id 简化实现与重跑合并。 |
| 6 | 备注是 item 级还是全局级 | **方案 B：item 级备注**。每件事项含 `note` 子字段（LLM 才能把备注对应到具体事项）；保留全局 `notes` 为选填整体补充。 |
| 7 | `drive_items` 最终 JSON | `{"drive_items":[{"text":"...","drive":"external\|internal","note":"..."}],"notes":"可选整体补充"}`（无 id）。 |
| 8 | ratio 的计算方式 | **后端按事项数量派生**（method="item_count"）：`external_pct = external_count / total * 100`。不调 LLM、无滑块。 |
| 9 | ratio 的最终 JSON | `{"external_pct":60,"internal_pct":40,"method":"item_count"}`。两比例相加必为 100。 |
| 10 | ratio 是否由后端计算 | **是**。后端在提交时计算并写入 `parsed_output` 与 profile；LLM 只可在 commentary 文字里引用该数字，不负责算。 |
| 11 | LLM 是否可以修改 ratio | **否**。LLM 不得改写 ratio；若 LLM 返回值与后端计算不符，以 backend 为准（后端覆盖）。 |
| 12 | `commentary` 是否是正式 output field | **是**。加入 `output_fields`。 |
| 13 | `commentary` 类型 | **markdown**（整体映照+矛盾盲点分析，可分段/加粗）。 |
| 14 | `commentary` 是否允许编辑 | **否**（只读）。偏差时用户用「换一种说法」触发重跑（新建草稿 run），不内联编辑 commentary。 |
| 15 | `reclaim_item` 类型 | **text**（统一）。用户确认的是一句「最想收回主动权的事」，不是维护列表——与当前 config、开发侧倾向一致。修正：此前文档曾写 editable_list，现统一为 text。 |
| 16 | `reclaim_item` 是否必须引用事项 ID | **否**（见 5）。 |
| 17 | LLM 候选是否允许用户拒绝/重写 | **是**。LLM 只输出 1 个候选（最关键那件）；用户可改、可完全手写、可拒绝；拒绝时不强制从候选选。允许用户空值提交（仅当该用户确无可收回事项时）。 |
| 18 | 锁定粒度：整步还是字段级 | **整步提交即锁定**。采纳现状 `submitted` 后 `edit_output` 409 守卫；不实现字段级锁。reclaim_item 的「lockable:true」仅作 schema 意图声明（前端据此渲染「可锁定」态），真实锁定靠整步提交态。 |
| 19 | ch02 阶段1是否读取 ch01 | 见 21：references 是整段 step prompt 共享注入，不区分阶段。阶段1/2/3 都看得到 ch01 上下文。 |
| 20 | ch02 阶段2是否读取 ch01 | 见 21。 |
| 21 | 读取 `external_voices`、`misconceptions_cleared` 还是摘要 | **复用现有 `external_voices` + `misconceptions_cleared`**（白名单已含两者）。将 ch02 config 的 `mentor_hooks.references` 由 `["misconceptions_cleared"]` 改为 `["misconceptions_cleared","external_voices"]`。`external_voices` 在 ch01 是短编号映射（如 `{"1":"爸妈说稳定体面"}`），注入成本可控，无需摘要字段。 |
| 22 | 是否新增 `external_voices_summary` | **否**（修正前决策）。经核实 `external_voices` 已是短映射且白名单已含，复用即可，不新增字段、不碰 compaction。 |
| 23 | ch02 导师读取哪些已提交字段 | 导师对话（阶段4 后）只读 ch02 **已提交** profile：reclaim_item、internal_external_ratio；以及 ch01 已提交 misconceptions_cleared + external_voices（连续性）。草稿不可见。 |
| 24 | ch02 → ch04 是否本期实现 | **是，但仅以 profile 引用方式**。不新增跨章字段契约 API、不新增专用 UI；ch04 mentor prompt 读取 ch02 submitted 的 reclaim_item / internal_external_ratio 即可（白名单已含两键）。 |
| 25 | ch04 读取哪些字段 | reclaim_item、internal_external_ratio（作为 ch04 mentor prompt 的 profile 引用，自然语言回响）。 |
| 26 | 缺少 ch02 时 ch04 的行为 | **只提示、不阻断**。ch04 可独立进行；缺 ch02 时 ch04 导师不引用、仅正常推进。 |
| 27 | 缺字段 / 非法 JSON 是否阻止提交 | **是**。commentary / ratio / reclaim_item 任一缺失，或 LLM 返回非法 JSON，均阻止提交并进入 failed 态（不生成空成功）。ratio 若 LLM 漏给但后端可补算，则允许以 backend 值补齐后提交；非法 JSON 必须 failed。 |
| 28 | 重新运行时如何处理用户编辑 | 修改 drive_items 或 reclaim_item 后重跑：系统创建新草稿 run，**保留旧 submitted 记录不覆盖**；新草稿的初始 reclaim_item 取用户上次的编辑值；旧 commentary/reclaim_item 可作「上一次」对比参考。下游章节始终读取最新 submitted 版本。 |
| 29 | 本期必须实现的 E2E 场景 | 采纳开发侧 §10 的 12 步验收流（清理→填写 2–3 件标 external/internal→保存草稿不调 LLM→运行 LLM→ratio 与后端一致→编辑 reclaim_item→提交整步锁定→刷新保留→导师仅引已提交→ch04 回响（若本期实现）→审计 step_runs/profile/prompt）。 |
| 30 | 本期明确不实现、进入 backlog | ① 字段级锁定；② ratio 专用可视化组件（用占比条即可，非新组件）；③ `external_voices_summary` 字段；④ reclaim_item 多候选；⑤ 跨章显式字段契约 API；⑥ 前后两次分析差异高亮对比 UI。 |

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

---

## 14. 设计侧补充契约（最终 JSON 与决策修正）

### 14.1 最终用户输入 JSON（阶段1，保存草稿）

```json
{
  "drive_items": [
    {"text": "在XX公司做审计", "drive": "external", "note": "爸妈说稳定体面"},
    {"text": "周末学油画",     "drive": "internal", "note": "自己真的喜欢"}
  ],
  "notes": "最近总体想理清方向"
}
```

- `text` / `drive` 必填；`note` 选填；`notes` 全局选填。
- 无 item `id`；`drive ∈ {external, internal}`。
- 提交校验：`drive_items.length >= 2` 否则拦截。

### 14.2 最终 LLM 输出 JSON（阶段2，运行 LLM 后 `saved`）

```json
{
  "commentary": "## 映照\n你 3 件里 2 件外部驱动……\n\n## 一个值得注意的矛盾\n……",
  "internal_external_ratio": {"external_pct": 67, "internal_pct": 33, "method": "item_count"},
  "reclaim_item": "在XX公司做审计——这件事我一直是照着「稳定体面」在撑，其实最该由我自己重新拿主意。"
}
```

- `commentary`：`markdown`，只读（不进 profile）。
- `internal_external_ratio`：**后端计算后写入**，`method:"item_count"`；LLM 可在 `commentary` 引用，但不得改写该数字。
- `reclaim_item`：`text`，草稿态，用户可编辑。

### 14.3 最终 profile 落库键（阶段4，`submitted` 后 compaction）

```json
{
  "internal_external_ratio": {"external_pct": 67, "internal_pct": 33, "method": "item_count"},
  "reclaim_item": "……用户改定后的一句话"
}
```

- `commentary` **不**进入 profile（仅留 `step_runs.parsed_output`）。
- 两键已在 `compaction.py` 白名单，无需改白名单/compaction。

### 14.4 决策修正（如实同步开发侧）

1. **`external_voices_summary` → 取消，复用现有 `external_voices`**。
   此前设计稿（§10.4）建议新增浓缩摘要键以防上下文过长。经核实：`external_voices` 在 ch01 是**短编号映射**（如 `{"1":"爸妈说稳定体面","3":"同事都考CPA"}`，见 SPEC.md:348），且已在 `compaction.py` 白名单（第13行）。整值注入成本可控，无需摘要字段。改为：ch02 `mentor_hooks.references` 由 `["misconceptions_cleared"]` 扩展为 `["misconceptions_cleared","external_voices"]`。这是比前方案**更低影响**的落地路径，与开发侧 §6.2 建议一致。**用户「引用 ch01 延续性」的意图保留**，只是机制改回复用现有字段。
2. **`reclaim_item` 类型统一为 `text`**（非 `editable_list`）。此前文档 §9.2 因「单元素锁列表」叙述残留 `editable_list`；但真实运行时锁定靠整步提交态（无字段级合并），且用户确认的是一句话，故统一为 `text`，与当前 config、开发侧倾向一致。
3. **「仅限阶段1 注入 external_voices」→ 修正为「整段 step 共享」**。真实机制（`assembler.py:394-396`）是 `mentor_hooks.references` 一次性注入整段 step prompt，不区分阶段；`_build_ch01_evidence` 仅对 ch01 生效（assembler.py:104-106），不影响 ch02。故 ch02 阶段1/2/3 都可见 ch01 上下文，这是正确且足够的连续性呈现。

### 14.5 需要同步改动的文件（开发侧确认后）

- `config/chapters/chapter_config_ch02.json`：
  - `input_schema.drive_items.item_schema.fields` 增加 `note`（text，选填）；
  - `input_schema.drive_items.min_items` 1 → 2；
  - `output_fields` 增加 `{name:"commentary", type:"markdown"}`，`internal_external_ratio` 补 `readonly:true`，`reclaim_item` 维持 `type:"text", lockable:true`；
  - `mentor_hooks.references` → `["misconceptions_cleared","external_voices"]`；
  - `ratio` 的派生逻辑由后端在提交时计算写入（config 仅声明字段）。
- `docs/ch02_落地级步骤设计.md`：同步 14.4 的三处修正（设计侧据此回写，保持设计稿与契约一致）。
- 前端 `index.html`：reclaim_item 文本编辑态（textarea + 保存修改/确认并提交）+ ratio 占比条展示 + 提交后整步锁定 UI。
- 测试基线：补 §9.4 所列 10 项（重点 ratio 派生不被 LLM 覆盖、缺字段/非法 JSON 阻止提交、重跑不覆盖 submitted）。

### 14.6 设计侧对开发 review 的整体结论

开发侧的"影响总览"与"低影响落地方案"（§12）与设计拍板**高度一致**，且 §12 路径即为推荐落地路径。除 14.4 三处设计侧自我修正外，**无阻塞性设计分歧**。开发侧可在收到本确认后，按 §12 + 14.5 同步 config / Prompt / 后端 ratio 派生 / 前端 reclaim_item 编辑 / E2E。
