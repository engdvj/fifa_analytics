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


MANUAL_FRAGMENT_MARKER = "<!-- narrativa-manual -->"


def is_manual_fragment(match_id: str, fragment_name: str) -> bool:
    """Verifica se um fragmento foi escrito manualmente (ex: narrativa via skill
    atualizar-jogo) e por isso nao deve ser sobrescrito pela regeneracao automatica."""
    path = FRAGMENTS_DIR / match_id / f"{fragment_name}.md"
    if not path.exists():
        return False
    return path.read_text(encoding="utf-8").lstrip().startswith(MANUAL_FRAGMENT_MARKER)


def write_fragment(match_id: str, fragment_name: str, content: str, skip_if_manual: bool = False) -> Path:
    fragment_dir = ensure_dir(FRAGMENTS_DIR / match_id)
    path = fragment_dir / f"{fragment_name}.md"
    if skip_if_manual and is_manual_fragment(match_id, fragment_name):
        return path
    path.write_text(content, encoding="utf-8")
    return path

