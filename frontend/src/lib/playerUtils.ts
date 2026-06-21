import { PowerRankingPlayer } from "@/lib/api";

/** Cor de score (0–10) em 5 bandas. */
export function scoreColor(v: number | null): string {
  if (v == null) return "var(--text-muted)";
  if (v >= 8.5) return "#22c55e";   // green
  if (v >= 8.0) return "#84cc16";   // lime
  if (v >= 7.5) return "#eab308";   // yellow
  if (v >= 7.0) return "#f97316";   // orange
  return "#ef4444";                  // red
}

/** Cor de barra por posição no ranking (verde topo → amarelo meio → vermelho fim). */
export function rankBarColor(rank: number, total: number): string {
  const t = total <= 1 ? 0 : (rank - 1) / (total - 1); // 0=1º, 1=último
  if (t <= 0.5) {
    // verde → amarelo
    const f = t / 0.5;
    const r = Math.round(34 + f * (234 - 34));
    const g = Math.round(197 + f * (179 - 197));
    const b = Math.round(94 + f * (8 - 94));
    return `rgb(${r},${g},${b})`;
  } else {
    // amarelo → vermelho
    const f = (t - 0.5) / 0.5;
    const r = Math.round(234 + f * (239 - 234));
    const g = Math.round(179 + f * (68 - 179));
    const b = Math.round(8 + f * (68 - 8));
    return `rgb(${r},${g},${b})`;
  }
}

/** Label de posição. */
export function positionLabel(playerType: string): string {
  return playerType === "goalkeeper" ? "Goleiro" : "Linha";
}

/** Score composto ponderado. */
export function compositeScore(p: PowerRankingPlayer): number | null {
  if (p.player_type === "goalkeeper") {
    const atk = p.attacking_score;
    const def = p.defensive_score;
    if (atk === null && def === null) return null;
    if (atk === null) return def !== null ? def * 0.6 : null;
    if (def === null) return atk * 0.4;
    return atk * 0.4 + def * 0.6;
  }
  const atk = p.attacking_score;
  const def = p.defensive_score;
  const crt = p.creativity_score;
  if (atk === null && def === null && crt === null) return null;
  let score = 0;
  let weight = 0;
  if (atk !== null) { score += atk * 0.4; weight += 0.4; }
  if (def !== null) { score += def * 0.3; weight += 0.3; }
  if (crt !== null) { score += crt * 0.3; weight += 0.3; }
  return weight > 0 ? score / weight : null;
}

/** Formata ranking com seta de change. */
export function rankLabel(
  rank: number | null,
  change: number | null
): { rank: string; arrow: "↑" | "↓" | "—"; color: string } {
  const rankStr = rank !== null ? `#${rank}` : "—";
  if (change === null || change === 0) {
    return { rank: rankStr, arrow: "—", color: "var(--text-muted)" };
  }
  if (change > 0) {
    return { rank: rankStr, arrow: "↑", color: "var(--green)" };
  }
  return { rank: rankStr, arrow: "↓", color: "var(--red)" };
}
