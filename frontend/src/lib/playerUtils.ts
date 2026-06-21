import { PowerRankingPlayer } from "@/lib/api";

/** Cor de score (0–10). */
export function scoreColor(v: number | null): string {
  if (v === null) return "var(--text-muted)";
  if (v >= 7) return "var(--green)";
  if (v >= 5) return "var(--yellow)";
  return "var(--red)";
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
