"use client";

import { useRef } from "react";
import { Match } from "@/lib/api";

interface ProgressDotsProps {
  matches: Match[];
  currentGame: number;
  onSelect: (n: number) => void;
}

function matchLabel(m: Match) {
  const home = m.home_team ?? "?";
  const away = m.away_team ?? "?";
  if (m.home_score != null && m.away_score != null) {
    return `Jogo ${m.match_number} · ${home} ${m.home_score}x${m.away_score} ${away}`;
  }
  return `Jogo ${m.match_number} · ${home} vs ${away}`;
}

export default function ProgressDots({ matches, currentGame, onSelect }: ProgressDotsProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={containerRef}
      style={{ overflowX: "auto", padding: "8px 4px" }}
      className="flex items-center gap-1.5"
    >
      {matches.map((m) => {
        const active = m.match_number === currentGame;
        return (
          <div key={m.match_id} style={{ position: "relative" }} className="group">
            <button
              onClick={() => onSelect(m.match_number)}
              aria-label={matchLabel(m)}
              style={{
                width: active ? 10 : 8,
                height: active ? 10 : 8,
                borderRadius: "50%",
                background: active ? "var(--accent)" : "transparent",
                border: `2px solid ${active ? "var(--accent)" : "var(--border)"}`,
                padding: 0,
                cursor: "pointer",
                transition: "all 0.15s",
                flexShrink: 0,
              }}
              className="hover:border-accent/70"
            />
            <div
              style={{
                position: "absolute",
                bottom: "calc(100% + 6px)",
                left: "50%",
                transform: "translateX(-50%)",
                background: "var(--surface2)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                padding: "4px 8px",
                fontSize: "0.72rem",
                color: "var(--text)",
                whiteSpace: "nowrap",
                pointerEvents: "none",
                opacity: 0,
                transition: "opacity 0.12s",
                zIndex: 10,
              }}
              className="group-hover:opacity-100"
            >
              {matchLabel(m)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
