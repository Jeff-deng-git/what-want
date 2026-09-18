"""Step runner: orchestrates user input + LLM call + output parsing + persistence.

Flow:
1. Load chapter config (JSON)
2. Get user answers (or generate from prev step outputs)
3. Build prompt via Jinja2 with cross-step references
4. Call LLM
5. Parse output according to schema
6. Persist to step_runs table
"""
import json
import os
import uuid
from typing import Optional

from app.db import get_conn
from app.services.prompt_renderer import PromptRenderer
from app.services.llm_client import call_llm


class StepRunner:
    def __init__(self):
        self.renderer = PromptRenderer()

    def get_step_config(self, chapter_id: str, step_id: str) -> dict:
        """读取章节配置中特定 step 的定义。"""
        with get_conn() as conn:
            row = conn.execute(
                "SELECT config_json FROM chapter_configs WHERE chapter_id = ? AND active = 1 ORDER BY version DESC LIMIT 1",
                (chapter_id,),
            ).fetchone()
        if not row:
            raise ValueError(f"No active config for chapter {chapter_id}")
        config = json.loads(row["config_json"])
        for step in config.get("steps", []) or []:
            if step.get("step_id") == step_id:
                return step
        for ex in config.get("exercises", []) or []:
            if ex.get("step_id") == step_id or ex.get("name") == step_id:
                return ex
        raise ValueError("Step " + str(step_id) + " not found in chapter " + str(chapter_id))

    def get_prior_outputs(self, chapter_id: str, current_step_id: str) -> dict:
        """查找同一章前面已提交步骤的输出。用 normalize 后的 key。"""
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT step_id, user_answers, parsed_output
                   FROM step_runs
                   WHERE chapter_id = ? AND status = 'submitted' AND stale = 0
                   ORDER BY created_at""",
                (chapter_id,),
            ).fetchall()
        ctx = {}
        for r in rows:
            parsed = json.loads(r["parsed_output"]) if r["parsed_output"] else {}
            sid = r["step_id"]
            sid_norm = sid.replace("-", "_")
            data = {
                "answers": json.loads(r["user_answers"]) if r["user_answers"] else [],
                "output": parsed,
            }
            ctx[sid_norm] = data
            ctx[sid] = data  # both keys
        return ctx

    def build_context(self, chapter_id: str, current_step_id: str, user_answers: list) -> dict:
        """构建 Jinja2 渲染上下文：prior_outputs + 本步 user_answers。

        step_id 中的连字符 (`step-1`) 标准化为下划线 (`step_1`) 以匹配
        Jinja2 变量命名规则。
        """
        ctx = self.get_prior_outputs(chapter_id, current_step_id)
        # Normalize step_id (step-1 -> step_1)
        normalized_id = current_step_id.replace("-", "_")
        ctx[normalized_id] = {"answers": user_answers}
        # Also store under original key for flexibility
        ctx[current_step_id] = {"answers": user_answers}
        return ctx

    async def run_step(
        self,
        chapter_id: str,
        step_id: str,
        user_answers: list,
        role_row: dict,
        preserve_output: dict = None,
    ) -> dict:
        """执行步骤：渲染 prompt -> 调 LLM -> 解析 -> 与 preserve 合并 -> 持久化。

        preserve_output (optional): 当前已保存的输出。锁定元素会原样保留。
        """
        step = self.get_step_config(chapter_id, step_id)
        llm_op = step.get("llm_op", {})
        template = llm_op.get("prompt_template", "")
        output_schema = llm_op.get("output_schema", {})

        # Build template context with prior outputs + this step's answers
        ctx = self.build_context(chapter_id, step_id, user_answers)
        # Always provide preserve_output (even empty) so templates can use `{% if %}` safely
        ctx["preserve_output"] = preserve_output or {}
        rendered = self.renderer.render(template, ctx)

        # Call LLM
        api_key = os.getenv(f"{role_row['provider'].upper()}_API_KEY", "")
        if not api_key:
            raise ValueError(f"No API key for provider {role_row['provider']}")

        json_mode = output_schema.get("type") in ("structured", "editable_list", "list")
        response = await call_llm(
            provider=role_row["provider"],
            model=role_row["model"],
            api_key=api_key,
            system=role_row["system_prompt"],
            user=rendered,
            temperature=role_row.get("temperature", 0.7),
            max_tokens=role_row.get("max_tokens", 2000),
            json_mode=json_mode,
        )

        # Parse output
        try:
            parsed = self._parse_output(response, output_schema)
            parse_error = None
        except Exception as parse_err:
            parsed = {"raw": response, "parse_error": str(parse_err)}
            parse_error = f"parse error: {parse_err}"

        # Merge with preserve_output (locked items preserved)
        if preserve_output and not parse_error:
            parsed = self._merge_with_locked(parsed, preserve_output, output_schema)

        # Save to step_runs
        run_id = str(uuid.uuid4())
        status = "failed" if parse_error else "saved"
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO step_runs
                   (id, chapter_id, step_id, user_answers, referenced_outputs,
                    role_id, rendered_prompt, llm_response, parsed_output,
                    status, error, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (
                    run_id, chapter_id, step_id,
                    json.dumps(user_answers),
                    json.dumps(ctx),
                    role_row["id"],
                    rendered,
                    response,
                    json.dumps(parsed) if not parse_error else None,
                    status,
                    parse_error,
                ),
            )
        return {
            "run_id": run_id,
            "parsed": parsed,
            "rendered_prompt": rendered,
            "status": status,
        }

    def _merge_with_locked(self, new_parsed: dict, old_parsed: dict, schema: dict) -> dict:
        """合并新输出与旧输出：旧输出中的 locked 元素原样保留。

        处理 editable_list 类型字段（如 keywords, ranked）。
        """
        merged = dict(new_parsed)
        for field in schema.get("fields", []):
            fname = field["name"]
            field_type = field.get("type", "")
            if "list<" in field_type or field_type == "list<string>":
                old_list = old_parsed.get(fname, [])
                if not old_list:
                    continue
                # Identify locked items from old
                locked = [x for x in old_list if isinstance(x, dict) and x.get("locked")]
                if not locked:
                    continue
                # Ensure new list is in object form
                new_list = merged.get(fname, [])
                new_normalized = []
                for item in new_list:
                    if isinstance(item, str):
                        new_normalized.append({"value": item, "locked": False})
                    else:
                        new_normalized.append(dict(item, locked=False))
                # Prepend locked items (they don't get replaced)
                merged[fname] = locked + new_normalized
        return merged

    def _parse_output(self, raw: str, schema: dict) -> dict:
        """Parse LLM output according to output_schema. Raise on parse failure
        so the caller (run_step) can persist status='failed' + error."""
        schema_type = schema.get("type", "markdown")
        if schema_type == "markdown":
            return {"markdown": raw}
        # For structured/list, JSON is required.
        try:
            # Extract JSON from raw (may be wrapped in ```json ...```)
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[1:])
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM output is not valid JSON for schema type={schema_type!r}: {e}")
