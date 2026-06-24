// Mapa único de fases FIFA (string do gold, em inglês) → rótulo pt-BR + ordem.
// Reaproveitado pelos seletores de escopo e visões de bolão.

export const STAGE_ORDER = [
  "First Stage",
  "Round of 32",
  "Round of 16",
  "Quarter-final",
  "Semi-final",
  "Play-off for third place",
  "Final",
] as const;

export type Stage = (typeof STAGE_ORDER)[number];

const STAGE_PTBR: Record<string, string> = {
  "First Stage": "Fase de Grupos",
  "Round of 32": "16-avos de Final",
  "Round of 16": "Oitavas de Final",
  "Quarter-final": "Quartas de Final",
  "Semi-final": "Semifinal",
  "Play-off for third place": "Disputa 3º lugar",
  "Final": "Final",
};

export function stageLabel(s: string | null | undefined): string {
  return STAGE_PTBR[s ?? ""] ?? s ?? "Fase";
}

export function stageRank(s: string | null | undefined): number {
  const i = STAGE_ORDER.indexOf((s ?? "") as Stage);
  return i === -1 ? 99 : i;
}
