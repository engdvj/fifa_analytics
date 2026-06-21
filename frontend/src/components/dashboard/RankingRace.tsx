"use client";

import useSWR from "swr";
import { analytics, Match } from "@/lib/api";
import { useAvailableMetrics } from "@/lib/hooks";
import Spinner from "@/components/ui/Spinner";

// High-interest metrics shown first in the dropdown
const PRIORITY_METRICS = [
  "XG",
  "Possession",
  "PitchControl",
  "FinalThirdPitchControl",
  "AttemptAtGoal",
  "GoalkeeperSaves",
  "TotalDistance",
  "Sprints",
  "ForcedTurnovers",
  "CompletedBallProgressions",
];

interface StatRow {
  match_id: string;
  match_number: number;
  id_team: string;
  value: number | null;
}

interface RankingRaceProps {
  matches: Match[];
  currentGame: number;
  selectedTeams: string[];
  onTeamToggle: (team: string) => void;
  metric: string;
  onMetricChange: (m: string) => void;
}

function buildTeamNameMap(matches: Match[]): Map<string, string> {
  // TODO: id_team_home / id_team_away are not in the Match type yet.
  // For now we cannot map id_team -> team name from matches alone.
  // We return an empty map and fall back to displaying id_team as label.
  void matches;
  return new Map();
}

function buildSnapshot(
  stats: StatRow[],
  upToGame: number
): { id_team: string; value: number }[] {
  const latest = new Map<string, { value: number; match_number: number }>();
  for (const row of stats) {
    if (row.match_number > upToGame || row.value == null) continue;
    const existing = latest.get(row.id_team);
    if (!existing || row.match_number > existing.match_number) {
      latest.set(row.id_team, { value: row.value, match_number: row.match_number });
    }
  }
  return [...latest.entries()]
    .map(([id_team, { value }]) => ({ id_team, value }))
    .sort((a, b) => b.value - a.value);
}

function sortMetrics(metrics: string[]): string[] {
  const priority = PRIORITY_METRICS.filter((m) => metrics.includes(m));
  const rest = metrics.filter((m) => !PRIORITY_METRICS.includes(m)).sort();
  return [...priority, ...rest];
}

export default function RankingRace({
  matches,
  currentGame,
  selectedTeams,
  onTeamToggle,
  metric,
  onMetricChange,
}: RankingRaceProps) {
  const { metrics, isLoading: metricsLoading } = useAvailableMetrics();

  const { data: rawStats, isLoading: statsLoading } = useSWR(
    metric ? ["team-stats-by-game", metric] : null,
    () => analytics.teamStatsByGame(metric)
  );

  const nameMap = buildTeamNameMap(matches);
  const snapshot = rawStats ? buildSnapshot(rawStats, currentGame) : [];
  const maxValue = snapshot[0]?.value ?? 1;

  const sortedMetrics = sortMetrics(metrics);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <label style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>Métrica:</label>
        {metricsLoading ? (
          <Spinner size={16} />
        ) : (
          <select
            value={metric}
            onChange={(e) => onMetricChange(e.target.value)}
            style={{
              background: "var(--surface2)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              color: "var(--text)",
              padding: "5px 10px",
              fontSize: "0.82rem",
              cursor: "pointer",
              outline: "none",
              maxWidth: 240,
            }}
          >
            {sortedMetrics.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        )}

        {selectedTeams.length > 0 && (
          <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginLeft: "auto" }}>
            {selectedTeams.length} seleção(ões) na trajetória — clique para remover
          </span>
        )}
      </div>

      {statsLoading && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "24px 0" }}>
          <Spinner size={20} />
          <span style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>Carregando dados…</span>
        </div>
      )}

      {!statsLoading && snapshot.length === 0 && (
        <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", padding: "16px 0" }}>
          Nenhum dado disponível para &quot;{metric}&quot; até o jogo {currentGame}.
        </p>
      )}

      {!statsLoading && snapshot.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {snapshot.map((row, idx) => {
            const label = nameMap.get(row.id_team) ?? row.id_team;
            const isSelected = selectedTeams.includes(label);
            const pct = maxValue > 0 ? (row.value / maxValue) * 100 : 0;

            return (
              <button
                key={row.id_team}
                onClick={() => onTeamToggle(label)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 10px",
                  borderRadius: 7,
                  border: isSelected
                    ? "1px solid var(--accent)"
                    : "1px solid transparent",
                  background: isSelected ? "rgba(88,166,255,0.07)" : "transparent",
                  cursor: "pointer",
                  textAlign: "left",
                  width: "100%",
                  transition: "all 0.15s",
                }}
              >
                <span
                  style={{
                    color: "var(--text-muted)",
                    fontSize: "0.72rem",
                    minWidth: 22,
                    textAlign: "right",
                  }}
                >
                  #{idx + 1}
                </span>

                <span
                  style={{
                    fontSize: "0.82rem",
                    fontWeight: isSelected ? 600 : 400,
                    color: isSelected ? "var(--accent)" : "var(--text)",
                    minWidth: 140,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {label}
                </span>

                <div style={{ flex: 1, height: 18, position: "relative" }}>
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      borderRadius: 4,
                      background: "var(--surface2)",
                    }}
                  />
                  <div
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      bottom: 0,
                      width: `${pct}%`,
                      borderRadius: 4,
                      background: isSelected
                        ? "var(--accent)"
                        : rawStats
                        ? "var(--green)"
                        : "var(--border)",
                      transition: "width 0.6s ease",
                    }}
                  />
                </div>

                <span
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    minWidth: 60,
                    textAlign: "right",
                    color: isSelected ? "var(--accent)" : "var(--text)",
                  }}
                >
                  {row.value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
