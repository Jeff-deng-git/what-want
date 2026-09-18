# PRD：What Want 平台 · 第五章《只要找到擅长的事，就可以应用到工作中》

> 文件：`PRD-ch5.md`
> 对应章节：原书第五章（擅长的事 / 才能）
> 原书页码：PDF 第 139–174 页（按正文章节；含「擅长的定义」「发挥优点」「自我提升陷阱」「强化长处」「回答5问」「使用说明书」）
> 状态：待审 → 设计稿 → 开发 → **交付中（2026-08-14 初报完成，实测 ch05 stale 级联选项 A 尚未实现，待补）**
> 设计基调：ch5 继承 ch4 定义的「书卷气」视觉体系（颜色 / 字体 / 纸纹），见本文件 §6。

> **题库与清单权威来源**：本章涉及的「擅长的事（才能）30 问」「擅长的事（才能）100 例清单」等结构化内容，统一维护在
> `D:\AI_Project\What_Want\chapter_md\问题清单.md`（含：重要的事 / 擅长的事 / 喜欢的事 各自的 30 问与 100 例）。
> 本 PRD 不再重复罗列，后端题库与 LLM 少样本提示均以该文件为唯一权威来源。

---

## 0. 关键发现：第五章是「2 步」的才能深化章

SPEC 里那句「从第 4 章起每个章节有 5 个步骤 × 5 个问题的工作流」是被 ch5/ch6 证伪的概括（详见 PRD-ch4 §0）。真正的书结构是分章的：

| 维度 | 第四章（重要的事 / 价值观） | **第五章（擅长的事 / 才能）** | 第六章 | 第七章 | 第八章 |
|------|----------------------------|------------------------------|--------|--------|--------|
| 工作法 | 真正的 5 步级联 | **1 个方法（回答 5 问）+ 1 个综合产出** | 同 ch5 | 组合收口 | 收尾落地 |
| 步骤数 | 5 个独立步骤 | **2 步**（step-1 找长处 / step-2 评级+说明书） | 2 步 | 2 步 + 迭代 | 3 步 |
| 综合产出 | 价值观排序（金字塔）+ 工作目的 | **《使用说明书》（带 ◎〇△ 评级的长处清单）** | 《喜欢的事清单》 | 真正想做的事 | 实现手段 / 海胆日记 / 宣言 |

**结论**：第五章是全书「擅长」维度唯一的深化章。**ch03 已产出初始 `talents` 键，ch05 在本章把它深化为带 ◎〇△ 评级的正式 `talents`**（同名键覆盖，ch05 为权威写方）。ch07「组合」直接消费本章 `talents`（以◎级为主），故 `talents` 是稳定的跨章种子。

> ⚠️ **重构提示（重要）**：本章**权威配置源是 `config/chapters/chapter_config_ch05.json`**（new-schema：`exercises[]` + `input_schema` + `output_fields` + `references.from_exercise` 级联，由 `seed_all_chapters.py` 灌入 `chapter_configs` 表供运行时消费）。旧版单步「九宫格擅长梳理」配置（git HEAD 中的 `chapter_config_ch05.json`）已作废，不再作为权威源。5 个步骤已对齐书本方法（step-1 回答 5 问 → step-2 评级+使用说明书）。详见 §8。

---

## 1. 第五章内容摘要（基于原书正文 + 配图 + 配套清单）

### 1.1 叙事模块（6 个概念铺垫）

1. **「擅长的事」的重新定义**
   擅长的事 = 通过无意识的思考、感情和行动模式取得成果。它不是运动/音乐那种耀眼才华，而是你「无意识中自然而然在做的事」（像惯用手）。因为无意识，所以难捕捉。
   **POINT**：擅长的事（才能）= 无意识的习惯，需要通过回顾自己的行为去发现。

2. **由「努力改变自己」变成「努力发挥自己的长处」**
   擅长的事（才能）本身只是「习惯」，无好坏。同一项才能，用对地方是优点（慎重→不出错），用错地方是缺点（慎重→工作太慢）。关键不是改正它，而是把它作为长处使用。
   **POINT**：× 努力改变自己的缺点。√ 努力灵活运用自己的优点。

