"use client";

import React from "react";
import { Match, TeamSnapshot } from "@/lib/api";
import { rankBarColor } from "@/lib/playerUtils";
import { selectionColor, eliminatedStyle, ELIMINATED_BADGE } from "@/lib/teamUtils";
import { useEliminations } from "@/lib/hooks";
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

// métricas onde "menor é melhor" (gols/chutes sofridos, impedimentos, disciplina)
const LOWER_IS_BETTER = new Set([
  "gols_contra", "gols_contra_pj", "chutes_sofridos_pj", "chutes_sofridos_no_alvo_pj",
  "impedimentos_pj", "faltas_cometidas_pj", "amarelos_pj", "vermelhos_pj",
]);
const PERCENT_FRAC = new Set([
  "posse", "aproveitamento", "precisao_chutes", "precisao_passes", "save_pct_goleiro",
]); // 0-1 → %

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
  const { isEliminated } = useEliminations(currentSnapshot);
  const [hideEliminated, setHideEliminated] = React.useState(false);
  const [syncArea, setSyncArea] = React.useState(false);
  const [sharedArea, setSharedArea] = React.useState(0);
  const [sharedMode, setSharedMode] = React.useState<"pj" | "total">("pj");
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
    // Rank de QUALIDADE (1 = melhor): em métricas "menor é melhor" (faltas,
    // cartões, gols sofridos) o melhor é o MENOR valor. Define cor e medalha —
    // independente da ordem de exibição.
    const lib = LOWER_IS_BETTER.has(metric);
    const byQuality = [...rows].sort((a, b) => (lib ? a.value - b.value : b.value - a.value));
    const qrank = new Map(byQuality.map((r, i) => [r.team, i + 1]));
    // Ordem de EXIBIÇÃO: literal pela seta (asc = "menor primeiro" mostra os
    // menores valores no topo, sempre — sem inverter pela qualidade).
    const asc = sortDir === "asc";
    rows.sort((a, b) => (asc ? a.value - b.value : b.value - a.value));
    return rows.map((r) => ({ ...r, qualityRank: qrank.get(r.team) ?? 1 }));
  }, [snapshots, currentSnapshot, metric, passesFilters, sortDir, search]);

  const anyEliminated = ranked.some((r) => isEliminated(r.team));
  // Toggle "só vivos": remove eliminados e RENUMERA o rank (1,2,3… só entre os
  // vivos). Com todos visíveis, mantém o qualityRank original do snapshot.
  const shown = React.useMemo(() => {
    if (!hideEliminated) return ranked;
    const lib = LOWER_IS_BETTER.has(metric);
    const alive = ranked.filter((r) => !isEliminated(r.team));
    const byQuality = [...alive].sort((a, b) => (lib ? a.value - b.value : b.value - a.value));
    const qrank = new Map(byQuality.map((r, i) => [r.team, i + 1]));
    return alive.map((r) => ({ ...r, qualityRank: qrank.get(r.team) ?? 1 }));
  }, [ranked, hideEliminated, isEliminated, metric]);
  const maxValue = shown.length ? Math.max(...shown.map((r) => Math.abs(r.value)), 1) : 1;

  return (
    <div className="v2-race-list">
      <div className="v2-race-list-head">
        <SnapshotMatchLabel snapshot={currentSnapshot} maxSnapshot={maxSnapshot} match={currentMatch} />
        <span className="v2-race-metric-label">
          {METRIC_LABEL[metric] ?? metric}
          {METRIC_DEF_ID[metric] && <DefinitionBubble id={METRIC_DEF_ID[metric]} size={14} />}
        </span>
        {anyEliminated && (
          <button
            onClick={() => setHideEliminated((v) => !v)}
            title={hideEliminated ? "Mostrar também os eliminados" : "Ocultar os eliminados (só vivos)"}
            style={{
              background: hideEliminated ? "#1f6feb" : "#161b22",
              color: hideEliminated ? "#fff" : "#8b949e",
              border: "1px solid #30363d", borderRadius: 6,
              padding: "4px 9px", fontSize: 11, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap",
            }}
          >
            {hideEliminated ? `Só vivos ✓ (${shown.length})` : `${ELIMINATED_BADGE} Ocultar eliminados`}
          </button>
        )}
        {selectedTeams.length > 0 && (
          <span style={{ color: "#8b949e", fontSize: 11 }}>
            {selectedTeams.length} selecionada(s)
          </span>
        )}
      </div>

      {shown.length === 0 ? (
        <p className="v2-race-empty">
          {ranked.length > 0 && hideEliminated ? "Todas as seleções deste filtro já foram eliminadas." : `Sem dados para essa métrica no snapshot ${currentSnapshot}.`}
        </p>
      ) : (
        <div className="v2-race-rows">
          {shown.map((row) => {
            // posição/medalha/cor = rank de QUALIDADE (melhor=1=verde), não a
            // posição na lista — assim invertendo a ordem o vermelho vai pro topo.
            const rank = row.qualityRank;
            const isSelected = selectedTeams.includes(row.team);
            const isPlaying = activeMatchTeams.has(row.team);
            const isDimmed = focusMode && !isSelected;
            const out = isEliminated(row.team);
            const pct = maxValue > 0 ? (Math.abs(row.value) / maxValue) * 100 : 0;
            const barColor = isSelected ? "#58a6ff" : rankBarColor(rank, shown.length);
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
                className={`v2-race-row ${isSelected ? "is-selected" : ""} ${isPlaying ? "is-playing" : ""}`}
                onClick={() => onTeamToggle(row.team)}
                aria-pressed={isSelected}
                style={{
                  border: isSelected ? "1px solid #58a6ff" : "1px solid transparent",
                  background: isSelected ? "linear-gradient(90deg, rgba(88,166,255,0.16), rgba(88,166,255,0.05))" : "transparent",
                  boxShadow: isSelected ? "inset 0 0 0 1px rgba(88,166,255,0.35), 0 0 18px rgba(88,166,255,0.08)" : "none",
                  opacity: isDimmed ? 0.16 : 1,
                  transition: "opacity 0.18s ease, background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease",
                  ...(out && !isDimmed ? eliminatedStyle(true) : {}),
                }}
              >
                <span style={badge}>{rank}</span>
                <span className="v2-race-flag" title={out ? "Eliminada" : undefined}>
                  {out ? <span style={{ fontSize: 14 }}>{ELIMINATED_BADGE}</span> : <Flag team={row.team} height={14} />}
                </span>
                <span className="v2-race-team" style={{ fontWeight: isSelected || isPlaying ? 700 : 400, color: isSelected ? "#58a6ff" : "#e6edf3" }}>
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
                <div className="v2-race-bar">
                  <div style={{ position: "absolute", inset: 0, borderRadius: 4, background: isSelected ? "#13233a" : "#111722" }} />
                  <div style={{ position: "absolute", top: 0, left: 0, bottom: 0, width: `${pct}%`, borderRadius: 4, background: barColor, transition: "width 0.55s cubic-bezier(0.4,0,0.2,1), background 0.45s ease", opacity: isSelected ? 1 : 0.85 }} />
                </div>
                <span className="v2-race-value" style={{ color: isSelected ? "#58a6ff" : "#e6edf3" }}>
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
          sharedMode={sharedMode}
          onModeChange={setSharedMode}
          onToggleSync={(on, area, m) => { setSyncArea(on); if (on) { setSharedArea(area); setSharedMode(m); } }}
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
      <span className="v2-snapshot-label">
        Snapshot {snapshot}/{maxSnapshot}
      </span>
    );
  }

  const hasScore = match.home_score != null && match.away_score != null;
  return (
    <div className="v2-snapshot-label">
      <span>Após {snapshot}/{maxSnapshot} · Jogo {String(match.match_number).padStart(3, "0")} ·</span>
      <span className="v2-snapshot-match">
        <Flag team={match.home_team} height={12} />
        <span>{match.home_team ?? "Mandante"}</span>
        <span style={{ color: "#79c0ff" }}>{hasScore ? `${match.home_score}–${match.away_score}` : "vs"}</span>
        <Flag team={match.away_team} height={12} />
        <span>{match.away_team ?? "Visitante"}</span>
      </span>
    </div>
  );
}
