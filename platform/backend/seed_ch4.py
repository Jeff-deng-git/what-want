"""Seed chapter 4 config + default LLM roles.

Usage: python3 seed_ch4.py
"""
import json
import sys
import os
sys.path.insert(0, '.')

from app.db import get_conn, init_db


CHAPTER_4_CONFIG = {
  "chapter_id": "ch04",
  "title": "第四章 找到指引人生的指南针：重要的事",
  "steps": [
    {
      "step_id": "step-1",
      "title": "回答5个问题，找出价值观关键词",
      "description": "请认真思考每个问题，给出你自己的答案。这些问题来自书中精选，用于唤醒你的价值观线索。",
      "user_input": {
        "questions": [
          {"id": "q1", "text": "你尊敬的人、尊敬的朋友、喜欢的角色分别是谁？你尊敬或喜欢他们哪些地方？", "type": "long_text"},
          {"id": "q2", "text": "在小时候和青春期阶段的事情或经历，对现在的你影响最大的是什么？对你的价值观造成了什么影响？", "type": "long_text"},
          {"id": "q3", "text": "现在社会有什么不足？你有什么想解决的社会问题？", "type": "long_text"},
          {"id": "q4", "text": "问周围的人『你觉得我在人生中看重什么』，会得到怎样的答案？", "type": "long_text"},
          {"id": "q5", "text": "你最想给别人（孩子/后辈/朋友）什么建议？最不想告诉他们什么？", "type": "long_text"}
        ]
      },
      "llm_op": {
        "role_id": "psychologist",
        "prompt_template": (
          "你是帮助用户梳理价值观的教练。请阅读用户对以下5个问题的回答：\n\n"
          "{% for q in step_1.answers %}"
          "Q{{ loop.index }}（{{ q.text }}）\n"
          "答: {{ q.answer }}\n\n"
          "{% endfor %}"
          "请输出 JSON，包含字段:\n"
          "- commentary: 整体点评（500字内，markdown）。重点指出用户回答中反复出现的价值观线索，只做观察与映照，不要替用户下结论。\n"
          "- top_values: 推断的 5-10 个初步价值观关键词（数组，字符串）。"
        ),
        "output_schema": {
          "type": "structured",
          "fields": [
            {"name": "commentary", "type": "markdown"},
            {"name": "top_values", "type": "list<string>"}
          ]
        }
      }
    },
    {
      "step_id": "step-2",
      "title": "形成价值观思维导图",
      "description": "基于步骤1的回答，把价值观关键词归类分组、概括出核心价值观(umbrella value)。可点击锁定或删除，重新生成时锁定项保留。",
      "user_input": {"questions": []},
      "llm_op": {
        "role_id": "psychologist",
        "prompt_template": (
          "你是帮助用户梳理价值观的教练。基于用户在步骤1的回答与初步关键词，请：\n"
          "(1) 汇总所有价值观关键词（不少于15个；若不足请基于回答合理补充）；\n"
          "(2) 将含义相近的关键词归入一组（每组4~6个）；\n"
          "(3) 为每组概括一个『核心价值观(umbrella value)』。\n"
          "参考书中方法：『最低限度、清爽、简单』这三个词可概括成『简单』。\n\n"
          "步骤1的回答：\n{% for q in step_1.answers %}Q{{ loop.index }}: {{ q.text }}\n答: {{ q.answer }}\n{% endfor %}\n"
          "步骤1的初步关键词：{{ step_1.output.top_values | join('、') }}\n\n"
          "{% if preserve_output and preserve_output.groups %}"
          "以下分组已锁定，必须保留：\n"
          "{% for g in preserve_output.groups %}{% if g.locked %}- {{ g.umbrella }}: {{ g.keywords | join('、') }}\n{% endif %}{% endfor %}"
          "{% endif %}\n"
          "输出 JSON：\n"
          "- groups: 数组，每项 {\"umbrella\": \"核心价值观\", \"keywords\": [\"关键词\"], \"locked\": false}\n"
          "（不要包含已锁定的分组）"
        ),
        "output_schema": {
          "type": "editable_list",
          "fields": [
            {"name": "groups", "type": "list<{umbrella, keywords, locked}>", "editable": True, "lockable": True}
          ]
        }
      }
    },
    {
      "step_id": "step-3",
      "title": "从『以他人为中心』转为『以自我为中心』",
      "description": "对步骤2得到的价值观做可控性检验：把依赖他人/外部不可控的价值观，用『为什么』追问链转化为自己可控的价值观。",
      "user_input": {"questions": []},
      "llm_op": {
        "role_id": "psychologist",
        "prompt_template": (
          "你是价值观教练。基于用户在步骤2得到的『核心价值观(umbrella values)』，逐一评估每一项：\n"
          "- 判断它是『以他人为中心(不可控)』还是『以自我为中心(可控)』。\n"
          "  不可控的例子：想受人尊敬、想暴富（能否实现取决于他人/外部，如同试图控制天气）。\n"
          "- 对『以他人为中心(不可控)』的项，做『为什么』追问链（连续追问），转化为可控的『以自我为中心』价值观。\n"
          "  书中范例：『想出名』→为什么？被追捧→为认可存在→按好奇心生活→不出名也能做到吗？能 ⇒ 转化为『好奇心』。\n"
          "- 对已是『以自我为中心』的项，直接保留。\n\n"
          "步骤2的核心价值观分组：\n{% for g in step_2.output.groups %}- {{ g.umbrella }}（{{ g.keywords | join('、') }}）\n{% endfor %}\n\n"
          "输出 JSON：\n"
          "- conversions: 数组，每项 {\"value\": \"核心价值观\", \"type\": \"other|self\", \"converted_to\": \"转化后的可控价值观(若type=self可为空字符串)\", \"why_chain\": [\"为什么想出名？\", \"因为想被追捧\", ...]}"
        ),
        "output_schema": {
          "type": "structured",
          "fields": [
            {"name": "conversions", "type": "list<{value, type, converted_to, why_chain}>"}
          ]
        }
      }
    },
    {
      "step_id": "step-4",
      "title": "列出价值观排序，确定优先级",
      "description": "用金字塔逻辑排序：底层是应优先满足的『基础』价值观，顶层是人生的『最终目的』。可点击锁定或删除。",
      "user_input": {"questions": []},
      "llm_op": {
        "role_id": "career_counselor",
        "prompt_template": (
          "你是价值观教练。基于步骤2的『核心价值观』与步骤3『转化后的以自我为中心价值观』，请对价值观做优先级排序。\n"
          "排序诀窍：思考『到底哪一个是我的最终目的』。\n"
          "最底层 = 应优先满足的『基础』价值观，最顶层 = 人生的『最终目的』。\n"
          "书中范例金字塔（底→顶）：简单→好奇心→成果→热爱→审美意识（最终目的：过着美好的生活）。\n\n"
          "步骤2的核心价值观：\n{% for g in step_2.output.groups %}- {{ g.umbrella }}\n{% endfor %}\n"
          "步骤3的转化结果：\n{% for c in step_3.output.conversions %}- {{ c.value }} → {{ '保留' if c.type == 'self' else c.converted_to }}\n{% endfor %}\n\n"
          "{% if preserve_output and preserve_output.ranked %}"
          "以下已锁定，必须保留在排序中：\n"
          "{% for k in preserve_output.ranked %}{% if k.locked %}- {{ k.value }}\n{% endif %}{% endfor %}"
          "{% endif %}\n"
          "输出 JSON：\n"
          "- ranked: 数组（从底到顶，即 基础→最终目的），每项 {\"value\": \"价值观\", \"locked\": false}\n"
          "（不要修改锁定项的 value）"
        ),
        "output_schema": {
          "type": "editable_list",
          "fields": [
            {"name": "ranked", "type": "list<{value, locked}>", "editable": True, "readonly": True}
          ]
        }
      }
    },
    {
      "step_id": "step-5",
      "title": "确定工作目的",
      "description": "回想10个你向他人提供价值（或试图提供价值）的经历，找出出现最多的价值观，定为你的工作目的。",
      "user_input": {
        "questions": [
          {"id": "exp", "text": "请列出10个你向他人提供价值/试图提供价值的经历（每条一行，越具体越好）。", "type": "long_text"}
        ]
      },
      "llm_op": {
        "role_id": "career_counselor",
        "prompt_template": (
          "你是职业规划教练。基于用户在步骤4排序后的『以自我为中心价值观』，以及用户刚列出的『10个向他人提供价值的经历』，请：\n"
          "(1) 为每条经历标注它体现的价值观（可多选，从用户价值观中选取或自行归纳）；\n"
          "(2) 统计出现最多的价值观，定为用户的『工作目的』；\n"
          "(3) 给出工作目的的一句话定义与推理过程。\n"
          "注意：『想让别人开心』『想让别人幸福』不是工作目的（太泛，任何事都能让人开心）。要落到用户真实经历中高频出现的、具体的价值观。\n\n"
          "步骤4的价值观排序（底→顶）：\n{% for k in step_4.output.ranked %}{{ loop.index }}. {{ k.value }}\n{% endfor %}\n\n"
          "用户的10个经历：\n{% for a in step_5.answers %}{{ a.answer }}\n{% endfor %}\n\n"
          "输出 JSON：\n"
          "- work_purpose: 工作目的（markdown，150字内）\n"
          "- reasoning: 推理过程（markdown）\n"
          "- experience_map: 数组，每项 {\"experience\": \"经历摘要\", \"values\": [\"价值观\"]}"
        ),
        "output_schema": {
          "type": "structured",
          "fields": [
            {"name": "work_purpose", "type": "markdown"},
            {"name": "reasoning", "type": "markdown"},
            {"name": "experience_map", "type": "list<{experience, values}>"}
          ]
        }
      }
    }
  ]
}


