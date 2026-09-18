# What Want Code Review (2026-08-04)

Scope: files touched in this refactor (backend + frontend single-file index.html).

## 0. Positive findings
- app/main.py: include_router moved after route decorators (config endpoint now works).
- All routers use parameterized SQL (? placeholders). No string concatenation into SQL.
- Legacy jinja2 path removed (M3.3 Q9 = drop jinja2). mentor/summary use USE_AGENT_* env (reversible).
- chapter_config exercises[] bridge, role lock, ch07 upstream gating all in place.
- 93 backend tests pass; manual browser regression complete for chapter/role pages.

## P0 - Correctness / data integrity

### P0-1 SQLite check_same_thread=False missing
- File: app/db.py:get_conn
- Issue: sqlite3.connect() defaults to check_same_thread=True. FastAPI runs handlers in a thread pool; concurrent requests on the same connection will raise ProgrammingError.
- Fix: connect(..., check_same_thread=False, timeout=10.0); consider PRAGMA journal_mode=WAL for concurrency.

### P0-2 chat persistence is not atomic
- File: app/routers/chat.py:_send_message_v2
- Issue: Two INSERT INTO chapter_chat run inside one contextmanager, but if the second raises after the first commits, the user message is persisted without a mentor reply.
- Fix: Wrap both inserts in a single transaction; on exception, rollback both.

### P0-3 step_run status machine allows downgrades
- File: app/routers/steps.py:save_draft / _run_step_option_b / submit_step
- Issue: After a step is submitted, calling /draft overwrites it back to draft (no guard). Re-running /run reuses the same row. There is no documented state transition table.
- Fix: On save_draft, refuse if current status == submitted, or insert a new draft row keyed by (chapter_id, step_id, version). Document the allowed transitions.

### P0-4 user_answers not validated against input_schema
- File: app/routers/steps.py:save_draft; app/routers/steps.py:run (Pydantic DraftIn.user_answers: Any)
- Issue: Schema-aware fields (checklist, list_of_items, select options) are persisted as raw JSON without server-side validation. Malformed data will later reach the LLM prompt.
- Fix: In save_draft, load step config; if input_schema exists, validate required, list length, item ids, option whitelist; return 422 on failure.

### P0-5 mentor history has no token budget
- File: app/runtime/agent.py HISTORY_LIMIT=12; app/routers/chat.py HISTORY_LIMIT=10
- Issue: Two different HISTORY_LIMIT constants. No character/token budget on history concatenation. Long chapters may push the system+user over STEP_TOKEN_GUARD silently.
- Fix: Extract one constant; add a budget guard similar to build_step_prompt (drop oldest messages until under budget).

## P1 - Consistency / performance

### P1-1 Pydantic DraftIn.user_answers: Any without validation
- See P0-4.

### P1-2 list_roles group_by_name uses full table scan
- File: app/routers/roles.py
- Issue: ROW_NUMBER PARTITION BY scans all rows. Fine for now (<= 20 rows).
- Fix: Defer; add (name, provider) index if row count > 1k.

### P1-3 chat ordering relies on rowid tiebreak
- File: app/routers/chat.py:_history
- Issue: datetime('now') has 1s precision; user + mentor rows in the same second can swap order.
- Fix: Use timestamp with sub-second precision or order by rowid explicitly.

### P1-4 get_role_refs parses all chapter_configs JSON per request
- File: app/routers/roles.py:get_role_refs
- Issue: O(N chapter configs) per role reference query. Acceptable at 8 chapters.
- Fix: Defer until N > 50; add chapter_config_meta(chapter_id, step_id, role_name) when needed.

### P1-5 LLM client timeout/retry not yet reviewed
- File: app/services/llm_client.py
- Fix: Add 30s timeout, 1 retry on transient failure, and prompt-length guard.

### P1-6 Frontend fetch has no timeout/retry helper
- File: frontend/index.html
- Issue: Many fetch calls have no AbortController; errors are surfaced via alert(). Multiple tab switches can pile up requests.
- Fix: Add fetchJson helper with 30s timeout, one retry, and toast-based errors.

## P2 - Style / robustness

### P2-1 Mojibake in docstrings/comments
- Several files have garbled Chinese in docstrings (chat.py, steps.py, main.py).
- Fix: Replace with readable Chinese or English in one sweep.

### P2-2 Stray .bak-* files inside app/ directory
- app/runtime/assembler.py.bak-m58-step3, app/db.py.bak-20260804-155056, etc.
- Fix: Move to backups/ subdir or delete once git tracks current versions.

### P2-3 Legacy paths still use deepseek-chat
- File: app/routers/chat.py:_send_message_legacy, app/routers/summary.py:_regenerate_legacy
- Issue: model=deepseek-chat is retired. If USE_AGENT_CHAT=0 is ever set, calls fail immediately.
- Fix: Read model from env or hardcode DeepSeek-V4-Flash to keep rollback viable.

### P2-4 md[:12000] duplicated
- File: app/routers/chat.py, summary.py, agent.py
- Fix: Move to app.config constant SUMMARY_MD_CAP.

### P2-5 Single-file frontend with no JSDoc
- File: frontend/index.html
- Fix: Add JSDoc to top-level functions (renderStepBody, renderBridgeCard, openBridgeChat).

### P2-6 API base hardcoded in HTML
- File: frontend/index.html (top const API)
- Fix: Allow ?api=... override or read window.location.

## Recommended order of work
1. P0-1 SQLite threading.
2. P0-3 step status machine.
3. P0-4 + P1-1 user_answers validation.
4. P0-5 chat history budget.
5. P2-3 legacy model name.
6. P1-5/P1-6 timeout/retry.