3. **「所以」→「正因为」的视角转换**
   把缺点变优点的简单方法：把「……所以（辩白）」换成「正因为……（解释）」。例：「我很认生，所以很难交新朋友」→「正因为认生，我才能认真地和重要的人相处」。
   **POINT**：同一项才能，根据看法不同可成优点或缺点。

4. **「自我提升类图书」读得越多，人越易失去自信**
   这类书教的是「作者优点的使用方法」，不一定适合你。自己的成功法则只存在于自己身上。
   **POINT**：× 读自我提升类图书就知道成功方法。√ 自己的成功法则只存在于自己身上。

5. **打磨长处，成为不可替代的存在**
   发挥长处的效率远高于弥补短处（速读研究：B 组原 350 字/分，训练后 2900 字/分，提升近 8 倍；A 组仅约 1 倍）。星形比喻：磨尖星角而非磨平棱角。
   **POINT**：克服短处得普通成果；强化长处得惊人成果。

6. **回答 5 个问题，找出擅长的事**
   目标：找到 **10 个长处**（理想 20 个）。5 问分别唤醒：充实的体验 / 最近烦躁的事 / 问身边人 / 辞职后留恋 / 取得的成果与做法。

### 1.2 两步方法概览

| 步骤 | 书本原句 | 平台落点 |
|------|---------|---------|
| 步骤一 | 回答 5 个问题，找出擅长的事 | Step 1 |
| 步骤二 | 归纳长处，写《使用说明书》（◎〇△ 评级） | Step 2 |

### 1.3 步骤一：回答 5 个问题，找出擅长的事

> 平台 Step 1 的 5 个问题直接取自书中「寻找擅长的事的 5 问」，由 `chapter_config_ch05.json` 的 `step-1.input_schema` 配置即生效（权威源已是 new-schema JSON）：

| 编号 | 问题 |
|------|------|
| Q1 | 在迄今为止的人生中，你觉得充实的体验是什么？ |
| Q2 | 最近让你感到烦躁或是心慌的是什么事？ |
| Q3 | 问身边亲近的人：「你认为我的长处是什么？」 |
| Q4 | 如果明天辞职了，之前的工作中有没有你留恋的部分？ |
| Q5 | 你至今为止取得过什么样的成果，你是如何做到的呢？ |

- 作答时可参考「擅长的事（才能）100 例清单」触发思路。
- 长处少于 10 个时，引导用户去问题清单追加回答。
- 书中要点：做时感到充实 = 擅长；感到疲劳 = 不擅长。对别人烦躁却自己理所当然的事，往往是擅长。

### 1.4 步骤二：归纳长处，写《使用说明书》

- LLM 汇总 step-1 的 `talents` 与用户从 100 例清单引用、已并入 `talents` 的项（带 `source:'100_examples'`），给出 10+ 长处初稿。
- 用户给每项标 **◎〇△** 三级：
  - **◎** 有充实感，与成功有关
  - **〇** 有充实感
  - **△** 目前还不确定
- 用户可增删、锁定；LLM 不替用户定性。
- 最终归纳成《使用说明书》概述（`user_manual`）：如何把自己的长处作为优点发挥。
- 书中范例长处清单（八木的 20 项）：找到值得尊敬的人并模仿他 / 多进行实操 / 花时间制定战略 / 使成果可视化 / 树立明确目标 / 描绘远大理想 / 不满足现状 / 发现并利用长短处 / 开拓新事业 / 不断学习 / 计划让人开心 / 在热爱上倾注时间 / 剔除不需要的 / 整理信息成体系 / 用语言帮人 / 极具表现力 / 富有创意 / 构筑信赖关系 / 传授经验感染别人 / 做可传授的工作。
- **下游**：第七章结合「喜欢的事」得出「想做的事」时，以 **◎ 级长处为主**。

### 1.5 配套资源

- **擅长的事（才能）30 问（方案A 收口）**：已固化进 step-1 `input_schema.talent_questions`（可选 `list_of_items`，q_order 31–60）；答案走 questions 服务 + `book_notes`，运行前前端按 q_order 取回填入本字段；**发现辅助、非产出物，不进入 `talents`、不流下游**。
- **擅长的事（才能）100 例清单**：100 条才能示例（已固化进 config `ui_context.strength_examples`，前端读 config 即生效），用于触发用户发现自己无意识的长处。

