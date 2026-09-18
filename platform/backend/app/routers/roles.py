"""LLM roles CRUD. M3."""
import json
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.db import get_conn

router = APIRouter(prefix="/api/roles", tags=["roles"])


class RoleIn(BaseModel):
    name: str
    description: str
    system_prompt: str
    provider: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    enabled: bool = True


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    enabled: Optional[bool] = None


@router.get("")
def list_roles(enabled_only: bool = False, group_by_name: bool = False):
    """List llm_roles rows.

    Args:
        enabled_only: if True, only enabled=1 rows.
        group_by_name: if True, dedup by (name, provider) keeping the newest.
            Uses ROW_NUMBER() OVER PARTITION BY to avoid ties when multiple
            rows share the same max created_at (the MAX+JOIN approach could
            over-match and still return duplicates).
    """
    enabled_clause = "WHERE enabled = 1" if enabled_only else ""
    if group_by_name:
        sql = (
            "SELECT * FROM ("
            " SELECT r.*, ROW_NUMBER() OVER ("
            "   PARTITION BY r.name, r.provider"
            "   ORDER BY r.created_at DESC, r.id DESC"
            " ) AS rn"
            " FROM llm_roles r " + enabled_clause + " ) t"
            " WHERE t.rn = 1 ORDER BY t.created_at"
        )
    else:
        sql = "SELECT * FROM llm_roles " + enabled_clause + " ORDER BY created_at"
    with get_conn() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


@router.post("")
def create_role(body: RoleIn):
    role_id = str(uuid.uuid4())
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM llm_roles WHERE name = ? AND provider = ? AND enabled = 1",
            (body.name, body.provider),
        ).fetchone()
        if existing:
            raise HTTPException(
                409, "role already exists: " + body.name + " (" + body.provider + "); go to /?page=roles to edit"
            )
        conn.execute(
            """INSERT INTO llm_roles
               (id, name, description, system_prompt, provider, model,
                temperature, max_tokens, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (role_id, body.name, body.description, body.system_prompt,
             body.provider, body.model, body.temperature, body.max_tokens,
             1 if body.enabled else 0),
        )
    return {"id": role_id, "ok": True}


@router.put("/{role_id}")
def update_role(role_id: str, body: RoleUpdate):
    updates = []
    params = []
    for field in ("name", "description", "system_prompt", "provider", "model"):
        val = getattr(body, field)
        if val is not None:
            updates.append(f"{field} = ?")
            params.append(val)
    if body.temperature is not None:
        updates.append("temperature = ?"); params.append(body.temperature)
    if body.max_tokens is not None:
        updates.append("max_tokens = ?"); params.append(body.max_tokens)
    if body.enabled is not None:
        updates.append("enabled = ?"); params.append(1 if body.enabled else 0)
    if not updates:
        raise HTTPException(400, "Nothing to update")
    updates.append("updated_at = datetime('now')")
    params.append(role_id)

    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE llm_roles SET {', '.join(updates)} WHERE id = ?", params
        )
        if cur.rowcount == 0:
            raise HTTPException(404, f"Role {role_id} not found")
    return {"ok": True}


@router.delete("/{role_id}")
def delete_role(role_id: str):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM llm_roles WHERE id = ?", (role_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, f"Role {role_id} not found")
    return {"ok": True}


@router.get("/{role_id}/refs")
def get_role_refs(role_id: str):
    """Return chapters/steps that reference this role by step_role_id.

    Used by the role management page to surface "this role is used by X steps".
    """
    import json
    with get_conn() as conn:
        meta_row = conn.execute(
            "SELECT name FROM llm_roles WHERE id = ?", (role_id,)
        ).fetchone()
        if not meta_row:
            raise HTTPException(404, "role not found: " + role_id)
        target_name = meta_row["name"]
        rows = conn.execute(
            "SELECT chapter_id, config_json FROM chapter_configs WHERE active = 1"
        ).fetchall()
    refs = []
    for r in rows:
        try:
            cfg = json.loads(r["config_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        for ex in cfg.get("exercises") or []:
            if ex.get("step_role_id") == target_name:
                refs.append({
                    "chapter_id": r["chapter_id"],
                    "step_id": ex.get("step_id", ""),
                    "step_name": ex.get("name", ""),
                })
    return {"role_id": role_id, "name": target_name, "refs": refs, "count": len(refs)}


class BulkDisableIn(BaseModel):
    confirm: bool = False


@router.post("/bulk-disable-empty")
def bulk_disable_empty(body: BulkDisableIn):
    """Soft-disable (enabled=0) all llm_roles whose system_prompt is empty/short.

    Empty definition: system_prompt IS NULL OR trim(length) < 10.
    Safety: requires `confirm: true` in body; otherwise returns candidate list
    (dry-run). Soft-disable only (enabled=0, not DELETE) so the user can
    re-enable via PUT if they change their mind. Never silent batch-disable.
    """
    with get_conn() as conn:
        candidates = conn.execute(
            "SELECT id, name, provider, length(trim(system_prompt)) AS L,"
            " substr(system_prompt, 1, 60) AS preview"
            " FROM llm_roles WHERE enabled = 1"
            " AND (system_prompt IS NULL OR length(trim(system_prompt)) < 10)"
        ).fetchall()
        if not body.confirm:
            return {
                "confirmed": False,
                "candidates": [dict(r) for r in candidates],
                "count": len(candidates),
                "note": "send {\"confirm\": true} to actually disable",
            }
        n = conn.execute(
            "UPDATE llm_roles SET enabled = 0, updated_at = datetime('now')"
            " WHERE enabled = 1"
            " AND (system_prompt IS NULL OR length(trim(system_prompt)) < 10)"
        ).rowcount
    return {"confirmed": True, "disabled_count": n}