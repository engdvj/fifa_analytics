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

// Seleções eliminadas no mata-mata até `snapshot` (vazio na fase de grupos).
// Devolve um Set normalizado + um predicado `isEliminated(team)` para os
// componentes aplicarem o tratamento visual (cinza + ☠️).
const _norm = (s: string) => s.trim().toLowerCase();
export function useEliminations(snapshot?: number) {
  const { data } = useSWR(
    ["eliminations", snapshot ?? "all"],
    () => analytics.eliminations(snapshot)
  );
  const names = data?.eliminated ?? [];
  const set = new Set(names.map(_norm));
  const isEliminated = (team?: string | null) => !!team && set.has(_norm(team));
  return { eliminated: names, isEliminated };
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

// Panorama agregado cumulativo até `snapshot` (Descritiva). `enabled=false` não dispara.
export function useDescriptive(snapshot: number, enabled = true) {
  const { data, isLoading, error } = useSWR(
    enabled ? ["descriptive", snapshot] : null,
    () => analytics.descriptive(snapshot)
  );
  return { digest: data, isLoading, error };
}

// Padrões exploratórios cumulativos até `snapshot`. `enabled=false` não dispara.
export function useExploratory(snapshot: number, enabled = true) {
  const { data, isLoading } = useSWR(
    enabled ? ["exploratory", snapshot] : null,
    () => analytics.exploratory(snapshot)
  );
  return { explore: data, isLoading };
}

// Próximos jogos com probabilidade e placar provável.
export function usePredictive(params?: { snapshot?: number; enabled?: boolean }) {
  const enabled = params?.enabled ?? true;
  const { data, isLoading, error } = useSWR(
    enabled ? ["predictive", params?.snapshot ?? "latest"] : null,
    () => analytics.predictive({ snapshot: params?.snapshot })
  );
  return { predictive: data, isLoading, error };
}

export function usePredictiveBacktest(params?: { start?: number; end?: number; display_start?: number; enabled?: boolean }) {
  const enabled = params?.enabled ?? true;
  const { data, isLoading, error } = useSWR(
    enabled ? ["predictive-backtest", params?.start ?? 25, params?.end ?? "latest", params?.display_start ?? "none"] : null,
    () => analytics.predictiveBacktest({ start: params?.start, end: params?.end, display_start: params?.display_start })
  );
  return { backtest: data, isLoading, error };
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
