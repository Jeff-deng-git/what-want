# PRD：What Want 平台 · 第二章《我们为什么会因为找不到想做的事而迷茫》

> 文件：`PRD-ch2.md`
> 对应章节：原书第二章（迷茫根源 / 内外标准）
> 状态：待审 → 设计稿 → 开发
> 设计基调：继承 `PRD-ch4.md` §6「书卷气」视觉体系；全书重构视角下文。
> 全书定位：ch2 是**内外标准分辨层**。它消费 ch1 的 `external_voices`（用户自检出的外部声音），并把结论沉淀为 `learner_profile` 的 `internal_external_ratio` / `reclaim_item`，是刘老师解释「你为什么迷茫」的关键支点。

---

## 0. 关键发现：第二章是「迷茫」的归因章，承接 ch1

全书流水线中，ch2 紧接 ch1：

```
ch1 解构误区（外部声音从哪来）→ ch2 区分内外标准（外部声音如何导致迷茫）→ ch3 建立三要素公式
```

ch2 的核心论断：**迷茫是因为用「外部标准」（别人觉得好 / 赚钱 / 体面）做选择，而非「内部标准」（自己的价值观与满足感）**。它用三个实证素材支撑：外部优势会随时间崩塌（市值前 50 变迁）、选择越多越瘫痪（果酱实验）、外部过滤器 vs 内心过滤器。

ch2 同样只有一个轻量练习（内外标准对照），但它是**连接 ch1 外部声音与 ch3+ 内部标准的第一座桥**——刘老师在 ch2 可引用 ch1 的 `external_voices`，指出「你 ch1 写的那个外部声音，正在这里变成你的选择标准」。

> ⚠️ **重构提示**：ch2 配置尚未 seed 入 DB（同 ch1），本次重构需补 seed 并映射产出到 `learner_profiles`。

---

## 1. 第二章内容摘要（基于正文）

### 1.1 核心概念

- **外部标准**：社会/他人期待、薪资排名、热门行业、体面——随时间变化、不反映真实自我。
- **内部标准**：你自己的价值观与满足感——稳定、可依赖。
- **迷茫的根因**：选择依据落在外部标准，导致「达成也不开心」「越选越乱」。
- **三个实证**：①外部优势 30 年就变（市值前 50 变迁）②选择越多越瘫痪（果酱实验）③外部过滤器（赚钱/体面/人气 → 无热情工作）vs 内心过滤器（喜欢/擅长/重要）。

### 1.2 配套练习

- **内外标准对照表**：用户列出当前主要事项，逐件标注「外部驱动 / 内部驱动」，可补充推动自己的声音或理由，找出「最该收回主动权」的一件事。

---

## 2. 可设计成互动的部分

### 2.1 通用阅读层（与 ch4–ch8 一致）

同 `PRD-ch1.md` §2.1。

### 2.2 本章练习（轻量，1 个）

#### 内外标准对照

- 页面结构：
  - 阶段 1「填写」：可增删事项行；每行填写事项、选择「外部驱动/内部驱动」、可选填写推动你的声音或理由；至少 2 件，顶层可补充 `notes`。
  - 阶段 2「AI 分析」：展示结合本章正文、事项、drive 标签和 note 的 Markdown `commentary`；展示后端按事项数量派生的 `internal_external_ratio`；展示 `reclaim_item` 草稿。
  - 阶段 3「确认并提交」：`commentary` 和 ratio 只读，用户可接受、修改、完全重写或留空 `reclaim_item`，点击「确认并提交」后整步锁定。
  - 阶段 4「沉淀归档」：提示已了解用户信息，展示「对话」入口；「重新做本章」创建新 draft，历史 submitted run 保留。
- LLM 输出 `commentary`（逐项映照）+ `internal_external_ratio`（后端按件数派生）+ `reclaim_item`（用户可编辑文本）。LLM 不负责计算 ratio，也不替用户改 drive 标签。
- LLM 的活是**发现盲点**：很多人把「外部驱动」误标成「内部」（如「我喜欢加班因为能学东西」——其实可能是外部认可驱动）。LLM 点出矛盾，不替用户定性。

### 2.3 右侧 tab 面板

| tab | 第二章内容 |
|-----|-----------|
| 摘要 | 基于本章 MD：内外标准定义、三个实证、迷茫根因、内外过滤器对比 + 关键流程编号。 |
| 对话 | 刘老师基于对照结果 + ch1 外部声音做追问（如「你 ch1 写『父亲的选错行说教』，现在这份额里是不是又出现了？」）。 |
| 步骤 | 内外标准对照 runner。 |
| 笔记 | 选区笔记 + 独立笔记。 |

### 2.4 导师「刘老师」融合设计（mentor）

- **knows**：book_md + 已提交的 user_progress（事项/drive/note、后端 ratio、reclaim_item）+ ch1 的 `misconceptions_cleared`、`external_voices`（跨章引用）。
- **grounding_rules**：引用 ch1 外部声音建立连续性；指出内外标准矛盾；不替用户定性。
- **示例对话**（取自 `mentor_config.json` 的 `exercise_informed_dialogue`）：
  - 用户 ch2 标「为体面加班」最该收回主动权 → 刘老师在后续对话引用此锚点。

---

## 3. 需要大模型介入的部分

