import useSWR from "swr";
import { analytics, Match } from "@/lib/api";

export function useMatches() {
  const { data, isLoading, error } = useSWR("matches-all", () => analytics.matches());
  return { matches: data ?? [], isLoading, error };
}

export function useTeamStatsByGame(metric: string) {
  const { data, isLoading, error } = useSWR(
    metric ? ["team-stats-by-game", metric] : null,
    () => analytics.teamStatsByGame(metric)
  );
  return { data: data ?? [], isLoading, error };
}

export function useAvailableMetrics() {
  const { data, isLoading, error } = useSWR("available-metrics", () =>
    analytics.availableMetrics()
  );
  return { metrics: data ?? [], isLoading, error };
}

export function useFinalizedMatches() {
  const { matches, isLoading, error } = useMatches();
  return {
    matches: matches.filter((m: Match) => m.status === "finalizado"),
    isLoading,
    error,
  };
}

// Scores de seleção por snapshot. Sem argumento → todos os snapshots (base da
// Ranking Race). Com `snapshot` → só aquele momento.
export function useTeamSnapshots(snapshot?: number) {
  const { data, isLoading, error } = useSWR(
    ["team-snapshots", snapshot ?? "all"],
    () => analytics.teamSnapshots(snapshot)
  );
  return { snapshots: data ?? [], isLoading, error };
}

export function usePlayerSnapshots(params?: { snapshot?: number; team?: string }) {
  const { data, isLoading, error } = useSWR(
    ["player-snapshots", params?.snapshot ?? "last", params?.team ?? "all"],
    () => analytics.playerSnapshots(params)
  );
  return { players: data ?? [], isLoading, error };
}

export function useWeights() {
  const { data, isLoading, error } = useSWR("weights", () => analytics.weights());
  return { weights: data, isLoading, error };
}
