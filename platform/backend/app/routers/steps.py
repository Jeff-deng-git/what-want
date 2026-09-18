"""Steps API -- execute and manage step runs. M3 refactor."""
import json
import logging
import os
import re
import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from collections.abc import Mapping
from typing import Any, Optional

from app.db import get_conn
from app.runtime.agent import ContextIntegrityError, run_step as agent_run_step
from app.runtime.assembler import merge_preserved_output
from app.runtime.config_loader import load_chapter_config, load_profile
from app.services.compaction import compact_profile
from app.services.llm_client import LLMEmptyResponseError, LLMTimeoutError
from app.services.step_runner import StepRunner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chapters/{chapter_id}/steps", tags=["steps"])
runner = StepRunner()


def _require_upstream_context(chapter_id: str):
    from app.runtime.context_requirements import get_upstream_context_status

    status = get_upstream_context_status(chapter_id, os.getenv("DEFAULT_USER_ID", "local"))
    if status and not status["ready"]:
        missing = "; ".join(
            producer + ": " + ", ".join(fields)
            for producer, fields in status["missing_profile_fields"].items()
        )
        detail = "Chapter context incomplete"
        if missing:
            detail += ": " + missing
        raise HTTPException(409, detail)


def _build_ui_context(chapter_id: str, chapter_cfg: dict) -> dict:
    """Return only the profile fields explicitly allowed for UI rendering."""
    ui_context = chapter_cfg.get("ui_context") or {}
    refs = ui_context.get("references") or []
    context = {}
    strength_examples = ui_context.get("strength_examples")
    if isinstance(strength_examples, list):
        context["strength_examples"] = strength_examples
    passion_examples = ui_context.get("passion_examples")
    if isinstance(passion_examples, list):
        context["passion_examples"] = passion_examples
    values_examples = ui_context.get("values_examples")
    if isinstance(values_examples, list):
        context["values_examples"] = values_examples
    if chapter_id == "ch06":
        profile = load_profile(os.getenv("DEFAULT_USER_ID", "local")) or {}
        talents = profile.get("talents")
        if isinstance(talents, list):
            context["reference_talents"] = [
                {"text": str(item.get("text") if isinstance(item, Mapping) else item).strip()}
                for item in talents
                if str(item.get("text") if isinstance(item, Mapping) else item).strip()
            ]
    if not refs:
        return context
    profile = load_profile(os.getenv("DEFAULT_USER_ID", "local")) or {}
    if "external_voices" in refs:
        voices = profile.get("external_voices")
        labels = {}
        ch01_cfg = load_chapter_config("ch01") or {}
        for exercise in ch01_cfg.get("exercises") or []:
            for field in exercise.get("input_schema") or []:
                if field.get("name") != "misconceptions":
                    continue
                for item in field.get("items") or []:
                    item_id = str(item.get("id", ""))
                    if item_id:
                        labels[item_id] = str(item.get("label") or item_id)
        entries = []
        if isinstance(voices, dict):
            def sort_key(pair):
                key = str(pair[0])
                try:
                    return (0, int(key))
                except ValueError:
                    return (1, key)
            for item_id, voice in sorted(voices.items(), key=sort_key):
                voice_text = str(voice or "").strip()
                if not voice_text:
                    continue
                item_id = str(item_id)
                entries.append({
                    "misconception_id": item_id,
                    "misconception_label": labels.get(item_id, item_id),
                    "voice_text": voice_text,
                })
        if entries:
            context["external_voices"] = entries
    return context


class DraftIn(BaseModel):
    user_answers: Any
    new_run: bool = False


class RunIn(BaseModel):
    user_answers: Any
    role_id: Optional[str] = None  # only required for legacy jinja2 path
    preserve_output: Optional[dict] = None


class OutputEdit(BaseModel):
    parsed_output: dict
    user_answers: Optional[Any] = None




def _persist_run(run_id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status):
    """Persist a run without overwriting a previously submitted run.

    Reuse only the run id selected by _get_or_create_run_id (draft/saved).
    A new id is inserted after a failed or submitted run so history remains intact.
    """
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, status FROM step_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if existing and existing["status"] != "submitted":
            conn.execute(
                """UPDATE step_runs
                   SET user_answers = ?, role_id = ?, rendered_prompt = ?,
                       llm_response = ?, parsed_output = ?, status = ?,
                       updated_at = datetime('now'), error = NULL
                   WHERE id = ? AND status != 'submitted'""",
                (json.dumps(user_answers), role_id, rendered_prompt,
                 llm_response, json.dumps(parsed_output), status, run_id),
            )
            return run_id
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (run_id, chapter_id, step_id, json.dumps(user_answers), role_id,
             rendered_prompt, llm_response, json.dumps(parsed_output), status),
        )
        return run_id


def _mark_failed_run(run_id, chapter_id, step_id, user_answers, error):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, status FROM step_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if existing and existing["status"] == "saved":
            # A retry must never erase the learner's usable saved result.
            conn.execute(
                "UPDATE step_runs SET error = ?, updated_at = datetime('now') WHERE id = ?",
                (error, run_id),
            )
            return
        if existing:
            conn.execute(
                "UPDATE step_runs SET user_answers = ?, rendered_prompt = '', status = 'failed', error = ?, llm_response = '', parsed_output = NULL, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(user_answers), error, run_id),
            )
            return
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt,
                llm_response, parsed_output, status, error, updated_at)
               VALUES (?, ?, ?, ?, '', '', '', NULL, 'failed', ?, datetime('now'))""",
            (run_id, chapter_id, step_id, json.dumps(user_answers), error),
        )

def _try_parse_json(text):
    """Best-effort JSON parse. Returns {} on failure (LLM may return prose)."""
    if not text:
        return {}
    text = text.strip()
    if not (text.startswith("{") or text.startswith("[")):
        return {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}


def _validate_parsed_against_types(parsed, output_fields):
    """Lightweight type check per Q6 (i)+(iii): warn but do not block (Q6).

    For each declared output_field, verify the parsed value matches the type
    hint. Failures only log a warning; the parsed output is still persisted.
    Frontend renderStepOutput does the strict rendering per type (handoff S7.0).
    """
    if not isinstance(parsed, dict) or not output_fields:
        return
    for f in output_fields:
        name = f.get("name")
        ftype = f.get("type", "")
        if not name or name not in parsed:
            continue
        v = parsed[name]
        if ftype in ("editable_list", "list"):
            if not isinstance(v, list):
                logger.warning("output field %s expected %s, got %s", name, ftype, type(v).__name__)
        elif ftype == "table":
            if not isinstance(v, (list, dict)):
                logger.warning("output field %s expected table, got %s", name, type(v).__name__)
        elif ftype in ("text", "markdown"):
            if not isinstance(v, str):
                logger.warning("output field %s expected %s, got %s", name, ftype, type(v).__name__)
        elif ftype == "number":
            try:
                float(v)
            except (TypeError, ValueError):
                logger.warning("output field %s expected number, got %r", name, v)


def _get_or_create_run_id(chapter_id, step_id):
    """Return existing draft id or create a fresh one.

    Review P0-3: if the most recent run is ``submitted``, do not reuse it
    for a new LLM run -- create a brand new run id so the submitted row
    is preserved. A failed or submitted latest run starts a fresh run id so history remains intact.
    """
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, status FROM step_runs WHERE chapter_id = ? AND step_id = ? AND stale = 0 ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (chapter_id, step_id),
        ).fetchone()
        if existing and existing["status"] == "draft":
            return existing["id"]
        if existing and existing["status"] == "saved" and chapter_id != "ch03":
            return existing["id"]
        return str(uuid.uuid4())


@router.get("/{step_id}")
def get_step(chapter_id: str, step_id: str):
    """Get step definition + current run status."""
    try:
        step = runner.get_step_config(chapter_id, step_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    with get_conn() as conn:
        run = conn.execute(
            """SELECT id, user_answers, parsed_output, status, created_at, updated_at, submitted_at
               FROM step_runs WHERE chapter_id = ? AND step_id = ? AND stale = 0
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            (chapter_id, step_id),
        ).fetchone()
        stale_history = conn.execute(
            "SELECT COUNT(*) AS n FROM step_runs WHERE chapter_id = ? AND step_id = ? AND stale = 1",
            (chapter_id, step_id),
        ).fetchone()
    chapter_cfg = load_chapter_config(chapter_id) or {}
    return {
        "step_config": step,
        "current_run": dict(run) if run else None,
        "stale_history": bool(stale_history and stale_history["n"]),
        "ui_context": _build_ui_context(chapter_id, chapter_cfg),
    }


