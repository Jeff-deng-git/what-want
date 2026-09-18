# PRD：What Want 平台 · 第三章《能最快找到想做的事的公式：自我认知法》

> 文件：`PRD-ch3.md`
> 对应章节：原书第三章（公式 / 自我认知法）
> 状态：待审 → 设计稿 → 开发
> 设计基调：继承 `PRD-ch4.md` §6「书卷气」视觉体系；全书重构视角下文。
> 全书定位：ch3 是**框架建立层**——提出全书核心公式「喜欢 × 擅长 × 重要 = 真正想做的事」，并把三要素沉淀为 `learner_profile` 的 `likes` / `talents` / `importance`，是 ch5–ch8 全部练习的「输入源（概念层）」。（注：ch3 是三要素**框架/种子**章；ch7 实际组合的是 ch4–ch6 深化版——ch6 `likes` × ch5 `talents`，用 ch4 `work_purpose` 筛选、以 `values` 作核心价值观，详见 ch07 config；ch7 不读 ch3。）

---

## 0. 关键发现：第三章是全书的方法论总纲

全书流水线中，ch3 是从「解构」转向「建设」的转折点：

```
ch1 误区 → ch2 内外标准 → ch3 三要素公式（框架）
   → ch4 重要(价值观) → ch5 擅长 → ch6 喜欢 → ch7 组合 → ch8 实践
```

ch3 给出全书最核心的两个公式：
- **公式 1**：喜欢 × 擅长 = 想做的事（What × How）
- **公式 2**：喜欢 × 擅长 × 重要 = 真正想做的事（What × How × Why）

并明确三条**寻找顺序规则**（纠正常见错误）：
- 规则 1：「喜欢」只是手段，先找「重要的事」（价值观）。
- 规则 2：在找「喜欢」之前，先找「擅长的事」（建立「什么都能变成工作」的自信）。
- 规则 3：不要先想「实现手段」（博客/YouTube/创业/跳槽都是手段，最后再定）。

ch3 的产出——`likes` / `talents` / `importance`——是后续所有章的输入：ch4 的价值观、ch5 的擅长、ch6 的喜欢、ch7 的组合、ch8 的实践，都回指这三要素。这是全书跨章连续性的「主干」。（【2026-08-13 校正】此为概念层「回指」；数据层 ch7 直接消费的是 ch4–ch6 深化版——ch6 `likes`、ch5 `talents`、ch4 `work_purpose`+`values`——而非 ch3 的扁平三要素；ch3 为 seed 章。）

> ⚠️ **重构提示**：ch3 必须使用结构化三组输入，并把 `commentary`、`likes`、`talents`、`importance`、`intersection` 的真实提交结果映射到运行时；其中 `likes`/`talents`/`importance` 是最重要的一组跨章字段。

---

## 1. 第三章内容摘要（基于正文）

### 1.1 前提：找不到是因为不会把词语分类

寻找想做的事前，必须先厘清并正确分类四个概念：想做的事 / 真我本色 / 人生坐标轴 / 自我中心坐标轴。模糊语言思考会陷入迷宫（图 3-1）。

### 1.2 两大公式（图 3-2）

- 公式 1：喜欢的事 × 擅长的事 = 想做的事
- 公式 2：喜欢的事 × 擅长的事 × 重要的事 = 真正想做的事

### 1.3 三要素严格定义（易混淆，需重点设计交互）

| 要素 | 定义 | 关键警告 |
|------|------|---------|
| **喜欢的事** | 能持续投入热情的「领域/方向」（如心理学、设计），不是具体一份工作 | 区别于「想成为的人」（职业名） |
| **擅长的事** | 天生才能（talent）：自然而然做得好、不痛苦、舒畅 | **≠ 技能和知识**（编程/英语是后天学的，会过时） |
| **重要的事** | 价值观（Being 状态）：想怎样生活（自由/安心/热情） | 向内=人生目的，向外=工作目的 |

**POINT**：想做的事 = 用什么(What) × 怎么做(How)；真正想做的事 = What × How × 为什么(Why)。

### 1.4 三条寻找规则

1. 喜欢是手段，先找重要的事（工作目的前提）。
2. 先找擅长的事（建立自信），再找喜欢的事。
3. 实现手段（博客/YouTube/创业/跳槽）最后再考虑。

---

## 2. 可设计成互动的部分

### 2.1 通用阅读层（与 ch4–ch8 一致）

同 `PRD-ch1.md` §2.1。

### 2.2 本章练习（轻量，1 个，但信息密度最高）

#### 三圆交集练习

- 页面结构：
  - 三栏输入区：分别输入「重要的事」「擅长的事」「喜欢的事」各 3–5 项（每项一行，可增删），**推荐顺序：先重要→再擅长→最后喜欢**（UI 三栏按此序排）。
  - 中部：三圆陈列区，把用户已填的三组清单分别陈列；**重叠区不靠几何求交**，由阶段2 的 LLM `intersection` 结论回填（前端不做几何求交，详见落地设计 §7 维恩口径）。
  - 底部：「让 AI 帮你找交集」按钮。
