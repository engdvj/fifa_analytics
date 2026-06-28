"use client";

import { useMemo } from "react";
import { Match } from "@/lib/api";

// Resultado da previsão por jogo (vem do backtest). undefined = modo normal.
type PredCat = "exact" | "winner" | "partial" | "miss";
type PredictionResult = { cat: PredCat; lowConf: boolean };

interface ProgressDotsProps {
  matches: Match[]; // TODOS os jogos (match_number real + stage real)
  matchSnapshot: Map<string, number>; // match_id → snapshot (só finalizados)
  currentSnapshot: number;
  onSelect: (snapshot: number) => void;
  predictionResults?: Map<string, PredictionResult>; // ativa o modo Preditiva
  minPredictionGame?: number; // antes disso: "não previsto"
}

// Cores do modo Preditiva — semáforo de acerto da previsão.
const PRED_COLORS = {
  exact: "#2dd4ff",   // acertou placar EXATO (cravado) — azul
  winner: "#3fb950",  // acertou o vencedor — verde
  partial: "#f5c542", // errou vencedor mas acertou o saldo (chegou perto) — amarelo
  miss: "#f85149",    // errou tudo — vermelho
  future: "#a78bfa",  // jogo futuro (ainda vai prever) — roxo
  notpredicted: "#6b7280", // antes do jogo mínimo — cinza
} as const;

// stage (gold, inglês) → rótulo pt-BR + cor + ordem
const STAGE_PTBR: Record<string, string> = {
  "First Stage": "Grupos",
  "Round of 32": "16-avos",
  "Round of 16": "Oitavas",
  "Quarter-final": "Quartas",
  "Semi-final": "Semifinal",
  "Play-off for third place": "3º lugar",
  "Final": "Final",
};
const STAGE_ORDER = [
  "First Stage", "Round of 32", "Round of 16",
  "Quarter-final", "Semi-final", "Play-off for third place", "Final",
];
const STAGE_COLORS: Record<string, string> = {
  "First Stage": "#58a6ff",
  "Round of 32": "#a78bfa",
  "Round of 16": "#f97316",
  "Quarter-final": "#f5c542",
  "Semi-final": "#34d399",
  "Play-off for third place": "#9ca3af",
  "Final": "#22c55e",
};

function tooltip(m: Match): string {
  const h = m.home_team ?? "?";
  const a = m.away_team ?? "?";
  if (m.home_score != null && m.away_score != null) {
    return `J${m.match_number} · ${h} ${m.home_score}×${m.away_score} ${a}`;
  }
  return `J${m.match_number} · ${h} vs ${a}`;
}

// fases terminais ganham 🏆; as demais (rodadas de grupo + 16-avos/oitavas/
// quartas/semi) ganham ⚽ no ÚLTIMO jogo da fase.
const TERMINAL_STAGES = new Set(["Final", "Play-off for third place"]);

interface Group {
  key: string;
  label: string;
  color: string;
  stage: string;
  matches: Match[];
  endMatchNumber: number; // match_number do último jogo da fase (marcador ⚽/🏆)
}