@router.post("/{step_id}/draft")
def save_draft(chapter_id: str, step_id: str, body: DraftIn):
    """Save draft (no LLM call).

    State machine guard (review.md P0-3): if the latest run is already
    ``submitted``, refuse to overwrite it. Instead create a new draft row
    so the original submission stays intact for the learner profile.
    """
    _require_upstream_context(chapter_id)
    try:
        runner.get_step_config(chapter_id, step_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    with get_conn() as conn:
        existing = conn.execute(
            """SELECT id, status FROM step_runs
               WHERE chapter_id = ? AND step_id = ? AND stale = 0
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            (chapter_id, step_id),
        ).fetchone()
        if existing and existing["status"] == "submitted":
            if not body.new_run:
                raise HTTPException(409, "step already submitted; set new_run=true to create a new draft")
            run_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO step_runs
                   (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status, updated_at)
                   VALUES (?, ?, ?, ?, '', '', '', NULL, 'draft', datetime('now'))""",
                (run_id, chapter_id, step_id, json.dumps(body.user_answers)),
            )
            return {"id": run_id, "ok": True, "status": "draft"}
        schema_errors = _validate_user_answers(
            _current_input_schema(chapter_id, step_id), body.user_answers, strict=False
        )
        if schema_errors:
            raise HTTPException(422, {"detail": "schema validation failed", "errors": schema_errors})
        if existing:
            conn.execute(
                """UPDATE step_runs
                   SET user_answers = ?, status = 'draft', error = NULL,
                       llm_response = '', parsed_output = NULL, submitted_at = NULL,
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (json.dumps(body.user_answers), existing["id"]),
            )
            return {"id": existing["id"], "ok": True, "status": "draft"}
        run_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, status, updated_at)
               VALUES (?, ?, ?, ?, '', '', '', 'draft', datetime('now'))""",
            (run_id, chapter_id, step_id, json.dumps(body.user_answers)),
        )
        return {"id": run_id, "ok": True, "status": "draft"}


@router.post("/{step_id}/run")
async def run_step(chapter_id: str, step_id: str, body: RunIn):
    """Trigger LLM execution via agent.run_step (M3 Option B).

    Legacy jinja2 path was removed in M3.3 per handoff Q9 (decision 1 = drop jinja2).
    All 8 chapters are on the exercises[] schema; step_runner still reads both
    schemas for backwards compatibility with older chapter_configs.
    """
    _require_upstream_context(chapter_id)
    return await _run_step_option_b(chapter_id, step_id, body)


async def _run_step_option_b(chapter_id, step_id, body):
    schema_errors = _validate_user_answers(
        _current_input_schema(chapter_id, step_id), body.user_answers, strict=True
    )
    if schema_errors:
        run_id = _get_or_create_run_id(chapter_id, step_id)
        _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, "; ".join(schema_errors))
        raise HTTPException(422, {"detail": "schema validation failed", "errors": schema_errors})
    run_id = _get_or_create_run_id(chapter_id, step_id)
    try:
        result = await agent_run_step(
            chapter_id,
            step_id,
            body.user_answers,
            return_details=True,
            preserve_output=body.preserve_output,
        )
        if isinstance(result, dict):
            raw = result.get("raw", "")
            rendered = (result.get("system_prompt", "") + "\n\n" + result.get("user_prompt", "")).strip()
        else:
            raw = result
            rendered = "(agent prompt unavailable)"
    except ContextIntegrityError as e:
        logger.warning("step context incomplete for %s/%s: %s", chapter_id, step_id, e)
        raise HTTPException(409, "Step context incomplete: " + str(e))
    except LLMTimeoutError as e:
        logger.error("agent.run_step timed out for %s/%s: %s", chapter_id, step_id, e)
        _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, str(e))
        raise HTTPException(504, "Step run failed: " + str(e))
    except LLMEmptyResponseError as e:
        logger.error("agent.run_step returned empty LLM content for %s/%s: %s", chapter_id, step_id, e)
        _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, str(e))
        raise HTTPException(502, "Step run failed: " + str(e))
    except Exception as e:
        logger.exception("agent.run_step failed for %s/%s", chapter_id, step_id)
        _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, str(e))
        raise HTTPException(500, "Step run failed: " + str(e))
    if not isinstance(raw, str) or not raw.strip():
        message = "Step run failed: LLM returned an empty response"
        _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, message)
        raise HTTPException(502, message)
    cfg = load_chapter_config(chapter_id) or {}
    ex = None
    for item in cfg.get("exercises") or []:
        if item.get("step_id") == step_id or item.get("name") == step_id:
            ex = item
            break
    role_id = (ex or {}).get("step_role_id") or "career_counselor"
    parsed = _try_parse_json(raw)
    _validate_parsed_against_types(parsed, (ex or {}).get("output_fields") or [])
    if _is_ch04_step(chapter_id, step_id):
        parsed = _normalize_ch04_run_output(parsed, step_id, body.user_answers)
        parsed = merge_preserved_output(parsed, body.preserve_output)
        parsed = _normalize_ch04_run_output(parsed, step_id, body.user_answers)
    elif _is_ch05_step(chapter_id, step_id):
        parsed = _normalize_ch05_run_output(parsed, step_id, body.user_answers)
        parsed = merge_preserved_output(parsed, body.preserve_output)
        parsed = _normalize_ch05_edit_output(parsed, step_id, parsed)
    elif _is_ch06_step(chapter_id, step_id):
        parsed = _normalize_ch06_run_output(parsed, step_id)
        parsed = merge_preserved_output(parsed, body.preserve_output)
        parsed = _normalize_ch06_edit_output(parsed, step_id, parsed)
    elif _is_ch07_step(chapter_id, step_id):
        parsed = _normalize_ch07_run_output(parsed, step_id)
        parsed = merge_preserved_output(parsed, body.preserve_output)
        parsed = _normalize_ch07_edit_output(parsed, step_id, parsed)
    else:
        parsed = merge_preserved_output(parsed, body.preserve_output)
    if _is_ch02_step(chapter_id, step_id):
        output_errors = _validate_ch02_output(parsed)
        if output_errors:
            message = "; ".join(output_errors)
            _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, message)
            raise HTTPException(502, "Step run failed: " + message)
        parsed = _normalize_ch02_output(parsed, body.user_answers)
    if _is_ch03_step(chapter_id, step_id):
        output_errors = _validate_ch03_output(parsed)
        if output_errors:
            message = "; ".join(output_errors)
            _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, message)
            raise HTTPException(502, "Step run failed: " + message)
    if _is_ch04_step(chapter_id, step_id):
        output_errors = _validate_ch04_output(
            parsed, step_id, body.user_answers, require_complete=step_id == "step-4"
        )
        if output_errors and step_id == "step-4":
            repair_feedback = "; ".join(output_errors)
            try:
                repaired_result = await agent_run_step(
                    chapter_id,
                    step_id,
                    body.user_answers,
                    return_details=True,
                    preserve_output=body.preserve_output,
                    repair_feedback=repair_feedback,
                )
                repaired_raw = repaired_result.get("raw", "") if isinstance(repaired_result, dict) else repaired_result
                repaired_rendered = (
                    repaired_result.get("system_prompt", "") + "\n\n" + repaired_result.get("user_prompt", "")
                ).strip() if isinstance(repaired_result, dict) else "(agent repair prompt unavailable)"
                repaired = _try_parse_json(repaired_raw)
                _validate_parsed_against_types(repaired, (ex or {}).get("output_fields") or [])
                repaired = _normalize_ch04_run_output(repaired, step_id, body.user_answers)
                repaired = merge_preserved_output(repaired, body.preserve_output)
                repaired = _normalize_ch04_run_output(repaired, step_id, body.user_answers)
                repaired_errors = _validate_ch04_output(
                    repaired, step_id, body.user_answers, require_complete=True
                )
                if not repaired_errors:
                    raw, rendered, parsed, output_errors = repaired_raw, repaired_rendered, repaired, []
                else:
                    output_errors = repaired_errors
            except ContextIntegrityError as e:
                _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, str(e))
                raise HTTPException(409, "Step context incomplete: " + str(e))
            except LLMTimeoutError as e:
                _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, str(e))
                raise HTTPException(504, "Step repair failed: " + str(e))
            except LLMEmptyResponseError as e:
                _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, str(e))
                raise HTTPException(502, "Step repair failed: " + str(e))
            except HTTPException:
                raise
            except Exception as e:
                logger.exception("agent.run_step repair failed for %s/%s", chapter_id, step_id)
                _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, str(e))
                raise HTTPException(500, "Step repair failed: " + str(e))
        if output_errors:
            message = "; ".join(output_errors)
            _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, message)
            raise HTTPException(502, "Step run failed: " + message)
    if _is_ch05_step(chapter_id, step_id):
        output_errors = _validate_ch05_output(parsed, step_id)
        if output_errors:
            message = "; ".join(output_errors)
            _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, message)
            raise HTTPException(502, "Step run failed: " + message)
    if _is_ch06_step(chapter_id, step_id):
        output_errors = _validate_ch06_output(parsed, step_id)
        if output_errors:
            message = "; ".join(output_errors)
            _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, message)
            raise HTTPException(502, "Step run failed: " + message)
    if _is_ch07_step(chapter_id, step_id):
        output_errors = _validate_ch07_output(parsed, step_id)
        if output_errors:
            message = "; ".join(output_errors)
            _mark_failed_run(run_id, chapter_id, step_id, body.user_answers, message)
            raise HTTPException(502, "Step run failed: " + message)
    _persist_run(run_id, chapter_id, step_id, body.user_answers, role_id,
                 rendered, raw, parsed, "saved")
    return {"id": run_id, "ok": True, "status": "saved",
            "llm_response": raw, "parsed_output": parsed, "role_id": role_id}


