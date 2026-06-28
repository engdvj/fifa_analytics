const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token");
}

async function req<T>(path: string, init?: RequestInit, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  // Anexa o token automaticamente (do localStorage) quando não passado explícito.
  // Forward-compatible com o lockdown de auth: enquanto os endpoints estiverem
  // abertos, segue funcionando sem token; quando fecharem, já manda o Bearer.
  const authToken = token ?? getToken();
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
  const res = await fetch(`${BASE}${path}`, {
    headers,
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
  id_team_home: string | null;
  id_team_away: string | null;
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

// Scores de seleção por snapshot (snapshot_timeline). Campos fixos tipados; o
// resto (métricas por-jogo, eixos de estilo) acessível pelo index signature.
export interface TeamSnapshot {
  team: string;
  team_slug: string | null;
  snapshot_jogo: number;
  match_id_referencia: string | null;
  jogos: number | null;
  points: number | null;
  score_geral: number | null;
  score_resultado: number | null;
  score_ataque: number | null;
  score_defesa: number | null;
  score_eficiencia: number | null;
  score_controle: number | null;
  score_forca_relativa: number | null;
  score_disciplina: number | null;
  ranking_score_geral: number | null;
  elo_rating: number | null;
  estilo_jogo: string | null;
  gols: number | null;
  gols_contra: number | null;
  saldo_gols: number | null;
  aproveitamento: number | null;
  [metric: string]: number | string | null;
}

export interface PlayerSnapshot {
  id_player: string;
  player_slug: string | null;
  player_name: string | null;
  team: string | null;
  perfil: string | null;
  shirt_number: number | null;
  snapshot_jogo: number;
  jogos: number | null;
  score_geral: number | null;
  ranking_score_geral: number | null;
  [metric: string]: number | string | null;
}

export interface ScoreWeights {
  pesos: Record<string, number>;
  tipo: string;
}

// Infos curadas da seleção (config/teams_info.yaml) — identidade, não stats.
export interface TeamInfo {
  apelido?: string;
  confederacao?: string;
  tecnico?: string;
  titulos_copa?: number;
  vices_copa?: number;
  participacoes?: number;
  estreia?: number;
  melhor_campanha?: string;
  curiosidade?: string;
}

// Achado de análise (fact_insights). A camada de inferência da plataforma —
// restrita a admin. `evidencia` é o objeto com os números que sustentam o achado.
export interface Insight {
  snapshot: number;
  match_id: string;
  match_number: number | null;
  escopo: string;
  team: string;
  adversario: string;
  tipo_analise: string;
  categoria: string;
  achado_key: string;
  titulo: string;
  detalhe: string;
  direcao: "positivo" | "negativo" | "neutro";
  severidade: "alta" | "media" | "baixa" | "info";
  evidencia: Record<string, unknown>;
}

// Leitura analítica em prosa de um snapshot (escrita pela skill analisar-snapshot).
export interface InsightNarrative {
  tipo: string;
  snapshot: number | null;
  exists: boolean;
  paragraphs: string[];
}

// Panorama agregado da fase (camada Descritiva) — total + tendência por rodada.
export interface DescriptiveDigest {
  fase: string;
  totais: {
    jogos: number; gols: number; gols_por_jogo: number; xg_por_jogo: number | null;
    empates: number; decisivos: number; pct_decisivos: number;
    vitorias_mandante: number; pct_mandante: number; goleadas: number;
  };
  tendencia: { rodada: string; jogos: number; gols_por_jogo: number; xg_medio: number | null; empates: number; goleadas: number }[];
  lideres: { categoria: string; team: string; valor: string }[];
  recordes: { label: string; valor: string; match_id?: string }[];
  zebras: { titulo: string; nota: string; match_id?: string }[];
}

// Padrões e relações entre jogos (camada Exploratória — EDA com sentido).
export interface ExploratoryData {
  amostra: number;
  confianca?: { nivel: "robusto" | "moderado" | "baixo" | "insuficiente"; label: string };
  decide?: { metric: string; label: string; corr: number; n?: number }[];
  eficiencia?: { team: string; xg: number; gols: number; overperf: number; jogos?: number }[];
  quadrante?: { cria_ref: number | null; mx?: number; my?: number; pontos: { team: string; cria: number; converte: number; perfil: string; jogos?: number }[] };
  estilo_resultado?: {
    arquetipo: string; n: number; pts_jogo: number; aproveitamento: number;
    jogos?: number; vitorias?: number; empates?: number; derrotas?: number;
    gols_pj?: number | null; xg_pj?: number | null; xg_sofrido_pj?: number | null; saldo_pj?: number | null;
    metricas_chave?: { label: string; valor: number; unit?: string; decimals?: number }[];
    times?: string[];
    times_detalhe?: {
      team: string; arquetipo: string; jogos?: number; points?: number; pts_jogo: number; aproveitamento: number;
      vitorias?: number; empates?: number; derrotas?: number;
      gols_pj?: number | null; xg_pj?: number | null; xg_sofrido_pj?: number | null; saldo_pj?: number | null;
      metricas_chave?: { label: string; valor: number; unit?: string; decimals?: number }[];
    }[];
  }[];
  estilos_mapa?: { team: string; posse: number; verticalidade: number; arquetipo: string | null; jogos?: number }[];
  confrontos_estilo?: {
    estilo: string; contra: string; jogos: number; vitorias: number; empates: number; derrotas: number;
    pts_jogo: number; aproveitamento: number;
    saldo_pj?: number | null; xg_diff_pj?: number | null; score_diff_medio?: number | null;
    times?: string[];
  }[];
  influencias_confronto?: {
    fator: string; corr: number | null; n?: number; leitura: string; nota?: string;
  }[];
  fases?: { fase: string; team: string; top?: { team: string; valor: number; jogos?: number }[] }[];
  defesa?: { team: string; xg_sofrido: number; clean_sheets: number; estilo: string | null; jogos?: number }[];
}

export interface PredictiveData {
  snapshot: number | null;
  as_of_snapshot?: number | null;
  base?: {
    xg_medio_time: number | null;
    gols_medio_time: number | null;
    modelo?: string;
    treino_jogos?: number;
    modelos?: string[];
    modo?: string;
    min_prediction_game?: number;
    min_display_game?: number;
    low_confidence?: boolean;
    status?: string;
  };
  matches: {
    match_id: string;
    match_number: number | null;
    official_match_number?: number | null;
    home_team: string;
    away_team: string;
    stage: string | null;
    group: string | null;
    date_utc: string | null;
    expected_goals: { home: number | null; away: number | null };
    probabilities: {
      home_win: number;
      draw: number;
      away_win: number;
      score: { home: number; away: number };
      scoreline?: {
        recommended: { home: number; away: number; probability: number };
        most_likely: { home: number; away: number; probability: number };
        alternatives: { home: number; away: number; probability: number; result: "home" | "draw" | "away" }[];
      };
    };
    favorite: string;
    favorite_side?: "home" | "draw" | "away";
    low_confidence?: boolean;
    frozen_at?: string | null;
    actual_result?: { home: number; away: number; outcome: "home" | "draw" | "away" } | null;
    evaluation?: {
      predicted_outcome: "home" | "draw" | "away";
      actual_outcome: "home" | "draw" | "away";
      winner_hit: boolean;
      exact_score: boolean;
      goal_error_home: number;
      goal_error_away: number;
      goal_error_total: number;
      goal_mae: number | null;
      actual_probability: number | null;
    } | null;
    models?: Record<string, {
      available: boolean;
      reason?: string;
      probabilities?: {
        home_win: number;
        draw: number;
        away_win: number;
        score?: { home: number; away: number };
        scoreline?: {
          recommended: { home: number; away: number; probability: number };
          most_likely: { home: number; away: number; probability: number };
          alternatives: { home: number; away: number; probability: number; result: "home" | "draw" | "away" }[];
        };
      };
      expected_goals?: { home: number | null; away: number | null };
      sample_size?: number;
    }>;
    ensemble?: {
      level: "forte" | "media" | "baixa";
      divergence: "baixa" | "media" | "alta";
      avg_probability_gap?: number | null;
      models: string[];
    };
    consensus?: "forte" | "media" | "baixa";
    divergence?: "baixa" | "media" | "alta";
    confidence: { nivel: "alta" | "media" | "baixa"; label: string };
    summary?: {
      title: string;
      detail: string;
      draw_risk: "baixo" | "medio" | "alto";
      total_xg: number | null;
      xg_gap: number | null;
      draw_calibration: number | null;
    };
    factors: { label: string; home: number | null; away: number | null; diff?: number | null; unit?: string; edge: "home" | "away" | "even" }[];
  }[];
}

export interface PredictiveBacktest {
  summary: {
    n?: number;
    accuracy?: number | null;
    log_loss?: number | null;
    brier?: number | null;
    goal_mae?: number | null;
    draw_rate?: { predicted: number | null; actual: number | null };
    evolution?: {
      early?: { n?: number; accuracy?: number | null; log_loss?: number | null; brier?: number | null; goal_mae?: number | null };
      recent?: { n?: number; accuracy?: number | null; log_loss?: number | null; brier?: number | null; goal_mae?: number | null };
      accuracy_delta?: number | null;
      log_loss_delta?: number | null;
    };
    models?: Record<string, { n?: number; accuracy?: number | null; log_loss?: number | null; brier?: number | null; goal_mae?: number | null }>;
  };
  rows: {
    snapshot: number;
    as_of_snapshot: number | null;
    match_id: string;
    match_number: number;
    home_team: string;
    away_team: string;
    predicted_outcome: "home" | "draw" | "away";
    actual: { home: number; away: number; outcome: "home" | "draw" | "away" };
    hit: boolean;
    exact_score: boolean;
    partial_hit: boolean;
    low_confidence: boolean;
    log_loss: number;
    brier: number;
    goal_mae: number;
  }[];
}

// Métricas das duas seleções no jogo, lado a lado (head-to-head).
export interface MatchComparison {
  match_id: string;
  home_team: string | null;
  away_team: string | null;
  home_score: number | null;
  away_score: number | null;
  home: Record<string, number | null>;
  away: Record<string, number | null>;
}

export const analytics = {
  matches: (status?: string) =>
    req<Match[]>(`/analytics/matches${status ? `?status=${status}` : ""}`),

  insights: (params?: { tipo?: string; snapshot?: number; match_id?: string }) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]))
    ).toString();
    return req<Insight[]>(`/analytics/insights${qs ? `?${qs}` : ""}`);
  },

  insightNarrative: (params?: { tipo?: string; snapshot?: number }) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]))
    ).toString();
    return req<InsightNarrative>(`/analytics/insights/narrative${qs ? `?${qs}` : ""}`);
  },

  descriptive: (snapshot?: number) =>
    req<DescriptiveDigest>(`/analytics/descriptive${snapshot != null ? `?snapshot=${snapshot}` : ""}`),

  exploratory: (snapshot?: number) =>
    req<ExploratoryData>(`/analytics/exploratory${snapshot != null ? `?snapshot=${snapshot}` : ""}`),

  predictive: (params?: { snapshot?: number }) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]))
    ).toString();
    return req<PredictiveData>(`/analytics/predictive${qs ? `?${qs}` : ""}`);
  },

  predictiveBacktest: (params?: { start?: number; end?: number; display_start?: number }) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]))
    ).toString();
    return req<PredictiveBacktest>(`/analytics/predictive/backtest${qs ? `?${qs}` : ""}`);
  },

  teamSnapshots: (snapshot?: number) =>
    req<TeamSnapshot[]>(`/analytics/snapshots/teams${snapshot != null ? `?snapshot=${snapshot}` : ""}`),

  playerSnapshots: (params?: { snapshot?: number; team?: string }) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]))
    ).toString();
    return req<PlayerSnapshot[]>(`/analytics/snapshots/players${qs ? `?${qs}` : ""}`);
  },

  weights: () => req<ScoreWeights>("/analytics/weights"),

  teamsInfo: (team: string) =>
    req<TeamInfo>(`/analytics/teams-info?team=${encodeURIComponent(team)}`),

  matchStats: (matchId: string) =>
    req<MatchStatsResponse>(`/analytics/matches/${matchId}/stats`),

  matchComparison: (matchId: string) =>
    req<MatchComparison>(`/analytics/matches/${matchId}/comparison`),

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
  username: string;
  name: string;
  is_admin?: boolean;
}

