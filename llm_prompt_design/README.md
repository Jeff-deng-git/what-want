# LLM 提示词设计交付物（统一目录）

> 本目录汇总了《如何找到想做的事》交互式自我认知平台的全部 LLM 提示词设计产物。
> 按「文档 / 配置 / 图片」三类分桶，取代原先散落在 `platform/`、`llm_config/`、`根目录` 的混乱布局。
> 整理时间：2026-08-03

---

## 目录结构

```
llm_prompt_design/
├── README.md                      本索引
├── docs/                          设计规范 / 总结 / PRD / 总览
│   ├── LLM提示词设计总结.md        四件套 + 第四章修正 + 导师融合 的总览
│   ├── mentor_design_spec.md       全书级导师（刘老师）设计规范（权威规格）
│   ├── 全书重构设计总览.md          ★ 伞文档：站在全书角度统一定义 mentor+summary+8章+统一运行时
│   ├── 工程实施交接文档.md          ★★ 单一权威入口(v2.0)：实施/评审只须读此一份即可串起全部信息；已内联 7 项决策(ADR-001)+评审纠错(references 两机制/类型化 output_fields/agent_configs/SPEC 已对齐)+逐章 step→文档映射+桥接卡B+验收。其余文档仅溯源
│   ├── 站点重构与开发计划.md        ★ 通读 platform 代码后的代码级重构计划：SPEC偏差审计、7项决策(已拍板)、M0–M6里程碑、SPEC更新清单
│   ├── ADR-001-exercises-schema.md  ★ 架构决策记录：为何选 exercises 原生(Option B)、references 跨步引用、output_fields 类型化(oneOf)
│   ├── 重构plan_待设计拍板.md       另一 agent 的 review plan（M1–M6 实施草案，4 项待拍板）
│   └── 重构plan_设计侧回复.md       ★ 对上份 review 的评审回复：Q1/Q2/Q4 已闭环、Q2 机制纠错、Q3 拍板(agent_configs hybrid)
│   └── PRD/
│       ├── PRD-ch1.md             第一章（误区·认知解构层）
│       ├── PRD-ch2.md             第二章（内外标准·分辨层）
│       ├── PRD-ch3.md             第三章（三要素公式·框架层）
│       ├── PRD-ch4.md             第四章（价值观·5步级联，价值观源头）
│       ├── PRD-ch5.md
│       ├── PRD-ch6.md
│       ├── PRD-ch7.md
│       └── PRD-ch8.md
├── config/                        JSON 配置与 Schema（给编程 Agent + 运行时）
│   ├── schema/
│   │   └── chapter_task_config.schema.json   统一 Schema（含 mentor_hooks + exercises[references 跨步引用 / output_fields 类型化 oneOf]）
│   ├── mentor/
│   │   └── mentor_config.json                全书级导师配置（人设 / 苏格拉底策略 / 跨章示例 / exercise_informed_dialogue）
│   ├── agents/
│   │   └── summary_config.json              全书级摘要生成配置（消除 summary.py 硬编码）
│   └── chapters/
│       ├── chapter_config_ch01.json ~ ch08.json   8 章任务配置（均含 mentor_hooks + 练习交互字段；output_fields 全部类型化对象，ch04 为 canonical：5步 references 级联）
│       └── chapter_config.ch03.example.json       第三章配置示例
└── assets/                        设计图（Ardot 导出 PNG）
    ├── LLM提示词架构图.png
    ├── 章节任务配置模板.png
    ├── LLM运行时数据流图.png
    └── 第四章LLM设计修正与导师融合.png
```

---

## Ardot 云端设计图（fileId 映射）

| 设计图 | fileId | 本地 PNG |
|---|---|---|
| LLM 提示词架构图 | `710630790445620` | `assets/LLM提示词架构图.png` |
| 章节任务配置模板 | `710631995475007` | `assets/章节任务配置模板.png` |
| LLM 运行时数据流图 | `710635388127241` | `assets/LLM运行时数据流图.png` |
| 第四章 LLM 设计修正与导师融合 | `710643309154221` | `assets/第四章LLM设计修正与导师融合.png` |

打开方式：`https://ardot.tencent.com/file/<fileId>`

---

## 各角色怎么用

| 角色 | 用什么 | 说明 |
|---|---|---|
| 你 / 产品 / 设计 | 4 张 Ardot 图 | 用 fileId URL 审阅整体结构、字段契约、第四章修正方向 |
| 编程 Agent | `config/` 下的 schema + 8 份 JSON + `assets/` 下的数据流图 | 照 schema 写 Loader：按 `chapter_id` 读对应 JSON + 章节 MD → 拼成纯文本 prompt |
| 运行时 | `config/chapters/*.json` + `config/mentor/mentor_config.json` + 各章 `.md` | 作为真实数据，由 Loader 在应用侧读取注入 |

---

## 重要说明

- **`seed_ch4.py` 不在本目录**：它是 `platform/backend/seed_ch4.py` 下的**活代码**（写入 DB 的第四章 5 步配置源），保持原位不动。重跑方式：`cd D:\AI_Project\What_Want\platform\backend && python seed_ch4.py`。
- **JSON 不被运行时硬加载**：`config/` 下的 JSON 是「设计源文件 / 数据契约」，运行时配置实际在数据库（由 seed 脚本写入）；应用代码不读取 `llm_config/` 路径，故本目录移动不会影响程序。
- **全书统一重构视角**：本目录所有产物（8 章 PRD + 配置 + 导师规范 + 总览）已从「第四章改写」升级为「全书统一重构」——mentor（全书常驻苏格拉底导师）与 summary（全书常驻摘要 Agent）同走 `app/runtime/` 统一运行时，共享 `learner_profile` 跨章档案。详见 `docs/全书重构设计总览.md`。
- **各章「摘要生成」LLM 已纳入统一架构**：设计侧已落地 `config/agents/summary_config.json`（消除 `summary.py` 的 `SUMMARY_SYSTEM` 硬编码）；`chat.py` 的「刘老师」硬编码同理将由 `mentor_config.json` + 运行时取代。代码接入属工程重构范围（见总览 §6）。
- 详见 `docs/LLM提示词设计总结.md`、`docs/mentor_design_spec.md` 与 `docs/全书重构设计总览.md`。