@router.put("/{step_id}/output")
def edit_output(chapter_id: str, step_id: str, body: OutputEdit):
    """User edits LLM output."""
    with get_conn() as conn:
        run = conn.execute(
            """SELECT id, status, user_answers, parsed_output FROM step_runs WHERE chapter_id = ? AND step_id = ? AND stale = 0
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            (chapter_id, step_id),
        ).fetchone()
        if not run:
            raise HTTPException(404, "No run to edit")
        if run["status"] == "submitted":
            raise HTTPException(409, "submitted step output is locked")
        parsed_output = dict(body.parsed_output or {})
        try:
            stored_user_answers = json.loads(run["user_answers"] or "{}")
        except (json.JSONDecodeError, TypeError):
            stored_user_answers = {}
        effective_user_answers = body.user_answers if body.user_answers is not None else stored_user_answers
        if body.user_answers is not None:
            schema_errors = _validate_user_answers(
                _current_input_schema(chapter_id, step_id), effective_user_answers, strict=False
            )
            if schema_errors:
                raise HTTPException(422, {"detail": "schema validation failed", "errors": schema_errors})
        if _is_ch02_step(chapter_id, step_id):
            try:
                user_answers = json.loads(run["user_answers"] or "{}")
                existing_output = json.loads(run["parsed_output"] or "{}")
            except (json.JSONDecodeError, TypeError):
                user_answers = {}
                existing_output = {}
            if "commentary" in parsed_output and parsed_output["commentary"] != existing_output.get("commentary"):
                raise HTTPException(409, "commentary is readonly")
            if "internal_external_ratio" in parsed_output and parsed_output["internal_external_ratio"] != existing_output.get("internal_external_ratio"):
                raise HTTPException(409, "internal_external_ratio is readonly")
            merged_output = dict(existing_output)
            if "reclaim_item" in parsed_output:
                merged_output["reclaim_item"] = parsed_output["reclaim_item"]
            output_errors = _validate_ch02_output(merged_output)
            if output_errors:
                raise HTTPException(422, {"detail": "output validation failed", "errors": output_errors})
            parsed_output = _normalize_ch02_output(merged_output, user_answers)
        if _is_ch03_step(chapter_id, step_id):
            try:
                existing_output = json.loads(run["parsed_output"] or "{}")
            except (json.JSONDecodeError, TypeError):
                existing_output = {}
            if "commentary" in parsed_output and parsed_output["commentary"] != existing_output.get("commentary"):
                raise HTTPException(409, "commentary is readonly")
            if "intersection" in parsed_output and parsed_output["intersection"] != existing_output.get("intersection"):
                raise HTTPException(409, "intersection is readonly")
            # 合并已有输出：保留只读字段，仅应用客户端提交的可编辑清单，避免 partial body 静默清空只读字段
            merged_output = dict(existing_output)
            for name in ("importance", "talents", "likes"):
                if name in parsed_output:
                    if not isinstance(parsed_output[name], list):
                        raise HTTPException(422, {"detail": "output validation failed", "errors": [f"output field '{name}' must be a list"]})
                    merged_output[name] = parsed_output[name]
            parsed_output = merged_output
            output_errors = _validate_ch03_output(parsed_output)
            if output_errors:
                raise HTTPException(422, {"detail": "output validation failed", "errors": output_errors})
        if _is_ch04_step(chapter_id, step_id):
            parsed_output = _normalize_ch04_run_output(parsed_output, step_id, effective_user_answers)
            output_errors = _validate_ch04_output(
                parsed_output, step_id, effective_user_answers, require_complete=False
            )
            if output_errors:
                raise HTTPException(422, {"detail": "output validation failed", "errors": output_errors})
        if _is_ch05_step(chapter_id, step_id):
            try:
                existing_output = json.loads(run["parsed_output"] or "{}")
            except (json.JSONDecodeError, TypeError):
                existing_output = {}
            readonly = "commentary" if step_id == "step-1" else "user_manual"
            if readonly in parsed_output and parsed_output[readonly] != existing_output.get(readonly):
                raise HTTPException(409, f"{readonly} is readonly")
            merged_output = dict(existing_output)
            if "talents" in parsed_output:
                if not isinstance(parsed_output["talents"], list):
                    raise HTTPException(422, {"detail": "output validation failed", "errors": ["output field 'talents' must be a list"]})
                merged_output["talents"] = parsed_output["talents"]
            parsed_output = _normalize_ch05_edit_output(merged_output, step_id, existing_output)
            output_errors = _validate_ch05_output(parsed_output, step_id)
            if output_errors:
                raise HTTPException(422, {"detail": "output validation failed", "errors": output_errors})
        if _is_ch06_step(chapter_id, step_id):
            try:
                existing_output = json.loads(run["parsed_output"] or "{}")
            except (json.JSONDecodeError, TypeError):
                existing_output = {}
            if "commentary" in parsed_output and parsed_output["commentary"] != existing_output.get("commentary"):
                raise HTTPException(409, "commentary is readonly")
            merged_output = dict(existing_output)
            if "likes" in parsed_output:
                if not isinstance(parsed_output["likes"], list):
                    raise HTTPException(422, {"detail": "output validation failed", "errors": ["output field 'likes' must be a list"]})
                merged_output["likes"] = parsed_output["likes"]
            parsed_output = _normalize_ch06_edit_output(merged_output, step_id, existing_output)
            output_errors = _validate_ch06_output(parsed_output, step_id)
            if output_errors:
                raise HTTPException(422, {"detail": "output validation failed", "errors": output_errors})
        if _is_ch07_step(chapter_id, step_id):
            try:
                existing_output = json.loads(run["parsed_output"] or "{}")
            except (json.JSONDecodeError, TypeError):
                existing_output = {}
            if "commentary" in parsed_output and parsed_output["commentary"] != existing_output.get("commentary"):
                raise HTTPException(409, "commentary is readonly")
            if step_id == "step-2" and "next_action" in parsed_output and parsed_output["next_action"] != existing_output.get("next_action"):
                raise HTTPException(409, "next_action is readonly")
            merged_output = dict(existing_output)
            if "ideal_works" in parsed_output:
                if not isinstance(parsed_output["ideal_works"], list):
                    raise HTTPException(422, {"detail": "output validation failed", "errors": ["output field 'ideal_works' must be a list"]})
                merged_output["ideal_works"] = parsed_output["ideal_works"]
            parsed_output = _normalize_ch07_edit_output(merged_output, step_id, existing_output)
            output_errors = _validate_ch07_output(parsed_output, step_id)
            if output_errors:
                raise HTTPException(422, {"detail": "output validation failed", "errors": output_errors})
        if body.user_answers is not None:
            conn.execute(
                """UPDATE step_runs SET parsed_output = ?, user_answers = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (json.dumps(parsed_output, ensure_ascii=False), json.dumps(effective_user_answers, ensure_ascii=False), run["id"]),
            )
        else:
            conn.execute(
                """UPDATE step_runs SET parsed_output = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (json.dumps(parsed_output, ensure_ascii=False), run["id"]),
            )
    return {"ok": True, "parsed_output": parsed_output}


def _maybe_compact(chapter_id):
    """If all steps in this chapter are submitted, run compaction.

    Trigger condition from handoff S6.3: chapter all-steps submitted.
    Returns the resulting profile (or None on skip/error).
    """
    cfg = load_chapter_config(chapter_id) or {}
    exercises = cfg.get("exercises") or []
    if not exercises:
        return None
    step_ids = [ex.get("step_id") for ex in exercises if ex.get("step_id")]
    if not step_ids:
        return None
    with get_conn() as conn:
        rows = []
        for step_id in step_ids:
            row = conn.execute(
                """SELECT step_id, parsed_output FROM step_runs
                   WHERE chapter_id = ? AND step_id = ? AND status = 'submitted' AND stale = 0
                   ORDER BY submitted_at DESC, created_at DESC, rowid DESC LIMIT 1""",
                (chapter_id, step_id),
            ).fetchone()
            if row:
                rows.append(row)
    if len(rows) < len(step_ids):
        return None
    outputs = []
    for r in rows:
        parsed = json.loads(r["parsed_output"]) if r["parsed_output"] else {}
        outputs.append(parsed)
    user_id = os.getenv("DEFAULT_USER_ID", "local")
    from app.runtime.config_loader import save_profile
    from app.runtime.config_loader import load_profile
    existing_profile = load_profile(user_id) or {}
    profile = compact_profile(
        [existing_profile, *outputs],
        current_chapter=chapter_id,
        open_questions=existing_profile.get("open_questions"),
    )
    save_profile(user_id, profile)
    logger.info("compaction done for %s: %d fields", chapter_id, len(profile))
    return profile


def _update_profile_likes(conn, likes, chapter_id):
    user_id = os.getenv("DEFAULT_USER_ID", "local")
    row = conn.execute(
        "SELECT profile_json FROM learner_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    try:
        profile = json.loads(row["profile_json"] or "{}") if row else {}
    except (json.JSONDecodeError, TypeError):
        profile = {}
    if not isinstance(profile, dict):
        profile = {}
    profile["likes"] = likes if isinstance(likes, list) else []
    profile["current_chapter"] = chapter_id
    conn.execute(
        """INSERT INTO learner_profiles (user_id, profile_json, updated_at)
           VALUES (?, ?, datetime('now'))
           ON CONFLICT(user_id) DO UPDATE SET
             profile_json = excluded.profile_json,
             updated_at = excluded.updated_at""",
        (user_id, json.dumps(profile, ensure_ascii=False)),
    )
    return profile


@router.post("/{step_id}/submit")
def submit_step(chapter_id: str, step_id: str, background_tasks: BackgroundTasks):
    """Submit step (lock) + trigger compaction if last step.

    M3.3 Q8: after a successful compaction, fire-and-forget an LLM-based
    open_questions extraction so the next mentor prompt sees fresh gaps.
    BackgroundTasks keeps submit_step sync and unblocks on LLM latency.
    """
    _require_upstream_context(chapter_id)
    with get_conn() as conn:
        run = conn.execute(
            """SELECT id, status, llm_response, parsed_output, user_answers FROM step_runs WHERE chapter_id = ? AND step_id = ? AND stale = 0
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            (chapter_id, step_id),
        ).fetchone()
        if not run:
            raise HTTPException(404, "No run to submit")
        if run["status"] != "saved":
            raise HTTPException(409, "Only a successful run can be submitted")
        if not (run["llm_response"] or "").strip() or not (run["parsed_output"] or "").strip():
            raise HTTPException(409, "Cannot submit an empty LLM result")
        parsed_output = json.loads(run["parsed_output"])
        if _is_ch02_step(chapter_id, step_id):
            output_errors = _validate_ch02_output(parsed_output)
            if output_errors:
                raise HTTPException(409, {"detail": "output validation failed", "errors": output_errors})
            try:
                user_answers = json.loads(run["user_answers"] or "{}")
            except (json.JSONDecodeError, TypeError):
                user_answers = {}
            parsed_output = _normalize_ch02_output(parsed_output, user_answers)
        if _is_ch03_step(chapter_id, step_id):
            output_errors = _validate_ch03_output(parsed_output)
            if output_errors:
                raise HTTPException(409, {"detail": "output validation failed", "errors": output_errors})
        if _is_ch04_step(chapter_id, step_id):
            try:
                user_answers = json.loads(run["user_answers"] or "{}")
            except (json.JSONDecodeError, TypeError):
                user_answers = {}
            parsed_output = _normalize_ch04_run_output(parsed_output, step_id, user_answers)
            output_errors = _validate_ch04_output(
                parsed_output, step_id, user_answers, require_complete=True
            )
            if output_errors:
                raise HTTPException(409, {"detail": "output validation failed", "errors": output_errors})
        if _is_ch05_step(chapter_id, step_id):
            parsed_output = _normalize_ch05_edit_output(parsed_output, step_id, parsed_output)
            output_errors = _validate_ch05_output(parsed_output, step_id)
            if output_errors:
                raise HTTPException(409, {"detail": "output validation failed", "errors": output_errors})
        if _is_ch06_step(chapter_id, step_id):
            parsed_output = _normalize_ch06_edit_output(parsed_output, step_id, parsed_output)
            output_errors = _validate_ch06_output(parsed_output, step_id)
            if output_errors:
                raise HTTPException(409, {"detail": "output validation failed", "errors": output_errors})
        if _is_ch07_step(chapter_id, step_id):
            parsed_output = _normalize_ch07_edit_output(parsed_output, step_id, parsed_output)
            output_errors = _validate_ch07_output(parsed_output, step_id)
            if output_errors:
                raise HTTPException(409, {"detail": "output validation failed", "errors": output_errors})
        conn.execute(
            """UPDATE step_runs
               SET parsed_output = ?, status = 'submitted', submitted_at = datetime('now')
               WHERE id = ?""",
            (json.dumps(parsed_output, ensure_ascii=False), run["id"]),
        )
        ch06_profile = None
        if _is_ch06_step(chapter_id, step_id):
            if step_id == "step-1":
                conn.execute(
                    """UPDATE step_runs
                       SET stale = 1, updated_at = datetime('now')
                       WHERE chapter_id = 'ch06' AND step_id = 'step-2'
                         AND stale = 0 AND status IN ('saved', 'submitted')"""
                )
                _update_profile_likes(conn, [], chapter_id)
            else:
                ch06_profile = _update_profile_likes(conn, parsed_output.get("likes", []), chapter_id)
        ch07_profile = None
        if _is_ch07_step(chapter_id, step_id):
            if step_id == "step-1":
                conn.execute(
                    """UPDATE step_runs
                       SET stale = 1, updated_at = datetime('now')
                       WHERE chapter_id = 'ch07' AND step_id = 'step-2'
                         AND stale = 0 AND status IN ('saved', 'submitted')"""
                )
                _update_profile_ideal_works(conn, [], chapter_id)
            else:
                ch07_profile = _update_profile_ideal_works(conn, parsed_output.get("ideal_works", []), chapter_id)
        if chapter_id == "ch04" and _downstream_step_ids(chapter_id, step_id):
            _mark_downstream_stale(conn, chapter_id, step_id)
            _clear_chapter_profile_keys(conn, ("values", "ranked", "work_purpose"))
        if chapter_id == "ch05" and _downstream_step_ids(chapter_id, step_id):
            _mark_downstream_stale(conn, chapter_id, step_id)
            _clear_chapter_profile_keys(conn, ("talents",))
    if _is_ch06_step(chapter_id, step_id):
        return {"ok": True, "status": "submitted", "compacted": step_id == "step-2", "profile_updated": ch06_profile is not None}
    if _is_ch07_step(chapter_id, step_id):
        return {"ok": True, "status": "submitted", "compacted": step_id == "step-2", "profile_updated": ch07_profile is not None}
    profile = None
    try:
        profile = _maybe_compact(chapter_id)
    except Exception as e:
        logger.warning("compaction skipped for %s: %s", chapter_id, e)
    if profile is not None and os.getenv("DISABLE_OPEN_QUESTIONS_EXTRACT") != "1":
        # Fire-and-forget: Q8 cheap LLM extraction of unresolved questions.
        from app.services.compaction import extract_and_persist_open_questions
        background_tasks.add_task(
            extract_and_persist_open_questions,
            os.getenv("DEFAULT_USER_ID", "local"),
            chapter_id,
        )
    return {"ok": True, "status": "submitted", "compacted": profile is not None}