// ── Scoring (regras flexíveis) ──────────────────────────────────────────────

export interface ScoringCriterion {
  key: string;
  label: string;
  description: string;
}

// O backend devolve os modos como strings: ["max", "sum"].
export type ScoringMode = "max" | "sum";

export interface ScoringCriteriaResponse {
  criteria: ScoringCriterion[];
  modes: ScoringMode[];
}

// spec: { <criterion>: points, ..., _mode?: "max" | "sum" }
export type ScoringSpec = Record<string, number | string>;

export interface ScoringRule {
  id: number;
  name: string;
  description: string | null;
  spec: ScoringSpec;
  owner_id: number | null;
}

// ── Pools (escopo flexível + grupos aninhados) ──────────────────────────────

export interface PoolScope {
  type: "all" | "stage" | "matches";
  stages?: string[];
  match_ids?: string[];
}

export interface PoolMember {
  user_id: number;
  name: string;
}

export interface PoolRuleSummary {
  id: number;
  name: string;
  spec: ScoringSpec;
}

// Nó da árvore de bolões. Um bolão "grupo" (is_group) tem children.
export interface Pool {
  id: number;
  name: string;
  scope: PoolScope;
  is_group: boolean;
  rule?: PoolRuleSummary | null;
  rule_id?: number | null;
  rule_name?: string | null;
  owner_id?: number | null;
  parent_id?: number | null;
  n_members?: number;
  n_matches?: number;
  status?: "a_iniciar" | "em_andamento" | "finalizado";
  winners?: string[];
  members?: PoolMember[];
  children?: Pool[];
}

