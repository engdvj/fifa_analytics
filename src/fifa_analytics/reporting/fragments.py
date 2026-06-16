from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from fifa_analytics.paths import FRAGMENTS_DIR, TEMPLATES_DIR
from fifa_analytics.utils.io import ensure_dir


def render_template(template_name: str, context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_name)
    return template.render(**context)


def write_fragment(match_id: str, fragment_name: str, content: str) -> Path:
    fragment_dir = ensure_dir(FRAGMENTS_DIR / match_id)
    path = fragment_dir / f"{fragment_name}.md"
    path.write_text(content, encoding="utf-8")
    return path