@router.get("/{step_id}/config")
def get_chapter_config(chapter_id: str):
    """Read chapter config (frontend display)."""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT config_json FROM chapter_configs WHERE chapter_id = ? AND active = 1 ORDER BY version DESC LIMIT 1",
                (chapter_id,),
            ).fetchone()
        if not row:
            return {"chapter_id": chapter_id, "steps": []}
        return json.loads(row["config_json"])
    except Exception:
        return {"chapter_id": chapter_id, "steps": []}


@router.post("/{step_id}/config")
def save_chapter_config(chapter_id: str, config: dict):
    """Save chapter config (new version; existing kept)."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS v FROM chapter_configs WHERE chapter_id = ?",
            (chapter_id,),
        ).fetchone()
        next_v = (cur["v"] if cur else 0) + 1
        conn.execute("UPDATE chapter_configs SET active = 0 WHERE chapter_id = ?", (chapter_id,))
        conn.execute(
            """INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at)
               VALUES (?, ?, ?, 1, datetime('now'))""",
            (chapter_id, next_v, json.dumps(config)),
        )
    return {"ok": True, "version": next_v}

def _is_ch07_step(chapter_id, step_id):
    return chapter_id == "ch07" and step_id in {"step-1", "step-2"}


CH07_BUCKETS = ("真正想做的事", "作为兴趣的想做的事", "未定")


def _normalize_ch07_works(items):
    if not isinstance(items, list):
        return []
    normalized = []
    for item in items:
        raw = item if isinstance(item, Mapping) else {}
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        bucket = str(raw.get("bucket") or "未定").strip()
        if bucket not in CH07_BUCKETS:
            bucket = "未定"
        normalized.append({
            "title": title,
            "like_source": str(raw.get("like_source") or "").strip(),
            "strength_source": str(raw.get("strength_source") or "").strip(),
            "bucket": bucket,
            "locked": raw.get("locked") is True,
        })
    return normalized


def _normalize_ch07_run_output(parsed, step_id):
    normalized = dict(parsed or {})
    normalized["ideal_works"] = _normalize_ch07_works(normalized.get("ideal_works"))
    return normalized


def _normalize_ch07_edit_output(parsed, step_id, existing_output=None):
    normalized = dict(parsed or {})
    normalized["ideal_works"] = _normalize_ch07_works(normalized.get("ideal_works"))
    if isinstance(existing_output, Mapping):
        normalized["commentary"] = existing_output.get("commentary", normalized.get("commentary", ""))
        if step_id == "step-2":
            normalized["next_action"] = existing_output.get("next_action", normalized.get("next_action", ""))
    return normalized


def _validate_ch07_output(parsed, step_id):
    if not isinstance(parsed, Mapping) or not parsed:
        return ["LLM output must be a JSON object"]
    errors = []
    commentary = parsed.get("commentary")
    if not isinstance(commentary, str) or not commentary.strip():
        errors.append("output field 'commentary' is required")
    works = parsed.get("ideal_works")
    if not isinstance(works, list):
        return errors + ["output field 'ideal_works' must be a list"]
    for index, item in enumerate(works):
        number = index + 1
        if not isinstance(item, Mapping):
            errors.append(f"ideal_works item {number} must be an object")
            continue
        if not str(item.get("title") or "").strip():
            errors.append(f"ideal_works item {number} must include non-empty title")
        if not isinstance(item.get("locked"), bool):
            errors.append(f"ideal_works item {number} locked must be boolean")
        if str(item.get("bucket") or "未定") not in CH07_BUCKETS:
            errors.append(f"ideal_works item {number} bucket must be one of {list(CH07_BUCKETS)}")
    if step_id == "step-2":
        next_action = parsed.get("next_action")
        if not isinstance(next_action, str) or not next_action.strip():
            errors.append("output field 'next_action' is required for step-2")
    return errors


def _update_profile_ideal_works(conn, works, chapter_id):
    user_id = os.getenv("DEFAULT_USER_ID", "local")
    row = conn.execute(
        "SELECT profile_json FROM learner_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    try:
        profile = json.loads(row["profile_json"] or "{}") if row else {}
    except (json.JSONDecodeError, TypeError):
        profile = {}
    if not isinstance(profile, dict):
        profile = {}
    profile["ideal_works"] = works if isinstance(works, list) else []
    profile["current_chapter"] = chapter_id
    conn.execute(
        """INSERT INTO learner_profiles (user_id, profile_json, updated_at)
           VALUES (?, ?, datetime('now'))
           ON CONFLICT(user_id) DO UPDATE SET
             profile_json = excluded.profile_json,
             updated_at = excluded.updated_at""",
        (user_id, json.dumps(profile, ensure_ascii=False)),
    )
    return profile


def _downstream_step_ids(chapter_id, step_id):
    """Transitive closure over exercises[].references[].from_exercise."""
    cfg = load_chapter_config(chapter_id) or {}
    downstream = set()
    stack = [step_id]
    while stack:
        current = stack.pop()
        for exercise in cfg.get("exercises") or []:
            for ref in exercise.get("references") or []:
                if isinstance(ref, Mapping) and ref.get("from_exercise") == current:
                    nxt = exercise.get("step_id")
                    if nxt and nxt not in downstream:
                        downstream.add(nxt)
                        stack.append(nxt)
    return sorted(downstream)


def _mark_downstream_stale(conn, chapter_id, step_id):
    downstream = _downstream_step_ids(chapter_id, step_id)
    if not downstream:
        return
    placeholders = ", ".join("?" for _ in downstream)
    conn.execute(
        f"UPDATE step_runs SET stale = 1, updated_at = datetime('now') "
        f"WHERE chapter_id = ? AND step_id IN ({placeholders}) "
        f"AND stale = 0 AND status IN ('saved', 'submitted')",
        (chapter_id, *downstream),
    )


def _clear_chapter_profile_keys(conn, keys):
    user_id = os.getenv("DEFAULT_USER_ID", "local")
    row = conn.execute(
        "SELECT profile_json FROM learner_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not row:
        return
    try:
        profile = json.loads(row["profile_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        profile = {}
    if not isinstance(profile, dict):
        return
    changed = False
    for key in keys:
        if key in profile:
            profile.pop(key, None)
            changed = True
    if changed:
        conn.execute(
            "UPDATE learner_profiles SET profile_json = ?, updated_at = datetime('now') WHERE user_id = ?",
            (json.dumps(profile, ensure_ascii=False), user_id),
        )


def _validate_user_answers(input_schema, answers, *, strict=True):
    """Validate answers against input_schema (review.md P0-4).

    Returns an empty list when input_schema is empty or answers are incomplete
    in draft mode; strict runs enforce required fields and item counts.
    Schema rules implemented:
      - checklist: required ids within items[]; followup field text only.
      - list_of_items: respects min/max_items; each row must satisfy item_schema.
      - select/radio: value must be one of options[] (or empty string).
      - text: presence only when required=True.
    """
    errors = []
    if not input_schema or not isinstance(answers, dict):
        return errors
    for field in input_schema:
        if not isinstance(field, dict): continue
        name = field.get("name")
        if not name: continue
        value = answers.get(name)
        ftype = field.get("type")
        required = bool(field.get("required"))
        if strict and required and (value is None or value == "" or value == [] or value == {}):
            errors.append(f"field '{name}' is required")
            continue
        if value is None: continue
        if ftype == "checklist":
            if not isinstance(value, dict):
                errors.append(f"checklist '{name}' must be an object")
                continue
            ids = value.get("checked_ids") or []
            if not isinstance(ids, list):
                errors.append(f"checklist '{name}' checked_ids must be a list"); continue
            valid_ids = {item.get("id") for item in field.get("items") or []}
            for cid in ids:
                if str(cid) not in {str(v) for v in valid_ids}:
                    errors.append(f"checklist '{name}' unknown id {cid}")
        elif ftype == "list_of_items":
            if not isinstance(value, list):
                errors.append(f"list_of_items '{name}' must be a list"); continue
            lo = field.get("min_items"); hi = field.get("max_items")
            if strict and lo is not None and len(value) < int(lo):
                errors.append(f"list_of_items '{name}' requires at least {lo} items")
            if hi is not None and len(value) > int(hi):
                errors.append(f"list_of_items '{name}' allows at most {hi} items")
            item_schema = (field.get("item_schema") or {}).get("fields") or []
            for row in value:
                if not isinstance(row, dict):
                    errors.append(f"list_of_items '{name}' row must be object"); continue
                for sub in item_schema:
                    sname = sub.get("name")
                    v = row.get(sname)
                    if strict and sub.get("required") and (v is None or v == ""):
                        errors.append(f"list_of_items '{name}.{sname}' is required")
                        continue
                    if sub.get("type") == "select" and v is not None and v != "":
                        if v not in (sub.get("options") or []):
                            errors.append(f"list_of_items '{name}.{sname}' invalid option {v}")
        elif ftype in ("select", "radio"):
            opts = field.get("options") or []
            if value not in opts:
                errors.append(f"{ftype} '{name}' value {value!r} not in options")
    return errors


def _current_input_schema(chapter_id, step_id):
    cfg = load_chapter_config(chapter_id) or {}
    for ex in cfg.get("exercises") or []:
        if ex.get("step_id") == step_id or ex.get("name") == step_id:
            return ex.get("input_schema") or cfg.get("input_schema") or []
    return []


def _is_ch02_step(chapter_id, step_id):
    return chapter_id == "ch02" and step_id == "step-1"


def _is_ch03_step(chapter_id, step_id):
    return chapter_id == "ch03" and step_id == "step-1"


def _derive_ch02_ratio(user_answers):
    items = (user_answers or {}).get("drive_items") if isinstance(user_answers, dict) else None
    items = items if isinstance(items, list) else []
    external = sum(1 for item in items if isinstance(item, dict) and item.get("drive") == "external")
    internal = sum(1 for item in items if isinstance(item, dict) and item.get("drive") == "internal")
    total = external + internal
    if not total:
        return {"external_pct": 0, "internal_pct": 0, "method": "item_count"}
    external_pct = round(external * 100 / total)
    return {
        "external_pct": external_pct,
        "internal_pct": 100 - external_pct,
        "method": "item_count",
    }


def _validate_ch02_output(parsed):
    errors = []
    if not isinstance(parsed, dict) or not parsed:
        return ["LLM output must be a JSON object"]
    commentary = parsed.get("commentary")
    if not isinstance(commentary, str) or not commentary.strip():
        errors.append("output field 'commentary' is required")
    if "reclaim_item" not in parsed:
        errors.append("output field 'reclaim_item' is required")
    elif not isinstance(parsed.get("reclaim_item"), str):
        errors.append("output field 'reclaim_item' must be text")
    return errors


def _normalize_ch02_output(parsed, user_answers):
    normalized = dict(parsed or {})
    normalized["internal_external_ratio"] = _derive_ch02_ratio(user_answers)
    return normalized


def _is_ch04_step(chapter_id, step_id):
    return chapter_id == "ch04" and step_id in {"step-2", "step-3", "step-4"}


def _ch04_item_text(item):
    if isinstance(item, Mapping):
        item = item.get("value") or item.get("text") or item.get("name")
    return str(item or "").strip()


def _ch04_text_key(item):
    return re.sub(r"\s+", " ", _ch04_item_text(item)).casefold()


def _ch04_step2_candidates(user_answers):
    """Load the submitted Step 1 values and merge Step 2 supplements once."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT parsed_output FROM step_runs
               WHERE chapter_id = 'ch04' AND step_id = 'step-1'
                 AND status = 'submitted' AND stale = 0
               ORDER BY submitted_at DESC, created_at DESC, rowid DESC LIMIT 1"""
        ).fetchone()
    try:
        step_1_output = json.loads(row["parsed_output"] or "{}") if row else {}
    except (json.JSONDecodeError, TypeError):
        step_1_output = {}
    excluded = {
        _ch04_text_key(value)
        for value in (user_answers or {}).get("excluded_top_values", [])
        if _ch04_text_key(value)
    } if isinstance(user_answers, Mapping) else set()
    candidates, seen = [], set()

    def add(item):
        text = _ch04_item_text(item)
        key = _ch04_text_key(text)
        if not text or not key or key in seen:
            return
        seen.add(key)
        candidates.append(text)

    for item in step_1_output.get("top_values", []) if isinstance(step_1_output, Mapping) else []:
        if _ch04_text_key(item) not in excluded:
            add(item)
    supplements = user_answers.get("supplemental_keywords", []) if isinstance(user_answers, Mapping) else []
    for item in supplements if isinstance(supplements, list) else []:
        add(item)
    return candidates


def _ch04_step3_candidates():
    """Flatten submitted Step 2 groups into stable, user-visible value items."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT parsed_output FROM step_runs
               WHERE chapter_id = 'ch04' AND step_id = 'step-2'
                 AND status = 'submitted' AND stale = 0
               ORDER BY submitted_at DESC, created_at DESC, rowid DESC LIMIT 1"""
        ).fetchone()
    try:
        output = json.loads(row["parsed_output"] or "{}") if row else {}
    except (json.JSONDecodeError, TypeError):
        output = {}
    candidates, seen = [], set()
    for group in output.get("groups", []) if isinstance(output, Mapping) else []:
        if not isinstance(group, Mapping):
            continue
        umbrella = str(group.get("umbrella") or "未命名分组").strip()
        keywords = group.get("keywords") if isinstance(group.get("keywords"), list) else group.get("values") or []
        for keyword in keywords:
            value = _ch04_item_text(keyword)
            key = _ch04_text_key(value)
            if value and key not in seen:
                seen.add(key)
                candidates.append({"group": umbrella, "value": value})
    return candidates


def _ch04_step4_candidates():
    """Load the Step 2 core group themes that must form the pyramid levels."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT parsed_output FROM step_runs
               WHERE chapter_id = 'ch04' AND step_id = 'step-2'
                 AND status = 'submitted' AND stale = 0
               ORDER BY submitted_at DESC, created_at DESC, rowid DESC LIMIT 1"""
        ).fetchone()
    try:
        output = json.loads(row["parsed_output"] or "{}") if row else {}
    except (json.JSONDecodeError, TypeError):
        output = {}
    candidates, seen = [], set()
    for group in output.get("groups", []) if isinstance(output, Mapping) else []:
        if not isinstance(group, Mapping):
            continue
        value = str(group.get("umbrella") or "").strip()
        key = _ch04_text_key(value)
        if value and key and key not in seen:
            seen.add(key)
            candidates.append(value)
    return candidates


def _ch04_previous_step3_conversions():
    """Read the existing Step 3 screening so a proposal can update only answered items."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT parsed_output FROM step_runs
               WHERE chapter_id = 'ch04' AND step_id = 'step-3'
                 AND status = 'saved' AND stale = 0 AND parsed_output IS NOT NULL
               ORDER BY updated_at DESC, created_at DESC, rowid DESC LIMIT 1"""
        ).fetchone()
    try:
        output = json.loads(row["parsed_output"] or "{}") if row else {}
    except (json.JSONDecodeError, TypeError):
        output = {}
    return output.get("conversions") if isinstance(output.get("conversions"), list) else []


def _normalize_ch04_run_output(parsed, step_id, user_answers):
    if step_id == "step-3":
        return _normalize_ch04_step3_output(parsed, user_answers)
    if step_id == "step-4":
        return _normalize_ch04_step4_output(parsed)
    if step_id != "step-2":
        return dict(parsed or {}) if isinstance(parsed, Mapping) else {}
    normalized = dict(parsed or {}) if isinstance(parsed, Mapping) else {}
    normalized.pop("ungrouped", None)
    candidates = _ch04_step2_candidates(user_answers)
    canonical = {_ch04_text_key(value): value for value in candidates}
    assigned, groups = set(), []
    raw_groups = normalized.get("groups") if isinstance(normalized.get("groups"), list) else []
    locked_keys = {
        _ch04_text_key(keyword)
        for item in raw_groups if isinstance(item, Mapping) and item.get("locked") is True
        for keyword in (
            item.get("keywords") if isinstance(item.get("keywords"), list)
            else item.get("values") if isinstance(item.get("values"), list)
            else []
        )
        if _ch04_text_key(keyword) in canonical
    }
    for item in raw_groups:
        if not isinstance(item, Mapping):
            continue
        umbrella = str(item.get("umbrella") or "").strip()
        locked = item.get("locked") is True
        raw_keywords = item.get("keywords")
        if not isinstance(raw_keywords, list) or (not raw_keywords and isinstance(item.get("values"), list)):
            raw_keywords = item.get("values") if isinstance(item.get("values"), list) else []
        keywords = []
        for keyword in raw_keywords:
            key = _ch04_text_key(keyword)
            if not key or key not in canonical or (not locked and (key in assigned or key in locked_keys)):
                continue
            if not locked:
                assigned.add(key)
            keywords.append(canonical[key])
        if locked:
            assigned.update(_ch04_text_key(keyword) for keyword in keywords)
        if umbrella or keywords:
            groups.append({
                "umbrella": umbrella,
                "keywords": keywords,
                "locked": locked,
            })
    normalized["groups"] = groups
    return normalized


def _normalize_ch04_step4_output(parsed):
    normalized = dict(parsed or {}) if isinstance(parsed, Mapping) else {}
    ranked = []
    for item in normalized.get("ranked", []) if isinstance(normalized.get("ranked"), list) else []:
        value = _ch04_item_text(item)
        if value:
            ranked.append({
                "value": value,
                "locked": item.get("locked") is True if isinstance(item, Mapping) else False,
            })
    normalized["ranked"] = ranked
    links = []
    for item in normalized.get("support_links", []) if isinstance(normalized.get("support_links"), list) else []:
        if not isinstance(item, Mapping):
            continue
        links.append({
            "from_value": str(item.get("from_value") or "").strip(),
            "to_value": str(item.get("to_value") or "").strip(),
            "reason": str(item.get("reason") or "").strip(),
        })
    normalized["support_links"] = links
    purpose = normalized.get("final_purpose") if isinstance(normalized.get("final_purpose"), Mapping) else {}
    normalized["final_purpose"] = {
        "value": str(purpose.get("value") or "").strip(),
        "life_state": str(purpose.get("life_state") or "").strip(),
        "reason": str(purpose.get("reason") or "").strip(),
    }
    normalized["gap_note"] = str(normalized.get("gap_note") or "").strip()
    if normalized.get("basis_stale") is True:
        normalized["basis_stale"] = True
    else:
        normalized.pop("basis_stale", None)
    return normalized


def _normalize_ch04_step3_output(parsed, user_answers):
    """Keep Step 3 tied to the confirmed Step 2 keyword pool and learner choice."""
    normalized = dict(parsed or {}) if isinstance(parsed, Mapping) else {}
    candidates = _ch04_step3_candidates()
    canonical = {_ch04_text_key(item["value"]): item for item in candidates}
    has_clarifications = isinstance(user_answers, Mapping) and any(
        isinstance(item, Mapping) and str(item.get("answer") or "").strip()
        for item in (user_answers.get("clarifications") or [])
    )
    phase = "proposal" if has_clarifications else "screening"
    raw_items = normalized.get("conversions") if isinstance(normalized.get("conversions"), list) else []
    if phase == "proposal":
        # The proposal call deliberately returns only clarified values. Merge it
        # over the first-pass screening instead of asking the model to repeat 20 items.
        raw_items = [*raw_items, *_ch04_previous_step3_conversions()]
    conversions, seen = [], set()
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            continue
        key = _ch04_text_key(raw.get("value") or raw.get("keyword"))
        candidate = canonical.get(key)
        if not candidate or key in seen:
            continue
        seen.add(key)
        legacy_status = raw.get("status")
        value_type = raw.get("type") if raw.get("type") in {"self", "other", "uncertain"} else (
            legacy_status if legacy_status in {"self", "other", "uncertain"} else "uncertain"
        )
        assessment = raw.get("assessment") if raw.get("assessment") in {"keep", "explore", "convert_candidate"} else (
            "keep" if value_type == "self" else "explore" if value_type == "uncertain" else "convert_candidate"
        )
        legacy_action = raw.get("action")
        decision = raw.get("decision") if raw.get("decision") in {"pending", "keep", "convert"} else (
            legacy_action if legacy_action in {"keep", "convert"} else "keep" if value_type == "self" else "pending"
        )
        converted_to = str(raw.get("converted_to") or "").strip()[:160]
        why_chain = [str(item).strip()[:180] for item in raw.get("why_chain", []) if str(item).strip()][:3] if isinstance(raw.get("why_chain"), list) else []
        question = str(raw.get("question") or raw.get("clarification") or "").strip()[:240]
        if value_type == "uncertain" and not question:
            question = "这个词对你具体意味着什么？你期待自己可以怎样实践它？"
        if value_type == "other" and not converted_to and not question:
            question = "你期待这个词带来的具体感受或状态是什么？哪些部分可以由你自己主动实践？"
        conversions.append({
            "group": candidate["group"],
            "value": candidate["value"],
            "type": value_type,
            "assessment": assessment,
            "evidence_summary": str(raw.get("evidence_summary") or "").strip()[:240],
            "question": question,
            "converted_to": converted_to,
            "why_chain": why_chain,
            "decision": decision,
        })
    for candidate in candidates:
        key = _ch04_text_key(candidate["value"])
        if key not in seen:
            conversions.append({
                "group": candidate["group"],
                "value": candidate["value"],
                "type": "uncertain",
                "assessment": "explore",
                "evidence_summary": "",
                "question": "这个词对你具体意味着什么？你期待自己可以怎样实践它？",
                "converted_to": "",
                "why_chain": [],
                "decision": "pending",
            })
    normalized["phase"] = phase
    normalized["conversions"] = conversions
    return normalized


def _validate_ch04_output(parsed, step_id, user_answers, require_complete=False):
    if step_id == "step-3":
        return _validate_ch04_step3_output(parsed, require_complete)
    if step_id == "step-4":
        return _validate_ch04_step4_output(parsed, require_complete)
    if step_id != "step-2":
        return []
    if not isinstance(parsed, Mapping) or not parsed:
        return ["LLM output must be a JSON object"]
    groups = parsed.get("groups")
    if not isinstance(groups, list):
        return ["output field 'groups' must be a list"]
    errors, assigned = [], set()
    candidate_values = _ch04_step2_candidates(user_answers)
    candidate_keys = {_ch04_text_key(value) for value in candidate_values}
    for index, group in enumerate(groups):
        number = index + 1
        if not isinstance(group, Mapping):
            errors.append(f"groups item {number} must be an object")
            continue
        if not str(group.get("umbrella") or "").strip():
            errors.append(f"groups item {number} must include non-empty umbrella")
        keywords = group.get("keywords")
        if not isinstance(keywords, list):
            errors.append(f"groups item {number} keywords must be a list")
            continue
        if not isinstance(group.get("locked"), bool):
            errors.append(f"groups item {number} locked must be boolean")
        for keyword in keywords:
            key = _ch04_text_key(keyword)
            if not key or key not in candidate_keys:
                errors.append(f"groups item {number} contains an unknown keyword: {_ch04_item_text(keyword)}")
            elif key in assigned:
                errors.append(f"keyword may only appear once: {_ch04_item_text(keyword)}")
            else:
                assigned.add(key)
    if require_complete:
        missing = [value for value in candidate_values if _ch04_text_key(value) not in assigned]
        if missing:
            errors.append("all confirmed keywords must be assigned before submit: " + "、".join(missing))
    return errors


def _validate_ch04_step4_output(parsed, require_complete=False):
    if not isinstance(parsed, Mapping) or not parsed:
        return ["LLM output must be a JSON object"]
    ranked = parsed.get("ranked")
    if not isinstance(ranked, list) or not ranked:
        return ["output field 'ranked' must contain every Step 2 core group theme"]
    candidates = _ch04_step4_candidates()
    candidate_keys = [_ch04_text_key(value) for value in candidates]
    ranked_values = [_ch04_item_text(item) for item in ranked]
    ranked_keys = [_ch04_text_key(value) for value in ranked_values if value]
    errors = []
    if len(ranked_keys) != len(set(ranked_keys)):
        errors.append("ranked core group themes must not be duplicated")
    missing = [value for value, key in zip(candidates, candidate_keys) if key not in ranked_keys]
    unexpected = [value for value, key in zip(ranked_values, ranked_keys) if key not in set(candidate_keys)]
    if missing:
        errors.append("ranked is missing Step 2 core group themes: " + ", ".join(missing))
    if unexpected:
        errors.append("ranked contains invented or renamed themes: " + ", ".join(unexpected))
    for index, item in enumerate(ranked):
        if not isinstance(item, Mapping) or not isinstance(item.get("locked"), bool):
            errors.append(f"ranked item {index + 1} locked must be boolean")

    basis_stale = parsed.get("basis_stale") is True
    if require_complete and basis_stale:
        errors.append("ranking basis is stale; rerun the LLM before submit")
    if require_complete and not basis_stale:
        links = parsed.get("support_links")
        expected_pairs = list(zip(ranked_values, ranked_values[1:]))
        if not isinstance(links, list) or len(links) != len(expected_pairs):
            errors.append("support_links must explain every adjacent lower-to-higher pair")
        else:
            for index, ((lower, higher), link) in enumerate(zip(expected_pairs, links)):
                if not isinstance(link, Mapping):
                    errors.append(f"support link {index + 1} must be an object")
                    continue
                if _ch04_text_key(link.get("from_value")) != _ch04_text_key(lower) or _ch04_text_key(link.get("to_value")) != _ch04_text_key(higher):
                    errors.append(f"support link {index + 1} must match adjacent ranked themes")
                if not str(link.get("reason") or "").strip():
                    errors.append(f"support link {index + 1} reason is required")
        purpose = parsed.get("final_purpose")
        if not isinstance(purpose, Mapping):
            errors.append("final_purpose must be an object")
        else:
            if not ranked_values or _ch04_text_key(purpose.get("value")) != _ch04_text_key(ranked_values[-1]):
                errors.append("final_purpose value must equal the top ranked theme")
            if not str(purpose.get("life_state") or "").strip():
                errors.append("final_purpose life_state is required")
            if not str(purpose.get("reason") or "").strip():
                errors.append("final_purpose reason is required")
        if not isinstance(parsed.get("gap_note"), str):
            errors.append("gap_note must be text")
    return errors


def _validate_ch04_step3_output(parsed, require_complete=False):
    if not isinstance(parsed, Mapping) or not isinstance(parsed.get("conversions"), list):
        return ["output field 'conversions' must be a list"]
    candidates = _ch04_step3_candidates()
    expected = {_ch04_text_key(item["value"]) for item in candidates}
    seen, errors = set(), []
    for number, item in enumerate(parsed["conversions"], 1):
        if not isinstance(item, Mapping):
            errors.append(f"conversions item {number} must be an object")
            continue
        key = _ch04_text_key(item.get("value"))
        if not key or key not in expected:
            errors.append(f"conversions item {number} contains an unknown value")
        elif key in seen:
            errors.append(f"value may only appear once: {_ch04_item_text(item.get('value'))}")
        else:
            seen.add(key)
        if item.get("type") not in {"self", "other", "uncertain"}:
            errors.append(f"conversions item {number} type must be self, other, or uncertain")
        if require_complete and item.get("type") != "self":
            decision = item.get("decision")
            if decision not in {"keep", "convert"}:
                errors.append(f"value needs learner confirmation: {_ch04_item_text(item.get('value'))}")
            elif decision == "convert" and not str(item.get("converted_to") or "").strip():
                errors.append(f"converted value cannot be empty: {_ch04_item_text(item.get('value'))}")
    if require_complete:
        missing = [item["value"] for item in candidates if _ch04_text_key(item["value"]) not in seen]
        if missing:
            errors.append("all Step 2 keywords need a control check: " + "、".join(missing))
    return errors



def _is_ch05_step(chapter_id, step_id):
    return chapter_id == "ch05" and step_id in {"step-1", "step-2"}


def _ch05_item_text(item):
    if isinstance(item, Mapping):
        item = item.get("text")
    return str(item or "").strip()


def _ch05_text_key(item):
    return re.sub(r"\s+", " ", _ch05_item_text(item))


def _ch05_step2_candidates(user_answers):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT parsed_output FROM step_runs
               WHERE chapter_id = 'ch05' AND step_id = 'step-1' AND status = 'submitted' AND stale = 0
               ORDER BY submitted_at DESC, created_at DESC, rowid DESC LIMIT 1"""
        ).fetchone()
    try:
        step_1_output = json.loads(row["parsed_output"] or "{}") if row else {}
    except (json.JSONDecodeError, TypeError):
        step_1_output = {}
    candidates, seen = [], set()

    def add(item, source):
        text = _ch05_item_text(item)
        key = _ch05_text_key(text)
        if not text or not key or key in seen:
            return
        seen.add(key)
        candidates.append({"text": text, "source": source})

    for item in step_1_output.get("talents", []) if isinstance(step_1_output, Mapping) else []:
        add(item, None)
    references = user_answers.get("reference_strengths", []) if isinstance(user_answers, Mapping) else []
    for item in references if isinstance(references, list) else []:
        add(item, "100_examples")
    return candidates