---

### 1.6 前置依赖与未就绪处理（Prerequisite Gating）

ch5 的**练习本身无硬性上游依赖**（step_context = []，step 不读任何前章档案），可独立进入并作答 5 个问题。它是被依赖方而非依赖方：

| 被依赖章节 | 需要的 ch5 产出字段 | 必需/可选 | 未就绪时的界面表现（在该章） |
|---|---|---|---|
| ch7 想做的事 | `talents`（带 ◎〇△ 评级） | 必需（作为「真正想做的事」组合原料，以◎为主） | 整章锁定：半透明遮罩 + 未就绪说明卡「请先完成第五章」，含「去第五章」直达按钮 |
| ch6 喜欢的事 | （无直接依赖；ch6 独立深化「喜欢」） | — | 不阻断 |

**判定逻辑**：ch5 自身进入时不触发任何上游判定。后续章节（ch7）在进入时读取 ch5 的 `status` 与 `talents` 字段，缺失则按上表锁定。
**导师连续性**：ch5 的 `mentor_hooks.references = ["work_purpose"]` 引用 ch4 工作目的，仅用于刘老师开场回响（非练习输入）。

---

## 2. 可设计成互动的部分

### 2.1 通用阅读层（ch4 定义、ch5–ch8 继承）

- 三栏布局：左步骤导航 / 中正文 / 右 tab 面板。
- 顶部 sticky bar：☰ 目录、面包屑、前后章。
- 正文可选中记笔记（选区笔记 + 独立笔记）。
- 目录下拉：全部卷章 + 本章 h2 锚点。
- 进度保存：上次阅读位置、已提交步骤数。

### 2.2 步骤工作流（2 个正式步骤）

#### Step 1：回答 5 个问题，找出擅长的事
- 5 个长文本输入框，逐个展开；Q2 下方提示「对别人烦躁却自己理所当然的事，往往是你擅长的事」；Q3 下方提示「把身边人的原话记录下来」。
- 每个问题支持「保存草稿」；5 问全部完成后可「提交」。
- 提交后 LLM（psychologist）输出 `commentary`（整体映照点评）+ `talents`（10+ 初步长处）。
- 顶部显示「已收集 N / 10 个长处」，低于 10 高亮「去回答 30 问 / 查 100 例」。
- 状态变为 `submitted`，供 Step 2 引用。

#### Step 2：评级与使用说明书
- 页面结构：
  - 顶部：进度提示「已收集 N / 10 个长处」（N = 当前编辑中 `talents` 列表长度，含 step-1 初版 + 用户手动新增 + 100 例引用项）。
  - 主体：可增删改的「长处」列表，每项带 **◎〇△ 三级评价**选择器 + 🔒 锁定 / 删除。
  - 可折叠「参考 100 例清单」输入区：用户可引用示例长处到 `reference_strengths`。
- 「让 LLM 从 Step 1 汇总长处并建议 ◎〇△」按钮（手动触发，控制 token）。
- 底部：`user_manual`《使用说明书》概述卡片（只读，LLM 生成；如需调整只能重新运行 LLM，用户不能就地编辑文本）。
- 「让 LLM 重新生成」按钮（保留锁定项）。

### 2.3 右侧 tab 面板（ch5 + 通用结构）

| tab | 第五章内容 |
|-----|-----------|
| 摘要 | 基于本章 MD 生成的摘要 + 核心概念（擅长=无意识习惯 / 发挥优点 / 所以→正因为 / 100例清单 / ◎〇△ / 使用说明书）+ 关键流程编号。 |
| 对话 | 导师「刘老师」多轮对话。可引导 5 问作答、追问长处、帮写使用说明书。 |
| 步骤 | 完整 runner（Step 1–2），显示每步提交状态、锁定项。 |
| 笔记 | 选区笔记 + 独立笔记。 |

### 2.4 导师「刘老师」融合设计（mentor）

