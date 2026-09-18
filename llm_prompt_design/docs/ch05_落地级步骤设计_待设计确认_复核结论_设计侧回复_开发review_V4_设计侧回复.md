# ch05 设计侧回复（V4 复审 + 双专家深度复核收口）

> 本文件为对 `ch05_落地级步骤设计_待设计确认_复核结论_设计侧回复_开发review_V4.md` 的设计侧最终回复，并整合了应需求启动的**第二轮双专家深度 review（架构 + 产品管理）**结论。
> **开发侧阅读入口（唯一交接文件）**：`docs/ch05_落地级步骤设计.md`（§0–§10）。字段契约以 `config/chapters/chapter_config_ch05.json` 为准；LLM 角色原文见 `docs/PRD/PRD-ch5.md` §3.1；视觉/交互对齐见 `platform/prototype/ch05_exercise_mockup.html` + 原书 `chapter_md/第五章-*.md`。本文为沟通件，不进落地文档 refer。

---

## 一、V4 复审 4 项 — 全部已修复并落盘

| 项 | V4 问题 | 修复 | 落盘位置 |
|---|---|---|---|
| V4-1 | 旧数据流残留（config label + 落地 P1-3 仍写「提交时并入 talents」） | label 改为用户语言，去掉「即加入 talents/提交时并入」 | `chapter_config_ch05.json` label、`docs/ch05_落地级步骤设计.md` §10 P1-3 |
| V4-2 | `reference_strengths` payload 字符串数组 vs 对象数组不一致 | 统一为对象数组 `[{text}]`（方案 A），与 config `list_of_items`+`item_schema` 一致 | mockup `addFromExample` 改 `push({text})` |
| V4-3 | 100 例清单载体未定义 | 权威载体 = `ui_context.strength_examples`（随 active config 发布，前端读 config，不另接接口），100 条 `{id,text,becomes_strength?,becomes_weakness?}` | config + `config/schema/chapter_task_config.schema.json`（新增 `strength_examples` 属性）+ 落地 §8.3/§10 |
| V4-4 | 草稿持久化契约缺失 | 新增 §8.6 草稿持久化契约（跨刷新恢复 / 时间戳 / 不进下游 / 保存失败明示 / 回归测试） | `docs/ch05_落地级步骤设计.md` §8.6 |

**一致性校验（已通过）**：旧数据流残留 config/落地/PRD/mockup 全 = 0；`ui_context.strength_examples` config=100、schema 合法（无 `additionalProperties:false`）；mockup `STRENGTH_EXAMPLES` 对象数组就位、`id:'s01'..'s100'` 完整。

---

## 二、双专家深度复核结论（2026-08-11 第二轮）

应需求「确认所有设计合理，不会再有问题」，拉架构设计专家 + 产品管理专家做只读深度 review（读 config/schema/落地/PRD/mockup/原书/运行时代码）。

**结论：架构与产品双层面均无 P0，设计合理、不会再有问题。**

- **架构专家**：P0=0。config↔schema 一致、`strength_examples` 已同步 schema、`reference_strengths` 对象数组一致、100 例数据流自洽、状态机同构（submitted 态 409 与 `steps.py` 一致）、`talents` 已在 compaction 白名单**零迁移**。残留 P1=4 全为**开发侧实现跟踪项**，P2=2（schema `item_template` 命名通病、评审记录历史注记）。
- **产品专家**：P0=0。三栏布局/100 例抽屉/◎〇△ 控件/空评级提交/文案一致性均 OK。唯一 P1（step-2 评级图例缺失）**设计侧已于本轮修复**；其余 P2 为开发侧实现或后续迭代建议。
- 完整记录：`docs/ch05_专家评审记录_v2.md`。

---

## 三、设计侧本轮已修（仅 mockup 原型，未动运行时代码）

1. **P1 评级图例**：step-2 评级列表上方加 ◎〇△ 含义图例（◎ 有充实感且与成功有关 / 〇 有充实感 / △ 目前还不确定；附注「ch7 以◎为主、目标 10/理想 20」），文案复用 PRD §1.4 / 原书。
2. **P2 文案对齐**：「运行 LLM 汇总」→「让教练汇总并建议 ◎〇△」（左栏步骤说明、reflabel、引用 toast 三处统一为真实按钮名，消除用户困惑）。
3. **P2 极性视觉**：100 例抽屉「用对/用错」加绿/橙配色（`.epolar .good/.bad`）。
4. 备份：`.backups_ch05_20260811_v7/ch05_exercise_mockup.html.orig`。

---

## 四、开发侧待办（请开发处理，设计侧不动代码）

设计侧已给出清晰契约与字段定义，开发侧按以下落地即可，无新设计歧义：

- **P0-1 reseed**：ch05 config 覆盖旧九宫格，消除 `check_config_consistency.py --chapter ch05` DRIFT（`missing_in_db=step_context,ui_context`）。
- **P1 后端合并去重**：assembler 加 ch05 专用 merge/dedup 分支，结构性保证 `step-1.talents ∪ reference_strengths` 去重并标 `source:'100_examples'`（对齐 ch04 step-2 特判）。
- **P1 ch07 gating**：`context_requirements.py` 补 ch07 读 ch05 `status`/`talents`（现登记为 ch03 生产者，缺失不拦截）。
- **P1 talents 剥离 locked**：`compaction.py` 落库前剥离 `talents.locked`（低优先级，风险可控）。
- **P1 契约测试**：`test_assembler.py`/`test_step_runner.py` 补 ch05 `strength_examples`/`reference_strengths`/级联/409 场景。
- **P2 草稿真实持久化 + 失败提示**：按落地 §8.6 落地 localStorage/后端持久化与保存失败明示（原型仅静态演示意图）。
- **P2 整体导出**：才能清单 + ◎〇△ 评级整体导出入口（单个 `user_manual` 导出已有）。
- **P2 题库服务**：30 问清单接入（100 例已由 config 载体解决）。

---

## 五、最终收口说明

- 设计侧交付物（四份 + 双专家评审记录 v2 + 本回复）已齐备且自洽。
- V4 四项 + 深度复核均**无 P0**；唯一产品侧 P1 已修；其余全为开发侧实现跟踪项。
- **设计侧结论：ch05 设计合理，不会再有问题；待开发侧按第四节收口后，即可端到端贯通。**
