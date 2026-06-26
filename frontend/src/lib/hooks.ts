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

// Achados de análise (admin-only). `enabled=false` não dispara o fetch (evita
// 403 para não-admin). Filtra por snapshot quando informado.
export function useInsights(params?: { snapshot?: number; tipo?: string; enabled?: boolean }) {
  const enabled = params?.enabled ?? true;
  const tipo = params?.tipo ?? "diagnostica";
  const { data, isLoading, error } = useSWR(
    enabled ? ["insights", tipo, params?.snapshot ?? "all"] : null,
    () => analytics.insights({ tipo, snapshot: params?.snapshot })
  );
  return { insights: data ?? [], isLoading, error };
}

// Panorama agregado da fase (Descritiva). `enabled=false` não dispara.
export function useDescriptive(enabled = true) {
  const { data, isLoading, error } = useSWR(
    enabled ? ["descriptive"] : null,
    () => analytics.descriptive()
  );
  return { digest: data, isLoading, error };
}

// Métricas head-to-head de um jogo. `enabled=false` não dispara.
export function useMatchComparison(matchId: string | null, enabled = true) {
  const { data, isLoading } = useSWR(
    enabled && matchId ? ["match-comparison", matchId] : null,
    () => analytics.matchComparison(matchId as string)
  );
  return { comparison: data, isLoading };
}

// Narrativa (prosa) de um snapshot. `enabled=false` não dispara (evita 403).
export function useInsightNarrative(params?: { snapshot?: number; tipo?: string; enabled?: boolean }) {
  const enabled = params?.enabled ?? true;
  const tipo = params?.tipo ?? "diagnostica";
  const { data, isLoading } = useSWR(
    enabled ? ["insight-narrative", tipo, params?.snapshot ?? "latest"] : null,
    () => analytics.insightNarrative({ tipo, snapshot: params?.snapshot })
  );
  return { narrative: data, isLoading };
}