> 刘老师不是「只导读 MD 的旁白」，而是像真人导师一样**读取用户在全书各章步骤的实际答案**，基于跨章学习者档案做苏格拉底式引导。详见 §3.1.4、`../../docs/mentor_design_spec.md` 与 `../../config/mentor/mentor_config.json`。

- **knows**：book_md（本章正文）+ user_progress（各步答案 / LLM 输出：talents、评级、使用说明书）+ conversation_history。
- **grounding_rules**：
  - 只基于本章内容展开，不编造本章没有的观点。
  - 引用用户步骤里写下的原话 / 长处，指出其中蕴含的才能线索。
  - 卡住时建议「书写冥想」或「提问对话」两种方法。
  - 一次只聚焦一个点，不直接给结论。
  - 把书中方法（5 问 / 所以→正因为 / 100例清单 / ◎〇△）与用户实际回答连接。
- **ch5 专属钩子**：`mentor_hooks.references = ["work_purpose"]`，刘老师开场回响 ch4 工作目的，建立 ch4→ch5 连续性。
- **示例对话**：
  - 用户「我好像没什么擅长的事」→ 刘老师用「擅长的事是无意识的习惯」引导其从 Q1 充实体验挖起。
  - 用户把「带动气氛」标了◎ → 刘老师追问它和 ch4 工作目的的关系，并提示第七章会以◎为主组合。

---

## 3. 需要大模型介入的部分

> **提示词去哪看**：下表只说明「哪个场景由哪个角色负责做什么」。每个角色的具体提示词——身份设定、需要内化的书籍背景、目标、约束，以及可调用的 `user` 模板——统一在 **§3.1 LLM 提示词设计规范** 中给出。后端调用时，按该节把书籍背景作为 `system` 常驻注入、把用户答案作为 `user` 传入。

| 场景 | LLM 角色 | 作用 | 输出位置 |
|------|---------|------|---------|
| **Step 1 映照点评** | psychologist | 阅读 5 问答案，给出整体映照点评 + 提炼长处（**10+ 是引导目标**，素材不足返回已有证据并提示补充）。 | Step 1 的 commentary + talents |
| **Step 2 评级与使用说明书** | psychologist | 汇总长处，建议 ◎〇△ 评级，生成《使用说明书》概述；保留锁定项。 | Step 2 的 talents（带评级）+ user_manual |
| **导师对话** | mentor（刘老师） | 引导 5 问作答、追问长处、帮写使用说明书、建立 ch4→ch5 连续性。 | 对话 tab |
| 章节摘要生成 | psychologist / deepseek json | 基于 chapter MD 前 12000 字生成 `{summary, core_concepts[], key_process[]}`。 | 摘要 tab |

**锁定机制**：Step 1 的 `talents`、Step 2 的 `talents` 均支持 `locked: true`。重新生成时，已锁定的项被传入 prompt（`preserve_output.talents`）要求保留，未锁定的可被替换 / 补充。

---

### 3.1 LLM 提示词设计规范（身份 / 背景 / 目标 / 约束）★必需章节

> 本章 LLM 角色配置以 `config/chapters/chapter_config_ch05.json` 为权威源（`exercises[].step_role_id` 指向 `psychologist`，`few_shot_examples` 在各 exercise 内）；角色系统提示正文由 `platform/backend/scripts/seed_roles.py`（`PSYCHOLOGIST_SYSTEM` / `MENTOR_SYSTEM`）灌入 `llm_roles` 表，运行时由 `config_loader.load_role` 读取。下面把各角色 system / user 提示词固化成规范，供重构时直接复用。

#### 3.1.0 书籍背景知识（所有 ch5 角色共用的 system 上下文）

