"""Prompt renderer: Jinja2 template with step reference resolution.

Usage:
  renderer = PromptRenderer()
  rendered = renderer.render(
      template_str="{{ step_1.answers }}",
      ctx={"step_1": {"answers": [...], "output": {...}}}
  )
"""
from jinja2 import Environment, StrictUndefined, TemplateError


class PromptRenderer:
    def __init__(self):
        self.env = Environment(
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )

    def render(self, template_str: str, context: dict) -> str:
        """Render a Jinja2 template with strict undefined (missing var = error)."""
        try:
            tmpl = self.env.from_string(template_str)
            return tmpl.render(**context)
        except TemplateError as e:
            raise ValueError(f"Prompt render failed: {e}")
