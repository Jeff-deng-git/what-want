"""Unified Agent runtime package.

Single dispatcher for step / mentor / summary agent types, replacing the
hardcoded call_llm invocations in chat.py, summary.py, step_runner.py.

This is the REFACTOR STARTING POINT (draft). Routes are NOT yet rewired to
import this package; see TODOs in each router. Design authority:
llm_prompt_design/docs/mentor_design_spec.md (S2, S5, S12).
"""
from app.runtime.agent import run_mentor, run_summary
from app.runtime.config_loader import (
    load_role,
    load_chapter_config,
    load_profile,
    save_profile,
)
from app.runtime.assembler import build_mentor_prompt, build_summary_prompt

__all__ = [
    "run_mentor",
    "run_summary",
    "load_role",
    "load_chapter_config",
    "load_profile",
    "save_profile",
    "build_mentor_prompt",
    "build_summary_prompt",
]