- **擅长的事 = 无意识的习惯**：通过无意识的思考/感情/行动模式取得成果，不是耀眼才华；像惯用手一样难察觉。
- **发挥优点而非改正缺点**：同一项才能用对地方是优点、用错地方是缺点；把「……所以」换成「正因为……」。
- **自我提升类图书陷阱**：学的是作者优点的用法，自己的成功法则只存在于自己身上。
- **强化长处**：发挥长处的效率远高于弥补短处（速读研究 B 组提升近 8 倍）；磨尖星角而非磨平棱角。
- **5 问找擅长**：充实体验 / 最近烦躁的事 / 问身边人 / 辞职后留恋 / 取得的成果与做法；做时充实=擅长，疲劳=不擅长。
- **◎〇△ 三级**：◎ 有充实感且与成功有关 / 〇 有充实感 / △ 目前还不确定；目标 10 个、理想 20 个。
- **《使用说明书》**：归纳长处，第七章结合「喜欢的事」以◎为主得出「想做的事」。
- **少样本素材**：作者 20 项长处范例（见 §1.4）、「所以→正因为」例句、速读研究数据。

#### 3.1.1 `psychologist`（心理咨询师）— Step 1 映照点评

**system prompt：**
```
你是帮助用户发现「擅长的事」的资深自我认知教练，熟悉《如何找到想做的事》第五章「擅长的事」方法论。
你的回应温暖、深度、富有洞察力，避免泛泛而谈。请用 JSON 格式输出结构化结果。
你必须内化的书籍背景：
- 擅长的事=无意识的习惯（不是耀眼才华），需要通过回顾行为去发现。
- 做时感到充实=擅长，感到疲劳=不擅长；对别人烦躁却自己理所当然的事，往往是擅长。
- 卡住时可建议「书写冥想」或「提问对话」两种方法。
目标：阅读 5 问答案，给出整体映照点评 + 提炼长处（talents）。**10+ 是引导目标**：素材不足时返回已有证据并提示补充，不得为达到数量而补写（避免幻觉补齐）。
约束：
- 点评控制在 500 字内（markdown），重点指出反复出现的才能线索。
- 不臆造用户未透露的长处。
- 输出严格 JSON：{ "commentary": "...", "talents": [{"text":"...", "locked":false, "source":null}] }
  - canonical schema（step-2）：`{text, rating, locked, source?}`；**step-1 输出 `{text, locked, source:null}`，无 `rating`**（评级由 step-2 引入，见 §3.1.2）。
```

**user prompt 模板：**
```
【用户 5 个问题答案】
{% for q in step_1.answers %}Q{{ loop.index }}（{{ q.text }}）
答: {{ q.answer }}

{% endfor %}
请输出 JSON：commentary（整体映照点评，500字内markdown）+ talents（10+ 是引导目标；素材不足时返回已有证据并提示补充，不得幻觉补齐）。
```

#### 3.1.2 `psychologist`（心理咨询师）— Step 2 评级与使用说明书

**Step 2 system prompt：**
```
你是帮助用户梳理「擅长的事」的教练。基于用户 Step 1 已确认的长处（`step_1.output.talents`，来自 5 问映照）与从 100 例清单引用的参考长处（`reference_strengths`，带 `source:'100_examples'`）——**运行时后端会把两份合并去重（文本相同保留步骤1项）后形成候选清单**——请：
(1) 汇总去重，得到长处清单（**10+ 是引导目标**，素材不足时返回已有证据并提示补充，不得为达到数量而补写）；
(2) 为每项建议一个 ◎〇△ 评级（◎有充实感且与成功有关 / 〇有充实感 / △目前还不确定）；
(3) 归纳一段《使用说明书》概述，说明如何把长处作为优点发挥。
参考书中方法：把「我很认生，所以…」重写成「正因为认生，我才能…」。
约束：
- 保留已锁定的长处（preserve_output.talents 中 locked=true 的必须原样保留，不重新生成）。
- 不臆造用户未透露的长处。
- 建议 ◎〇△ 评级，但**不替用户下定论**（评级最终由用户确认）。
- 输出严格 JSON：{ "talents": [{"text":"...","rating":"◎|〇|△","locked":false,"source":"100_examples(可选)"}], "user_manual":"..." }
```