def _normalize_ch05_talents(items, step_id, existing_output=None):
    if not isinstance(items, list):
        items = []
    prior_sources = {}
    if isinstance(existing_output, Mapping):
        for item in existing_output.get("talents", []):
            key = _ch05_text_key(item)
            if key and isinstance(item, Mapping):
                prior_sources[key] = item.get("source")
    normalized = []
    for item in items:
        text = _ch05_item_text(item)
        if not text:
            continue
        raw = item if isinstance(item, Mapping) else {}
        candidate = {"text": text, "locked": raw.get("locked") is True, "source": None}
        if step_id == "step-2":
            rating = raw.get("rating", "")
            candidate["rating"] = rating if rating in {chr(0x25CE), chr(0x3007), chr(0x25B3), ""} else ""
            candidate["source"] = "100_examples" if prior_sources.get(_ch05_text_key(text)) == "100_examples" else None
        normalized.append(candidate)
    return normalized


def _normalize_ch05_run_output(parsed, step_id, user_answers):
    normalized = dict(parsed or {})
    if step_id == "step-1":
        normalized["talents"] = _normalize_ch05_talents(normalized.get("talents"), step_id)
        return normalized
    candidates = _ch05_step2_candidates(user_answers)
    raw_ratings = {}
    raw_items = normalized.get("talents") if isinstance(normalized.get("talents"), list) else []
    for item in raw_items:
        key = _ch05_text_key(item)
        if key and key not in raw_ratings and isinstance(item, Mapping):
            raw_ratings[key] = item
    talents = []
    for candidate in candidates:
        raw = raw_ratings.get(_ch05_text_key(candidate)) or {}
        rating = raw.get("rating", "") if isinstance(raw, Mapping) else ""
        talents.append({
            "text": candidate["text"],
            "rating": rating if rating in {chr(0x25CE), chr(0x3007), chr(0x25B3), ""} else "",
            "locked": raw.get("locked") is True if isinstance(raw, Mapping) else False,
            "source": candidate["source"],
        })
    normalized["talents"] = talents
    return normalized


