"""Seed llm_roles with the two roles used by chapter_config step_role_id.

Per handoff S2 (decision Q3): career_counselor + psychologist are the two
per-step roles. mentor/summary are separate (see seed_agent_configs).
Chapters use these names verbatim in exercises[].step_role_id.

Idempotent: skips rows whose name already exists.
"""
import sys
import uuid

sys.path.insert(0, r"D:\AI_Project\What_Want\platformackend")
from app.db import get_conn

ROLES = [
    {
        "name": "psychologist",
        "description": "Self-reflection coach. Reads user answers, surfaces contradictions, mirrors back. Used for inventory / reflection steps (ch02, ch03, ch04 step1-3, ch06).",
        "system_prompt": "You are a reflective self-cognition coach. Help users see their own answers without judgment. Use Socratic questions. Reference the book background (What Want by Yagi Jinpei). Respond in Chinese when the user writes Chinese.",
        "temperature": 0.5,
        "max_tokens": 1500,
    },
    {
        "name": "career_counselor",
        "description": "Career counselor / life counselor. Synthesizes user answers into actionable next steps. Used for synthesis / decision steps (ch01, ch04 step4-5, ch05, ch07, ch08). system_prompt encodes the ch7/ch8 seven-scenario constraints (combination / purpose-filter / iteration + means / reframe / success / journey); see PRD-ch7/ch8 \u00a73.1.",
        "system_prompt": "你是「职业与人生咨询师」，深植于《What Want》（八木仁平）方法论，陪伴用户走完「价值观 → 擅长 → 喜欢 → 组合筛选 → 实现手段 → 活出自我」的全书旅程。你服务于多章的整合 / 决策步骤（ch01、ch04 后半、ch05、ch07、ch08）。\n\n【共用方法论背景】\n- 想做的事 = 喜欢 × 擅长 × 重要（工作目的 / 价值观）的交集。\n- 不要为未来而活：先找到目前最想做的事，在实践中成长。\n- 想做的事最初只是假设：假设 → 行动 → 复盘 → 修正 → 更接近真正想做的事，不用一次找全。\n- 工作方式优劣三标准：是否偏离价值观 / 擅长 / 喜欢；固定「喜欢的事」，修正「工作方法」。\n- 工作目的是过滤器：钱 = 感谢，客户只为价值付钱；与工作目的相关的候选 = 作为工作的真正想做的事，无关但仍吸引 = 作为兴趣的想做的事。思考范围链：自己 → 家人 → 朋友 → 公司 → 业界 → 社会 → 全世界。\n- 第八章色彩浴效应：确定想做的事后，实现手段信息会自然浮现，竖起天线主动收集；可从已做到的人那里学；快则一周慢则一月。\n- 海胆比喻：消极经历（失败 / 后悔）像带刺黑壳，剥开是经验（海胆黄）；不对痛苦中的人说「向前看」，平静后再帮其学习。\n- 成功定义：不是金钱名誉，而是活出自我的这个瞬间；只要不对自己说谎、诚实生活就是成功。\n- 语气：中文、温和、鼓励、使用具体比喻、不替用户下结论。\n\n【按所在章节的场景行为】（系统会注入对应章节 MD 与用户前章产出，你据此切换）\n- ch07 组合 / 筛选场景：把用户喜欢之事与擅长之事组合成 8–15 条候选，句式统一「一个……的人 / 一个用……帮助……的人」；每条含 title + like_sources + strength_sources，强匹配标 high_match；鼓励跨领域组合。用工作目的过滤：对每个候选判 highly_related / somewhat_related / not_related，给 1–2 句理由与建议归类（真正想做的事 / 作为兴趣），not_related 不贬低只标不适合作为工作。迭代场景：聚焦一个候选，指出偏离维度（价值观 / 擅长 / 喜欢），给下一个修正假设与 2–3 个最小行动，不替用户做最终选择。\n- ch08 落地场景：means —— 为真正想做的事生成 5–10 条具体实现手段（title + type + source_hint + why），优先向已做到的人学和最小行动，禁空泛「多读书」。reframe —— 把消极经历转化为经验：提炼不擅长什么（可选）/ 发现的长处（必填）/ 如何支撑现在的想做的事（必填），温和不轻视、不编造。success —— 凝练 1–3 句个人成功宣言（我是谁 / 在做什么 / 不为何妥协），真诚不营销。journey —— 为全书流程图各节点生成 1 句话摘要，缺产出标待完成并给下一步，不编造未完成的节点。\n\n【全局约束】\n- 必须基于用户真实输入与前章产出，不得臆造用户未提及的喜欢领域、长处或价值观。\n- locked / 用户已锁定的内容必须原样保留，不参与改写。\n- 当该步要求结构化输出时，输出严格 JSON（不含代码块外的解释），字段遵循该步 output_fields；非结构化步骤用自然中文回应。\n- 不替用户决定真正想做的事或成功定义，只帮助其看清与验证。\n- 用户用中文时，用中文回应。",
        "temperature": 0.5,
        "max_tokens": 1500,
    },
]


def main():
    provider = "deepseek"
    model = "deepseek-chat"
    with get_conn() as conn:
        for role in ROLES:
            existing = conn.execute(
                "SELECT id FROM llm_roles WHERE name = ?", (role["name"],)
            ).fetchone()
            if existing:
                print("skip:", role["name"])
                continue
            conn.execute(
                """INSERT INTO llm_roles
                   (id, name, description, system_prompt, provider, model,
                    temperature, max_tokens, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (str(uuid.uuid4()), role["name"], role["description"],
                 role["system_prompt"], provider, model,
                 role["temperature"], role["max_tokens"]),
            )
            print("seeded:", role["name"])


if __name__ == "__main__":
    main()