**Step 2 user prompt 模板：**
```
【步骤1已确认的长处（5问衍生，source:null）】
{% for t in step_1.output.talents %}- {{ t.text }}
{% endfor %}
【从100例清单引用的参考长处（source:'100_examples'）】
{% for r in step_2.answers.reference_strengths %}- {{ r }}
{% endfor %}
{% if preserve_output and preserve_output.talents %}【已锁定长处，必须保留】
{% for t in preserve_output.talents %}{% if t.locked %}- {{ t.text }}（{{ t.rating }}）
{% endif %}{% endfor %}{% endif %}
> 注：运行时后端会把上方两份（步骤1长处 ∪ 100例引用）合并去重（文本相同保留步骤1项），形成候选清单送入 LLM；请基于候选清单建议评级并生成 user_manual。请勿把 `reference_strengths` 再次单独注入，避免重复。
请输出 JSON：talents（数组，每项 {text, rating:""|"◎"|"〇"|"△", locked:false, source:"100_examples(可选)"}）+ user_manual（《使用说明书》概述）。
```

#### 3.1.4 `mentor`（刘老师，全书级苏格拉底导师）— 逐点引导

> 刘老师不是第五章专属角色，而是贯穿全书的常驻导师身份。她的配置见 `../../config/mentor/mentor_config.json`，运行时由统一 Agent 的「导师模式」加载；本章通过 `mentor_hooks` 声明需要引用的跨章字段（ch5 引用 `work_purpose`）。详见 `../../docs/mentor_design_spec.md`。其 system/user 提示词规范见 PRD-ch4 §3.1.4（全局复用，不重复）。

---

## 4. 推荐的工作流配置（chapter_config JSON）

> ⚠️ 本节仅为**示意**，字段契约的**唯一权威来源是 `config/chapters/chapter_config_ch05.json`**（new-schema）。若本节与其不一致，**以 config JSON 为准**（与落地设计文档同口径）。完整 `few_shot_examples` / `core_concepts` / `guiding_questions` 见该 JSON；角色系统提示见 `scripts/seed_roles.py`。

```json
{
  "chapter_id": "ch05",
  "chapter_title": "只要找到擅长的事，就可以应用到工作中",
  "exercises": [
    {
      "step_id": "step-1",
      "name": "回答5个问题，找出擅长的事",
      "input_schema": [
        {"name":"q1","label":"在迄今为止的人生中，你觉得充实的体验是什么？","type":"text"},
        {"name":"q2","label":"最近让你感到烦躁或是心慌的是什么事？","type":"text"},
        {"name":"q3","label":"问身边亲近的人：「你认为我的长处是什么？」","type":"text"},
        {"name":"q4","label":"如果明天辞职了，之前的工作中有没有你留恋的部分？","type":"text"},
        {"name":"q5","label":"你至今为止取得过什么样的成果，你是如何做到的呢？","type":"text"},
        {"name":"talent_questions","label":"（可选）从「擅长的事 30 问」题库追加回答，作为发现素材补充（题库由 questions 服务接入，本题回答存于 book_notes，运行前由前端按 q_order 取回填入本字段）","type":"list_of_items","required":false,"item_schema":{"fields":[{"name":"question_id","type":"number","label":"题库题目全局序号 q_order（才能分类 31–60）"},{"name":"question","type":"text","label":"题目原文（建议保存以抗题库更新）","optional":true},{"name":"answer","type":"text","label":"用户回答"}]}}
      ],
      "output_fields": [
        {"name":"talents","type":"editable_list","lockable":true},
        {"name":"commentary","type":"markdown"}
      ],
      "step_role_id": "psychologist"
    },
    {
      "step_id": "step-2",
      "name": "评级与使用说明书",
      "references": [{"from_exercise":"step-1","fields":["talents"]}],
      "input_schema": [
        {"name":"reference_strengths","label":"参考「擅长的事100例清单」补充的长处","type":"list_of_items","required":false,
         "item_schema":{"fields":[{"name":"text","type":"text","label":"一个参考长处"}]}}
      ],
      "output_fields": [
        {"name":"talents","type":"editable_list","lockable":true},
        {"name":"user_manual","type":"markdown"}
      ],
      "step_role_id": "psychologist"
    }
  ],
  "mentor_hooks": {
    "focus": "才能识别：你天生被赋能的事",
    "references": ["work_purpose"]
  }
}
```