def _normalize_ch05_edit_output(parsed, step_id, existing_output=None):
    normalized = dict(parsed or {})
    normalized["talents"] = _normalize_ch05_talents(normalized.get("talents"), step_id, existing_output)
    return normalized


def _validate_ch05_output(parsed, step_id):
    if not isinstance(parsed, Mapping) or not parsed:
        return ["LLM output must be a JSON object"]
    errors = []
    readonly = "commentary" if step_id == "step-1" else "user_manual"
    if not isinstance(parsed.get(readonly), str) or not parsed.get(readonly).strip():
        errors.append(f"output field '{readonly}' is required")
    talents = parsed.get("talents")
    if not isinstance(talents, list):
        return errors + ["output field 'talents' must be a list"]
    for index, item in enumerate(talents):
        if not isinstance(item, Mapping) or not _ch05_item_text(item):
            errors.append(f"talents item {index + 1} must include non-empty text")
            continue
        if not isinstance(item.get("locked"), bool):
            errors.append(f"talents item {index + 1} locked must be boolean")
        if step_id == "step-1" and "rating" in item:
            errors.append(f"step-1 talents item {index + 1} must not include rating")
        if step_id == "step-2":
            if item.get("rating") not in {chr(0x25CE), chr(0x3007), chr(0x25B3), ""}:
                errors.append(f"step-2 talents item {index + 1} has invalid rating")
            if item.get("source") not in {None, "100_examples"}:
                errors.append(f"step-2 talents item {index + 1} has invalid source")
    return errors


