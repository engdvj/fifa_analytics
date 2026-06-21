"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import { analytics } from "@/lib/api";
import { useFinalizedMatches } from "@/lib/hooks";

import MatchesTab from "@/components/dashboard/MatchesTab";
import TeamsGrid from "@/components/dashboard/TeamsGrid";
import PlayersTable from "@/components/dashboard/PlayersTable";
import GameSlider from "@/components/dashboard/GameSlider";
import ProgressDots from "@/components/dashboard/ProgressDots";
import RankingRace from "@/components/dashboard/RankingRace";
import TrajectoryChart from "@/components/dashboard/TrajectoryChart";

const TABS = [
  { id: "matches", label: "Jogos" },
  { id: "race", label: "Ranking Race" },
  { id: "teams", label: "Seleções" },
  { id: "players", label: "Jogadores" },
] as const;

type TabId = (typeof TABS)[number]["id"];

function RankingRaceTab() {
  const { matches: finalized, isLoading } = useFinalizedMatches();

  const minGame = finalized.length > 0 ? Math.min(...finalized.map(m => m.match_number)) : 1;
  const maxGame = finalized.length > 0 ? Math.max(...finalized.map(m => m.match_number)) : 1;

  const [currentGame, setCurrentGame] = useState<number | null>(null);
  const [selectedTeams, setSelectedTeams] = useState<string[]>([]);
  const [metric, setMetric] = useState("XG");
  const [trajMode, setTrajMode] = useState<"rank" | "value">("value");

  const effectiveGame = currentGame ?? maxGame;

  const { data: rawStats } = useSWR(
    metric ? ["team-stats-by-game", metric] : null,
    () => analytics.teamStatsByGame(metric)
  );

  const dataByTeam = useMemo(() => {
    if (!rawStats) return {};
    const map: Record<string, { game: number; value: number | null }[]> = {};
    for (const row of rawStats) {
      if (!map[row.id_team]) map[row.id_team] = [];
      map[row.id_team].push({ game: row.match_number, value: row.value });
    }
    for (const arr of Object.values(map)) arr.sort((a, b) => a.game - b.game);
    return map;
  }, [rawStats]);

  function handleTeamToggle(team: string) {
    setSelectedTeams(prev =>
      prev.includes(team)
        ? prev.filter(t => t !== team)
        : prev.length < 16 ? [...prev, team] : prev
    );
  }

  function handleGameChange(n: number) {
    setCurrentGame(Math.min(maxGame, Math.max(minGame, n)));
  }

  if (isLoading) {
    return <p style={{ color: "var(--text-muted)", padding: 24 }}>Carregando jogos...</p>;
  }

  if (finalized.length === 0) {
    return <p style={{ color: "var(--text-muted)", padding: 24 }}>Nenhum jogo finalizado ainda.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: "16px 24px" }}>
      {/* Progress dots */}
      <ProgressDots
        matches={finalized}
        currentGame={effectiveGame}
        onSelect={handleGameChange}
      />

      {/* Controls */}
      <GameSlider
        matches={finalized}
        currentGame={effectiveGame}
        onGameChange={handleGameChange}
      />

      {/* Main content: bars left + trajectory right */}
      <div style={{
        display: "grid",
        gridTemplateColumns: selectedTeams.length > 0 ? "1fr 1fr" : "1fr",
        gap: 16,
        alignItems: "start",
      }}>
        <div style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: "16px",
        }}>
          <RankingRace
            matches={finalized}
            currentGame={effectiveGame}
            selectedTeams={selectedTeams}
            onTeamToggle={handleTeamToggle}
            metric={metric}
            onMetricChange={m => { setMetric(m); setSelectedTeams([]); }}
          />
        </div>

        {selectedTeams.length > 0 && (
          <div style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 10,
            padding: "16px",
          }}>
            <TrajectoryChart
              teams={selectedTeams}
              metric={metric}
              mode={trajMode}
              onModeChange={setTrajMode}
              onRemoveTeam={t => setSelectedTeams(prev => prev.filter(x => x !== t))}
              dataByTeam={dataByTeam}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<TabId>("matches");

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 3.5rem)" }}>
      {/* Tab bar */}
      <div style={{
        borderBottom: "1px solid var(--border)",
        background: "var(--surface)",
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
        gap: 2,
        flexShrink: 0,
      }}>
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            style={{
              background: "none",
              border: "none",
              borderBottom: activeTab === id ? "2px solid var(--accent)" : "2px solid transparent",
              color: activeTab === id ? "var(--accent)" : "var(--text-muted)",
              padding: "12px 16px",
              fontSize: 13,
              fontWeight: activeTab === id ? 600 : 400,
              cursor: "pointer",
              transition: "color 0.12s",
              marginBottom: -1,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {activeTab === "matches" && <MatchesTab />}
        {activeTab === "race" && <RankingRaceTab />}
        {activeTab === "teams" && (
          <div style={{ padding: "16px 24px" }}>
            <TeamsGrid />
          </div>
        )}
        {activeTab === "players" && (
          <div style={{ padding: "16px 24px" }}>
            <PlayersTable />
          </div>
        )}
      </div>
    </div>
  );
}
