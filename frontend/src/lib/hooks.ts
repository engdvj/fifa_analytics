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