def _is_ch06_step(chapter_id, step_id):
    return chapter_id == "ch06" and step_id in {"step-1", "step-2"}


def _ch06_text(value):
    if isinstance(value, Mapping):
        value = value.get("text")
    return str(value or "").strip()


_CH06_SOURCE_TOKEN_RE = re.compile(r"q(\d{1,3})", re.IGNORECASE)


def _ch06_source_tokens(value):
    """Extract canonical q1-q5 / q61-q90 tokens from a free-form source string."""
    if value is None:
        return []
    tokens = []
    for match in _CH06_SOURCE_TOKEN_RE.finditer(str(value)):
        number = int(match.group(1))
        if 1 <= number <= 5 or 61 <= number <= 90:
            token = f"q{number}"
            if token not in tokens:
                tokens.append(token)
    return tokens

def _normalize_ch06_list(items):
    if not isinstance(items, list):
        return []
    normalized = []
    for item in items:
        text = _ch06_text(item)
        if text:
            normalized.append({"text": text})
    return normalized


def _normalize_ch06_sources(items):
    if not isinstance(items, list):
        return []
    tokens = []
    for item in items:
        for token in _ch06_source_tokens(item):
            if token not in tokens:
                tokens.append(token)
    return tokens


def _is_valid_ch06_source(value):
    text = str(value or "").strip().lower()
    if not text:
        return False
    return all(re.fullmatch(r"q(?:[1-5]|6[1-9]|[78][0-9]|90)", part) for part in text.split(","))


