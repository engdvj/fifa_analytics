from typing import Any


def compare_match_records(primary: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for field in ["home_score", "away_score", "status", "stadium"]:
        primary_value = primary.get(field)
        reference_value = reference.get(field)
        if primary_value is None or reference_value is None:
            status = "ausente"
        elif primary_value == reference_value:
            status = "ok"
        else:
            status = "aviso"
        checks.append(
            {
                "field": field,
                "primary": primary_value,
                "reference": reference_value,
                "status": status,
            }
        )

    overall = "ok"
    if any(check["status"] == "aviso" for check in checks):
        overall = "aviso"
    if any(check["status"] == "ausente" for check in checks):
        overall = "ausente" if overall == "ok" else overall

    return {"status": overall, "checks": checks}
