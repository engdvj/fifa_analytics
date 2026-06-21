const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export interface Match {
  match_id: string;
  match_number: number;
  home_team: string | null;
  away_team: string | null;
  home_team_code: string | null;
  away_team_code: string | null;
  stage: string | null;
  group: string | null;
  date_utc: string | null;
  status: "agendado" | "finalizado" | "em_andamento";
  home_score: number | null;
  away_score: number | null;
  home_penalty: number | null;
  away_penalty: number | null;
  stadium: string | null;
  id_ifes: string | null;
}

export interface TeamStat {
  metric: string;
  value: number | null;
  is_official: boolean | null;
}

export interface MatchStatsResponse {
  match_id: string;
  teams: Record<string, TeamStat[]>;
}

export interface LineupPlayer {
  team_side: "home" | "away";
  id_team: string;
  id_player: string;
  player_name: string | null;
  shirt_number: number | null;
  position: string | null;
  is_starter: boolean;
  captain: boolean;
  lineup_x: number | null;
  lineup_y: number | null;
}

export interface MatchEvent {
  event_type: "goal" | "card" | "substitution";
  minute: string | null;
  id_team: string;
  id_player: string;
  player_name: string | null;
  detail: string | null;
  id_assist: string | null;
  id_player2: string | null;
  player2_name: string | null;
}

export interface PowerRankingPlayer {
  id_player: string;
  player_name: string | null;
  id_team: string;
  team_name: string | null;
  player_type: "outfield" | "goalkeeper";
  attacking_score: number | null;
  attacking_rank: number | null;
  attacking_rank_change: number | null;
  defensive_score: number | null;
  defensive_rank: number | null;
  defensive_rank_change: number | null;
  creativity_score: number | null;
  creativity_rank: number | null;
  creativity_rank_change: number | null;
}

export const analytics = {
  matches: (status?: string) =>
    req<Match[]>(`/analytics/matches${status ? `?status=${status}` : ""}`),

  matchStats: (matchId: string) =>
    req<MatchStatsResponse>(`/analytics/matches/${matchId}/stats`),

  matchLineups: (matchId: string) =>
    req<LineupPlayer[]>(`/analytics/matches/${matchId}/lineups`),

  matchEvents: (matchId: string) =>
    req<MatchEvent[]>(`/analytics/matches/${matchId}/events`),

  matchPlayerStats: (matchId: string) =>
    req<{ match_id: string; players: Record<string, { metric: string; value: number | null }[]> }>(
      `/analytics/matches/${matchId}/player-stats`
    ),

  powerRanking: (params?: { player_type?: string; team?: string }) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return req<PowerRankingPlayer[]>(`/analytics/power-ranking${qs ? `?${qs}` : ""}`);
  },

  availableMetrics: () => req<string[]>("/analytics/teams/available-metrics"),

  teamStatsByGame: (metric: string) =>
    req<{ match_id: string; match_number: number; id_team: string; value: number | null }[]>(
      `/analytics/teams/stats-by-game?metric=${encodeURIComponent(metric)}`
    ),
};

// ── Bolão ─────────────────────────────────────────────────────────────────────

export interface User {
  id: number;
  email: string;
  name: string;
}

export interface Pool {
  id: number;
  name: string;
  owner_id: number;
  rule_id: number;
}

export interface ScoringRule {
  id: number;
  name: string;
  description: string | null;
  spec: Record<string, unknown>;
}

export interface Prediction {
  id: number;
  pool_id: number;
  user_id: number;
  match_id: string;
  home_score: number;
  away_score: number;
  points: number | null;
}

export interface RankingRow {
  user_id: number;
  name: string;
  total_points: number;
  predictions: number;
}

export const bolao = {
  rules: () => req<ScoringRule[]>("/pools/rules"),
  pools: () => req<Pool[]>("/pools"),
  createPool: (data: { name: string; owner_id: number; rule_id: number }) =>
    req<Pool>("/pools", { method: "POST", body: JSON.stringify(data) }),
  ranking: (poolId: number) => req<RankingRow[]>(`/pools/${poolId}/ranking`),
  predict: (poolId: number, data: { user_id: number; match_id: string; home_score: number; away_score: number }) =>
    req<Prediction>(`/pools/${poolId}/predictions`, { method: "POST", body: JSON.stringify(data) }),
};

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export const auth = {
  register: (data: { email: string; name: string; password: string }) =>
    req<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (email: string, password: string) => {
    const form = new URLSearchParams({ username: email, password });
    return fetch(`${BASE}/auth/login`, { method: "POST", body: form }).then(
      (r) => r.json() as Promise<TokenResponse>
    );
  },

  me: (token: string) =>
    req<User>("/auth/me", { headers: { Authorization: `Bearer ${token}` } }),
};