- 提交后 LLM 输出：
  - `commentary`（`markdown` 类型、`readonly`，整体映照，重点纠正混淆：用户把「技能」当「擅长」、把「职业名」当「喜欢」）。
  - `importance` / `talents` / `likes`（归一化后的三要素清单，汇入 `learner_profile`；用户可在阶段3 覆盖）。
  - `intersection`（三圆交集的初步总结，AI 语义得出，非几何计算）。
- LLM 的活（非裁判）：
  - 纠正混淆：用户写「我会编程」→ 提示这是技能不是才能，追问天生不痛苦就能做的是什么。
  - 引导拆解：用户写「喜欢打游戏」→ 追问喜欢的是策略/协作/成就感。
  - 取交集：对齐公式给「你真正想做的事可能是 XX」。

### 2.3 右侧 tab 面板

| tab | 第三章内容 |
|-----|-----------|
| 摘要 | 基于本章 MD：两大公式、三要素严格定义、易混淆点（才能≠技能、喜欢≠职业名）、三条规则 + 关键流程编号。 |
| 对话 | 刘老师基于三圆结果做追问（如「你把『共情』写进擅长，ch1 也说过你爱管闲事——这俩是不是同一个才能？」）。 |
| 步骤 | 三圆交集 runner，含三圆陈列（非几何求交）。 |
| 笔记 | 选区笔记 + 独立笔记。 |

### 2.4 导师「刘老师」融合设计（mentor）

- **knows**：book_md + user_progress（三圆：likes/talents/importance）+ ch1 的 `external_voices`（跨章锚点，建立连续性）。
- **grounding_rules**：引用前章锚点建立连续性；纠正三要素混淆；把公式与用户实际回答连接。
- **示例对话**（取自 `mentor_config.json` 的 `exercise_informed_dialogue`）：
  - 用户 ch3 写 likes=['深度对话','心理学']、talents=['共情','倾听']、importance=['帮人成长'] → 刘老师引用此锚点。

---

## 3. 需要大模型介入的部分

| 场景 | LLM 角色 | 作用 | 输出位置 |
|------|---------|------|---------|
| **三圆交集辅助** | psychologist / 通用教练 | 纠正混淆、引导拆解、取交集，归一化三要素。 | commentary + likes + talents + importance + intersection |
| **导师对话** | mentor（刘老师） | 结合 ch1/ch2 锚点 + 三圆结果做苏格拉底追问。 | 对话 tab |
| **章节摘要生成** | summary（图书编辑） | 生成 `{summary, core_concepts[], key_process[]}`。 | 摘要 tab |

> 三调用统一走 `app/runtime/`，配置驱动（详见《全书重构设计总览》）。

---

### 3.1 心理咨询师（psychologist）系统提示原文

ch03 三圆交集练习的 `step_role_id` 为 `psychologist`，其系统提示由 `platform/backend/scripts/seed_roles.py` 的 `PSYCHOLOGIST_SYSTEM` 灌入 `llm_roles` 表，运行时由 `config_loader.load_role` 读取。**原文如下（开发侧以此为准，不另写一遍）**：

> You are a reflective self-cognition coach. Help users see their own answers without judgment. Use Socratic questions. Reference the book background (What Want by Yagi Jinpei). Respond in Chinese when the user writes Chinese.

- **角色定位**：反思型自我认知教练；不评判，用苏格拉底式提问帮用户自己看清答案。
- **与 ch3 设计的关系**：本角色负责阶段2「纠正两类混淆（技能当才能 / 职业名当喜欢）+ 引导拆解 + 取交集」，对应 config 的 `output_fields`（commentary / importance / talents / likes / intersection）。
- **约束**：不替用户定性（与落地设计 §4 阶段2 约束一致）；用户用中文时以中文回应。

## 4. 推荐的工作流配置（chapter_config JSON）

> ⚠️ 本节仅为**示意**，字段契约的**唯一权威来源是 `config/chapters/chapter_config_ch03.json`**。若本节与其不一致，**以 config JSON 为准**（与落地设计文档 §8.3 同口径）。本章三栏展示顺序遵循落地设计决策：**先重要 → 再擅长 → 最后喜欢**。

```json
{
  "chapter_id": "ch03",
  "chapter_title": "能最快找到想做的事的公式：自我认知法",
  "exercises": [
    {
      "name": "三圆交集练习",
      "instruction": "分别写下『重要』『擅长』『喜欢』的具体事项（三圆为陈列展示，非几何求交），由 LLM 在阶段2 给出交集结论。",
      "worksheet": "重要：[...] / 擅长：[...] / 喜欢：[...] / 交集（AI 给）：[...]",
      "user_action": "用户分别输入三类各 3–5 项，推荐顺序：先重要→再擅长→最后喜欢。LLM 不判对错，而是辅助纠正混淆、引导拆解、取交集。",
      "llm_role": "assist",
      "step_role_id": "psychologist",
      "input_schema": [
        { "name": "importance", "label": "重要的事", "type": "list_of_items", "min_items": 3, "max_items": 5 },
        { "name": "talents", "label": "擅长的事", "type": "list_of_items", "min_items": 3, "max_items": 5 },
        { "name": "likes", "label": "喜欢的事", "type": "list_of_items", "min_items": 3, "max_items": 5 }
      ],
      "output_fields": [
        { "name": "commentary", "type": "markdown", "readonly": true },
        { "name": "importance", "type": "editable_list", "lockable": true },
        { "name": "talents", "type": "editable_list", "lockable": true },
        { "name": "likes", "type": "editable_list", "lockable": true },
        { "name": "intersection", "type": "text", "readonly": true }
      ],
      "few_shot_examples": [ "（完整内容见 chapter_config_ch03.json）" ]
    }
  ],
  "mentor_hooks": {
    "focus": "建立『喜欢 × 擅长 × 重要』框架",
    "references": ["misconceptions_cleared", "external_voices"]
  }
}
```