export default function ProgressDots({ matches, matchSnapshot, currentSnapshot, onSelect, predictionResults }: ProgressDotsProps) {
  const predMode = !!predictionResults;
  const groups = useMemo<Group[]>(() => {
    const byKey = new Map<string, Group>();
    for (const m of matches) {
      const stage = m.stage ?? "First Stage";
      // Fase de grupos: divide em 3 rodadas pelo match_number (≤24, ≤48, resto).
      let key = stage;
      let label = STAGE_PTBR[stage] ?? stage;
      if (stage === "First Stage") {
        const rnd = m.match_number <= 24 ? 1 : m.match_number <= 48 ? 2 : 3;
        key = `First Stage-${rnd}`;
        label = `Grupos · Rodada ${rnd}`;
      }
      if (!byKey.has(key)) {
        byKey.set(key, { key, label, color: STAGE_COLORS[stage] ?? "#58a6ff", stage, matches: [], endMatchNumber: 0 });
      }
      byKey.get(key)!.matches.push(m);
    }
    for (const g of byKey.values()) {
      g.endMatchNumber = Math.max(...g.matches.map((m) => m.match_number));
    }
    // ordena os grupos pela ordem de fase (e rodada dentro de grupos)
    return [...byKey.values()].sort((a, b) => {
      const sa = STAGE_ORDER.findIndex((s) => a.key.startsWith(s));
      const sb = STAGE_ORDER.findIndex((s) => b.key.startsWith(s));
      if (sa !== sb) return sa - sb;
      return a.key.localeCompare(b.key);
    });
  }, [matches]);

  return (
    <div className="v2-progress-dots">
      {predMode && (
        <div className="v2-progress-legend" style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center", padding: "2px 8px 8px", fontSize: 11, color: "#8b949e" }}>
          <LegendItem color={PRED_COLORS.exact} label="placar cravado" />
          <LegendItem color={PRED_COLORS.winner} label="acertou vencedor" />
          <LegendItem color={PRED_COLORS.partial} label="acertou só o saldo" />
          <LegendItem color={PRED_COLORS.miss} label="errou" />
          <LegendItem color={PRED_COLORS.future} label="vai prever" hollow />
          <LegendItem color="#8b949e" label="pouca base (não conta)" dashed />
          <LegendItem color={PRED_COLORS.notpredicted} label="sem base" />
        </div>
      )}
      <div className="v2-progress-scroll" style={{ overflowX: "auto", padding: "8px 6px 12px", display: "flex", alignItems: "stretch", width: "100%" }}>
      {groups.map((g, gi) => {
        // largura mínima = espaço real dos dots (16px cada) ou o rótulo, o que for
        // maior — garante que nada embola e que as fases curtas têm folga.
        const minW = Math.max(g.matches.length * 16 + 24, 86);
        return (
        <div
          className="v2-progress-group"
          key={g.key}
          style={{
            flex: `${g.matches.length} 1 auto`, minWidth: minW,
            display: "flex", flexDirection: "column", alignItems: "center",
            padding: "0 14px",
            borderLeft: gi > 0 ? "1px solid #222b38" : "none",
          }}
        >
          <div style={{ fontSize: 10, fontWeight: 700, color: g.color, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 9, whiteSpace: "nowrap", textAlign: "center" }}>
            {g.label}
          </div>
          <div style={{ display: "flex", gap: 5, alignItems: "center", justifyContent: "center", minHeight: 18 }}>
            {g.matches
              .sort((a, b) => a.match_number - b.match_number)
              .map((m) => {
                const finalizedSnap = matchSnapshot.get(m.match_id);
                const snap = finalizedSnap ?? m.match_number;
                const hasData = finalizedSnap !== undefined;
                const canSelect = !!m.home_team && !!m.away_team;
                const isCurrent = snap === currentSnapshot;
                const isDone = hasData && finalizedSnap < currentSnapshot;
                const isPhaseEnd = m.match_number === g.endMatchNumber;
                const marker = isPhaseEnd ? (TERMINAL_STAGES.has(g.stage) ? "🏆" : "⚽") : null;
                const size = isCurrent ? 15 : 11;
                let bg = "transparent";
                let border = `2px solid ${g.color}55`;
                let shadow = "none";
                let predLabel: string | null = null;
                let predLowConf = false;
                if (predMode) {
                  // Semáforo de acerto: cada jogo finalizado pega a cor do resultado
                  // da previsão. Jogos de baixa confiança (antes do jogo mínimo)
                  // mostram a cor, mas com borda tracejada e mais apagada.
                  const result = predictionResults!.get(m.match_id);
                  let color: string = PRED_COLORS.future;
                  if (result) {
                    predLowConf = result.lowConf;
                    if (result.cat === "exact") { color = PRED_COLORS.exact; predLabel = "cravou o placar exato"; }
                    else if (result.cat === "winner") { color = PRED_COLORS.winner; predLabel = "acertou o vencedor"; }
                    else if (result.cat === "partial") { color = PRED_COLORS.partial; predLabel = "errou o vencedor, mas acertou o saldo"; }
                    else { color = PRED_COLORS.miss; predLabel = "errou"; }
                    if (predLowConf) predLabel += " · pouca base (não conta na métrica)";
                  } else if (hasData) {
                    color = PRED_COLORS.notpredicted; predLabel = "não previsto (sem base)";
                  } else {
                    predLabel = "ainda vai prever";
                  }
                  bg = result ? color : `${color}33`;
                  border = `2px ${predLowConf ? "dashed" : "solid"} ${color}`;
                  if (isCurrent) { border = "2px solid white"; shadow = `0 0 9px 2px ${color}cc`; }
                } else if (isCurrent) {
                  bg = "#2dd4ff"; border = "2px solid white"; shadow = "0 0 9px 2px #2dd4ffcc";
                } else if (isDone) {
                  bg = g.color; border = "none";
                } else if (hasData) {
                  bg = `${g.color}55`; border = `2px solid ${g.color}`;
                } else if (canSelect) {
                  bg = "transparent"; border = `2px solid ${g.color}88`;
                }
                // O marcador de fim de fase (⚽/🏆) vira o próprio "dot": brilho dourado.
                // No modo Preditiva os marcadores não roubam a cor do semáforo.
                if (marker && !isCurrent && !predMode) {
                  shadow = `0 0 0 1px ${hasData ? "#ffffff88" : "#6b728088"}, 0 0 8px 2px ${hasData ? "#f5c542aa" : "#6b728044"}`;
                }
                const showMarker = marker && !predMode;
                const title = predLabel ? `${tooltip(m)} — ${predLabel}` : tooltip(m);
                return (
                  <button
                    key={m.match_id}
                    onClick={() => canSelect && onSelect(snap)}
                    title={title}
                    aria-label={title}
                    disabled={!canSelect}
                    style={{
                      position: "relative",
                      width: showMarker ? 17 : size, height: showMarker ? 17 : size, borderRadius: "50%",
                      background: showMarker ? "transparent" : bg, border: showMarker ? "none" : border, padding: 0,
                      cursor: canSelect ? "pointer" : "default", boxShadow: showMarker ? "none" : shadow,
                      transform: isCurrent ? "scale(1.3)" : "scale(1)", transition: "all 0.15s",
                      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                      opacity: !canSelect ? (showMarker ? 0.5 : 0.35) : predLowConf ? 0.5 : 1,
                    }}
                  >
                    {showMarker && (
                      <span style={{ fontSize: 16, lineHeight: 1, filter: canSelect ? "drop-shadow(0 1px 2px rgba(0,0,0,0.85))" : "grayscale(1) opacity(0.7)" }}>
                        {marker}
                      </span>
                    )}
                  </button>
                );
              })}
          </div>
        </div>
        );
      })}
      </div>
    </div>
  );
}

function LegendItem({ color, label, hollow, dashed }: { color: string; label: string; hollow?: boolean; dashed?: boolean }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{ width: 10, height: 10, borderRadius: "50%", background: hollow || dashed ? `${color}33` : color, border: `2px ${dashed ? "dashed" : "solid"} ${color}`, flexShrink: 0, opacity: dashed ? 0.6 : 1 }} />
      {label}
    </span>
  );
}
