from pathlib import Path

from fifa_analytics.config import load_config
from fifa_analytics.paths import FINAL_REPORTS_DIR, FRAGMENTS_DIR, MANIFESTS_DIR
from fifa_analytics.utils.io import ensure_dir, write_yaml
from fifa_analytics.utils.time import utc_now_iso


def build_match_report(
    match_id: str,
    data_quality_status: str = "desconhecido",
    extra_manifest: dict[str, object] | None = None,
) -> dict[str, str | Path | list[str]]:
    section_config = load_config("report_sections.yaml")["match_report_sections"]
    fragment_dir = FRAGMENTS_DIR / match_id
    ensure_dir(FINAL_REPORTS_DIR)
    ensure_dir(MANIFESTS_DIR)

    parts = []
    missing_sections = []
    for section in section_config:
        fragment_path = fragment_dir / f"{section['id']}.md"
        if fragment_path.exists():
            parts.append(fragment_path.read_text(encoding="utf-8").strip())
        else:
            missing_sections.append(section["id"])
            if section.get("required"):
                parts.append(f"## {section['title']}\n\nSecao pendente: fragmento `{section['id']}` nao encontrado.")

    report_path = FINAL_REPORTS_DIR / f"{match_id}.md"
    report_path.write_text("\n\n".join(part for part in parts if part) + "\n", encoding="utf-8")

    manifest = {
        "match_id": match_id,
        "report_status": "completo" if not missing_sections else "parcial",
        "missing_sections": missing_sections,
        "data_quality_status": data_quality_status,
        "last_updated_at": utc_now_iso(),
        "final_report_path": str(report_path),
    }
    if extra_manifest:
        manifest.update(extra_manifest)
    manifest_path = write_yaml(MANIFESTS_DIR / f"{match_id}.yaml", manifest)

    return {"report_path": report_path, "manifest_path": manifest_path, **manifest}
