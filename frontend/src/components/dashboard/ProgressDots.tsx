"use client";

import { useMemo } from "react";
import { Match } from "@/lib/api";
import { flag } from "@/lib/teamUtils";

interface ProgressDotsProps {
  matches: Match[];
  currentGame: number;
  onSelect: (n: number) => void;
}

const PHASE_ORDER = [
  "Fase de Grupos", "Oitavas de Final", "Quartas de Final",
  "Semifinal", "Disputa do 3º lugar", "Final"
];

const PHASE_COLORS: Record<string, string> = {
  "Fase de Grupos": "#58a6ff",
  "Oitavas de Final": "#a78bfa",
  "Quartas de Final": "#f97316",
  "Semifinal": "#f5c542",
  "Disputa do 3º lugar": "#9ca3af",
  "Final": "#22c55e",
};

function matchTooltip(m: Match): string {
  const home = m.home_team ?? "?";
  const away = m.away_team ?? "?";
  const hf = flag(m.home_team);
  const af = flag(m.away_team);
  if (m.home_score != null && m.away_score != null) {
    return `J${m.match_number} · ${hf}${home} ${m.home_score}×${m.away_score} ${away}${af}`;
  }
  return `J${m.match_number} · ${hf}${home} vs ${away}${af}`;
}

export default function ProgressDots({ matches, currentGame, onSelect }: ProgressDotsProps) {
  // Group by stage
  const groups = useMemo(() => {
    const map = new Map<string, Match[]>();
    for (const m of matches) {
      const stage = m.stage ?? "Fase de Grupos";
      if (!map.has(stage)) map.set(stage, []);
      map.get(stage)!.push(m);
    }
    // Sort groups by phase order, then unknown phases at end
    const sorted: [string, Match[]][] = [];
    for (const phase of PHASE_ORDER) {
      if (map.has(phase)) sorted.push([phase, map.get(phase)!]);
    }
    for (const [k, v] of map) {
      if (!PHASE_ORDER.includes(k)) sorted.push([k, v]);
    }
    return sorted;
  }, [matches]);

  const maxGame = matches.length > 0 ? Math.max(...matches.map(m => m.match_number)) : 0;

  return (
    <div style={{
      overflowX: "auto",
      padding: "6px 0",
      display: "flex",
      alignItems: "flex-start",
      gap: 16,
    }}>
      {groups.map(([phase, phaseMatches]) => {
        const phaseColor = PHASE_COLORS[phase] ?? "#58a6ff";
        return (
          <div key={phase} style={{ flexShrink: 0 }}>
            {/* Phase label */}
            <div style={{
              fontSize: 9,
              fontWeight: 600,
              color: phaseColor,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 5,
              whiteSpace: "nowrap",
            }}>
              {phase}
            </div>
            {/* Dots row */}
            <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
              {phaseMatches
                .sort((a, b) => a.match_number - b.match_number)
                .map(m => {
                  const isCurrent = m.match_number === currentGame;
                  const isDone = m.match_number < currentGame;
                  const isLast = m.match_number === maxGame;

                  const dotSize = isCurrent ? 12 : 9;
                  let bg = "transparent";
                  let border = `2px solid ${phaseColor}44`;
                  let shadow = "none";

                  if (isCurrent) {
                    bg = "#2dd4ff";
                    border = "2px solid white";
                    shadow = "0 0 9px 2px #2dd4ffcc";
                  } else if (isDone) {
                    bg = phaseColor;
                    border = "none";
                  }
                  if (isLast && !isCurrent) {
                    shadow = `0 0 5px 1px ${phaseColor}88`;
                  }

                  return (
                    <div key={m.match_id} style={{ position: "relative" }} className="group">
                      <button
                        onClick={() => onSelect(m.match_number)}
                        title={matchTooltip(m)}
                        aria-label={matchTooltip(m)}
                        style={{
                          width: dotSize,
                          height: dotSize,
                          borderRadius: "50%",
                          background: bg,
                          border,
                          padding: 0,
                          cursor: "pointer",
                          boxShadow: shadow,
                          transform: isCurrent ? "scale(1.3)" : "scale(1)",
                          transition: "all 0.15s",
                          display: "block",
                        }}
                      />
                      {/* Tooltip */}
                      <div style={{
                        position: "absolute",
                        bottom: "calc(100% + 8px)",
                        left: "50%",
                        transform: "translateX(-50%)",
                        background: "#0d1117",
                        border: "1px solid #2b3950",
                        borderRadius: 8,
                        padding: "5px 10px",
                        fontSize: 11,
                        color: "#c8d3e0",
                        whiteSpace: "nowrap",
                        pointerEvents: "none",
                        opacity: 0,
                        zIndex: 50,
                        transition: "opacity 0.12s",
                      }}
                        className="group-hover:opacity-100"
                      >
                        {matchTooltip(m)}
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