> 注：本配置字段名（`talents` / `commentary` / `user_manual`）即前端需补渲染分支的字段。重构时前端 `renderStepOutput` 必须处理 `talents`（带 ◎〇△ 评级的可编辑列表）与 `user_manual`（只读概述），否则会退化成裸 JSON。

---

## 5. 数据模型与输出 schema

### 5.1 Step 1 输出
```json
{
  "commentary": "你在 Q1 反复提到『帮人理清楚』的充实感，Q3 朋友说你『特别能接住情绪』——几条线索都指向同一种无意识才能。",
  "talents": [
    {"text": "共情式梳理", "rating": "", "locked": false},
    {"text": "带动气氛", "rating": "", "locked": false},
    {"text": "在混乱中找结构", "rating": "", "locked": false},
    {"text": "把复杂讲简单", "rating": "", "locked": false},
    {"text": "让人安心", "rating": "", "locked": false}
  ]
}
```

### 5.2 Step 2 输出
```json
{
  "talents": [
    {"text": "共情式梳理", "rating": "◎", "locked": true},
    {"text": "带动气氛", "rating": "◎", "locked": false},
    {"text": "在混乱中找结构", "rating": "〇", "locked": false},
    {"text": "把复杂讲简单", "rating": "〇", "locked": false},
    {"text": "让人安心", "rating": "△", "locked": false}
  ],
  "user_manual": "我的使用说明书：我擅长在情绪和混乱中帮人理出结构（共情式梳理），并能带动气氛让团队安心。与其强迫自己『更外向』，不如把这份才能作为优点——在需要深度连接的场景里发挥，而非泛社交。"
}
```

- `commentary`：Step 1 映照点评（markdown）。
- `talents`：长处清单。**step-1 为 `{text, locked, source?}` 对象数组（无 `rating`）**；**step-2 为 `{text, rating, locked, source?}` 对象数组**（评级由 step-2 引入）；**以 step-2 的为准落库**（覆盖 ch03 初始 `talents`）。`source` 为可选字段，标记该项来源（如 `100_examples`）。
- `user_manual`：使用说明书概述（markdown，只读），仅留 step_runs，不进 profile。

---

## 6. 视觉与交互规范

### 6.1 ch5 设计体系（继承 ch4 源头）

- **颜色**：
  `--paper:#f6efde / --paper-edge:#ebe1c8 / --paper-light:#faf4e3 / --ink:#2a2620 / --ink-soft:#6b6354 / --accent:#7a4d2b / --accent-bg:#f1e8d2 / --rule:#d9cfb6`
- **字体**：中文衬线栈 `"Source Han Serif SC","Noto Serif SC","Songti SC","SimSun",serif`
- **纸纹背景**：径向渐变 vignette，全局统一。
- **赭石 accent**：用于步骤高亮、锁定图标、◎ 评级标记。

### 6.2 第五章专属视觉元素

- **Step 1 五问卡**：纸张卡片，5 个长文本输入框逐个展开；顶部显示「已收集 N / 10 个长处」。
- **Step 2 长处列表**：每项一行，左侧 ◎〇△ 三级评价选择器（◎赭石高亮 / 〇墨色 / △浅灰），右侧 🔒 锁定 / 删除；可折叠「参考 100 例清单」输入区。
- **《使用说明书》卡片**：底部纸张卷轴样式，显示 `user_manual` 概述，可导出。
- **100 例清单抽屉**：同 ch4 风格，可搜索、可引用长处到 Step 2。

### 6.3 动效与反馈

- 提交 Step 1 后，Step 2 卡片从折叠状态微动展开提示。
- 标 ◎〇△ 时图标 150ms 缩放反馈。
- 锁定 / 解锁时图标反馈。
- 《使用说明书》生成后有「落地」淡入动效。

---

## 7. 验收标准

