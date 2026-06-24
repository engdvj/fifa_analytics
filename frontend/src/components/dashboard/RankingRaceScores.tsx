"use client";

import React from "react";
import { Match, TeamSnapshot } from "@/lib/api";
import { rankBarColor } from "@/lib/playerUtils";
import { selectionColor } from "@/lib/teamUtils";
import Flag from "@/components/ui/Flag";
import { DefinitionBubble } from "@/components/DefinitionLink";
import { METRIC_OPTIONS } from "@/lib/metrics";
import TeamScoresCard from "./TeamScoresCard";

export { METRIC_OPTIONS } from "@/lib/metrics";

// Mapa chave-da-métrica → id de definição. Só as que têm conceito explicável.
const METRIC_DEF_ID: Record<string, string> = {
  score_geral: "score_geral",
  score_resultado: "score_resultado",
  score_ataque: "score_ataque",
  score_defesa: "score_defesa",
  score_eficiencia: "score_eficiencia",
  score_controle: "score_controle",
  score_forca_relativa: "score_forca_relativa",
  score_disciplina: "score_disciplina",
  elo_rating: "elo",
  points: "pontos",
  aproveitamento: "aproveitamento",
  saldo_gols: "saldo_gols",
  xg_pj: "xg",
  posse: "posse",
  pitch_control: "pitch_control",
  chutes_no_alvo_pj: "chutes_no_alvo",
};

const METRIC_LABEL: Record<string, string> = Object.fromEntries(
  METRIC_OPTIONS.flatMap((g) => g.items)
);

// métricas onde "menor é melhor" (não há scores assim, mas gols_contra etc.)
const LOWER_IS_BETTER = new Set(["gols_contra", "gols_contra_pj"]);
const PERCENT_FRAC = new Set(["posse", "aproveitamento"]); // 0-1 → %

interface Props {
  snapshots: TeamSnapshot[];
  currentSnapshot: number;
  metric: string;
  sortDir?: "desc" | "asc";
  selectedTeams: string[];
  onTeamToggle: (team: string) => void;
  passesFilters: (team: string) => boolean;
  currentMatch?: Match;
  maxSnapshot: number;
  focusMode?: boolean;
  onMetricChange?: (metric: string) => void;
  search?: string;
}

function metricValue(row: TeamSnapshot, metric: string): number | null {
  const v = row[metric];
  return typeof v === "number" ? v : null;
}

function formatValue(v: number, metric: string): string {
  if (PERCENT_FRAC.has(metric)) {
    const pct = v <= 1 ? v * 100 : v;
    return `${pct.toFixed(0)}%`;
  }
  return v.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
}

