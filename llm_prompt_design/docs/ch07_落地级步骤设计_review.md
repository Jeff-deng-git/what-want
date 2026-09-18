# ch07 落地文档 Review（基于 ch06 六轮教训主动预检）

> 生成时间：2026-08-13
> 背景：ch06 经历 6 轮设计↔开发契约 review 才最终收敛，每轮都暴露新的契约/一致性问题。本 review 在 ch07 进入开发实施前，**主动**把 ch06 六轮暴露的 10 类典型问题逐一映射到 ch07 预检，避免重蹈覆辙。
> 权威基准：`config/chapters/chapter_config_ch07.json`（config 为唯一权威）；后端实测代码（`db.py` / `context_requirements.py` / `compaction.py` / `assembler.py` / `agent.py`）。

## §0 结论

- **ch07 config 上游键本身正确**：`step_context.references` / `mentor_hooks.references` = `[talents, likes, work_purpose, values]`，不读 ch03、不消费 `importance`、弃用 `intersection`（改用 `ideal_works`）。这部分早于 ch06 六轮就已对齐，无需改。
- **最大风险是设计文档对 ch06 第六轮拍板的 `stale` 机制零承接**：ch07 落地文档 / PRD-ch7 原写"零迁移/零新增"，且全文无 `stale` 字样；进入门禁只锁 ch4/ch5/ch6 文案、缺 stale 维度与 `len(likes)>0` 完成判定。
- **跨文档旧键残留 2 处**：`全书重构设计总览.md` 把 ch7 产出写成 `intersection`（应为 `ideal_works`）、`mentor_design_spec.md` 漏 `values`。
- **本次已主动修正 11 处设计文档 + ch07 config instruction**，并列出后端 4 类待办（归开发侧实施，设计侧不改代码）。

## §1 ch06 教训 → ch07 检查清单（10 类逐项结论）

| 类 | ch06 教训 | ch07 预检结论 | 严重度 | 处理 |
|---|---|---|---|---|
| A | 零迁移 vs stale 列冲突 | ch07 文档原写"零新增表/列/迁移" | 阻塞 | ✅ 已修（落地 §8.1 / §10.2 / PRD §4 改 stale 列沿用） |
| B | likes 权威来源 | 原只写"ch06 likes"，未指明 step-2 | 非阻塞 | ✅ 已修（落地 §5 / config instruction 显式标注 ch06 step-2 `submitted&stale=0`） |
| C | stale 过滤覆盖 | ch07 文档全篇无 stale | 阻塞 | ✅ 已修（落地 §10.1.2 统一读取语义 `status='submitted' AND stale=0`） |
| D | summary 隔离 | ch07 无 summary 节点、不消费 likes | — | ✅ 已对齐，无需改 |
| E | 门禁双校验 | 原只锁 ch4/5/6 文案，缺 stale 维度 | 阻塞 | ✅ 已修（落地 §10.1.1 双校验） |
| F | canonical 写入 | `ideal_works` step-1/step-2 同键缺规则 | 阻塞 | ✅ 已修（落地 §8.1 canonical 规则，仿 ch06 §8.8） |
| G | 跨文档残留 | 全书重构 `intersection`、mentor 漏 `values` | 阻塞 | ✅ 已修（全书重构 L49/L96、mentor L149） |
| H | 路径错误 | 无 `app/runtime/step_runner` 误引 | — | ✅ 已对齐，无需改 |
| I | 白名单一致性 | 文档未谎称 `ideal_works` 已加 | — | ✅ 已对齐，无需改 |
| J | ch07 内部 stale 传播 | 原完全未讨论 | 阻塞 | ✅ 已修（落地 §10.1.2 三动作事务） |

## §2 设计侧已修正清单（11 处，均已落盘）