def _normalize_ch06_likes(items, step_id):
    if not isinstance(items, list):
        return []
    normalized = []
    for item in items:
        raw = item if isinstance(item, Mapping) else {}
        if step_id == "step-1":
            text = _ch06_text(raw)
            if not text:
                continue
            source = raw.get("source")
            normalized.append({
                "text": text,
                "locked": raw.get("locked") is True,
                "source": ",".join(_ch06_source_tokens(source)) if _ch06_source_tokens(source) else None,
            })
            continue
        field = str(raw.get("field") or "").strip()
        if not field:
            continue
        normalized.append({
            "field": field,
            "aspects": _normalize_ch06_list(raw.get("aspects")),
            "linked_strengths": _normalize_ch06_list(raw.get("linked_strengths")),
            "sources": _normalize_ch06_sources(raw.get("sources")),
            "locked": raw.get("locked") is True,
        })
    return normalized


def _normalize_ch06_run_output(parsed, step_id):
    normalized = dict(parsed or {})
    normalized["likes"] = _normalize_ch06_likes(normalized.get("likes"), step_id)
    return normalized


def _normalize_ch06_edit_output(parsed, step_id, existing_output=None):
    normalized = dict(parsed or {})
    normalized["likes"] = _normalize_ch06_likes(normalized.get("likes"), step_id)
    if isinstance(existing_output, Mapping):
        normalized["commentary"] = existing_output.get("commentary", normalized.get("commentary", ""))
    return normalized


def _validate_ch06_output(parsed, step_id):
    if not isinstance(parsed, Mapping) or not parsed:
        return ["LLM output must be a JSON object"]
    errors = []
    commentary = parsed.get("commentary")
    if not isinstance(commentary, str) or not commentary.strip():
        errors.append("output field 'commentary' is required")
    likes = parsed.get("likes")
    if not isinstance(likes, list):
        return errors + ["output field 'likes' must be a list"]
    for index, item in enumerate(likes):
        number = index + 1
        if not isinstance(item, Mapping):
            errors.append(f"likes item {number} must be an object")
            continue
        if step_id == "step-1":
            if not _ch06_text(item):
                errors.append(f"likes item {number} must include non-empty text")
            if not isinstance(item.get("locked"), bool):
                errors.append(f"likes item {number} locked must be boolean")
            source = item.get("source")
            if source not in (None, "") and (not isinstance(source, str) or not _is_valid_ch06_source(source)):
                errors.append(f"likes item {number} source must match q1-q5 or q61-q90")
            continue
        field = str(item.get("field") or "").strip()
        if not field:
            errors.append(f"likes item {number} field is required")
        for name in ("aspects", "linked_strengths"):
            values = item.get(name)
            if not isinstance(values, list):
                errors.append(f"likes item {number} {name} must be a list")
                continue
            for child_index, child in enumerate(values):
                if not isinstance(child, Mapping) or not _ch06_text(child):
                    errors.append(f"likes item {number} {name} item {child_index + 1} must include non-empty text")
        sources = item.get("sources")
        if not isinstance(sources, list) or any(
            not isinstance(source, str) or not source.strip() or not _is_valid_ch06_source(source)
            for source in sources
        ):
            errors.append(f"likes item {number} sources must match q1-q5 or q61-q90")
        if not isinstance(item.get("locked"), bool):
            errors.append(f"likes item {number} locked must be boolean")
    return errors

def _validate_ch03_output(parsed):
    """Validate ch03's canonical output and editable-list contract."""
    errors = []
    if not isinstance(parsed, dict) or not parsed:
        return ["LLM output must be a JSON object"]
    commentary = parsed.get("commentary")
    if not isinstance(commentary, str) or not commentary.strip():
        errors.append("output field 'commentary' is required")
    intersection = parsed.get("intersection")
    if not isinstance(intersection, str) or not intersection.strip():
        errors.append("output field 'intersection' is required")
    for name in ("importance", "talents", "likes"):
        value = parsed.get(name)
        if value is None:
            errors.append(f"output field '{name}' is required")
            continue
        if not isinstance(value, list):
            errors.append(f"output field '{name}' must be a list")
            continue
        if len(value) < 3:
            errors.append(f"output field '{name}' must have at least 3 items")
        if len(value) > 5:
            errors.append(f"output field '{name}' must have at most 5 items")
        for index, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                errors.append(f"output field '{name}' item {index + 1} must be a non-empty string")
    return errors