export default function RankingRaceScores({
  snapshots,
  currentSnapshot,
  metric,
  sortDir = "desc",
  selectedTeams,
  onTeamToggle,
  passesFilters,
  currentMatch,
  maxSnapshot,
  focusMode = false,
  onMetricChange,
  search = "",
}: Props) {
  const [compareTeams, setCompareTeams] = React.useState<string[]>([]);
  const [syncArea, setSyncArea] = React.useState(false);
  const [sharedArea, setSharedArea] = React.useState(0);
  const toggleCompare = React.useCallback((team: string) => {
    setCompareTeams((prev) => prev.includes(team) ? prev.filter((t) => t !== team) : [...prev, team]);
  }, []);

  const activeMatchTeams = React.useMemo(
    () => new Set([currentMatch?.home_team, currentMatch?.away_team].filter(Boolean) as string[]),
    [currentMatch]
  );

  // Todas as seleções no snapshot atual — usado pelo card de scores p/ ranks absolutos.
  const rowsAtSnapshot = React.useMemo(
    () => snapshots.filter((s) => s.snapshot_jogo === currentSnapshot),
    [snapshots, currentSnapshot]
  );

  const ranked = React.useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = snapshots
      .filter((s) => s.snapshot_jogo === currentSnapshot && passesFilters(s.team) && (!q || s.team.toLowerCase().includes(q)))
      .map((s) => ({ team: s.team, value: metricValue(s, metric) }))
      .filter((r): r is { team: string; value: number } => r.value != null);
    // ordem natural da métrica (LOWER_IS_BETTER = menor melhor); a setinha do
    // shell inverte isso (sortDir="asc").
    const asc = LOWER_IS_BETTER.has(metric) !== (sortDir === "asc");
    rows.sort((a, b) => (asc ? a.value - b.value : b.value - a.value));
    return rows;
  }, [snapshots, currentSnapshot, metric, passesFilters, sortDir, search]);

  const maxValue = ranked.length ? Math.max(...ranked.map((r) => Math.abs(r.value)), 1) : 1;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <SnapshotMatchLabel snapshot={currentSnapshot} maxSnapshot={maxSnapshot} match={currentMatch} />
        <span style={{ display: "inline-flex", alignItems: "center", color: "#8b949e", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em" }}>
          {METRIC_LABEL[metric] ?? metric}
          {METRIC_DEF_ID[metric] && <DefinitionBubble id={METRIC_DEF_ID[metric]} size={14} />}
        </span>
        {selectedTeams.length > 0 && (
          <span style={{ color: "#8b949e", fontSize: 11 }}>
            {selectedTeams.length} selecionada(s)
          </span>
        )}
      </div>

      {ranked.length === 0 ? (
        <p style={{ color: "#8b949e", fontSize: 13, padding: "16px 0" }}>
          Sem dados para essa métrica no snapshot {currentSnapshot}.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {ranked.map((row, idx) => {
            const rank = idx + 1;
            const isSelected = selectedTeams.includes(row.team);
            const isPlaying = activeMatchTeams.has(row.team);
            const isDimmed = focusMode && !isSelected;
            const pct = maxValue > 0 ? (Math.abs(row.value) / maxValue) * 100 : 0;
            const barColor = isSelected ? "#58a6ff" : rankBarColor(rank, ranked.length);
            const badge: React.CSSProperties = {
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              width: 24, height: 24, borderRadius: "50%", fontSize: 11, fontWeight: 700, flexShrink: 0,
              background: rank === 1 ? "#f5c542" : rank === 2 ? "#c0c0c0" : rank === 3 ? "#cd7f32" : "#161b22",
              color: rank <= 3 ? "#111827" : "#8b949e",
              border: rank <= 3 ? "none" : "1px solid #30363d",
            };
            return (
              <button
                key={row.team}
                onClick={() => onTeamToggle(row.team)}
                aria-pressed={isSelected}
                style={{
                  display: "grid",
                  gridTemplateColumns: "24px 22px minmax(138px, 170px) minmax(0, 1fr) 64px",
                  alignItems: "center",
                  columnGap: 8,
                  padding: "5px 8px",
                  borderRadius: 7,
                  border: isSelected ? "1px solid #58a6ff" : "1px solid transparent",
                  background: isSelected ? "linear-gradient(90deg, rgba(88,166,255,0.16), rgba(88,166,255,0.05))" : "transparent",
                  boxShadow: isSelected ? "inset 0 0 0 1px rgba(88,166,255,0.35), 0 0 18px rgba(88,166,255,0.08)" : "none",
                  opacity: isDimmed ? 0.16 : 1,
                  cursor: "pointer", width: "100%", textAlign: "left", transition: "opacity 0.18s ease, background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease", fontFamily: "inherit",
                }}
              >
                <span style={badge}>{rank}</span>
                <span style={{ width: 22, display: "inline-flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
                  <Flag team={row.team} height={14} />
                </span>
                <span style={{ fontSize: 13, fontWeight: isSelected || isPlaying ? 700 : 400, color: isSelected ? "#58a6ff" : "#e6edf3", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 5 }}>
                  <span
                    role="button"
                    title="Clique para comparar scores (abre/adiciona no card)"
                    onClick={(e) => { e.stopPropagation(); toggleCompare(row.team); }}
                    style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", cursor: "pointer", textDecoration: "underline", textDecorationColor: compareTeams.includes(row.team) ? "#3fb950" : "transparent", textDecorationThickness: 2, textUnderlineOffset: 3, transition: "text-decoration-color 0.15s" }}
                    onMouseEnter={(e) => { if (!compareTeams.includes(row.team)) e.currentTarget.style.textDecorationColor = "currentColor"; }}
                    onMouseLeave={(e) => { if (!compareTeams.includes(row.team)) e.currentTarget.style.textDecorationColor = "transparent"; }}
                  >{row.team}</span>
                  {isPlaying && <span title="Jogou neste snapshot" aria-label="Jogou neste snapshot" style={{ flexShrink: 0, fontSize: 12 }}>⚽</span>}
                </span>
                <div style={{ width: "100%", minWidth: 0, height: 20, position: "relative" }}>
                  <div style={{ position: "absolute", inset: 0, borderRadius: 4, background: isSelected ? "#13233a" : "#111722" }} />
                  <div style={{ position: "absolute", top: 0, left: 0, bottom: 0, width: `${pct}%`, borderRadius: 4, background: barColor, transition: "width 0.55s cubic-bezier(0.4,0,0.2,1), background 0.45s ease", opacity: isSelected ? 1 : 0.85 }} />
                </div>
                <span style={{ fontSize: 12, fontWeight: 700, width: 64, textAlign: "right", color: isSelected ? "#58a6ff" : "#e6edf3" }}>
                  {formatValue(row.value, metric)}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {compareTeams.map((t, i) => (
        <TeamScoresCard
          key={t}
          team={t}
          rows={rowsAtSnapshot}
          metric={metric}
          color={selectionColor(t, selectedTeams)}
          index={i}
          onSelectMetric={onMetricChange}
          syncArea={syncArea}
          sharedArea={sharedArea}
          onAreaChange={setSharedArea}
          onToggleSync={(on, area) => { setSyncArea(on); if (on) setSharedArea(area); }}
          onClose={() => setCompareTeams((prev) => prev.filter((x) => x !== t))}
        />
      ))}
    </div>
  );
}

function SnapshotMatchLabel({
  snapshot,
  maxSnapshot,
  match,
}: {
  snapshot: number;
  maxSnapshot: number;
  match?: Match;
}) {
  if (!match) {
    return (
      <span style={{ color: "#8b949e", fontSize: 13 }}>
        Snapshot {snapshot}/{maxSnapshot}
      </span>
    );
  }

  const hasScore = match.home_score != null && match.away_score != null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#b7c7dc", fontSize: 13, minWidth: 0 }}>
      <span>Após {snapshot}/{maxSnapshot} · Jogo {String(match.match_number).padStart(3, "0")} ·</span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "#f0f6fc", fontWeight: 800, minWidth: 0 }}>
        <Flag team={match.home_team} height={12} />
        <span>{match.home_team ?? "Mandante"}</span>
        <span style={{ color: "#79c0ff" }}>{hasScore ? `${match.home_score}–${match.away_score}` : "vs"}</span>
        <Flag team={match.away_team} height={12} />
        <span>{match.away_team ?? "Visitante"}</span>
      </span>
    </div>
  );
}
