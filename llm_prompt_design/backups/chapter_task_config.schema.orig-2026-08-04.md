{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ChapterTaskConfig",
  "description": "每章 LLM 任务配置模板。运行时由统一 Agent 按 chapter_id 动态加载，与系统层、上下文层拼装为完整 Prompt。8 章复用同一 Schema，仅字段内容不同。",
  "type": "object",
  "required": [
    "chapter_id",
    "chapter_title",
    "md_source",
    "core_concepts",
    "guiding_questions",
    "output_template",
    "few_shot_examples"
  ],
  "properties": {
    "chapter_id": {
      "type": "string",
      "description": "章节唯一标识，如 ch03。运行时据此加载对应配置与 MD。"
    },
    "chapter_title": {
      "type": "string",
      "description": "章节标题，用于上下文与前端 UI 展示。"
    },
    "md_source": {
      "type": "string",
      "description": "对应章节 MD 正文路径（已为纯文本 + 图内文字总结），作为知识上下文源。"
    },
    "core_concepts": {
      "type": "array",
      "items": { "type": "string" },
      "description": "本章核心知识点，写入上下文层，帮助模型把握章节主旨。"
    },
    "guiding_questions": {
      "type": "array",
      "items": { "type": "string" },
      "description": "引导用户思考 / 回答的问题清单，是任务层的核心。"
    },
    "exercises": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "step_id": { "type": "string", "description": "练习 / 步骤唯一标识（如 step-1）。references.from_exercise 据此指代前序步骤；未设则按数组顺序隐式编号。" },
          "name": { "type": "string", "description": "练习 / 工作表名称" },
          "instruction": { "type": "string", "description": "练习指引" },
          "method": { "type": "string", "description": "方法说明（书中方法 / 操作路径），作为 LLM 辅助纠偏的依据，不直接喂用户。" },
          "worksheet": { "type": "string", "description": "工作表字段模板" },
          "user_action": { "type": "string", "description": "用户主操作描述（勾选/填写/标注），LLM 不替用户下判断，仅辅助。" },
          "llm_role": { "type": "string", "enum": ["assist", "guide", "none"], "description": "LLM 在本练习中的角色：assist=辅助纠正/深化/取交集；guide=引导但不判断；none=纯用户自评。" },
          "references": {
            "type": "array",
            "description": "跨步引用：声明本步需注入哪些前序 exercise 的哪些 output_fields。由 build_step_prompt 从同章已 submitted 的 step_runs.parsed_output 取前序字段注入（解决 ch4 五步级联）。受 ≤3k assembler 护栏约束，仅按需注入、不全量。",
            "items": {
              "type": "object",
              "properties": {
                "from_exercise": { "type": "string", "description": "被引用步骤的 step_id，如 step-1" },
                "fields": { "type": "array", "items": { "type": "string" }, "description": "要注入的该步 output_fields 字段名（省略则注入该步全部 output）" }
              },
              "required": ["from_exercise"]
            }
          },
          "output_fields": {
            "type": "array",
            "description": "本练习产出并落库 / 汇入 learner_profile 的字段。兼容两种写法：① 字符串（如 \"groups\"，等价 {name, type:unknown}）；② 对象（带类型 / 渲染元数据，推荐）。前端 renderStepOutput 按 type 分支渲染。",
            "items": {
              "oneOf": [
                { "type": "string" },
                {
                  "type": "object",
                  "properties": {
                    "name": { "type": "string", "description": "字段名（落库键 / learner_profile 键）" },
                    "type": { "type": "string", "enum": ["markdown", "text", "editable_list", "list", "number", "select", "json", "table"], "description": "渲染/存储类型：markdown=富文本渲染；text=纯文本输入；editable_list=可编辑列表(chip，支持锁定)；list=只读列表；number=数字；select=单选；json=原生 JSON；table=表格(行数组)。" },
                    "readonly": { "type": "boolean", "description": "true=用户不可编辑（如 step-4 ranked 的只读排序项）。默认 false。" },
                    "lockable": { "type": "boolean", "description": "true=用户可锁定以阻止 LLM 覆盖（如 groups 分组）。默认 false。" }
                  },
                  "required": ["name"]
                }
              ]
            }
          },
          "few_shot_examples": { "type": "array", "items": { "type": "object", "properties": { "user": { "type": "string", "description": "用户操作/输入示例" }, "assistant": { "type": "string", "description": "LLM 辅助回复示例" } }, "required": ["user", "assistant"] }, "description": "练习交互示例（用户操作 → LLM 辅助），作为 few-shot 供 step 模式 LLM 参考。" },
          "step_role_id": {
            "type": "string",
            "description": "本步调用的角色键（指向 llm_roles.name，如 psychologist / career_counselor / mentor）。原书/PRD 的多步多角色经统一重构后，每步锁定单一角色；前端据此展示角色标签。"
          },
          "allow_role_override": {
            "type": "boolean",
            "description": "true=前端允许用户在 UI 切换本步角色（罕见）；默认 false，前端以静态标签+锁图标展示，不渲染下拉。",
            "default": false
          },
          "input_schema": {
            "type": "array",
            "description": "声明本 exercise 的结构化输入字段（替代旧 worksheet/user_action 散文字段），前端按 type 渲染对应控件。ch01 用 checklist，ch02 用 list_of_items。",
            "items": {
              "type": "object",
              "properties": {
                "name": { "type": "string", "description": "字段键（落库 user_answers 的键）" },
                "label": { "type": "string", "description": "UI 显示名（缺省用 name）" },
                "type": { "type": "string", "enum": ["text", "list_of_items", "checklist", "select", "radio"], "description": "控件类型：text=多行文本；list_of_items=开放列表(每项可带子字段，如 drive 外部/内部)；checklist=固定 N 项(每项含 ❌/✅ 对照 + 勾选 + 外部声音文本)；select/radio=单选。" },
                "required": { "type": "boolean", "default": false },
                "placeholder": { "type": "string" },
                "default": {},
                "show_when": { "type": "string", "description": "触发条件：always / checked / 表达式" },
                "options": { "type": "array", "items": { "type": "string" }, "description": "select/radio 的选项；checklist 时为固定项定义数组" },
                "item_template": { "type": "object", "description": "list_of_items/checklist 每项的子字段模板，如 list_of_items 的 {text, drive(select external/internal)}" }
              },
              "required": ["name", "type"]
            }
          }
        },
        "required": ["name", "instruction"]
      },
      "description": "本章练习或工作表（可选）。每个 exercise 即一步；step_id 稳定后可被后续 exercise 的 references 引用。"
    },
    "output_template": {
      "type": "string",
      "description": "期望的回答 / 产出格式约束，约束模型输出结构。"
    },
    "few_shot_examples": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "user": { "type": "string", "description": "用户示例发言" },
          "assistant": { "type": "string", "description": "教练式示例回复" }
        },
        "required": ["user", "assistant"]
      },
      "description": "1–2 组引导对话示例，作为 few-shot。"
    },
    "mentor_hooks": {
      "type": "object",
      "description": "导师入口钩子：声明本章苏格拉底焦点与优先引用的跨章学习者档案字段。",
      "properties": {
        "focus": {
          "type": "string",
          "description": "本章苏格拉底焦点（一句话），指导刘老师在本章的追问方向。"
        },
        "references": {
          "type": "array",
          "items": { "type": "string" },
          "description": "优先引用的 learner_profile 字段名（如 work_purpose / talents / likes），严格对应档案键。"
        },
        "entry_prompt": {
          "type": "string",
          "description": "进入本章时刘老师的开场白模板（可选）。"
        }
      },
      "required": ["focus"]
    }
  }
}
