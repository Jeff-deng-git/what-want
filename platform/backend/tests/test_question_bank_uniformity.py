"""Contract tests for the cross-chapter question bank uniformity (方案A)."""

import json
from pathlib import Path

PROJECT_ROOT = Path(r"D:\AI_Project\What_Want")
CONFIG_DIR = PROJECT_ROOT / "llm_prompt_design" / "config" / "chapters"


def load_config(chapter_id):
    return json.loads((CONFIG_DIR / f"chapter_config_{chapter_id}.json").read_text(encoding="utf-8"))


def test_ch04_has_value_questions_and_100_values_examples():
    cfg = load_config("ch04")
    step1_fields = {field["name"]: field for field in cfg["exercises"][0]["input_schema"]}
    assert "value_questions" in step1_fields
    assert step1_fields["value_questions"]["type"] == "list_of_items"
    assert step1_fields["value_questions"]["required"] is False
    assert len(cfg["ui_context"]["values_examples"]) == 100


def test_ch05_has_talent_questions_and_100_strength_examples():
    cfg = load_config("ch05")
    step1_fields = {field["name"]: field for field in cfg["exercises"][0]["input_schema"]}
    assert "talent_questions" in step1_fields
    assert step1_fields["talent_questions"]["type"] == "list_of_items"
    assert step1_fields["talent_questions"]["required"] is False
    assert len(cfg["ui_context"]["strength_examples"]) == 100


def test_ch06_baseline_remains_passion_questions_and_100_passion_examples():
    cfg = load_config("ch06")
    step1_fields = {field["name"]: field for field in cfg["exercises"][0]["input_schema"]}
    assert "passion_questions" in step1_fields
    assert len(cfg["ui_context"]["passion_examples"]) == 100