> 注：以上 `few_shot_examples` 与 `output_template` 的完整内容见 `chapter_config_ch03.json`；PRD 只保留角色与交互意图，字段细节（类型、lockable/readonly、references）以 config 为准。

---

## 5. 数据模型与输出 schema

### 5.1 三圆交集输出

```json
{
  "commentary": "你把『写代码』列为擅长，但那是技能；我们把它挪到『手段』，真正的才能可能是『把复杂的事讲清楚』……",
  "importance": ["帮人成长", "自由地生活"],
  "talents": ["共情", "倾听", "化繁为简"],
  "likes": ["深度对话", "心理学"],
  "intersection": "在对话里帮人理清自己"
}
```

- `commentary`：`markdown` 类型、`readonly`（前端渲染 markdown，用户不可编辑）；为 LLM 整体映照/纠正，重点指出两类混淆（技能当才能、职业名当喜欢）。
- `importance` / `talents` / `likes`：三要素清单，**最重要的一组跨章字段**，汇入 `learner_profile`（顺序遵循落地设计：先重要→再擅长→最后喜欢）。
- `intersection`：三圆交集的初步总结（AI 语义得出，非几何计算）。

---

## 6. 视觉与交互规范

### 6.1 继承 ch4 书卷气体系（颜色/字体/纸纹一致）

### 6.2 第三章专属视觉

- **三圆陈列（非几何求交）**：三圆（重要=赭石 / 擅长=冷色 / 喜欢=暖色）分别陈列用户已填清单；重叠区不靠几何求交，由阶段2 LLM `intersection` 结论文本回填（前端不做几何求交，详见落地设计 §7 维恩口径）。
- **混淆提示徽章**：⚠️ **首版不做**（需结构化 per-item 输出，非「配置即生效」；首版由 `commentary` 的 markdown 文本统一指出混淆）。
- **取交集卡**：底部显示 `intersection` 一句话总结（AI 语义，非几何计算），纸张卷轴样式。

---

## 7. 验收标准

- [ ] 第三章正文渲染完整，两大公式与三要素定义正确呈现。
- [ ] 三圆输入区可分别增删「重要/擅长/喜欢」各 3–5 项（顺序先重要→再擅长→最后喜欢），三圆陈列正确、重叠区由 LLM `intersection` 回填（前端不做几何求交）。
- [ ] LLM 输出 `commentary` + 归一化 `likes`/`talents`/`importance` + `intersection`，正确汇入 `learner_profile`。
- [ ] 刘老师对话能引用 ch1/ch2 锚点 + 三圆结果做跨章追问。
- [ ] 通用功能与 ch4–ch8 一致。

---

## 8. 待确认事项

1. **三要素是否允许用户在 LLM 归一化后手动覆盖**？建议允许，LLM 仅给建议。
2. **`intersection` 是否直接作为 ch7 组合的输入**？~~建议「是」——ch7 直接读 ch3 的 `intersection` 起手。~~ **【已推翻，2026-08-13】** 当前 ch07 config `step_context`/`mentor_hooks.references=[talents,likes,work_purpose,values]`，**不消费 ch3 的 `intersection` 或 `importance`**，也不读 ch3。ch7 起手读 ch6 结构化 `likes` × ch5 `talents`（含◎〇△），用 ch4 `work_purpose` 筛分、以 `values` 作核心价值观。本 PRD 的「ch3 三要素是 ch5–ch8 输入源」为早期框架表述，实际数据消费以各章深化版（ch4–ch6）为准。
3. **章末桥接卡形态**：按 §11 决策采用形态 B（回顾卡），默认展示不强制对话。

---

## 9. 与 Ardot 画布的衔接

同 `PRD-ch4.md` §9：绘制三栏布局、三圆维恩图、混淆提示、取交集卡、刘老师对话面板。

---

## 10. 参考文件

- 原书第三章 MD：`chapter_md/第三章-能最快找到想做的事的公式：自我认知法.md`
- 上下文层配置：`../../config/chapters/chapter_config_ch03.json`
- 全书级导师配置：`../../config/mentor/mentor_config.json`
- 导师设计规范：`../../docs/mentor_design_spec.md`
- 全书重构总览：`../../docs/全书重构设计总览.md`
- 相邻章节 PRD：`PRD-ch1.md`、`PRD-ch2.md`、`PRD-ch4.md` ~ `PRD-ch8.md`