| 场景 | LLM 角色 | 作用 | 输出位置 |
|------|---------|------|---------|
| **内外标准对照辅助** | psychologist / 通用教练 | 读用户标注，发现自相矛盾处，给出映照与「收回主动权」建议。 | commentary + internal_external_ratio + reclaim_item |
| **导师对话** | mentor（刘老师） | 结合 ch1 外部声音做苏格拉底追问。 | 对话 tab |
| **章节摘要生成** | summary（图书编辑） | 生成 `{summary, core_concepts[], key_process[]}`。 | 摘要 tab |

> 三调用统一走 `app/runtime/`，配置驱动（详见《全书重构设计总览》）。

---

## 4. 推荐的工作流配置（chapter_config JSON）

> 等价于 `config/chapters/chapter_config_ch02.json`。

```json
{
  "chapter_id": "ch02",
  "chapter_title": "我们为什么会因为找不到想做的事而迷茫",
  "exercises": [
    {
      "name": "内外标准对照",
      "instruction": "列出你当前在做的主要事项，逐件标注是『外部驱动』还是『内部驱动』，并写下推动你的声音或理由。",
      "worksheet": "事项 / 驱动类型 / 推动你的声音或理由",
      "user_action": "用户至少列出 2 件当前主要事项，逐件自己标注『外部驱动/内部驱动』并可补充备注。LLM 必须结合事项、驱动标签和备注发现自相矛盾处，不替用户定性。",
      "llm_role": "assist",
      "output_fields": [
        {"name": "commentary", "type": "markdown", "readonly": true},
        {"name": "internal_external_ratio", "type": "table", "readonly": true},
        {"name": "reclaim_item", "type": "text", "lockable": true}
      ],
      "few_shot_examples": [
        {
          "user": "事项：加班做项目。我标内部驱动，因为『能学到东西』。备注：领导会看到我的进步。",
          "assistant": "你把它标成了内部驱动，但备注里出现了『领导会看到』这个外部评价线索。可以继续观察：如果没有人知道这件事，也没有升职或认可，你还会愿意用同样的时间投入吗？"
        }
      ]
    }
  ],
  "mentor_hooks": {
    "focus": "区分外部期待与内在标准",
    "references": ["misconceptions_cleared", "external_voices"]
  }
}
```

---

## 5. 数据模型与输出 schema

### 5.1 内外标准对照输出

```json
{
  "commentary": "你 7 个事项里有 5 个外部占比过半，最明显的是『为体面加班』……",
  "internal_external_ratio": {"external_pct": 62, "internal_pct": 38, "method": "item_count"},
  "reclaim_item": "为体面而做的加班"
}
```

- `internal_external_ratio`：后端按 `drive_items[].drive` 的件数派生，LLM 不负责计算或修改；汇入 `learner_profile`。
- `reclaim_item`：最该收回主动权的事项，汇入 `learner_profile`，供刘老师后续引用；阶段 3 允许用户改写或留空。
- `commentary`：Markdown 只读分析，必须结合用户具体事项、drive 标签和 note，不得只是章节摘要或输入复述。

---

## 6. 视觉与交互规范

### 6.1 继承 ch4 书卷气体系（颜色/字体/纸纹一致）

### 6.2 第二章专属视觉

- **内外标准对照行**：每行左右两个占比条（外部=灰蓝 / 内部=赭石），直观显示失衡。
- **矛盾高亮**：LLM 检测到「标内部但实际外部」时，该行闪现提示徽章。
- **收回主动权卡**：底部高亮 `reclaim_item`，纸张便签样式。

---

## 7. 验收标准

- [ ] 第二章正文渲染完整，内外标准定义与三个实证正确呈现。
- [ ] 内外标准对照表可增删事项、标记驱动、补充备注、提交。
- [ ] LLM 输出 `commentary` + `internal_external_ratio` + `reclaim_item`，正确汇入 `learner_profile`。
- [ ] 刘老师对话能引用 ch1 `external_voices` + 本章 `reclaim_item` 做跨章追问。
- [ ] 通用功能与 ch4–ch8 一致。

---

## 8. 已确认的实现决策

1. 不提供滑块或用户手填 ratio；ratio 由后端按 `drive_items[].drive` 件数派生，输出 `external_pct`、`internal_pct`、`method:"item_count"`。
2. `reclaim_item` 是单段 `text`；阶段 3 可接受、编辑、完全重写或留空；提交后整步锁定。
3. ch02 step 和 mentor 都通过现有 profile 引用 ch01 的 `misconceptions_cleared`、`external_voices`；不新增 `external_voices_summary`。
4. ch02 → ch04 只复用已有 profile，不新增专用 API/UI；缺少 ch02 时 ch04 只提示、不阻断。
5. 重跑创建新 draft，历史 submitted run 保留；下游读取最新 submitted 版本。
6. 暂不实现字段级锁定、多个 reclaim 候选、专用跨章字段 API、前后两次分析差异 UI。

---

## 9. 与 Ardot 画布的衔接

同 `PRD-ch4.md` §9：绘制三栏布局、内外标准对照行、占比条、收回主动权卡、刘老师对话面板。

---

## 10. 参考文件

- 原书第二章 MD：`chapter_md/第二章-我们为什么会因为_找不到想做的事而迷茫.md`
- 上下文层配置：`../../config/chapters/chapter_config_ch02.json`
- 全书级导师配置：`../../config/mentor/mentor_config.json`
- 导师设计规范：`../../docs/mentor_design_spec.md`
- 全书重构总览：`../../docs/全书重构设计总览.md`
- 相邻章节 PRD：`PRD-ch1.md`、`PRD-ch3.md` ~ `PRD-ch8.md`