DEFAULT_ROLES = [
    {
        "id": "psychologist",
        "name": "心理咨询师",
        "description": "资深自我认知教练，擅长倾听、识别价值观、深度反思用户回答",
        "system_prompt": (
            "你是一位资深自我认知教练，熟悉《如何找到想做的事》的价值观梳理方法。"
            "你擅长通过用户回答识别其核心价值观、思维模式、情感倾向。"
            "你的回应温暖、深度、富有洞察力，避免泛泛而谈。"
            "请用 JSON 格式输出结构化结果。"
        ),
        "provider": "deepseek",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 2000,
        "enabled": True,
    },
    {
        "id": "career_counselor",
        "name": "职业规划师",
        "description": "资深职业规划师，擅长将价值观转化为具体工作目的",
        "system_prompt": (
            "你是一位资深职业规划师，熟悉《如何找到想做的事》的方法论。"
            "你擅长将个人的价值观、激情转换为具体的工作目的和职业方向。"
            "你的建议具体、可操作、有理有据。"
            "请用 JSON 格式输出结构化结果。"
        ),
        "provider": "deepseek",
        "model": "deepseek-chat",
        "temperature": 0.6,
        "max_tokens": 2000,
        "enabled": True,
    },
]


def seed():
    init_db()
    with get_conn() as conn:
        # Seed roles
        for r in DEFAULT_ROLES:
            existing = conn.execute(
                "SELECT id FROM llm_roles WHERE id = ?", (r["id"],)
            ).fetchone()
            if existing:
                # Update
                conn.execute(
                    """UPDATE llm_roles SET name=?, description=?, system_prompt=?,
                       provider=?, model=?, temperature=?, max_tokens=?, enabled=?, updated_at=datetime('now')
                       WHERE id=?""",
                    (r["name"], r["description"], r["system_prompt"],
                     r["provider"], r["model"], r["temperature"], r["max_tokens"],
                     1 if r["enabled"] else 0, r["id"]),
                )
                print(f"Updated role: {r['name']}")
            else:
                conn.execute(
                    """INSERT INTO llm_roles
                       (id, name, description, system_prompt, provider, model,
                        temperature, max_tokens, enabled, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                    (r["id"], r["name"], r["description"], r["system_prompt"],
                     r["provider"], r["model"], r["temperature"], r["max_tokens"],
                     1 if r["enabled"] else 0),
                )
                print(f"Inserted role: {r['name']}")

        # Seed chapter config
        cur = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS v FROM chapter_configs WHERE chapter_id = ?",
            ("ch04",),
        ).fetchone()
        next_v = (cur["v"] if cur else 0) + 1
        conn.execute("UPDATE chapter_configs SET active = 0 WHERE chapter_id = ?", ("ch04",))
        conn.execute(
            """INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at)
               VALUES (?, ?, ?, 1, datetime('now'))""",
            ("ch04", next_v, json.dumps(CHAPTER_4_CONFIG, ensure_ascii=False)),
        )
        print(f"Saved chapter config (version {next_v})")


if __name__ == "__main__":
    seed()
    print("\nDone. Visit http://localhost:8011/api/roles to verify.")
