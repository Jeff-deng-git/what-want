"""PromptRenderer: Jinja2 strict undefined, nested step refs, preserve_output guard."""
import pytest
from app.services.prompt_renderer import PromptRenderer


def test_renders_nested_step_reference():
    r = PromptRenderer()
    out = r.render(
        "Hi {{ step_1.answers[0].text }}",
        {"step_1": {"answers": [{"text": "world"}]}},
    )
    assert out == "Hi world"


def test_missing_variable_raises():
    r = PromptRenderer()
    with pytest.raises(ValueError, match="Prompt render failed"):
        r.render("{{ step_9.answers }}", {})


def test_preserve_output_conditional_renders_when_locked():
    r = PromptRenderer()
    out = r.render(
        "{% if preserve_output and preserve_output.keywords %}LOCKED{% endif %}",
        {"preserve_output": {"keywords": [{"value": "x", "locked": True}]}},
    )
    assert out == "LOCKED"


def test_preserve_output_conditional_skips_when_empty():
    r = PromptRenderer()
    out = r.render(
        "{% if preserve_output and preserve_output.keywords %}LOCKED{% endif %}",
        {"preserve_output": {}},
    )
    assert out == ""


def test_jinja_for_loop_over_answers():
    r = PromptRenderer()
    tmpl = "{% for q in step_1.answers %}{{ loop.index }}:{{ q.text }}\n{% endfor %}"
    ctx = {"step_1": {"answers": [{"text": "a"}, {"text": "b"}]}}
    out = r.render(tmpl, ctx)
    assert "1:a" in out and "2:b" in out
