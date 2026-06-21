"use client";

import { useEffect, useCallback } from "react";
import { PowerRankingPlayer } from "@/lib/api";
import { scoreColor, positionLabel, compositeScore, rankLabel } from "@/lib/playerUtils";

interface PlayerModalProps {
  player: PowerRankingPlayer;
  allPlayers: PowerRankingPlayer[];
  onClose: () => void;
}

function ProgressBar({ value, max = 10, color }: { value: number; max?: number; color: string }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div
      style={{
        background: "var(--surface2)",
        borderRadius: 4,
        height: 8,
        overflow: "hidden",
        flex: 1,
      }}
    >
      <div
        style={{
          background: color,
          width: `${pct}%`,
          height: "100%",
          borderRadius: 4,
          transition: "width 0.3s ease",
        }}
      />
    </div>
  );
}

function ComparisonBar({
  label,
  playerValue,
  avgValue,
}: {
  label: string;
  playerValue: number | null;
  avgValue: number | null;
}) {
  if (playerValue === null && avgValue === null) return null;
  return (
    <div style={{ marginBottom: 16 }}>
      <div
        style={{
          color: "var(--text-muted)",
          fontSize: "0.72rem",
          marginBottom: 6,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        {label}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ width: 90, fontSize: "0.78rem", color: "var(--text)" }}>Jogador</span>
          <ProgressBar value={playerValue ?? 0} color={scoreColor(playerValue)} />
          <span
            style={{
              width: 36,
              textAlign: "right",
              fontSize: "0.82rem",
              fontWeight: 700,
              color: scoreColor(playerValue),
            }}
          >
            {playerValue !== null ? playerValue.toFixed(1) : "—"}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ width: 90, fontSize: "0.78rem", color: "var(--text-muted)" }}>
            Média pos.
          </span>
          <ProgressBar value={avgValue ?? 0} color="var(--text-muted)" />
          <span
            style={{
              width: 36,
              textAlign: "right",
              fontSize: "0.82rem",
              color: "var(--text-muted)",
            }}
          >
            {avgValue !== null ? avgValue.toFixed(1) : "—"}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function PlayerModal({ player, allPlayers, onClose }: PlayerModalProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const isGoalkeeper = player.player_type === "goalkeeper";
  const composite = compositeScore(player);

  const sameType = allPlayers.filter((p) => p.player_type === player.player_type);

  function avg(getter: (p: PowerRankingPlayer) => number | null): number | null {
    const vals = sameType.map(getter).filter((v): v is number => v !== null);
    if (vals.length === 0) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  }

  const avgAtk = avg((p) => p.attacking_score);
  const avgDef = avg((p) => p.defensive_score);
  const avgCrt = avg((p) => p.creativity_score);

  const atkRank = rankLabel(player.attacking_rank, player.attacking_rank_change);
  const defRank = rankLabel(player.defensive_rank, player.defensive_rank_change);
  const crtRank = rankLabel(player.creativity_rank, player.creativity_rank_change);

  const kpiItems = isGoalkeeper
    ? [
        {
          label: "Jogo de bola",
          score: player.attacking_score,
          rankInfo: atkRank,
          change: player.attacking_rank_change,
        },
        {
          label: "Defesa do gol",
          score: player.defensive_score,
          rankInfo: defRank,
          change: player.defensive_rank_change,
        },
      ]
    : [
        {
          label: "Ataque",
          score: player.attacking_score,
          rankInfo: atkRank,
          change: player.attacking_rank_change,
        },
        {
          label: "Defesa",
          score: player.defensive_score,
          rankInfo: defRank,
          change: player.defensive_rank_change,
        },
        {
          label: "Criatividade",
          score: player.creativity_score,
          rankInfo: crtRank,
          change: player.creativity_rank_change,
        },
      ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.75)" }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          maxWidth: 560,
          width: "100%",
          maxHeight: "85vh",
          overflow: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
        className="p-6"
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            marginBottom: 20,
          }}
        >
          <div>
            <h2
              style={{
                fontWeight: 700,
                fontSize: "1.15rem",
                marginBottom: 4,
                color: "var(--text)",
              }}
            >
              {player.player_name ?? "—"}
            </h2>
            <p style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
              {player.team_name ?? "—"} · {positionLabel(player.player_type)}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              color: "var(--text-muted)",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              fontSize: "1.2rem",
              lineHeight: 1,
              padding: 4,
            }}
          >
            ✕
          </button>
        </div>

        {/* KPI grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${kpiItems.length}, 1fr)`,
            gap: 12,
            marginBottom: 20,
          }}
        >
          {kpiItems.map(({ label, score, rankInfo, change }) => (
            <div
              key={label}
              style={{
                background: "var(--surface2)",
                borderRadius: 8,
                padding: "12px 14px",
                textAlign: "center",
              }}
            >
              <div
                style={{
                  fontSize: "0.7rem",
                  color: "var(--text-muted)",
                  marginBottom: 6,
                  fontWeight: 600,
                }}
              >
                {label}
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  marginBottom: 6,
                }}
              >
                <span
                  style={{
                    fontSize: "1.35rem",
                    fontWeight: 800,
                    color: scoreColor(score),
                  }}
                >
                  {score !== null ? score.toFixed(1) : "—"}
                </span>
                {rankInfo.arrow !== "—" && change !== null && change !== 0 && (
                  <span
                    style={{
                      fontSize: "0.82rem",
                      color: rankInfo.color,
                      fontWeight: 600,
                    }}
                  >
                    {rankInfo.arrow}
                    {Math.abs(change)}
                  </span>
                )}
              </div>
              <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                {rankInfo.rank}
              </div>
            </div>
          ))}
        </div>

        {/* Score composto */}
        {composite !== null && (
          <div
            style={{
              background: "var(--surface2)",
              borderRadius: 8,
              padding: "12px 16px",
              marginBottom: 20,
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <span
              style={{
                fontSize: "0.78rem",
                color: "var(--text-muted)",
                whiteSpace: "nowrap",
              }}
            >
              Score composto
            </span>
            <ProgressBar value={composite} color={scoreColor(composite)} />
            <span
              style={{
                fontWeight: 800,
                fontSize: "1rem",
                color: scoreColor(composite),
                whiteSpace: "nowrap",
              }}
            >
              {composite.toFixed(1)}
            </span>
          </div>
        )}

        {/* Divider */}
        <div style={{ borderTop: "1px solid var(--border)", marginBottom: 16 }} />
        <div
          style={{
            fontSize: "0.72rem",
            color: "var(--text-muted)",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            marginBottom: 14,
          }}
        >
          Comparação com a posição
        </div>

        {/* Comparison bars */}
        <ComparisonBar
          label={isGoalkeeper ? "Jogo de bola" : "Ataque"}
          playerValue={player.attacking_score}
          avgValue={avgAtk}
        />
        <ComparisonBar
          label={isGoalkeeper ? "Defesa do gol" : "Defesa"}
          playerValue={player.defensive_score}
          avgValue={avgDef}
        />
        {!isGoalkeeper && (
          <ComparisonBar
            label="Criatividade"
            playerValue={player.creativity_score}
            avgValue={avgCrt}
          />
        )}
      </div>
    </div>
  );
}

