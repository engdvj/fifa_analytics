"use client";

import { useMemo } from "react";
import { Match } from "@/lib/api";

interface ProgressDotsProps {
  matches: Match[]; // TODOS os jogos (match_number real + stage real)
  matchSnapshot: Map<string, number>; // match_id → snapshot (só finalizados)
  currentSnapshot: number;
  onSelect: (snapshot: number) => void;
}

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

export default function ProgressDots({ matches, matchSnapshot, currentSnapshot, onSelect }: ProgressDotsProps) {
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
    <div style={{ overflowX: "auto", padding: "8px 6px 12px", display: "flex", alignItems: "stretch", width: "100%" }}>
      {groups.map((g, gi) => {
        // largura mínima = espaço real dos dots (16px cada) ou o rótulo, o que for
        // maior — garante que nada embola e que as fases curtas têm folga.
        const minW = Math.max(g.matches.length * 16 + 24, 86);
        return (
        <div
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
                const snap = matchSnapshot.get(m.match_id);
                const hasData = snap !== undefined;
                const isCurrent = hasData && snap === currentSnapshot;
                const isDone = hasData && (snap as number) < currentSnapshot;
                const isPhaseEnd = m.match_number === g.endMatchNumber;
                const marker = isPhaseEnd ? (TERMINAL_STAGES.has(g.stage) ? "🏆" : "⚽") : null;
                const size = isCurrent ? 15 : 11;
                let bg = "transparent";
                let border = `2px solid ${g.color}55`;
                let shadow = "none";
                if (isCurrent) {
                  bg = "#2dd4ff"; border = "2px solid white"; shadow = "0 0 9px 2px #2dd4ffcc";
                } else if (isDone) {
                  bg = g.color; border = "none";
                } else if (hasData) {
                  bg = `${g.color}55`; border = `2px solid ${g.color}`;
                }
                // O marcador de fim de fase (⚽/🏆) vira o próprio "dot": brilho dourado.
                if (marker && !isCurrent) {
                  shadow = `0 0 0 1px ${hasData ? "#ffffff88" : "#6b728088"}, 0 0 8px 2px ${hasData ? "#f5c542aa" : "#6b728044"}`;
                }
                return (
                  <button
                    key={m.match_id}
                    onClick={() => hasData && onSelect(snap as number)}
                    title={tooltip(m)}
                    aria-label={tooltip(m)}
                    disabled={!hasData}
                    style={{
                      position: "relative",
                      width: marker ? 17 : size, height: marker ? 17 : size, borderRadius: "50%",
                      background: marker ? "transparent" : bg, border: marker ? "none" : border, padding: 0,
                      cursor: hasData ? "pointer" : "default", boxShadow: marker ? "none" : shadow,
                      transform: isCurrent ? "scale(1.3)" : "scale(1)", transition: "all 0.15s",
                      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                      opacity: hasData ? 1 : marker ? 0.5 : 0.35,
                    }}
                  >
                    {marker && (
                      <span style={{ fontSize: 16, lineHeight: 1, filter: hasData ? "drop-shadow(0 1px 2px rgba(0,0,0,0.85))" : "grayscale(1) opacity(0.7)" }}>
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
  );
}
