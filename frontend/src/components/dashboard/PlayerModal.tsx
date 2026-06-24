"use client";

import { useEffect, useCallback } from "react";
import { PowerRankingPlayer } from "@/lib/api";
import { scoreColor, positionLabel, compositeScore, rankLabel } from "@/lib/playerUtils";
import { flag, getKit } from "@/lib/teamUtils";
import { DefinitionBubble } from "@/components/DefinitionLink";

// Mapeia o componente do Power Ranking → id da definição (ataque/defesa/criatividade).
const KPI_DEF: Record<string, string> = {
  attacking: "attacking_score",
  defensive: "defensive_score",
  creativity: "creativity_score",
};

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
  const kit = getKit(player.team_name);

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
          label: "Jogo de Bola",
          defId: KPI_DEF.attacking,
          score: player.attacking_score,
          rankInfo: atkRank,
          change: player.attacking_rank_change,
        },
        {
          label: "Defesa do Gol",
          defId: KPI_DEF.defensive,
          score: player.defensive_score,
          rankInfo: defRank,
          change: player.defensive_rank_change,
        },
      ]
    : [
        {
          label: "Ataque",
          defId: KPI_DEF.attacking,
          score: player.attacking_score,
          rankInfo: atkRank,
          change: player.attacking_rank_change,
        },
        {
          label: "Defesa",
          defId: KPI_DEF.defensive,
          score: player.defensive_score,
          rankInfo: defRank,
          change: player.defensive_rank_change,
        },
        {
          label: "Criatividade",
          defId: KPI_DEF.creativity,
          score: player.creativity_score,
          rankInfo: crtRank,
          change: player.creativity_rank_change,
        },
      ];

  const comparisonItems = [
    {
      label: isGoalkeeper ? "Jogo de bola" : "Ataque",
      defId: KPI_DEF.attacking,
      playerVal: player.attacking_score,
      avgVal: avgAtk,
    },
    {
      label: isGoalkeeper ? "Defesa do gol" : "Defesa",
      defId: KPI_DEF.defensive,
      playerVal: player.defensive_score,
      avgVal: avgDef,
    },
    ...(!isGoalkeeper
      ? [{ label: "Criatividade", defId: KPI_DEF.creativity, playerVal: player.creativity_score, avgVal: avgCrt }]
      : []),
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
          display: "flex",
          flexDirection: "column",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Hero */}
        <div style={{
          background: `linear-gradient(135deg, ${kit.main}33, var(--surface))`,
          borderBottom: "1px solid var(--border)",
          padding: "20px 24px",
          display: "flex", alignItems: "center", gap: 16, flexShrink: 0,
          borderRadius: "12px 12px 0 0",
        }}>
          {/* Jersey com bandeira */}
          <div style={{
            width: 56, height: 56, borderRadius: 12,
            background: kit.main, border: `3px solid ${kit.border}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 22, fontWeight: 900, color: kit.text,
            boxShadow: `0 4px 14px ${kit.main}55`,
            flexShrink: 0,
          }}>
            <span>{flag(player.team_name)}</span>
          </div>
          <div>
            <h2 style={{ color: "var(--text)", fontSize: 18, fontWeight: 800, margin: 0 }}>
              {player.player_name ?? "?"}
            </h2>
            <p style={{ color: "var(--text-muted)", fontSize: 12, margin: "4px 0 0" }}>
              {flag(player.team_name)} {player.team_name ?? "?"} · {positionLabel(player.player_type)}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              marginLeft: "auto",
              background: "none",
              border: "none",
              color: "var(--text-muted)",
              fontSize: 20,
              cursor: "pointer",
              padding: "4px 8px",
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "20px 24px", overflow: "auto" }}>
          {/* KPI grid */}
          <div style={{
            display: "grid",
            gridTemplateColumns: `repeat(${kpiItems.length}, 1fr)`,
            gap: 12,
            marginBottom: 20,
          }}>
            {kpiItems.map(({ label, defId, score, rankInfo, change }) => (
              <div
                key={label}
                style={{
                  background: "var(--surface2)",
                  border: "1px solid var(--border)",
                  borderRadius: 10,
                  padding: "14px 16px",
                  textAlign: "center",
                  borderTop: `3px solid ${scoreColor(score)}`,
                }}
              >
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }}>{label}{defId && <DefinitionBubble id={defId} size={13} />}</div>
                <div style={{
                  fontSize: 28, fontWeight: 900, color: scoreColor(score), lineHeight: 1,
                }}>
                  {score !== null ? score.toFixed(1) : "—"}
                </div>
                <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 6, marginTop: 6 }}>
                  {rankInfo.rank && rankInfo.rank !== "—" && (
                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{rankInfo.rank}</span>
                  )}
                  {change !== null && change !== 0 && (
                    <span style={{
                      fontSize: 11, fontWeight: 700, color: rankInfo.color,
                      background: `${rankInfo.color}18`,
                      border: `1px solid ${rankInfo.color}44`,
                      borderRadius: 4, padding: "1px 5px",
                    }}>
                      {rankInfo.arrow}{Math.abs(change)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Score composto — barra estilizada */}
          {composite !== null && (() => {
            const color = scoreColor(composite);
            return (
              <div style={{
                marginBottom: 20,
                padding: "12px 16px",
                background: "var(--surface2)",
                border: "1px solid var(--border)",
                borderRadius: 10,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                  <span style={{ fontSize: 13, color: "var(--text)", fontWeight: 600 }}>Score Composto<DefinitionBubble id="player_score_geral" size={13} /></span>
                  <span style={{ fontSize: 20, fontWeight: 800, color }}>{composite.toFixed(1)}</span>
                </div>
                <div style={{ height: 8, background: "var(--surface)", borderRadius: 4, overflow: "hidden" }}>
                  <div style={{
                    height: "100%",
                    width: `${(composite / 10) * 100}%`,
                    background: `linear-gradient(90deg, ${color}88, ${color})`,
                    borderRadius: 4,
                    transition: "width 0.4s ease",
                  }} />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
                  <span style={{ fontSize: 10, color: "var(--text-muted)" }}>0</span>
                  <span style={{ fontSize: 10, color: "var(--text-muted)" }}>10</span>
                </div>
              </div>
            );
          })()}

          {/* Divider */}
          <div style={{ borderTop: "1px solid var(--border)", marginBottom: 16 }} />
          <div style={{
            fontSize: "0.72rem",
            color: "var(--text-muted)",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            marginBottom: 14,
          }}>
            Comparação com a posição
          </div>

          {/* Comparison bars — barras duplas */}
          {comparisonItems.map(({ label, defId, playerVal, avgVal }) => {
            if (playerVal === null && avgVal === null) return null;
            return (
              <div key={label} style={{ marginBottom: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{label}{defId && <DefinitionBubble id={defId} size={12} />}</span>
                  <div style={{ display: "flex", gap: 12 }}>
                    <span style={{ fontSize: 12, color: "var(--accent)", fontWeight: 700 }}>
                      {playerVal !== null ? playerVal.toFixed(1) : "—"}
                    </span>
                    <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      ~{avgVal !== null ? avgVal.toFixed(1) : "—"} média
                    </span>
                  </div>
                </div>
                {/* Barra do jogador */}
                <div style={{ height: 6, background: "var(--surface2)", borderRadius: 3, overflow: "hidden", marginBottom: 2 }}>
                  <div style={{
                    height: "100%",
                    width: `${Math.min(100, (playerVal ?? 0) * 10)}%`,
                    background: "var(--accent)",
                    borderRadius: 3,
                    transition: "width 0.4s",
                  }} />
                </div>
                {/* Barra da média */}
                <div style={{ height: 4, background: "var(--surface2)", borderRadius: 2, overflow: "hidden", opacity: 0.5 }}>
                  <div style={{
                    height: "100%",
                    width: `${Math.min(100, (avgVal ?? 0) * 10)}%`,
                    background: "var(--text-muted)",
                    borderRadius: 2,
                  }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