1. **ch07 落地 §0**（L24）："前 3 章" → "前序三章 ch04/ch05/ch06"。
2. **ch07 落地 §5**（L73）：`likes` 行补注"权威来源 = `learner_profile.likes`，即 ch06 step-2 成功提交（`status='submitted' AND stale=0`）的结构化 likes；ch06 step-1 的 likes 永不入 profile、不参与 ch07 组合"。
3. **ch07 落地 §5**（L76）：ch06 预告措辞改写（去"×重要/三者交集"旧稿，改为"用工作目的含价值观筛选"）。
4. **ch07 落地 §8.1**（L97）："零新增表/列/迁移" → "ideal_works 自身零新增表/列" + 补 `stale` 列沿用说明。
5. **ch07 落地 §8.1**（L98 后）：新增 `ideal_works` canonical 写入规则（仿 ch06 §8.8 方案 A）。
6. **ch07 落地 §10.1.1**（新增）：进入门禁双校验（a/b/c 三上游 `submitted&stale=0` + profile 键非空，含 `len(likes)>0`）。
7. **ch07 落地 §10.1.2**（新增）：ch07 内部 stale 传播（三动作事务 + 统一读取语义）。
8. **ch07 落地 §10.2**（L142）："零迁移" → "stale 机制已承接 ch06 第六轮拍板"。
9. **ch07 config step-1 instruction**：补"ch6 喜欢之事取 ch06 step-2 已提交、`profile.likes` 的结构化版本，非 step-1 领域级"（JSON 已校验合法）。
10. **PRD-ch7 §4 / §5 / §7**：零迁移→stale 列、预告措辞、门禁双校验（含 `init_db()` 补 stale 列待办）。
11. **全书重构 L49/L96 + mentor_design_spec L149**：去 ch3 歧义、intersection→ideal_works、mentor 补 `values`。

备份：`docs/backups/pre-ch07-review-2026-08-13_*` 共 5 份（ch07 config / ch07 落地 / PRD-ch7 / 全书重构 / mentor_design_spec）。

## §3 后端代码待办（开发侧实施，设计侧不改代码）

ch07 复用 ch06 第六轮拍板的同一套机制，开发侧须确认以下存在（部分为 ch06 第六轮债）：

1. **`app/db.py` `init_db()`**：幂等 `ALTER TABLE step_runs ADD COLUMN stale INTEGER NOT NULL DEFAULT 0`（try/except 吞重复列）。ch07 全部 step-run 读取依赖此列。
2. **`app/runtime/context_requirements.py:11-15`**：ch07 上游改为 `ch04:(work_purpose,values) / ch05:(talents) / ch06:(likes)`，移除 `ch03`（当前代码仍登记 ch03，与已拍板口径冲突）。
3. **`app/runtime/context_requirements.py:57-61`**：上游就绪查询加 `AND (stale IS NULL OR stale = 0)`。
4. **12 个 stale 过滤入口**（沿用 ch06 清单）：`book.py:160,376` / `steps.py:207,226,484,521,740` / `agent.py:171` / `chat.py:98,117` / `services/step_runner.py:48` / `context_requirements.py:57-61`。ch07 step-2 读 step-1 `ideal_works` 的 `references.from_exercise` 解析路径（`steps.py:484,740`）须带 `stale=0`。
5. **`app/services/compaction.py`**：`PROFILE_FIELDS`/`STRUCTURED_FIELDS`/`MANDATORY_DOWNSTREAM_FIELDS` 三处加入 `ideal_works` + reseed 消除 DRIFT。ch07 提交逻辑绕过通用 `_flatten_outputs` 同名覆盖，用显式非-stale 选取（仿 ch06 §8.8）。

## §4 冲突安全

- 本轮仅改文档文字 + ch07 config instruction（字符串微调，JSON 已校验合法），**未碰 ch03/ch04/ch05/ch06 的 config / output / 上下文字段**。
- ch07 config 的 `step_context`/`mentor_hooks.references` 未变（仍 `[talents,likes,work_purpose,values]`），纯增量补充 instruction 说明，零冲突。
- ch03 仅修正文字表述（`importance`/`intersection` 仍在 compaction 白名单、未删字段）；ch04/ch05/ch07 其他章零影响。
- 备份齐全，任何回滚可用 `docs/backups/pre-ch07-review-2026-08-13_*`。

## §5 转发小结

ch07 已按 ch06 六轮教训**全量预检并修正**，开发侧实施前无需再等第六轮提问暴露同类问题。后端 `stale` 迁移与 `context_requirements.py` 上游映射修正为 ch06 第六轮债，ch07 复用同套机制即可。建议开发侧凭 §3 实施，并回归：① 上游章重提交后 ch07 门禁即时回退锁定；② ch07 step-1 重提交旧 step-2 `stale=1` + `profile.ideal_works=[]`；③ step-2 读 step-1 取最新非 stale。