- [ ] 第五章正文渲染完整，图 5-1～5-4 文字说明正确呈现，文字可选中。
- [ ] 左侧步骤导航显示 Step 1–2 共 2 个步骤，顺序与书本一致。
- [ ] Step 1 的 5 个问题可独立保存草稿、整体提交；LLM 输出 `commentary` + `talents`（10+）。
- [ ] Step 1 顶部显示「已收集 N / 10 个长处」，低于 10 高亮「去回答 30 问 / 查 100 例」。
- [ ] Step 2 可手动增删长处、标 ◎〇△、🔒 锁定；LLM 生成带评级的 `talents` 且锁定项保留。
- [ ] **Step 2 的 `talents`（带 ◎〇△ 评级）在前端有专门渲染分支（非裸 JSON）** —— 重构必须项。
- [ ] `user_manual`《使用说明书》卡片可渲染、可导出。
- [ ] 100 例清单 / 30 问抽屉可正常展开、搜索、引用。
- [ ] 导师对话能引用 ch4 `work_purpose` 做开场回响（刘老师融合设计）。
- [ ] 笔记、目录、进度、摘要、对话等通用功能与 ch4/ch6–ch8 行为一致。

---

## 8. 待确认事项

1. **前端 `renderStepOutput` 必须补 `talents`（带 ◎〇△ 评级）分支**（最高优先级）。当前硬编码字段可能不含带评级的可编辑列表，Step 2 会退化裸 JSON。建议在本轮重构一并修复。
2. **ch5 是否 2 步**？已拍板：第五章 = 2 个 step（step-1 5问 → step-2 评级+说明书），与 new-schema `references.from_exercise` 级联一致，非旧版单步「九宫格擅长梳理」（git HEAD 旧配置已作废）。
3. **`talents` 数据模型**：step-1 为 `{text, locked, source?}` 对象数组（无 `rating`）；step-2 为 `{text, rating, locked, source?}` 对象数组（评级由 step-2 引入）；以 step-2 为准落库，覆盖 ch3 初始 `talents`。下游 ch7 读取时取 `rating=="◎"` 优先。
4. **`work_purpose` 是否允许用户在 Step 2 覆盖 LLM 建议**？本 PRD 不覆盖（ch5 不产出 work_purpose）；ch5 仅消费 ch4 work_purpose 作导师连续性。
5. **刘老师对话是否跨步骤记忆**？本 PRD 设计 `user_progress` 注入 system，建议 chat.py 查询 step_runs 组装后注入。

---

## 9. 与 Ardot 画布的衔接

本 PRD 完成后，下一步是在 Ardot 中新建设计稿并绘制第五章高保真界面。操作方式：
1. 在 WorkBuddy 中确认 Ardot 编辑器已打开或新建一个 `.ardot` 文件。
2. 将文件 ID 或链接发给我，我通过 `open_design` 连接画布。
3. 我按本 PRD 绘制：三栏布局、Step 1 五问卡、Step 2 带 ◎〇△ 的长处列表、《使用说明书》卡片、100 例 / 30 问抽屉、导师对话面板。

> 注：此前已产出相关 Ardot 图（云端 fileId）：LLM 提示词架构图（710630790445620）、章节任务配置模板（710631995475007）、LLM 运行时数据流图（710635388127241）、第四章 LLM 设计修正与导师融合（710643309154221），可作为视觉与提示词架构参考。

---

## 10. 参考文件

- 原书 PDF：第 139–174 页（正文章节「擅长的事」）
- 原书第五章 HTML：`backend/book/.../05-strength.html`（或 mineru 提取版）
- 原书第五章 MD：`chapter_md/第五章-只要找到_擅长的事_，就可以应用到工作中.md`
- 后端权威配置（new-schema）：`../../config/chapters/chapter_config_ch05.json`（由 `seed_all_chapters.py` 灌入 `chapter_configs` 表）；角色系统提示见 `../../scripts/seed_roles.py`。git HEAD 中的旧版单步「九宫格」配置已作废。
- 上下文层配置（统一 Agent 架构）：`../../config/chapters/chapter_config_ch05.json`（core_concepts / mentor / few_shot）
- 题库权威源：`chapter_md/问题清单.md`（擅长的事 30 问 + 100 例清单）
- 平台总 SPEC：`SPEC.md`
- 前期章节 PRD：`PRD-ch4.md`；后续章节 PRD：`PRD-ch6.md`、`PRD-ch7.md`、`PRD-ch8.md`
- 设计原型：`platform/prototype/ch05_exercise_mockup.html`
