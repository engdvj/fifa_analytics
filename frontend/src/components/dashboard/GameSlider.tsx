"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Match } from "@/lib/api";

interface GameSliderProps {
  matches: Match[];
  currentGame: number;
  onGameChange: (n: number) => void;
}

type Speed = "slow" | "normal" | "fast";
const SPEED_MS: Record<Speed, number> = { slow: 2000, normal: 1000, fast: 400 };

function matchLabel(m: Match | undefined) {
  if (!m) return "";
  const home = m.home_team ?? "?";
  const away = m.away_team ?? "?";
  return `${home} vs ${away}`;
}

export default function GameSlider({ matches, currentGame, onGameChange }: GameSliderProps) {
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>("normal");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const currentGameRef = useRef(currentGame);
  currentGameRef.current = currentGame;

  const maxGame = matches.length > 0 ? Math.max(...matches.map((m) => m.match_number)) : 1;
  const minGame = matches.length > 0 ? Math.min(...matches.map((m) => m.match_number)) : 1;
  const maxGameRef = useRef(maxGame);
  maxGameRef.current = maxGame;

  const step = useCallback(
    (dir: 1 | -1) => {
      onGameChange(Math.min(maxGame, Math.max(minGame, currentGame + dir)));
    },
    [currentGame, maxGame, minGame, onGameChange]
  );

  useEffect(() => {
    if (!playing) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    intervalRef.current = setInterval(() => {
      const next = currentGameRef.current + 1;
      if (next > maxGameRef.current) {
        setPlaying(false);
        if (intervalRef.current) clearInterval(intervalRef.current);
        return;
      }
      onGameChange(next);
    }, SPEED_MS[speed]);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [playing, speed, onGameChange]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight") step(1);
      else if (e.key === "ArrowLeft") step(-1);
      else if (e.key === " ") {
        e.preventDefault();
        setPlaying((p) => !p);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [step]);

  const currentMatch = matches.find((m) => m.match_number === currentGame);

  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "12px 16px",
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: 12,
      }}
    >
      <button
        onClick={() => setPlaying((p) => !p)}
        style={{
          background: "var(--accent)",
          color: "#0d1117",
          border: "none",
          borderRadius: 6,
          width: 36,
          height: 36,
          fontSize: "1rem",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          fontWeight: 700,
        }}
        aria-label={playing ? "Pausar" : "Reproduzir"}
      >
        {playing ? "⏸" : "▶"}
      </button>

      <button
        onClick={() => step(-1)}
        disabled={currentGame <= minGame}
        style={{
          background: "var(--surface2)",
          border: "1px solid var(--border)",
          borderRadius: 6,
          width: 32,
          height: 32,
          cursor: currentGame <= minGame ? "not-allowed" : "pointer",
          color: currentGame <= minGame ? "var(--text-muted)" : "var(--text)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
        aria-label="Jogo anterior"
      >
        ◀
      </button>

      <button
        onClick={() => step(1)}
        disabled={currentGame >= maxGame}
        style={{
          background: "var(--surface2)",
          border: "1px solid var(--border)",
          borderRadius: 6,
          width: 32,
          height: 32,
          cursor: currentGame >= maxGame ? "not-allowed" : "pointer",
          color: currentGame >= maxGame ? "var(--text-muted)" : "var(--text)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
        aria-label="Próximo jogo"
      >
        ▶
      </button>

      <div style={{ flex: 1, minWidth: 160 }}>
        <input
          type="range"
          min={minGame}
          max={maxGame}
          value={currentGame}
          onChange={(e) => onGameChange(Number(e.target.value))}
          style={{ width: "100%", accentColor: "var(--accent)", cursor: "pointer" }}
        />
      </div>

      <div style={{ minWidth: 90, textAlign: "center" }}>
        <div style={{ fontWeight: 700, fontSize: "0.85rem", color: "var(--accent)" }}>
          Jogo {currentGame}
        </div>
        {currentMatch && (
          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: 1 }}>
            {matchLabel(currentMatch)}
          </div>
        )}
      </div>

      <select
        value={speed}
        onChange={(e) => setSpeed(e.target.value as Speed)}
        style={{
          background: "var(--surface2)",
          border: "1px solid var(--border)",
          borderRadius: 6,
          color: "var(--text)",
          padding: "5px 8px",
          fontSize: "0.78rem",
          cursor: "pointer",
          outline: "none",
        }}
        aria-label="Velocidade"
      >
        <option value="slow">Lenta</option>
        <option value="normal">Normal</option>
        <option value="fast">Rápida</option>
      </select>
    </div>
  );
}