export interface CreatePoolBody {
  name: string;
  scope: PoolScope;
  rule_id?: number;
  inline_spec?: ScoringSpec;
  parent_id?: number;
  nest_by_stage?: boolean;
}

// ── Predictions / ranking ───────────────────────────────────────────────────

export interface PoolMatch {
  match_id: string;
  match_number: number;
  home_team: string | null;
  away_team: string | null;
  stage: string | null;
  date_utc: string | null;
  status: "agendado" | "finalizado" | "em_andamento";
  home_score: number | null;
  away_score: number | null;
  prediction: { home_score: number; away_score: number; points?: number | null } | null;
}

export interface Prediction {
  match_id: string;
  home_score: number;
  away_score: number;
  points?: number | null;
}

export interface RankingRow {
  user_id: number;
  name: string;
  total_points: number;
  predictions: number;
}

export interface ChildRanking {
  child_id: number;
  child_name: string;
  stage: string | null;
  ranking: RankingRow[];
}

// Backend sempre devolve {ranking, children}. children=[] em bolão simples;
// em bolão-grupo, ranking = agregado e children = ranking por sub-bolão (fase).
export interface PoolRanking {
  ranking: RankingRow[];
  children: ChildRanking[];
}

export const scoring = {
  criteria: () => req<ScoringCriteriaResponse>("/scoring/criteria"),
  rules: () => req<ScoringRule[]>("/scoring/rules"),
  createRule: (data: { name: string; description?: string; spec: ScoringSpec }) =>
    req<ScoringRule>("/scoring/rules", { method: "POST", body: JSON.stringify(data) }),
  updateRule: (id: number, data: { name?: string; description?: string; spec?: ScoringSpec }) =>
    req<ScoringRule>(`/scoring/rules/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteRule: (id: number) =>
    req<{ deleted: number }>(`/scoring/rules/${id}`, { method: "DELETE" }),
};

// ── Registro de bolão encerrado / participantes / metadados ─────────────────

export interface AppUser {
  id: number;
  username: string;
  name: string;
  email?: string | null;
  is_admin?: boolean;
}

export interface RegistroItem {
  user_id: number;
  match_id: string;
  home_score: number;
  away_score: number;
}

export interface RegistroResult {
  registered: number;
  scored: number;
  ranking: RankingRow[];
}

export interface ParticipantStat {
  user_id: number;
  name: string;
  pools: number;
  predictions: number;
  total_points: number;
  exact_scores: number;
  correct_winners: number;
}

export interface GridParticipant { user_id: number; name: string }
export interface GridPrediction { user_id: number; match_id: string; home_score: number; away_score: number; points?: number | null }
export interface PoolGrid {
  matches: PoolMatch[];
  participants: GridParticipant[];
  predictions: GridPrediction[];
}

export interface AdminPool {
  id: number;
  name: string;
  owner_id: number;
  owner_name: string;
  is_group: boolean;
  parent_id: number | null;
  members: number;
  rule_name: string | null;
  scope: PoolScope | null;
}

export const bolao = {
  createPool: (data: CreatePoolBody) =>
    req<Pool>("/pools", { method: "POST", body: JSON.stringify(data) }),
  pools: () => req<Pool[]>("/pools"),
  pool: (poolId: number) => req<Pool>(`/pools/${poolId}`),
  deletePool: (poolId: number) =>
    req<{ deleted: number }>(`/pools/${poolId}`, { method: "DELETE" }),
  updatePool: (poolId: number, data: { name?: string; rule_id?: number; scope?: PoolScope }) =>
    req<Pool>(`/pools/${poolId}`, { method: "PATCH", body: JSON.stringify(data) }),
  rules: () => req<ScoringRule[]>("/pools/rules"),
  join: (poolId: number) => req<Pool>(`/pools/${poolId}/join`, { method: "POST", body: "{}" }),
  poolMatches: (poolId: number) => req<PoolMatch[]>(`/pools/${poolId}/matches`),
  ranking: (poolId: number) => req<PoolRanking>(`/pools/${poolId}/ranking`),
  predict: (poolId: number, data: { match_id: string; home_score: number; away_score: number }) =>
    req<Prediction>(`/pools/${poolId}/predictions`, { method: "POST", body: JSON.stringify(data) }),
  // Registra um bolão já encerrado: palpites de todos os participantes de uma vez.
  registro: (poolId: number, items: RegistroItem[]) =>
    req<RegistroResult>(`/pools/${poolId}/registro`, {
      method: "POST",
      body: JSON.stringify({ items }),
    }),
  // Grade de palpites de todos os participantes (dono/admin).
  poolGrid: (poolId: number) => req<PoolGrid>(`/pools/${poolId}/grid`),
  // Gestão admin: todos os bolões + transferência de posse.
  adminPools: () => req<AdminPool[]>("/pools/admin/all"),
  transferPool: (poolId: number, userId: number) =>
    req<Pool>(`/pools/${poolId}/transfer`, { method: "POST", body: JSON.stringify({ user_id: userId }) }),
  // ── Salas (ligas): grupo com participantes + regra padrão ──
  createSala: (data: { name: string; member_ids: number[]; rule_id?: number; inline_spec?: object }) =>
    req<Pool>("/pools/sala", { method: "POST", body: JSON.stringify(data) }),
  addMember: (poolId: number, userId: number) =>
    req<{ ok: boolean }>(`/pools/${poolId}/members`, { method: "POST", body: JSON.stringify({ user_id: userId }) }),
  removeMember: (poolId: number, userId: number) =>
    req<{ ok: boolean }>(`/pools/${poolId}/members/${userId}`, { method: "DELETE" }),
  movePool: (poolId: number, parentId: number | null) =>
    req<Pool>(`/pools/${poolId}/move`, { method: "POST", body: JSON.stringify({ parent_id: parentId }) }),
};

export const users = {
  list: () => req<AppUser[]>("/users"),
  get: (id: number) => req<AppUser>(`/users/${id}`),
  create: (data: { username: string; name?: string; password?: string; is_admin?: boolean }) =>
    req<AppUser>("/users", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: { name?: string; email?: string; is_admin?: boolean }) =>
    req<AppUser>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  remove: (id: number) =>
    req<{ deleted: number }>(`/users/${id}`, { method: "DELETE" }),
};

export const stats = {
  participants: () => req<{ participants: ParticipantStat[] }>("/stats/participants"),
};

// ── Admin (jobs de coleta / recálculo) ──────────────────────────────────────

export interface AdminJob {
  id: number;
  kind: "coleta" | "recalc" | "preditiva-learn";
  status: "pending" | "running" | "success" | "error";
  started_at: string | null;
  finished_at: string | null;
  log: string | null;
  created_at: string;
}

export interface AutoCollectStatus {
  enabled: boolean;
  interval_minutes: number | null;
  grace_minutes: number | null;
  started_at: string | null;
  last_check_at: string | null;
  last_finished_count: number | null;
  last_collect_at: string | null;
  last_collect_ok: boolean | null;
  waiting_until: string | null;
  pending: string[];
  last_error: string | null;
}

export const admin = {
  jobs: () => req<AdminJob[]>("/admin/jobs"),
  job: (id: number) => req<AdminJob>(`/admin/jobs/${id}`),
  collect: () => req<AdminJob>("/admin/collect", { method: "POST", body: "{}" }),
  recalc: () => req<AdminJob>("/admin/recalc", { method: "POST", body: "{}" }),
  learnPredictive: () => req<AdminJob>("/admin/predictive/learn", { method: "POST", body: "{}" }),
  autoCollect: () => req<AutoCollectStatus>("/admin/auto-collect"),
};

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export const auth = {
  register: (data: { username: string; password: string; name?: string }) =>
    req<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (username: string, password: string) => {
    const form = new URLSearchParams({ username, password });
    return fetch(`${BASE}/auth/login`, { method: "POST", body: form }).then(
      (r) => r.json() as Promise<TokenResponse>
    );
  },

  me: (token: string) =>
    req<User>("/auth/me", { headers: { Authorization: `Bearer ${token}` } }),

  updateMe: (data: { name?: string; password?: string }) =>
    req<User>("/auth/me", { method: "PATCH", body: JSON.stringify(data) }),
};
