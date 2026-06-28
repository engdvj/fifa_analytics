"use client";

import React from "react";
import { CircleQuestionMark, Maximize2, X } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Match, ScoreWeights, TeamSnapshot } from "@/lib/api";
import { useMatches, useTeamSnapshots, useWeights, usePredictiveBacktest } from "@/lib/hooks";
import { CONFEDERATION, deriveTeams, flagUrl, getKit, selectionColor } from "@/lib/teamUtils";
import GameSlider from "@/components/dashboard/GameSlider";
import ProgressDots from "@/components/dashboard/ProgressDots";
import RankingRaceScores, { METRIC_OPTIONS } from "@/components/dashboard/RankingRaceScores";
import SelecoesTab from "@/components/dashboard/SelecoesTab";
import PlayersTab from "@/components/dashboard/PlayersTab";
import GruposChaveTab from "@/components/dashboard/GruposChaveTab";
import AnaliseTab from "@/components/dashboard/AnaliseTab";
import Flag from "@/components/ui/Flag";
import { useAuth } from "@/lib/auth-context";

type Tab = "race" | "teams" | "players" | "groups" | "analise";

const TABS: { id: Tab; label: string; adminOnly?: boolean }[] = [
  { id: "groups", label: "Grupos" },
  { id: "teams", label: "Seleções" },
  { id: "players", label: "Jogadores" },
  { id: "race", label: "Ranking Race" },
  { id: "analise", label: "Analytics", adminOnly: true },
];

// Rótulos pt-BR das fases (o gold guarda em inglês).
const STAGE_LABELS: Record<string, string> = {
  "First Stage": "Fase de Grupos",
  "Round of 32": "16-avos",
  "Round of 16": "Oitavas",
  "Quarter-final": "Quartas",
  "Semi-final": "Semifinal",
  "Play-off for third place": "3º lugar",
  "Final": "Final",
};

export interface DashboardFilters {
  group: string;
  confed: string;
  stage: string;
}

const EMPTY_FILTERS: DashboardFilters = { group: "", confed: "", stage: "" };

const WEIGHT_ORDER = [
  "score_resultado",
  "score_ataque",
  "score_defesa",
  "score_eficiencia",
  "score_controle",
  "score_forca_relativa",
] as const;

type WeightKey = (typeof WEIGHT_ORDER)[number];
type GuideSection = "overview" | "components" | "faq";

const DEFAULT_WEIGHTS: Record<WeightKey, number> = {
  score_resultado: 0.35,
  score_ataque: 0.15,
  score_defesa: 0.20,
  score_eficiencia: 0.10,
  score_controle: 0.05,
  score_forca_relativa: 0.15,
};

const SIDEBAR_DEFAULT_WIDTH = 392;
const SIDEBAR_MIN_WIDTH = 320;

const WEIGHT_LABELS: Record<WeightKey, string> = {
  score_resultado: "Resultado",
  score_ataque: "Ataque",
  score_defesa: "Defesa",
  score_eficiencia: "Eficiência",
  score_controle: "Controle",
  score_forca_relativa: "Força Rel.",
};

function isWeightKey(metric: string): metric is WeightKey {
  return (WEIGHT_ORDER as readonly string[]).includes(metric);
}

const WEIGHT_DETAILS: Record<WeightKey, {
  label: string;
  color: string;
  summary: string;
  rationale: string;
  signals: { label: string; detail: string }[];
}> = {
  score_resultado: {
    label: "Resultado",
    color: "#58a6ff",
    summary: "Ancora a leitura no que o placar e a campanha já provaram.",
    rationale: "É o maior peso (30%) porque futebol de torneio precisa respeitar vitória, saldo e aproveitamento ponderado pelo adversário. Usa margem forte (70% aproveitamento / 30% saldo): golear pesa mais que vencer apertado. Processo ajuda a explicar, mas não passa por cima do resultado.",
    signals: [
      { label: "aproveitamento ponderado (70%)", detail: "Pontos conquistados com ajuste pela força do adversário (Elo pré-jogo)." },
      { label: "saldo por jogo (30%)", detail: "Diferença média entre gols marcados e sofridos — margem da vitória." },
    ],
  },
  score_ataque: {
    label: "Ataque",
    color: "#ff7b1a",
    summary: "Mede quanto perigo o time cria, não só o placar favorável.",
    rationale: "Pesa igual à defesa (20%). Premia quem CRIA perigo de verdade — entra na área, penetra o terço final — não só quem chuta de longe. xG e gols dividem o topo (60%); o resto capta volume de chance perigosa e penetração.",
    signals: [
      { label: "xG por jogo (30%)", detail: "Qualidade média das chances criadas." },
      { label: "gols por jogo (30%)", detail: "Produção ofensiva já convertida em placar." },
      { label: "chutes dentro da área (10%)", detail: "Volume de finalização de posição perigosa." },
      { label: "chutes no alvo (10%)", detail: "Frequência de finalizações que exigem defesa." },
      { label: "threat (10%)", detail: "Presença ofensiva em zonas perigosas." },
      { label: "entradas no terço final (10%)", detail: "Penetração consistente na zona de perigo." },
    ],
  },
  score_defesa: {
    label: "Defesa",
    color: "#2ecc71",
    summary: "Mede quão pouco perigo o time permite, não só quantos gols sofre.",
    rationale: "Pesa igual ao ataque (20%). Gols sofridos e xG sofrido dividem o topo (60%): o xG sofrido é a chave — separa quem DEFENDEU de quem teve sorte ou foi salvo pelo goleiro. Goleiro e recuperação refinam.",
    signals: [
      { label: "gols sofridos por jogo (30%)", detail: "Quanto a equipe concede no placar." },
      { label: "xG sofrido (30%)", detail: "Quanto perigo a defesa permitiu o adversário criar." },
      { label: "chutes sofridos no alvo (10%)", detail: "Chances no gol que a defesa cedeu." },
      { label: "save% (15%)", detail: "Taxa de defesas do goleiro em chutes no alvo." },
      { label: "turnovers forçados (15%)", detail: "Bolas recuperadas / erros provocados pela pressão." },
    ],
  },
  score_eficiencia: {
    label: "Eficiência",
    color: "#f2c94c",
    summary: "Mostra quem transforma recurso em impacto real.",
    rationale: "Captura finalização acima do esperado, conversão e uso eficiente da bola. Fica em 10% porque eficiência oscila bastante jogo a jogo e não deve carregar o ranking sozinha.",
    signals: [
      { label: "gols por xG (45%)", detail: "Finalização acima ou abaixo do esperado pelas chances." },
      { label: "conversão de chutes (30%)", detail: "Percentual de finalizações que viram gol." },
      { label: "progressões certas (10%)", detail: "Acerto ao avançar a bola (não só volume)." },
      { label: "distribuição sob pressão (15%)", detail: "Acerto de passes com o adversário pressionando." },
    ],
  },
  score_controle: {
    label: "Controle",
    color: "#a78bfa",
    summary: "Separa domínio territorial útil de posse vazia.",
    rationale: "É propositalmente o menor grupo de processo. Prioriza o controle ONDE importa (terço final, perto do gol adversário) e a circulação para espalhar o jogo — não só ter a bola.",
    signals: [
      { label: "controle no terço final (40%)", detail: "Domínio perto da área adversária — o que vira perigo." },
      { label: "posse (20%)", detail: "Tempo com a bola, tratado como apoio ao domínio." },
      { label: "precisão de passes (20%)", detail: "Qualidade de circulação para sustentar controle." },
      { label: "trocas de lado (20%)", detail: "Inversões certas — espalhar o jogo (eixo distinto da posse)." },
    ],
  },
  score_forca_relativa: {
    label: "Força Relativa",
    color: "#ff6b81",
    summary: "Mede a força via Elo — contra quem o time jogou.",
    rationale: "Única métrica recursiva: bater quem bateu os fortes te eleva (força de tabela). O peso de 10% vale integralmente — o Elo foi corrigido para valorizar o desempenho (gols, xG, ameaça), não o tempo de posse de bola.",
    signals: [
      { label: "Elo", detail: "Força estimada, atualizada a cada jogo conforme resultado e adversário." },
      { label: "Elo do adversário (pré-jogo)", detail: "Dificuldade do caminho já enfrentado, fixa no confronto." },
      { label: "índice de desempenho", detail: "Quão convincente foi a atuação (gols, xG, ameaça, posse)." },
    ],
  },
};

export default function DashboardV2Page() {
  const { user } = useAuth();
  const isAdmin = !!user?.is_admin;
  const visibleTabs = React.useMemo(() => TABS.filter((t) => !t.adminOnly || isAdmin), [isAdmin]);
  const [tab, setTab] = React.useState<Tab>("groups");
  const [filters, setFilters] = React.useState<DashboardFilters>(EMPTY_FILTERS);
  const [selectedTeams, setSelectedTeams] = React.useState<string[]>([]);
  const [currentSnapshot, setCurrentSnapshot] = React.useState<number>(0);
  const [metric, setMetric] = React.useState<string>("score_geral");
  const [sortDir, setSortDir] = React.useState<"desc" | "asc">("desc");
  const [dashSearch, setDashSearch] = React.useState("");
  const [searchFocused, setSearchFocused] = React.useState(false);
  const [weightsGuideOpen, setWeightsGuideOpen] = React.useState(false);
  const [guideWeight, setGuideWeight] = React.useState<WeightKey>("score_resultado");
  const [sidebarWidth, setSidebarWidth] = React.useState(SIDEBAR_DEFAULT_WIDTH);
  const [predictiveActive, setPredictiveActive] = React.useState(false);

  const { matches, isLoading: mLoading, error: mError } = useMatches();
  const { snapshots, isLoading: sLoading, error: sError } = useTeamSnapshots();
  const { weights } = useWeights();
  // Quando a Preditiva está ativa, o backtest dá o acerto por jogo → cor das
  // bolinhas. display_start=2 colore desde os primeiros jogos (baixa confiança),
  // mas a MÉTRICA do summary continua contando só a partir do jogo 25.
  const { backtest: predBacktest } = usePredictiveBacktest({ start: 25, display_start: 2, enabled: predictiveActive });
  const predictionResults = React.useMemo(() => {
    const map = new Map<string, { cat: "exact" | "winner" | "partial" | "miss"; lowConf: boolean }>();
    for (const r of predBacktest?.rows ?? []) {
      const cat = r.exact_score ? "exact" : r.hit ? "winner" : r.partial_hit ? "partial" : "miss";
      map.set(r.match_id, { cat, lowConf: r.low_confidence });
    }
    return map;
  }, [predBacktest]);

  const toggleTeam = React.useCallback(
    (team: string) =>
      setSelectedTeams((prev) => (prev.includes(team) ? prev.filter((t) => t !== team) : [...prev, team])),
    []
  );

  const startSidebarResize = React.useCallback(
    (event: React.PointerEvent<HTMLButtonElement>) => {
      if (event.button !== 0) return;
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = sidebarWidth;
      const maxWidth = Math.max(SIDEBAR_MIN_WIDTH, Math.floor(window.innerWidth * 0.5));

      function handlePointerMove(moveEvent: PointerEvent) {
        const nextWidth = startWidth + startX - moveEvent.clientX;
        setSidebarWidth(Math.min(maxWidth, Math.max(SIDEBAR_MIN_WIDTH, Math.round(nextWidth))));
      }

      function handlePointerUp() {
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        document.removeEventListener("pointermove", handlePointerMove);
        document.removeEventListener("pointerup", handlePointerUp);
        document.removeEventListener("pointercancel", handlePointerUp);
      }

      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      document.addEventListener("pointermove", handlePointerMove);
      document.addEventListener("pointerup", handlePointerUp);
      document.addEventListener("pointercancel", handlePointerUp);
    },
    [sidebarWidth]
  );

  const isLoading = mLoading || sLoading;
  const error = mError || sError;

  // snapshot_jogo → Match de referência (via match_id_referencia).
  const snapByGame = React.useMemo(() => {
    const byMatch = new Map(matches.map((m) => [m.match_id, m]));
    const out = new Map<number, Match>();
    for (const s of snapshots) {
      const n = s.snapshot_jogo;
      const ref = s.match_id_referencia as string | null;
      if (!out.has(n) && ref && byMatch.has(ref)) out.set(n, byMatch.get(ref)!);
    }
    return out;
  }, [snapshots, matches]);

  const maxSnapshot = React.useMemo(
    () => (snapByGame.size ? Math.max(...snapByGame.keys()) : 0),
    [snapByGame]
  );
  const activeSnapshot = currentSnapshot || maxSnapshot;

  // match_id → snapshot (para os dots: jogo real do calendário → seu snapshot).
  const matchSnapshot = React.useMemo(() => {
    const out = new Map<string, number>();
    for (const [n, m] of snapByGame) out.set(m.match_id, n);
    return out;
  }, [snapByGame]);

  // Jogos remapeados p/ a ordem cronológica real. O match_number oficial da FIFA
  // não é estritamente cronológico, então a navegação por snapshot usa este índice.
  const chronologicalMatches: Match[] = React.useMemo(
    () =>
      [...matches]
        .sort((a, b) => matchSortValue(a) - matchSortValue(b))
        .map((m, idx) => ({ ...m, match_number: idx + 1 })),
    [matches]
  );

  // Metadados estáveis de cada seleção (grupo/confederação) p/ os filtros.
  const teamMeta = React.useMemo(() => {
    const map = new Map<string, { group: string | null; confed: string }>();
    for (const t of deriveTeams(matches)) {
      map.set(t.name, { group: t.group, confed: t.confederation });
    }
    return map;
  }, [matches]);

  const groups = React.useMemo(
    () => Array.from(new Set(matches.map((m) => m.group).filter(Boolean) as string[])).sort(),
    [matches]
  );
  const confeds = React.useMemo(
    () => Array.from(new Set(Object.values(CONFEDERATION))).sort(),
    []
  );
  const stages = React.useMemo(
    () => Array.from(new Set(matches.map((m) => m.stage).filter(Boolean) as string[])),
    [matches]
  );

  // Dicas dos filtros: valor (confederação/grupo) → seleções escolhidas com a cor.
  const confedSuggested = React.useMemo(() => {
    const m = new Map<string, { team: string; color: string }[]>();
    for (const t of selectedTeams) {
      const meta = teamMeta.get(t);
      if (!meta) continue;
      (m.get(meta.confed) ?? m.set(meta.confed, []).get(meta.confed)!).push({ team: t, color: selectionColor(t, selectedTeams)! });
    }
    return m;
  }, [selectedTeams, teamMeta]);
  const groupSuggested = React.useMemo(() => {
    const m = new Map<string, { team: string; color: string }[]>();
    for (const t of selectedTeams) {
      const g = teamMeta.get(t)?.group;
      if (!g) continue;
      (m.get(g) ?? m.set(g, []).get(g)!).push({ team: t, color: selectionColor(t, selectedTeams)! });
    }
    return m;
  }, [selectedTeams, teamMeta]);

  function passesFilters(team: string): boolean {
    const meta = teamMeta.get(team);
    if (filters.group && meta?.group !== filters.group) return false;
    if (filters.confed && meta?.confed !== filters.confed) return false;
    // stage: filtro por fase aplica-se aos jogos; aqui mantemos a seleção visível
    // se ela disputou algum jogo naquela fase (refinado nas abas).
    if (filters.stage) {
      const playedStage = matches.some(
        (m) => m.stage === filters.stage && (m.home_team === team || m.away_team === team)
      );
      if (!playedStage) return false;
    }
    return true;
  }

  // Times com score no snapshot atual, após filtros (gate visual do shell).
  const teamsAtSnapshot = React.useMemo(() => {
    const rows = snapshots.filter((s) => s.snapshot_jogo === activeSnapshot);
    return rows.map((r) => r.team).filter(passesFilters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshots, activeSnapshot, filters, teamMeta]);

  const currentMatch = snapByGame.get(activeSnapshot);

  const searchSuggestions = React.useMemo(() => {
    const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    const q = norm(dashSearch.trim());
    if (!q) return [] as string[];
    const seen = new Set<string>();
    const out: string[] = [];
    for (const t of teamsAtSnapshot) {
      if (seen.has(t) || !norm(t).includes(q)) continue;
      seen.add(t);
      out.push(t);
      if (out.length >= 8) break;
    }
    return out;
  }, [dashSearch, teamsAtSnapshot]);

  return (
    <div className="v2-dashboard-shell">
      {/* Toolbar fixa: abas + pesos + slider + filtros + dots ficam grudados no
          topo (logo abaixo do header global de 52px) enquanto a lista rola. */}
      <div className="v2-dashboard-sticky">
      {/* Header + abas */}
      <header className="v2-dashboard-header">
        <nav className="v2-primary-tabs">
          {visibleTabs.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)} style={tabStyle(tab === t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        {/* Pills de pesos — não se aplicam ao Analytics, então ficam escondidos lá. */}
        {tab !== "analise" ? (
        <div className="v2-weight-strip">
          <span className="v2-weight-strip-label">Pesos fixos</span>
          {/* Geral = combinação dos 6 (100%); ranqueia pelo score_geral */}
          <button
            className={`v2-weight-pill ${metric === "score_geral" ? "is-active" : ""}`}
            onClick={() => setMetric("score_geral")}
            title="Ranquear pelo Score Geral (combinação dos 6 componentes)"
            style={{ "--weight-color": "#58a6ff" } as React.CSSProperties}
          >
            <span className="v2-weight-dot" />
            Geral <b>100%</b>
          </button>
          {weightRows(weights?.pesos).map(([k, w]) => (
              <button
                key={k}
                className={`v2-weight-pill ${metric === k ? "is-active" : ""}`}
                onClick={() => {
                  setMetric(k);
                  setGuideWeight(k);
                }}
                onDoubleClick={() => {
                  setGuideWeight(k);
                  setWeightsGuideOpen(true);
                }}
                title="Clique para ranquear. Dois cliques abrem o detalhe."
                style={{ "--weight-color": WEIGHT_DETAILS[k].color } as React.CSSProperties}
              >
                <span className="v2-weight-dot" />
                {WEIGHT_LABELS[k] ?? k} <b>{Math.round(w * 100)}%</b>
              </button>
            ))}
          <button
            type="button"
            className="v2-weight-help"
            onClick={() => {
              setGuideWeight(isWeightKey(metric) ? metric : guideWeight);
              setWeightsGuideOpen(true);
            }}
            title="Guia dos pesos fixos"
            aria-label="Abrir guia dos pesos fixos"
          >
            <CircleQuestionMark size={16} strokeWidth={2.2} />
          </button>
        </div>
        ) : <div className="v2-header-spacer" />}
        {/* Play + slider compacto, no topo (como o legacy) */}
        {chronologicalMatches.length > 0 && (
          <GameSlider matches={chronologicalMatches} currentGame={activeSnapshot} onGameChange={setCurrentSnapshot} compact />
        )}
      </header>

      {/* Barra de filtros — escondida no Analytics (que tem seu próprio seletor de seleções). */}
      {tab !== "analise" && (
      <div className="v2-filter-bar">
        <FilterSelect label="Grupo" value={filters.group} onChange={(v) => setFilters((f) => ({ ...f, group: v }))} options={groups.map((g) => [g, g])} suggested={groupSuggested} />
        <FilterSelect label="Confederação" value={filters.confed} onChange={(v) => setFilters((f) => ({ ...f, confed: v }))} options={confeds.map((c) => [c, c])} suggested={confedSuggested} />
        <FilterSelect label="Fase" value={filters.stage} onChange={(v) => setFilters((f) => ({ ...f, stage: v }))} options={stages.map((s) => [s, STAGE_LABELS[s] ?? s])} />
        <MetricSelect value={metric} onChange={setMetric} />
        <button
          onClick={() => setSortDir((d) => (d === "desc" ? "asc" : "desc"))}
          title={sortDir === "desc" ? "Maior primeiro (clique para inverter)" : "Menor primeiro (clique para inverter)"}
          className="v2-sort-button"
        >
          <span style={{ fontSize: 13 }}>{sortDir === "desc" ? "↓" : "↑"}</span>
          {sortDir === "desc" ? "Maior primeiro" : "Menor primeiro"}
        </button>
        <div className="v2-search-box">
          <input
            type="text"
            value={dashSearch}
            onChange={(e) => setDashSearch(e.target.value)}
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setTimeout(() => setSearchFocused(false), 150)}
            placeholder={tab === "players" ? "Buscar jogador ou seleção…" : "Buscar seleção…"}
            className="v2-dashboard-search"
          />
          {searchFocused && searchSuggestions.length > 0 && (
            <div className="v2-search-suggestions">
              {searchSuggestions.map((team) => {
                const sel = selectedTeams.includes(team);
                return (
                  <button key={team} type="button"
                    onMouseDown={(e) => { e.preventDefault(); toggleTeam(team); setDashSearch(""); }}
                    style={{ width: "100%", textAlign: "left", display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", background: sel ? "#10213a" : "none", border: "none", borderRadius: 6, color: "#e6edf3", fontSize: 13, cursor: "pointer" }}
                    onMouseEnter={(e) => { if (!sel) e.currentTarget.style.background = "#21262d"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = sel ? "#10213a" : "none"; }}>
                    <Flag team={team} height={13} />
                    <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{team}</span>
                    {sel && <span style={{ color: "#3fb950", fontSize: 11, flexShrink: 0 }}>✓ selecionada</span>}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        {(filters.group || filters.confed || filters.stage) && (
          <button onClick={() => setFilters(EMPTY_FILTERS)} style={{ ...tabStyle(false), padding: "4px 10px" }}>✕ Limpar</button>
        )}
        <div className="v2-filter-fill" />
        <span className="v2-api-status">
          {isLoading && "Conectando à API…"}
          {error && <span style={{ color: "#f85149" }}>Erro na API (rodando em :8001?): {String(error)}</span>}
          {!isLoading && !error && <span style={{ color: "#3fb950" }}>● {teamsAtSnapshot.length} seleções no snapshot {activeSnapshot}</span>}
        </span>
      </div>
      )}

      {/* Navegação no tempo: dots de fases, largura total */}
      {chronologicalMatches.length > 0 && (
        <div className="v2-progress-shell">
          <ProgressDots matches={chronologicalMatches} matchSnapshot={matchSnapshot} currentSnapshot={activeSnapshot} onSelect={setCurrentSnapshot} predictionResults={predictiveActive ? predictionResults : undefined} minPredictionGame={25} />
        </div>
      )}
      </div>

      {/* Conteúdo da aba */}
      <main className={tab === "race" ? "v2-main is-race" : "v2-main"}>
        {tab === "race" ? (
          <div
            className={`v2-race-workspace ${selectedTeams.length > 0 ? "has-selection" : ""}`}
            style={{ "--v2-sidebar-width": `${sidebarWidth}px` } as React.CSSProperties}
          >
            <section className="v2-race-stage" aria-label="Ranking race">
              <RankingRaceScores
                snapshots={snapshots}
                currentSnapshot={activeSnapshot}
                metric={metric}
                sortDir={sortDir}
                selectedTeams={selectedTeams}
                onTeamToggle={toggleTeam}
                passesFilters={passesFilters}
                currentMatch={currentMatch}
                maxSnapshot={maxSnapshot}
                focusMode={selectedTeams.length > 0}
                onMetricChange={setMetric}
                search={dashSearch}
              />
            </section>
            <button
              type="button"
              className="v2-sidebar-resizer"
              onPointerDown={startSidebarResize}
              aria-label={`Ajustar largura da lateral, atual ${sidebarWidth}px`}
              title="Arraste para ajustar a largura da lateral"
            />
            <RaceSelectionSidebar
              selectedTeams={selectedTeams}
              currentSnapshot={activeSnapshot}
              metric={metric}
              snapshots={snapshots}
              onRemoveTeam={(team) => setSelectedTeams((prev) => prev.filter((item) => item !== team))}
              onClear={() => setSelectedTeams([])}
              onMetricChange={setMetric}
            />
          </div>
        ) : tab === "teams" ? (
          <SelecoesTab
            matches={matches}
            snapshots={snapshots}
            activeSnapshot={activeSnapshot}
            matchSnapshot={matchSnapshot}
            passesFilters={passesFilters}
            selectedTeams={selectedTeams}
            onToggleTeam={toggleTeam}
            metric={metric}
            sortDir={sortDir}
            search={dashSearch}
          />
        ) : tab === "players" ? (
          <PlayersTab activeSnapshot={activeSnapshot} passesFilters={passesFilters} selectedTeams={selectedTeams} search={dashSearch} />
        ) : tab === "analise" ? (
          <AnaliseTab matches={matches} activeSnapshot={activeSnapshot} isAdmin={isAdmin} onSnapshotChange={setCurrentSnapshot} onPredictiveActive={setPredictiveActive} />
        ) : (
          <GruposChaveTab
            matches={matches}
            snapshots={snapshots}
            activeSnapshot={activeSnapshot}
            matchSnapshot={matchSnapshot}
            filters={filters}
            passesFilters={passesFilters}
            selectedTeams={selectedTeams}
            onToggleTeam={toggleTeam}
            metric={metric}
            search={dashSearch}
          />
        )}
      </main>
      <WeightsGuideModal
        open={weightsGuideOpen}
        onClose={() => setWeightsGuideOpen(false)}
        weights={weights}
        snapshot={activeSnapshot}
        match={currentMatch}
        selectedWeight={guideWeight}
        onWeightSelect={(key) => {
          setGuideWeight(key);
          setMetric(key);
        }}
      />
      <DashboardV2MotionStyles />
    </div>
  );
}

function weightRows(weights?: Record<string, number>): [WeightKey, number][] {
  return WEIGHT_ORDER.map((key) => [key, Number(weights?.[key] ?? DEFAULT_WEIGHTS[key])]);
}

function matchSortValue(match: Match): number {
  const parsed = match.date_utc ? Date.parse(match.date_utc) : Number.NaN;
  if (Number.isFinite(parsed)) return parsed;
  return match.match_number * 1_000_000;
}

const RACE_LOWER_IS_BETTER = new Set(["gols_contra", "gols_contra_pj"]);
const RACE_PERCENT_FRAC = new Set(["posse", "aproveitamento"]);
type TrajectoryMode = "rank" | "value";

const TEAM_ACCENT_COLORS = [
  "#58a6ff",
  "#3fb950",
  "#ff7b72",
  "#d29922",
  "#a371f7",
  "#39c5cf",
  "#ff8b3d",
  "#f778ba",
];

const POINT_COMPARE_METRICS: [string, string][] = [
  ["score_geral", "Geral"],
  ["score_resultado", "Resultado"],
  ["score_ataque", "Ataque"],
  ["score_defesa", "Defesa"],
  ["score_eficiencia", "Eficiência"],
  ["score_controle", "Controle"],
  ["score_forca_relativa", "Força Rel."],
  ["elo_rating", "Elo"],
  ["points", "Pontos"],
  ["saldo_gols", "Saldo"],
];

interface TimelinePoint {
  snapshot: number;
  value: number;
  rank: number | null;
}

interface TeamTimeline {
  team: string;
  color: string;
  points: TimelinePoint[];
  current: TimelinePoint | null;
  previous: TimelinePoint | null;
}

interface CompareTeamOrder {
  team: string;
  color: string;
  value: number | null;
}

interface PointCompareCell {
  team: string;
  color: string;
  value: number | null;
  rank: number | null;
}

interface PointCompareRow {
  metricKey: string;
  label: string;
  cells: PointCompareCell[];
}

interface AnalysisFrame {
  x: number;
  y: number;
  width: number;
  height: number;
}

function teamAccentColor(index: number): string {
  return TEAM_ACCENT_COLORS[index % TEAM_ACCENT_COLORS.length];
}

const ANALYSIS_MODAL_GAP = 16;
const ANALYSIS_MODAL_MIN_WIDTH = 520;
const ANALYSIS_MODAL_MIN_HEIGHT = 360;

function clampNumber(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

function analysisViewport(): { width: number; height: number } {
  if (typeof window === "undefined") return { width: 1440, height: 900 };
  return { width: window.innerWidth, height: window.innerHeight };
}

function constrainAnalysisFrame(frame: AnalysisFrame): AnalysisFrame {
  const viewport = analysisViewport();
  const maxWidth = Math.max(320, viewport.width - ANALYSIS_MODAL_GAP * 2);
  const maxHeight = Math.max(280, viewport.height - ANALYSIS_MODAL_GAP * 2);
  const minWidth = Math.min(ANALYSIS_MODAL_MIN_WIDTH, maxWidth);
  const minHeight = Math.min(ANALYSIS_MODAL_MIN_HEIGHT, maxHeight);
  const width = clampNumber(Math.round(frame.width), minWidth, maxWidth);
  const height = clampNumber(Math.round(frame.height), minHeight, maxHeight);
  return {
    width,
    height,
    x: clampNumber(Math.round(frame.x), ANALYSIS_MODAL_GAP, viewport.width - ANALYSIS_MODAL_GAP - width),
    y: clampNumber(Math.round(frame.y), ANALYSIS_MODAL_GAP, viewport.height - ANALYSIS_MODAL_GAP - height),
  };
}

function defaultAnalysisFrame(wide: boolean): AnalysisFrame {
  const viewport = analysisViewport();
  const width = Math.min(wide ? 1360 : 1120, viewport.width - ANALYSIS_MODAL_GAP * 2);
  const height = Math.min(840, viewport.height - ANALYSIS_MODAL_GAP * 2);
  return constrainAnalysisFrame({
    width,
    height,
    x: (viewport.width - width) / 2,
    y: (viewport.height - height) / 2,
  });
}

function hexLuminance(hex: string): number {
  const normalized = hex.replace("#", "");
  if (normalized.length !== 6) return 0.5;
  const [r, g, b] = [0, 2, 4].map((start) => parseInt(normalized.slice(start, start + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function countryChartColors(team: string): { main: string; accent: string; text: string } {
  if (team === "Alemanha") return { main: "#facc15", accent: "#ef4444", text: "#111827" };
  if (team === "Estados Unidos") return { main: "#2563eb", accent: "#dc2626", text: "#f8fafc" };

  const kit = getKit(team);
  const mainLum = hexLuminance(kit.main);
  const borderLum = hexLuminance(kit.border);
  const main = mainLum > 0.86 && borderLum < 0.82 ? kit.border : kit.main;
  const accent = kit.border !== main ? kit.border : kit.text;
  return { main, accent, text: kit.text };
}

function rankAccent(rank: number | null): { color: string; bg: string; border: string; medal: string; label: string } {
  if (rank === 1) {
    return { color: "#ffd166", bg: "rgba(245, 197, 66, 0.14)", border: "rgba(245, 197, 66, 0.62)", medal: "🥇", label: "1º" };
  }
  if (rank === 2) {
    return { color: "#d7dee8", bg: "rgba(192, 200, 212, 0.12)", border: "rgba(192, 200, 212, 0.52)", medal: "🥈", label: "2º" };
  }
  if (rank === 3) {
    return { color: "#e6a15f", bg: "rgba(205, 127, 50, 0.12)", border: "rgba(205, 127, 50, 0.52)", medal: "🥉", label: "3º" };
  }
  if (rank === 4) {
    return { color: "#79c0ff", bg: "rgba(88, 166, 255, 0.08)", border: "rgba(88, 166, 255, 0.34)", medal: "", label: "4º" };
  }
  if (rank) {
    return { color: "#8b949e", bg: "rgba(139, 148, 158, 0.05)", border: "rgba(139, 148, 158, 0.22)", medal: "", label: `${rank}º` };
  }
  return { color: "#6b7280", bg: "rgba(139, 148, 158, 0.04)", border: "rgba(139, 148, 158, 0.18)", medal: "", label: "—" };
}

function metricDisplayLabel(metric: string): string {
  for (const group of METRIC_OPTIONS) {
    const item = group.items.find(([value]) => value === metric);
    if (item) return item[1];
  }
  return metric.replaceAll("_", " ");
}

function snapshotMetricValue(row: TeamSnapshot | undefined, metric: string): number | null {
  if (!row) return null;
  const value = row[metric];
  return typeof value === "number" ? value : null;
}

function formatSnapshotMetric(value: number | null, metric: string): string {
  if (value == null) return "sem dado";
  if (RACE_PERCENT_FRAC.has(metric)) {
    const pct = value <= 1 ? value * 100 : value;
    return `${pct.toFixed(0)}%`;
  }
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
}

function formatDeltaValue(delta: number, metric: string): string {
  if (Math.abs(delta) < 0.005) return "=";
  const sign = delta > 0 ? "+" : "";
  if (RACE_PERCENT_FRAC.has(metric)) {
    const pct = Math.abs(delta) <= 1 ? delta * 100 : delta;
    return `${sign}${pct.toFixed(0)}%`;
  }
  return `${sign}${delta.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}`;
}

function buildMetricRankLookup(rows: TeamSnapshot[], metric: string): Map<string, number> {
  const asc = RACE_LOWER_IS_BETTER.has(metric);
  const ranked = rows
    .map((row) => ({ team: row.team, value: snapshotMetricValue(row, metric) }))
    .filter((row): row is { team: string; value: number } => row.value != null)
    .sort((a, b) => (asc ? a.value - b.value : b.value - a.value));
  const out = new Map<string, number>();
  let lastValue: number | null = null;
  let lastRank = 0;
  ranked.forEach((row, index) => {
    const rank = lastValue !== null && row.value === lastValue ? lastRank : index + 1;
    out.set(row.team, rank);
    lastValue = row.value;
    lastRank = rank;
  });
  return out;
}

function buildSelectedMetricRanks(items: { team: string; value: number | null }[], metric: string): Map<string, number> {
  const asc = RACE_LOWER_IS_BETTER.has(metric);
  const ranked = items
    .filter((item): item is { team: string; value: number } => item.value != null)
    .sort((a, b) => (asc ? a.value - b.value : b.value - a.value));
  const out = new Map<string, number>();
  let lastValue: number | null = null;
  let lastRank = 0;
  ranked.forEach((item, index) => {
    const rank = lastValue !== null && item.value === lastValue ? lastRank : index + 1;
    out.set(item.team, rank);
    lastValue = item.value;
    lastRank = rank;
  });
  return out;
}

function trajectoryDeltaText(current: TimelinePoint | null, previous: TimelinePoint | null, mode: TrajectoryMode, metric: string): string {
  if (!current || !previous) return "novo";
  if (mode === "rank") {
    if (current.rank == null || previous.rank == null) return "novo";
    const delta = current.rank - previous.rank;
    if (delta === 0) return "=";
    return `${delta < 0 ? "↑" : "↓"} ${Math.abs(delta)}`;
  }
  return formatDeltaValue(current.value - previous.value, metric);
}

function trajectoryDeltaTone(current: TimelinePoint | null, previous: TimelinePoint | null, mode: TrajectoryMode, metric: string): "good" | "bad" | "flat" {
  if (!current || !previous) return "flat";
  const delta = mode === "rank"
    ? (current.rank ?? 0) - (previous.rank ?? 0)
    : current.value - previous.value;
  if (Math.abs(delta) < 0.005) return "flat";
  const good = mode === "rank" || RACE_LOWER_IS_BETTER.has(metric) ? delta < 0 : delta > 0;
  return good ? "good" : "bad";
}

function RaceSelectionSidebar({
  selectedTeams,
  currentSnapshot,
  metric,
  snapshots,
  onRemoveTeam,
  onClear,
  onMetricChange,
}: {
  selectedTeams: string[];
  currentSnapshot: number;
  metric: string;
  snapshots: TeamSnapshot[];
  onRemoveTeam: (team: string) => void;
  onClear: () => void;
  onMetricChange: (metric: string) => void;
}) {
  const [trajectoryOpen, setTrajectoryOpen] = React.useState(true);
  const [compareOpen, setCompareOpen] = React.useState(true);
  const [trajectoryModalOpen, setTrajectoryModalOpen] = React.useState(false);
  const [compareModalOpen, setCompareModalOpen] = React.useState(false);
  const [trajectoryMode, setTrajectoryMode] = React.useState<TrajectoryMode>("rank");
  const [compareSortMetric, setCompareSortMetric] = React.useState("score_geral");
  const [focusedTeams, setFocusedTeams] = React.useState<string[]>([]);
  const metricLabel = metricDisplayLabel(metric);
  const activeCompareSortMetric = POINT_COMPARE_METRICS.some(([metricKey]) => metricKey === metric)
    ? metric
    : compareSortMetric;
  const validFocusedTeams = React.useMemo(
    () => focusedTeams.filter((team) => selectedTeams.includes(team)),
    [focusedTeams, selectedTeams]
  );
  const activePanelTeams = React.useMemo(
    () => (validFocusedTeams.length ? validFocusedTeams : selectedTeams),
    [validFocusedTeams, selectedTeams]
  );

  const snapshotRows = React.useMemo(
    () => snapshots.filter((row) => row.snapshot_jogo === currentSnapshot),
    [snapshots, currentSnapshot]
  );

  const rowByTeam = React.useMemo(
    () => new Map(snapshotRows.map((row) => [row.team, row])),
    [snapshotRows]
  );

  const sortedCompareTeams = React.useMemo<CompareTeamOrder[]>(() => {
    const asc = RACE_LOWER_IS_BETTER.has(activeCompareSortMetric);
    return activePanelTeams
      .map((team) => ({
        team,
        color: countryChartColors(team).main,
        value: snapshotMetricValue(rowByTeam.get(team), activeCompareSortMetric),
      }))
      .sort((a, b) => {
        if (a.value == null && b.value == null) return a.team.localeCompare(b.team, "pt-BR");
        if (a.value == null) return 1;
        if (b.value == null) return -1;
        const aValue = a.value;
        const bValue = b.value;
        if (aValue === bValue) return a.team.localeCompare(b.team, "pt-BR");
        return asc ? aValue - bValue : bValue - aValue;
      });
  }, [activeCompareSortMetric, activePanelTeams, rowByTeam]);

  const timelineSeries = React.useMemo<TeamTimeline[]>(() => {
    const rowsBySnapshot = new Map<number, TeamSnapshot[]>();
    for (const row of snapshots) {
      if (row.snapshot_jogo > currentSnapshot) continue;
      const rows = rowsBySnapshot.get(row.snapshot_jogo) ?? [];
      rows.push(row);
      rowsBySnapshot.set(row.snapshot_jogo, rows);
    }

    const snapshotNumbers = [...rowsBySnapshot.keys()].sort((a, b) => a - b);
    const ranksBySnapshot = new Map<number, Map<string, number>>();
    for (const snapshot of snapshotNumbers) {
      ranksBySnapshot.set(snapshot, buildMetricRankLookup(rowsBySnapshot.get(snapshot) ?? [], metric));
    }

    return activePanelTeams.map((team, index) => {
      const points = snapshotNumbers
        .map((snapshot) => {
          const row = (rowsBySnapshot.get(snapshot) ?? []).find((item) => item.team === team);
          const value = snapshotMetricValue(row, metric);
          if (value == null) return null;
          return {
            snapshot,
            value,
            rank: ranksBySnapshot.get(snapshot)?.get(team) ?? null,
          };
        })
        .filter((point): point is TimelinePoint => point != null);
      return {
        team,
        color: teamAccentColor(selectedTeams.indexOf(team) >= 0 ? selectedTeams.indexOf(team) : index),
        points,
        current: points[points.length - 1] ?? null,
        previous: points[points.length - 2] ?? null,
      };
    });
  }, [snapshots, currentSnapshot, metric, activePanelTeams, selectedTeams]);

  const compareRows = React.useMemo<PointCompareRow[]>(
    () =>
      POINT_COMPARE_METRICS.map(([metricKey, label]) => {
        const cells = sortedCompareTeams.map(({ team, color }) => ({
          team,
          color,
          value: snapshotMetricValue(rowByTeam.get(team), metricKey),
        }));
        const rankBySelectedTeam = buildSelectedMetricRanks(cells, metricKey);
        return {
          metricKey,
          label,
          cells: cells.map((cell) => ({
            ...cell,
            rank: rankBySelectedTeam.get(cell.team) ?? null,
          })),
        };
      }),
    [rowByTeam, sortedCompareTeams]
  );

  function selectCompareMetric(metricKey: string) {
    setCompareSortMetric(metricKey);
    onMetricChange(metricKey);
  }

  function toggleFocusedTeam(team: string) {
    setFocusedTeams((current) => {
      const valid = current.filter((item) => selectedTeams.includes(item));
      if (valid.length === 0) return [team];
      if (valid.includes(team)) return valid.filter((item) => item !== team);
      return [...valid, team];
    });
  }

  return (
    <>
    <aside className="v2-selection-sidebar" aria-label="Selecoes selecionadas">
      <div className="v2-sidebar-head">
        <div>
          <span>Painéis</span>
          <strong>{selectedTeams.length ? `${selectedTeams.length} fixada(s)` : "Nada fixado"}</strong>
        </div>
        {selectedTeams.length > 0 && (
          <button type="button" onClick={onClear}>
            Limpar
          </button>
        )}
      </div>

      <section className="v2-side-panel">
        <button type="button" className="v2-side-toggle" onClick={() => setTrajectoryOpen((open) => !open)}>
          <span>Trajetória</span>
          <i>{trajectoryOpen ? "−" : "+"}</i>
        </button>
        {trajectoryOpen && (
          <div className="v2-side-body">
            {selectedTeams.length === 0 ? (
              <p className="v2-side-empty">Nenhuma seleção fixa.</p>
            ) : (
              <>
                <TeamFocusControls
                  selectedTeams={selectedTeams}
                  activeTeams={activePanelTeams}
                  focusedCount={validFocusedTeams.length}
                  onToggleTeam={toggleFocusedTeam}
                  onRemoveTeam={onRemoveTeam}
                  onShowAll={() => setFocusedTeams([])}
                />
                <div className="v2-side-meta-grid">
                  <span>Snapshot</span>
                  <strong>{currentSnapshot}</strong>
                  <span>Métrica</span>
                  <strong>{metricLabel}</strong>
                </div>
                <button type="button" className="v2-side-open-button" onClick={() => setTrajectoryModalOpen(true)}>
                  <Maximize2 size={14} strokeWidth={2.2} />
                  Abrir trajetória
                </button>
                <div className="v2-traj-mode" role="group" aria-label="Modo da trajetória">
                  <button type="button" className={trajectoryMode === "rank" ? "is-active" : ""} onClick={() => setTrajectoryMode("rank")}>
                    Ranking
                  </button>
                  <button type="button" className={trajectoryMode === "value" ? "is-active" : ""} onClick={() => setTrajectoryMode("value")}>
                    Valor
                  </button>
                </div>
                <RechartsTrajectoryChart
                  series={timelineSeries}
                  mode={trajectoryMode}
                  metric={metric}
                  currentSnapshot={currentSnapshot}
                />
                <TrajectorySummaryRows series={timelineSeries} mode={trajectoryMode} metric={metric} />
              </>
            )}
          </div>
        )}
      </section>

      <section className="v2-side-panel">
        <button type="button" className="v2-side-toggle" onClick={() => setCompareOpen((open) => !open)}>
          <span>Comparação ponto a ponto</span>
          <i>{compareOpen ? "−" : "+"}</i>
        </button>
        {compareOpen && (
          <div className="v2-side-body">
            {activePanelTeams.length < 2 ? (
              <p className="v2-side-empty">Ative 2 ou mais seleções no foco.</p>
            ) : (
              <>
                <button type="button" className="v2-side-open-button" onClick={() => setCompareModalOpen(true)}>
                  <Maximize2 size={14} strokeWidth={2.2} />
                  Abrir comparação
                </button>
                <PointCompareMatrix
                  currentSnapshot={currentSnapshot}
                  metric={metric}
                  activeCompareSortMetric={activeCompareSortMetric}
                  sortedCompareTeams={sortedCompareTeams}
                  compareRows={compareRows}
                  onMetricSelect={selectCompareMetric}
                />
              </>
            )}
          </div>
        )}
      </section>
    </aside>

    <AnalysisModal
      open={trajectoryModalOpen}
      title="Trajetória"
      subtitle={`${activePanelTeams.length}/${selectedTeams.length} seleção${selectedTeams.length !== 1 ? "es" : ""} · ${metricLabel} · Snapshot ${currentSnapshot}`}
      onClose={() => setTrajectoryModalOpen(false)}
    >
      <div className="v2-modal-toolbar">
        <TeamFocusControls
          selectedTeams={selectedTeams}
          activeTeams={activePanelTeams}
          focusedCount={validFocusedTeams.length}
          onToggleTeam={toggleFocusedTeam}
          onRemoveTeam={onRemoveTeam}
          onShowAll={() => setFocusedTeams([])}
          variant="modal"
        />
        <MetricSelect value={metric} onChange={onMetricChange} variant="modal" label="Comparar" />
        <div className="v2-traj-mode" role="group" aria-label="Modo da trajetória no modal">
          <button type="button" className={trajectoryMode === "rank" ? "is-active" : ""} onClick={() => setTrajectoryMode("rank")}>
            Ranking
          </button>
          <button type="button" className={trajectoryMode === "value" ? "is-active" : ""} onClick={() => setTrajectoryMode("value")}>
            Valor
          </button>
        </div>
      </div>
      <RechartsTrajectoryChart
        series={timelineSeries}
        mode={trajectoryMode}
        metric={metric}
        currentSnapshot={currentSnapshot}
        variant="wide"
      />
      <TrajectorySummaryRows series={timelineSeries} mode={trajectoryMode} metric={metric} variant="wide" />
    </AnalysisModal>

    <AnalysisModal
      open={compareModalOpen}
      title="Comparação ponto a ponto"
      subtitle={`Snapshot ${currentSnapshot} · ${activePanelTeams.length}/${selectedTeams.length} seleções · Ordem: ${metricDisplayLabel(activeCompareSortMetric)}`}
      onClose={() => setCompareModalOpen(false)}
      wide
    >
      <PointCompareMatrix
        currentSnapshot={currentSnapshot}
        metric={metric}
        activeCompareSortMetric={activeCompareSortMetric}
        sortedCompareTeams={sortedCompareTeams}
        compareRows={compareRows}
        onMetricSelect={selectCompareMetric}
        variant="modal"
      />
    </AnalysisModal>
    </>
  );
}

function TeamFocusControls({
  selectedTeams,
  activeTeams,
  focusedCount,
  onToggleTeam,
  onRemoveTeam,
  onShowAll,
  variant = "side",
}: {
  selectedTeams: string[];
  activeTeams: string[];
  focusedCount: number;
  onToggleTeam: (team: string) => void;
  onRemoveTeam: (team: string) => void;
  onShowAll: () => void;
  variant?: "side" | "modal";
}) {
  const activeSet = new Set(activeTeams);

  return (
    <div className={`v2-focus-controls ${variant === "modal" ? "is-modal" : ""}`}>
      <div className="v2-focus-head">
        <span>{focusedCount ? `Foco ${activeTeams.length}/${selectedTeams.length}` : `Todas ${selectedTeams.length}`}</span>
        {focusedCount > 0 && (
          <button type="button" onClick={onShowAll}>
            Ver todas
          </button>
        )}
      </div>
      <div className="v2-focus-chip-list">
        {selectedTeams.map((team, index) => {
          const isActive = activeSet.has(team);
          return (
            <span
              key={team}
              className={`v2-focus-chip ${isActive ? "is-active" : "is-muted"}`}
              style={{ "--team-color": teamAccentColor(index) } as React.CSSProperties}
            >
              <button type="button" className="v2-focus-main" onClick={() => onToggleTeam(team)} title={`Isolar ${team}`}>
                <span className="v2-team-color-dot" />
                <Flag team={team} height={9} />
                <b>{team}</b>
              </button>
              <button type="button" className="v2-focus-remove" onClick={() => onRemoveTeam(team)} aria-label={`Remover ${team}`}>
                <X size={10} strokeWidth={2.4} />
              </button>
            </span>
          );
        })}
      </div>
    </div>
  );
}

function TrajectorySummaryRows({
  series,
  mode,
  metric,
  variant = "side",
}: {
  series: TeamTimeline[];
  mode: TrajectoryMode;
  metric: string;
  variant?: "side" | "wide";
}) {
  return (
    <div className={`v2-trajectory-summary ${variant === "wide" ? "is-wide" : ""}`}>
      {series.map((serie) => {
        const tone = trajectoryDeltaTone(serie.current, serie.previous, mode, metric);
        const valueLabel = !serie.current
          ? "sem dado"
          : mode === "rank"
            ? `#${serie.current.rank ?? "—"}`
            : formatSnapshotMetric(serie.current.value, metric);
        const subLabel = !serie.current
          ? "—"
          : mode === "rank"
            ? formatSnapshotMetric(serie.current.value, metric)
            : serie.current.rank
              ? `#${serie.current.rank}`
              : "sem rank";
        return (
          <div key={serie.team} className={`v2-trajectory-row ${tone}`} style={{ "--team-color": serie.color } as React.CSSProperties}>
            <span className="v2-team-color-dot" />
            <span className="v2-trajectory-team">
              <Flag team={serie.team} height={11} />
              {serie.team}
            </span>
            <strong>{valueLabel}</strong>
            <em title={subLabel}>{trajectoryDeltaText(serie.current, serie.previous, mode, metric)}</em>
          </div>
        );
      })}
    </div>
  );
}

function CompareBarTooltip({
  active,
  payload,
  label,
  metric,
}: {
  active?: boolean;
  payload?: Array<{ payload?: { rawValue?: number | null; color?: string }; value?: number | null }>;
  label?: string | number;
  metric: string;
}) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  const value = item.payload?.rawValue ?? item.value ?? null;

  return (
    <div className="v2-recharts-tooltip">
      <strong className="v2-recharts-tooltip-title">
        <Flag team={String(label ?? "")} height={12} />
        <span>{label}</span>
      </strong>
      <span style={{ "--team-color": item.payload?.color ?? "#58a6ff" } as React.CSSProperties}>
        <i />
        <b>{metricDisplayLabel(metric)}</b>
        <em>{formatSnapshotMetric(value, metric)}</em>
      </span>
    </div>
  );
}

interface CountryBarShapeProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: {
    flagSrc?: string | null;
    team?: string;
  };
}

function CountryBarShape({ x = 0, y = 0, width = 0, height = 0, payload }: CountryBarShapeProps) {
  if (width <= 0 || height <= 0) return null;

  const flagSrc = payload?.flagSrc ?? null;
  const flagHeight = Math.min(54, Math.max(36, width * 0.28));
  const flagWidth = flagHeight * 1.45;
  const badgePad = 8;
  const badgeWidth = flagWidth + badgePad * 2;
  const badgeHeight = flagHeight + badgePad * 2;
  const badgeX = x + width / 2 - badgeWidth / 2;
  const badgeY = Math.max(4, y - badgeHeight / 2);

  return (
    <g>
      {flagSrc && (
        <g>
          <rect
            x={badgeX - 8}
            y={badgeY - 8}
            width={badgeWidth + 16}
            height={badgeHeight + 16}
            rx={16}
            fill="rgba(88, 166, 255, 0.18)"
          />
          <rect
            x={badgeX - 3}
            y={badgeY - 3}
            width={badgeWidth + 6}
            height={badgeHeight + 6}
            rx={12}
            fill="rgba(13, 17, 23, 0.72)"
            stroke="rgba(121, 192, 255, 0.28)"
          />
          <rect
            x={badgeX}
            y={badgeY}
            width={badgeWidth}
            height={badgeHeight}
            rx={9}
            fill="#0d1117"
            stroke="rgba(240, 246, 252, 0.46)"
            strokeWidth={1.5}
          />
          <image
            href={flagSrc}
            x={badgeX + badgePad}
            y={badgeY + badgePad}
            width={flagWidth}
            height={flagHeight}
            preserveAspectRatio="xMidYMid meet"
          />
        </g>
      )}
      {!flagSrc && (
        <circle cx={x + width / 2} cy={y} r={7} fill="#79c0ff" stroke="#0d1117" strokeWidth={3} />
      )}
    </g>
  );
}

function PointCompareMatrix({
  currentSnapshot,
  metric,
  activeCompareSortMetric,
  sortedCompareTeams,
  compareRows,
  onMetricSelect,
  variant = "side",
}: {
  currentSnapshot: number;
  metric: string;
  activeCompareSortMetric: string;
  sortedCompareTeams: CompareTeamOrder[];
  compareRows: PointCompareRow[];
  onMetricSelect: (metric: string) => void;
  variant?: "side" | "modal";
}) {
  const chartHeight = variant === "modal" ? 260 : 150;
  const chartData = sortedCompareTeams.map((item) => {
    return {
      team: item.team,
      value: item.value ?? 0,
      rawValue: item.value,
      color: "#79c0ff",
      flagSrc: flagUrl(item.team, 20),
    };
  });

  return (
    <div className={`v2-pcmp ${variant === "modal" ? "is-modal" : ""}`}>
      <div className="v2-pcmp-head">
        <span>Snapshot {currentSnapshot}</span>
        <strong>Ordem: {metricDisplayLabel(activeCompareSortMetric)}</strong>
      </div>
      <div className="v2-pcmp-bars">
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart data={chartData} margin={variant === "modal" ? { top: 46, right: 18, bottom: 16, left: 0 } : { top: 40, right: 6, bottom: 0, left: -20 }}>
            <CartesianGrid stroke="#253041" strokeDasharray="3 5" vertical={false} />
            <XAxis
              dataKey="team"
              tickLine={false}
              axisLine={false}
              interval={0}
              tick={{ fill: "#8b949e", fontSize: variant === "modal" ? 11 : 9, fontWeight: 800 }}
              tickFormatter={(value) => String(value).slice(0, variant === "modal" ? 12 : 7)}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#8b949e", fontSize: variant === "modal" ? 11 : 9, fontWeight: 800 }}
              tickFormatter={(value) => formatSnapshotMetric(Number(value), activeCompareSortMetric)}
            />
            <Tooltip content={<CompareBarTooltip metric={activeCompareSortMetric} />} cursor={{ fill: "rgba(88, 166, 255, 0.08)" }} />
            <Bar dataKey="value" shape={<CountryBarShape />} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="v2-pcmp-scroll">
        <table className="v2-pcmp-table">
          <thead>
            <tr>
              <th>Componente</th>
              {sortedCompareTeams.map(({ team, color }) => (
                <th key={team} style={{ "--team-color": color } as React.CSSProperties}>
                  <span className="v2-pcmp-team-head">
                    <span className="v2-team-color-dot" />
                    <Flag team={team} height={10} />
                    <b>{team}</b>
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {compareRows.map((row) => (
              <tr key={row.metricKey} className={`${metric === row.metricKey ? "is-active" : ""} ${activeCompareSortMetric === row.metricKey ? "is-sort" : ""}`}>
                <th scope="row">
                  <button type="button" className="v2-pcmp-metric" onClick={() => onMetricSelect(row.metricKey)} title={`Ordenar por ${row.label}`}>
                    <span>{row.label}</span>
                    {activeCompareSortMetric === row.metricKey && <i>ordem</i>}
                  </button>
                </th>
                {row.cells.map((cell) => {
                  const accent = rankAccent(cell.rank);
                  return (
                  <td
                    key={`${row.metricKey}-${cell.team}`}
                    style={{
                      "--rank-color": accent.color,
                      "--rank-bg": accent.bg,
                      "--rank-border": accent.border,
                    } as React.CSSProperties}
                  >
                    <span className="v2-pcmp-cell">
                      <strong>{formatSnapshotMetric(cell.value, row.metricKey)}</strong>
                      <em>{accent.medal && <b>{accent.medal}</b>}{accent.label}</em>
                    </span>
                  </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AnalysisModal({
  open,
  title,
  subtitle,
  onClose,
  children,
  wide = false,
}: {
  open: boolean;
  title: string;
  subtitle: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const titleId = React.useId();
  const [frame, setFrame] = React.useState<AnalysisFrame | null>(null);
  const activeFrame = frame ? constrainAnalysisFrame(frame) : defaultAnalysisFrame(wide);

  React.useEffect(() => {
    if (!open) return;
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  React.useEffect(() => {
    if (!open) return;
    function handleWindowResize() {
      setFrame((current) => (current ? constrainAnalysisFrame(current) : current));
    }

    window.addEventListener("resize", handleWindowResize);
    return () => window.removeEventListener("resize", handleWindowResize);
  }, [open]);

  const startDrag = React.useCallback(
    (event: React.PointerEvent<HTMLElement>) => {
      if (event.button !== 0) return;
      const target = event.target as Element | null;
      if (target?.closest("button")) return;

      event.preventDefault();
      const startX = event.clientX;
      const startY = event.clientY;
      const startFrame = activeFrame;

      function handlePointerMove(moveEvent: PointerEvent) {
        setFrame(constrainAnalysisFrame({
          ...startFrame,
          x: startFrame.x + moveEvent.clientX - startX,
          y: startFrame.y + moveEvent.clientY - startY,
        }));
      }

      function handlePointerUp() {
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        document.removeEventListener("pointermove", handlePointerMove);
        document.removeEventListener("pointerup", handlePointerUp);
        document.removeEventListener("pointercancel", handlePointerUp);
      }

      document.body.style.cursor = "grabbing";
      document.body.style.userSelect = "none";
      document.addEventListener("pointermove", handlePointerMove);
      document.addEventListener("pointerup", handlePointerUp);
      document.addEventListener("pointercancel", handlePointerUp);
    },
    [activeFrame]
  );

  const startResize = React.useCallback(
    (event: React.PointerEvent<HTMLButtonElement>) => {
      if (event.button !== 0) return;
      event.preventDefault();
      event.stopPropagation();
      const startX = event.clientX;
      const startY = event.clientY;
      const startFrame = activeFrame;

      function handlePointerMove(moveEvent: PointerEvent) {
        setFrame(constrainAnalysisFrame({
          ...startFrame,
          width: startFrame.width + moveEvent.clientX - startX,
          height: startFrame.height + moveEvent.clientY - startY,
        }));
      }

      function handlePointerUp() {
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        document.removeEventListener("pointermove", handlePointerMove);
        document.removeEventListener("pointerup", handlePointerUp);
        document.removeEventListener("pointercancel", handlePointerUp);
      }

      document.body.style.cursor = "nwse-resize";
      document.body.style.userSelect = "none";
      document.addEventListener("pointermove", handlePointerMove);
      document.addEventListener("pointerup", handlePointerUp);
      document.addEventListener("pointercancel", handlePointerUp);
    },
    [activeFrame]
  );

  if (!open) return null;

  return (
    <div className="v2-analysis-backdrop" role="presentation" onClick={onClose}>
      <section
        className={`v2-analysis-dialog ${wide ? "is-wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={{
          left: activeFrame.x,
          top: activeFrame.y,
          width: activeFrame.width,
          height: activeFrame.height,
        }}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="v2-analysis-header" onPointerDown={startDrag}>
          <div>
            <h2 id={titleId}>{title}</h2>
            <span>{subtitle}</span>
          </div>
          <button type="button" className="v2-close-button" onClick={onClose} aria-label="Fechar painel" style={iconButtonStyle}>
            <X size={16} />
          </button>
        </header>
        <div className="v2-analysis-body">{children}</div>
        <button type="button" className="v2-analysis-resize" onPointerDown={startResize} aria-label="Redimensionar painel" />
      </section>
    </div>
  );
}

function TrajectoryTooltip({
  active,
  payload,
  label,
  mode,
  metric,
}: {
  active?: boolean;
  payload?: Array<{ name?: string; value?: number | null; color?: string; stroke?: string }>;
  label?: string | number;
  mode: TrajectoryMode;
  metric: string;
}) {
  if (!active || !payload?.length) return null;
  const orderedPayload = payload
    .filter((entry): entry is { name?: string; value: number; color?: string; stroke?: string } => entry.value != null)
    .sort((a, b) => {
      const aValue = Number(a.value);
      const bValue = Number(b.value);
      if (aValue === bValue) return (a.name ?? "").localeCompare(b.name ?? "", "pt-BR");
      if (mode === "rank" || RACE_LOWER_IS_BETTER.has(metric)) return aValue - bValue;
      return bValue - aValue;
    });

  return (
    <div className="v2-recharts-tooltip">
      <strong>J{label}</strong>
      {orderedPayload.map((entry) => (
        <span key={entry.name} style={{ "--team-color": entry.color ?? entry.stroke ?? "#58a6ff" } as React.CSSProperties}>
          <i />
          <b>{entry.name}</b>
          <em>{mode === "rank" ? `#${entry.value}` : formatSnapshotMetric(Number(entry.value), metric)}</em>
        </span>
      ))}
    </div>
  );
}

function orderedTimelineSeriesAtSnapshot(series: TeamTimeline[], snapshot: number, mode: TrajectoryMode, metric: string): TeamTimeline[] {
  const lowerFirst = mode === "rank" || RACE_LOWER_IS_BETTER.has(metric);
  return [...series].sort((a, b) => {
    const aPoint = a.points.find((point) => point.snapshot === snapshot);
    const bPoint = b.points.find((point) => point.snapshot === snapshot);
    const aValue = aPoint ? (mode === "rank" ? aPoint.rank : aPoint.value) : null;
    const bValue = bPoint ? (mode === "rank" ? bPoint.rank : bPoint.value) : null;
    if (aValue == null && bValue == null) return a.team.localeCompare(b.team, "pt-BR");
    if (aValue == null) return 1;
    if (bValue == null) return -1;
    if (aValue === bValue) return a.team.localeCompare(b.team, "pt-BR");
    return lowerFirst ? aValue - bValue : bValue - aValue;
  });
}

type TrajectoryChartMouseState = {
  activeLabel?: string | number;
  activePayload?: Array<{ payload?: { snapshot?: string | number } }>;
};

function snapshotFromTrajectoryMouse(state: TrajectoryChartMouseState | undefined): number | null {
  const fromLabel = Number(state?.activeLabel);
  if (Number.isFinite(fromLabel)) return fromLabel;

  const fromPayload = Number(state?.activePayload?.[0]?.payload?.snapshot);
  return Number.isFinite(fromPayload) ? fromPayload : null;
}

function TrajectoryLegend({
  series,
  snapshot,
  mode,
  metric,
}: {
  series: TeamTimeline[];
  snapshot: number;
  mode: TrajectoryMode;
  metric: string;
}) {
  return (
    <div className="v2-trajectory-legend" aria-label={`Legenda ordenada no jogo ${snapshot}`}>
      {series.map((serie) => (
        <TrajectoryLegendItem key={serie.team} serie={serie} snapshot={snapshot} mode={mode} metric={metric} />
      ))}
    </div>
  );
}

function TrajectoryLegendItem({
  serie,
  snapshot,
  mode,
  metric,
}: {
  serie: TeamTimeline;
  snapshot: number;
  mode: TrajectoryMode;
  metric: string;
}) {
  const point = serie.points.find((item) => item.snapshot === snapshot);
  const displayValue = point
    ? mode === "rank"
      ? point.rank == null ? "sem rank" : `#${point.rank}`
      : formatSnapshotMetric(point.value, metric)
    : "sem dado";
  return (
    <span className="v2-trajectory-legend-item" style={{ "--team-color": serie.color } as React.CSSProperties}>
      <i />
      <b>{serie.team}</b>
      <em>{displayValue}</em>
    </span>
  );
}

function RechartsTrajectoryChart({
  series,
  mode,
  metric,
  currentSnapshot,
  variant = "side",
}: {
  series: TeamTimeline[];
  mode: TrajectoryMode;
  metric: string;
  currentSnapshot: number;
  variant?: "side" | "wide";
}) {
  const isWide = variant === "wide";
  const visibleSeries = series.filter((serie) => serie.points.length > 0);
  const snapshots = Array.from(
    new Set(visibleSeries.flatMap((serie) => serie.points.map((point) => point.snapshot)))
  ).sort((a, b) => a - b);
  const [hoverSnapshot, setHoverSnapshot] = React.useState<number | null>(null);
  const handleChartMove = React.useCallback((state: TrajectoryChartMouseState | undefined) => {
    const nextSnapshot = snapshotFromTrajectoryMouse(state);
    if (nextSnapshot == null) return;
    setHoverSnapshot((previous) => (previous === nextSnapshot ? previous : nextSnapshot));
  }, []);
  const handleChartLeave = React.useCallback(() => setHoverSnapshot(null), []);

  if (!visibleSeries.length || !snapshots.length) {
    return <p className="v2-side-empty">Sem histórico para a métrica selecionada.</p>;
  }

  const chartData = snapshots.map((snapshot) => {
    const row: Record<string, number | null> & { snapshot: number } = { snapshot };
    for (const serie of visibleSeries) {
      const point = serie.points.find((item) => item.snapshot === snapshot);
      row[serie.team] = point ? (mode === "rank" ? point.rank : point.value) : null;
    }
    return row;
  });

  const values = visibleSeries.flatMap((serie) =>
    serie.points
      .map((point) => (mode === "rank" ? point.rank : point.value))
      .filter((value): value is number => typeof value === "number")
  );
  const sameValueDomain = values.length > 0 && Math.min(...values) === Math.max(...values);
  const yAxisReversed = mode === "rank" || RACE_LOWER_IS_BETTER.has(metric);
  const chartHeight = isWide ? 420 : 172;
  const strokeWidth = isWide ? 3 : 2.2;
  const activeDotRadius = isWide ? 6 : 4;
  const legendSnapshot = hoverSnapshot ?? currentSnapshot;
  const legendSeries = orderedTimelineSeriesAtSnapshot(visibleSeries, legendSnapshot, mode, metric);

  return (
    <div className={`v2-mini-chart v2-recharts-panel ${isWide ? "is-wide" : ""}`}>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <LineChart
          data={chartData}
          margin={isWide ? { top: 22, right: 28, bottom: 10, left: 2 } : { top: 14, right: 8, bottom: 0, left: -12 }}
          onMouseMove={handleChartMove}
          onMouseLeave={handleChartLeave}
        >
          <CartesianGrid stroke="#253041" strokeDasharray="3 5" vertical={false} />
          <XAxis
            dataKey="snapshot"
            type="number"
            domain={["dataMin", "dataMax"]}
            allowDecimals={false}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "#8b949e", fontSize: isWide ? 11 : 9, fontWeight: 800 }}
            tickFormatter={(value) => `J${value}`}
          />
          <YAxis
            reversed={yAxisReversed}
            domain={sameValueDomain ? ["dataMin - 1", "dataMax + 1"] : ["auto", "auto"]}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "#8b949e", fontSize: isWide ? 11 : 9, fontWeight: 800 }}
            width={isWide ? 54 : 34}
            tickFormatter={(value) => (mode === "rank" ? `#${value}` : formatSnapshotMetric(Number(value), metric))}
          />
          <Tooltip content={<TrajectoryTooltip mode={mode} metric={metric} />} cursor={{ stroke: "#79c0ff", strokeDasharray: "4 4", opacity: 0.38 }} />
          <ReferenceLine x={currentSnapshot} stroke="#79c0ff" strokeDasharray="5 6" strokeOpacity={0.72} ifOverflow="extendDomain" />
          {visibleSeries.map((serie) => (
            <Line
              key={serie.team}
              type="monotone"
              dataKey={serie.team}
              name={serie.team}
              stroke={serie.color}
              strokeWidth={strokeWidth}
              dot={isWide ? { r: 2.6, stroke: "#060910", strokeWidth: 1.2, fill: serie.color } : false}
              activeDot={{ r: activeDotRadius, stroke: "#f0f6fc", strokeWidth: 1.4, fill: serie.color }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      {isWide && <TrajectoryLegend series={legendSeries} snapshot={legendSnapshot} mode={mode} metric={metric} />}
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars -- legacy SVG kept only while this v2 file is being split up.
function MiniTrajectoryChart({
  series,
  mode,
  metric,
  currentSnapshot,
  variant = "side",
}: {
  series: TeamTimeline[];
  mode: TrajectoryMode;
  metric: string;
  currentSnapshot: number;
  variant?: "side" | "wide";
}) {
  const visibleSeries = series.filter((serie) => serie.points.length > 0);
  const chartPoints = visibleSeries.flatMap((serie) =>
    serie.points
      .filter((point) => mode === "value" || point.rank != null)
      .map((point) => ({ ...point, color: serie.color, team: serie.team }))
  );

  if (chartPoints.length === 0) {
    return <p className="v2-side-empty">Sem histórico para a métrica selecionada.</p>;
  }

  const isWide = variant === "wide";
  const width = isWide ? 920 : 270;
  const height = isWide ? 380 : 128;
  const padLeft = isWide ? 58 : 28;
  const padRight = isWide ? 24 : 10;
  const padTop = isWide ? 28 : 14;
  const padBottom = isWide ? 42 : 24;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;
  const minSnapshot = Math.min(...chartPoints.map((point) => point.snapshot));
  const maxSnapshot = Math.max(currentSnapshot, ...chartPoints.map((point) => point.snapshot));
  const values = chartPoints.map((point) => (mode === "rank" ? point.rank ?? 0 : point.value));
  let minValue = Math.min(...values);
  let maxValue = Math.max(...values);
  if (minValue === maxValue) {
    minValue -= 1;
    maxValue += 1;
  }

  const xFor = (snapshot: number) =>
    padLeft + ((snapshot - minSnapshot) / Math.max(maxSnapshot - minSnapshot, 1)) * plotWidth;
  const yFor = (point: TimelinePoint) => {
    const rawValue = mode === "rank" ? point.rank ?? maxValue : point.value;
    const normal = (rawValue - minValue) / Math.max(maxValue - minValue, 1e-9);
    const lowerIsTop = mode === "rank" || RACE_LOWER_IS_BETTER.has(metric);
    return padTop + (lowerIsTop ? normal : 1 - normal) * plotHeight;
  };
  const currentX = xFor(currentSnapshot);
  const lowerIsTopAxis = mode === "rank" || RACE_LOWER_IS_BETTER.has(metric);
  const topAxisValue = lowerIsTopAxis ? minValue : maxValue;
  const bottomAxisValue = lowerIsTopAxis ? maxValue : minValue;
  const axisTopLabel = mode === "rank" ? `#${Math.round(topAxisValue)}` : formatSnapshotMetric(topAxisValue, metric);
  const axisBottomLabel = mode === "rank" ? `#${Math.round(bottomAxisValue)}` : formatSnapshotMetric(bottomAxisValue, metric);

  return (
    <div className={`v2-mini-chart ${isWide ? "is-wide" : ""}`}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Trajetória de ${metricDisplayLabel(metric)}`}>
        <rect x={padLeft} y={padTop} width={plotWidth} height={plotHeight} rx="7" />
        {[0, 0.5, 1].map((ratio) => {
          const y = padTop + ratio * plotHeight;
          return <line key={ratio} x1={padLeft} x2={width - padRight} y1={y} y2={y} className="v2-mini-grid" />;
        })}
        <line x1={currentX} x2={currentX} y1={padTop} y2={padTop + plotHeight} className="v2-mini-current" />
        <text x={padLeft - 5} y={padTop + 4} textAnchor="end">{axisTopLabel}</text>
        <text x={padLeft - 5} y={padTop + plotHeight + 4} textAnchor="end">{axisBottomLabel}</text>
        <text x={padLeft} y={height - 6}>J{minSnapshot}</text>
        <text x={currentX} y={height - 6} textAnchor="middle" className="v2-mini-current-label">J{currentSnapshot}</text>
        {visibleSeries.map((serie) => {
          const points = serie.points.filter((point) => mode === "value" || point.rank != null);
          const path = points
            .map((point, index) => `${index === 0 ? "M" : "L"} ${xFor(point.snapshot).toFixed(1)} ${yFor(point).toFixed(1)}`)
            .join(" ");
          const current = serie.current;
          return (
            <g key={serie.team}>
              <path d={path} fill="none" stroke={serie.color} strokeWidth={isWide ? "8" : "5"} strokeLinecap="round" strokeLinejoin="round" opacity="0.12" />
              <path d={path} fill="none" stroke={serie.color} strokeWidth={isWide ? "3.2" : "2.2"} strokeLinecap="round" strokeLinejoin="round" />
              {points.map((point) => (
                <circle
                  key={`${serie.team}-${point.snapshot}`}
                  cx={xFor(point.snapshot)}
                  cy={yFor(point)}
                  r={point.snapshot === currentSnapshot ? (isWide ? 5.2 : 3.9) : (isWide ? 2.7 : 2)}
                  fill={serie.color}
                  stroke="#060910"
                  strokeWidth="1.4"
                >
                  <title>{`${serie.team} · J${point.snapshot} · ${mode === "rank" ? `#${point.rank}` : formatSnapshotMetric(point.value, metric)}`}</title>
                </circle>
              ))}
              {current && (
                <circle
                  cx={xFor(current.snapshot)}
                  cy={yFor(current)}
                  r={isWide ? "10" : "7"}
                  fill="none"
                  stroke={serie.color}
                  strokeWidth="1.2"
                  opacity="0.45"
                />
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

const iconButtonStyle: React.CSSProperties = {
  width: 28,
  height: 28,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  background: "#161b22",
  border: "1px solid #30363d",
  color: "#79c0ff",
  borderRadius: 6,
  cursor: "pointer",
  fontFamily: "inherit",
  flexShrink: 0,
};

function WeightsGuideModal({
  open,
  onClose,
  weights,
  snapshot,
  match,
  selectedWeight,
  onWeightSelect,
}: {
  open: boolean;
  onClose: () => void;
  weights: ScoreWeights | undefined;
  snapshot: number;
  match: Match | undefined;
  selectedWeight: WeightKey;
  onWeightSelect: (key: WeightKey) => void;
}) {
  const [section, setSection] = React.useState<GuideSection>("overview");

  React.useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  const rows = weightRows(weights?.pesos);
  const total = rows.reduce((sum, [, w]) => sum + w, 0);
  const matchLabel = match
    ? `Jogo ${String(snapshot).padStart(3, "0")} · ${match.home_team ?? "Mandante"} ${match.home_score ?? "–"}×${match.away_score ?? "–"} ${match.away_team ?? "Visitante"}`
    : `Snapshot ${snapshot || "atual"}`;
  const typeLabel = "pesos fixos";

  return (
    <div
      className="v2-guide-backdrop"
      role="presentation"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        background: "rgba(0, 0, 0, 0.68)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <section
        className="v2-guide-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="weights-guide-title"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(1280px, calc(100vw - 24px))",
          maxHeight: "min(760px, calc(100vh - 32px))",
          display: "grid",
          gridTemplateRows: "auto 1fr",
          overflow: "hidden",
          background: "#0d1117",
          border: "1px solid #30363d",
          borderRadius: 10,
          boxShadow: "0 24px 80px rgba(0, 0, 0, 0.45)",
        }}
      >
        <header style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 16px", borderBottom: "1px solid #253041" }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <h2 id="weights-guide-title" style={{ margin: 0, color: "#e6edf3", fontSize: 15, fontWeight: 800 }}>
              Guia dos pesos do ranking
            </h2>
            <p style={{ margin: "3px 0 0", color: "#8b949e", fontSize: 11 }}>
              {typeLabel} do score geral · {matchLabel}
            </p>
          </div>
          <button type="button" className="v2-close-button" onClick={onClose} aria-label="Fechar guia dos pesos" style={iconButtonStyle}>
            <X size={16} />
          </button>
        </header>

        <div style={{ minHeight: 0, display: "grid", gridTemplateColumns: "minmax(120px, 150px) minmax(0, 1fr)" }}>
          <aside style={{ padding: 12, borderRight: "1px solid #253041", background: "#090e16" }}>
          {[
              ["overview", "Visão geral"],
              ["components", "Componentes"],
              ["faq", "FAQ"],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`v2-guide-tab ${section === id ? "is-active" : ""}`}
                onClick={() => setSection(id as GuideSection)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  marginBottom: 8,
                  padding: "9px 10px",
                  borderRadius: 7,
                  border: `1px solid ${section === id ? "#1f6feb" : "transparent"}`,
                  background: section === id ? "#10213a" : "transparent",
                  color: section === id ? "#79c0ff" : "#b7c7dc",
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                {label}
              </button>
            ))}
          </aside>

          <div style={{ minHeight: 0, overflow: "auto", padding: 24 }}>
            {section === "overview" && (
              <WeightsOverview
                rows={rows}
                total={total}
                selectedWeight={selectedWeight}
                onWeightSelect={onWeightSelect}
                onInspect={(key) => {
                  onWeightSelect(key);
                  setSection("components");
                }}
              />
            )}
            {section === "components" && (
              <WeightsComponents
                rows={rows}
                selectedWeight={selectedWeight}
                onWeightSelect={onWeightSelect}
              />
            )}
            {section === "faq" && <WeightsFaq />}
          </div>
        </div>
      </section>
    </div>
  );
}

function WeightsOverview({
  rows,
  total,
  selectedWeight,
  onWeightSelect,
  onInspect,
}: {
  rows: [WeightKey, number][];
  total: number;
  selectedWeight: WeightKey;
  onWeightSelect: (key: WeightKey) => void;
  onInspect: (key: WeightKey) => void;
}) {
  const gradient = rows
    .reduce<{ acc: number; parts: string[] }>(
      (state, [key, weight]) => {
        const start = state.acc * 100;
        const end = (state.acc + weight / Math.max(total, 1)) * 100;
        state.parts.push(`${WEIGHT_DETAILS[key].color} ${start.toFixed(2)}% ${end.toFixed(2)}%`);
        state.acc += weight / Math.max(total, 1);
        return state;
      },
      { acc: 0, parts: [] }
    )
    .parts.join(", ");
  const selectedIndex = Math.max(0, rows.findIndex(([key]) => key === selectedWeight));
  const selected = WEIGHT_DETAILS[selectedWeight];
  const selectedPercent = rows.find(([key]) => key === selectedWeight)?.[1] ?? DEFAULT_WEIGHTS[selectedWeight];
  const nextKey = rows[(selectedIndex + 1) % rows.length]?.[0] ?? "score_resultado";

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div>
        <div style={{ color: "#79c0ff", fontSize: 11, fontWeight: 800, textTransform: "uppercase", letterSpacing: 0 }}>
          Régua atual
        </div>
        <h3 style={{ margin: "8px 0", color: "#f0f6fc", fontSize: 22, lineHeight: 1.2, fontWeight: 750 }}>
          O ranking usa pesos fixos para combinar placar, processo e contexto.
        </h3>
        <p style={{ margin: 0, color: "#c9d7e5", fontSize: 14, lineHeight: 1.55, maxWidth: 900 }}>
          Os percentuais não são recalibrados a cada jogo. O que muda em cada snapshot são as notas dos componentes:
          resultado, ataque, defesa, eficiência, controle e força relativa. Assim a comparação no tempo fica estável e
          a leitura não troca de régua no meio do torneio.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 22, alignItems: "center" }}>
        <button
          type="button"
          className="v2-donut-button"
          onClick={() => onWeightSelect(nextKey)}
          title={`Clique para alternar para ${WEIGHT_DETAILS[nextKey].label}`}
          style={{ "--selected-color": selected.color, background: `conic-gradient(${gradient})` } as React.CSSProperties}
        >
          <div className="v2-donut-core">
            <strong>{(selectedPercent * 100).toFixed(0)}%</strong>
            <span>{selected.label}</span>
          </div>
        </button>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 10 }}>
          {rows.map(([key, weight]) => (
            <button
              key={key}
              type="button"
              className={`v2-guide-weight-tile ${selectedWeight === key ? "is-active" : ""}`}
              onClick={() => onWeightSelect(key)}
              onDoubleClick={() => onInspect(key)}
              title="Clique para destacar. Dois cliques abrem o detalhe."
              style={{ "--weight-color": WEIGHT_DETAILS[key].color } as React.CSSProperties}
            >
              <span className="v2-weight-dot" />
              <span style={{ color: "#dbe7f3", fontSize: 13, fontWeight: 700 }}>{WEIGHT_DETAILS[key].label}</span>
              <strong style={{ color: "#79c0ff", fontSize: 13 }}>{(weight * 100).toFixed(0)}%</strong>
            </button>
          ))}
        </div>
      </div>

      <button
        type="button"
        className="v2-selected-weight-panel"
        onClick={() => onInspect(selectedWeight)}
        style={{ "--selected-color": selected.color } as React.CSSProperties}
      >
        <span className="v2-selected-weight-kicker">Componente em foco</span>
        <strong>{selected.label} · {(selectedPercent * 100).toFixed(0)}%</strong>
        <span>{selected.summary}</span>
      </button>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 10 }}>
        <GuideCard
          title="Fixo não quer dizer congelado"
          text="Os pesos ficam iguais; as métricas mudam conforme os jogos entregam evidência nova."
          onClick={() => onWeightSelect("score_eficiencia")}
        />
        <GuideCard
          title="Resultado é a âncora"
          text="A maior fatia protege o ranking contra uma leitura bonita no processo, mas fraca no placar."
          onClick={() => onInspect("score_resultado")}
        />
        <GuideCard
          title="Contexto entra com trava"
          text="Força relativa só cresce quando o Elo tem maturidade suficiente para diferenciar caminhos."
          onClick={() => onInspect("score_forca_relativa")}
        />
      </div>
    </div>
  );
}

function WeightsComponents({
  rows,
  selectedWeight,
  onWeightSelect,
}: {
  rows: [WeightKey, number][];
  selectedWeight: WeightKey;
  onWeightSelect: (key: WeightKey) => void;
}) {
  const selected = WEIGHT_DETAILS[selectedWeight];
  const selectedPercent = rows.find(([key]) => key === selectedWeight)?.[1] ?? DEFAULT_WEIGHTS[selectedWeight];

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div>
        <div style={{ color: "#79c0ff", fontSize: 11, fontWeight: 800, textTransform: "uppercase", letterSpacing: 0 }}>
          Detalhe dos componentes
        </div>
        <h3 style={{ margin: "8px 0", color: "#f0f6fc", fontSize: 21, lineHeight: 1.2, fontWeight: 750 }}>
          Cada peso responde uma pergunta diferente.
        </h3>
      </div>

      <div
        className="v2-component-focus"
        style={{ "--selected-color": selected.color } as React.CSSProperties}
      >
        <span>Selecionado agora</span>
        <strong>{selected.label} · {(selectedPercent * 100).toFixed(0)}%</strong>
        <p>{selected.rationale}</p>
      </div>

      <div className="v2-component-picker" role="list" aria-label="Componentes do score geral">
        {rows.map(([key, weight]) => {
          const item = WEIGHT_DETAILS[key];
          return (
            <button
              key={key}
              type="button"
              className={`v2-component-chip ${selectedWeight === key ? "is-active" : ""}`}
              onClick={() => onWeightSelect(key)}
              style={{ "--weight-color": item.color } as React.CSSProperties}
            >
              <span className="v2-weight-dot" />
              <span>{item.label}</span>
              <b>{(weight * 100).toFixed(0)}%</b>
            </button>
          );
        })}
      </div>

      <section
        key={selectedWeight}
        className="v2-tags-panel"
        style={{ "--selected-color": selected.color } as React.CSSProperties}
      >
        <div className="v2-tags-panel-head">
          <span>Tags explicadas</span>
          <strong>{selected.label}</strong>
        </div>
        <p className="v2-tags-summary">{selected.summary}</p>
        <div className="v2-tags-grid">
          {selected.signals.map((signal) => (
            <article key={signal.label} className="v2-tag-explained">
              <b>{signal.label}</b>
              <span>{signal.detail}</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function WeightsFaq() {
  const [openIndex, setOpenIndex] = React.useState(0);
  const questions = [
    {
      question: "Os pesos ainda mudam por snapshot?",
      answer: "Não. A régua é fixa: 30% Resultado, 20% Ataque, 20% Defesa, 10% Eficiência, 10% Controle e 10% Força Relativa. O que muda jogo a jogo é a pontuação de cada componente no snapshot.",
    },
    {
      question: "Por que não usar pesos iguais?",
      answer: "Porque os componentes não têm a mesma função. Resultado é a âncora competitiva; ataque e defesa pesam igual (20% cada) e explicam o processo ofensivo e defensivo; eficiência e controle são auxiliares; força relativa ajusta a dificuldade do caminho.",
    },
    {
      question: "Por que a Força Relativa pesa só 10%?",
      answer: "Porque o Resultado já pondera pela força do adversário (aproveitamento ponderado pelo Elo), então a Força Relativa complementa sem duplicar esse contexto. Seu peso de 10% vale integralmente — não há mais a antiga trava de 'maturidade do Elo'.",
    },
    {
      question: "Disciplina entra no score geral?",
      answer: "Não. Disciplina segue como score descritivo e pode ser ranqueada no seletor de métrica, mas não compõe o score geral fixo.",
    },
  ];

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {questions.map((item, index) => (
        <GuideQuestion
          key={item.question}
          question={item.question}
          answer={item.answer}
          open={openIndex === index}
          onToggle={() => setOpenIndex((current) => (current === index ? -1 : index))}
        />
      ))}
    </div>
  );
}

function GuideCard({ title, text, onClick }: { title: string; text: string; onClick?: () => void }) {
  return (
    <button type="button" className="v2-guide-card" onClick={onClick}>
      <strong style={{ display: "block", color: "#f0f6fc", fontSize: 13, marginBottom: 6 }}>{title}</strong>
      <p style={{ margin: 0, color: "#b7c7dc", fontSize: 12, lineHeight: 1.45 }}>{text}</p>
    </button>
  );
}

function GuideQuestion({
  question,
  answer,
  open,
  onToggle,
}: {
  question: string;
  answer: string;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button type="button" className={`v2-guide-question ${open ? "is-open" : ""}`} onClick={onToggle}>
      <span>
        <strong>{question}</strong>
        <i>{open ? "−" : "+"}</i>
      </span>
      <p>{answer}</p>
    </button>
  );
}

function DashboardV2MotionStyles() {
  return (
    <style>{`
      .v2-dashboard-shell {
        min-height: calc(100vh - 52px);
        background: #060910;
        color: #e6edf3;
        font-family: "Segoe UI", system-ui, sans-serif;
        width: 100%;
        max-width: 100vw;
        overflow-x: clip;
      }

      .v2-dashboard-sticky {
        position: sticky;
        top: 52px;
        z-index: 40;
        background: #0d1117;
      }

      .v2-dashboard-header {
        display: flex;
        align-items: center;
        gap: clamp(8px, 1.1vw, 16px);
        min-height: 48px;
        padding: 8px clamp(12px, 1.8vw, 24px);
        background: #0d1117;
        border-bottom: 1px solid #21262d;
        flex-wrap: wrap;
      }

      .v2-primary-tabs {
        display: flex;
        gap: 4px;
        min-width: 0;
        overflow-x: auto;
        scrollbar-width: thin;
      }

      .v2-primary-tabs button {
        flex: 0 0 auto;
      }

      .v2-header-spacer {
        flex: 1 1 120px;
        min-width: 0;
      }

      .v2-weight-strip {
        flex: 999 1 340px;
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 5px;
        flex-wrap: wrap;
        min-width: 340px;
        max-width: 100%;
      }

      .v2-weight-strip-label {
        color: #8b949e;
        font-size: 10px;
        font-weight: 800;
        text-transform: uppercase;
        white-space: nowrap;
      }

      .v2-filter-bar {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px clamp(12px, 1.8vw, 24px);
        background: #0d1117;
        border-bottom: 1px solid #161b22;
        flex-wrap: wrap;
      }

      .v2-filter-control {
        display: flex;
        align-items: center;
        gap: 6px;
        min-width: 0;
        max-width: 100%;
        color: #8b949e;
        font-size: 12px;
        white-space: nowrap;
      }

      .v2-filter-control select,
      .v2-metric-select,
      .v2-dashboard-search,
      .v2-game-speed {
        background: #161b22;
        color: #e6edf3;
        border: 1px solid #30363d;
        border-radius: 6px;
        font-family: inherit;
      }

      .v2-filter-control select,
      .v2-metric-select {
        min-width: 0;
        max-width: 100%;
        padding: 4px 8px;
        font-size: 12px;
      }

      .v2-metric-control {
        flex: 0 1 230px;
      }

      .v2-metric-select {
        width: min(100%, 180px);
      }

      .v2-sort-button {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: #161b22;
        color: #c9d1d9;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12px;
        cursor: pointer;
        font-family: inherit;
        white-space: nowrap;
      }

      .v2-search-box {
        position: relative;
        flex: 1 1 190px;
        min-width: 160px;
        max-width: 280px;
      }

      .v2-dashboard-search {
        width: 100%;
        padding: 4px 10px;
        color: #c9d1d9;
        font-size: 12px;
        outline: none;
      }

      .v2-search-suggestions {
        position: absolute;
        top: calc(100% + 4px);
        left: 0;
        z-index: 60;
        width: min(300px, calc(100vw - 24px));
        max-height: 300px;
        overflow-y: auto;
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
        padding: 4px;
      }

      .v2-filter-fill {
        flex: 1 1 48px;
        min-width: 0;
      }

      .v2-api-status {
        color: #8b949e;
        font-size: 12px;
        min-width: 0;
      }

      .v2-progress-shell {
        padding: 6px 8px;
        background: #0d1117;
        border-bottom: 1px solid #161b22;
      }

      .v2-main {
        width: 100%;
        max-width: 1760px;
        margin: 0 auto;
        padding: 24px clamp(14px, 1.7vw, 28px);
      }

      .v2-main.is-race {
        max-width: none;
        padding: 18px clamp(12px, 1.2vw, 20px) 24px;
      }

      .v2-analytics-shell {
        width: 100%;
        max-width: 1500px;
        margin: 0 auto;
        min-width: 0;
      }

      .v2-analytics-tabs {
        display: flex;
        gap: 4px;
        flex-wrap: wrap;
        justify-content: center;
        margin-bottom: 16px;
        min-width: 0;
      }

      .v2-diagnostic-shell {
        max-width: 1000px;
        margin: 0 auto;
        min-width: 0;
      }

      .v2-team-focus-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 16px;
        min-height: 34px;
        min-width: 0;
      }

      .v2-team-focus-picker {
        position: relative;
      }

      .v2-team-focus-popover {
        position: absolute;
        top: calc(100% + 6px);
        left: 0;
        z-index: 60;
        width: min(520px, calc(100vw - 24px));
        max-width: 90vw;
        background: var(--surface);
        border: 1px solid var(--surface2);
        border-radius: 10px;
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
        overflow: hidden;
      }

      .v2-team-focus-options {
        max-height: 320px;
        overflow-y: auto;
        padding: 8px;
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 4px;
      }

      .v2-predictive-shell {
        min-width: 0;
      }

      .v2-predictive-track {
        min-width: 0;
      }

      .v2-advice-shell {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 14px;
        max-width: 1180px;
        margin: 0 auto;
        min-width: 0;
      }

      .v2-advice-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr));
        gap: 14px;
        align-items: start;
        min-width: 0;
      }

      .v2-advice-strip {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 7px;
      }

      .v2-teams-tab,
      .v2-players-tab {
        min-width: 0;
      }

      .v2-teams-summary,
      .v2-players-toolbar {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 14px;
        flex-wrap: wrap;
        min-width: 0;
      }

      .v2-teams-grid {
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 12px;
        padding-bottom: 56px;
      }

      .v2-players-control,
      .v2-players-check {
        display: flex;
        align-items: center;
        gap: 6px;
        color: #8b949e;
        font-size: 12px;
      }

      .v2-players-check {
        gap: 5px;
        cursor: pointer;
      }

      .v2-players-segments {
        display: inline-flex;
        gap: 3px;
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 3px;
        max-width: 100%;
        overflow-x: auto;
        scrollbar-width: thin;
      }

      .v2-players-segments button {
        flex: 0 0 auto;
      }

      .v2-players-count {
        color: #8b949e;
        font-size: 12px;
        margin-left: auto;
      }

      .v2-players-table-wrap {
        max-width: 100%;
        overflow-x: auto;
        border: 1px solid #21262d;
        border-radius: 8px;
        scrollbar-width: thin;
      }

      .v2-players-table {
        min-width: 980px;
      }

      .v2-groups-shell,
      .v2-groups-table-tab,
      .v2-bracket-tab {
        min-width: 0;
      }

      .v2-groups-subtabs {
        display: inline-flex;
        gap: 4px;
        max-width: 100%;
        overflow-x: auto;
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 9px;
        padding: 4px;
        margin-bottom: 16px;
        scrollbar-width: thin;
      }

      .v2-groups-subtabs button {
        flex: 0 0 auto;
      }

      .v2-groups-legend {
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
        margin-bottom: 14px;
        color: #8b949e;
        font-size: 11.5px;
      }

      .v2-groups-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 16px;
      }

      .v2-group-card {
        min-width: 0;
        overflow: hidden;
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 12px;
      }

      .v2-group-table-wrap {
        max-width: 100%;
        overflow-x: auto;
        scrollbar-width: thin;
      }

      .v2-group-table {
        min-width: 540px;
      }

      .v2-bracket-scroll {
        overflow-x: auto;
        padding-bottom: 8px;
        scrollbar-width: thin;
        scroll-snap-type: x proximity;
      }

      .v2-bracket-board {
        display: flex;
        gap: 14px;
        align-items: stretch;
        width: fit-content;
        margin: 0 auto;
      }

      .v2-bracket-column {
        min-width: 158px;
        display: flex;
        flex: 0 0 auto;
        flex-direction: column;
        scroll-snap-align: start;
      }

      .v2-bracket-center {
        min-width: 230px;
        display: flex;
        flex: 0 0 auto;
        flex-direction: column;
        justify-content: center;
        gap: 22px;
        scroll-snap-align: center;
      }

      .v2-fixed-pager {
        max-width: 100vw;
        overflow-x: auto;
        scrollbar-width: thin;
      }

      .v2-fixed-pager > * {
        flex: 0 0 auto;
      }

      .v2-progress-dots {
        min-width: 0;
      }

      .v2-progress-legend {
        max-width: 100%;
        overflow-x: auto;
        scrollbar-width: thin;
      }

      .v2-progress-scroll {
        scrollbar-width: thin;
      }

      .v2-progress-group {
        scroll-snap-align: start;
      }

      .v2-team-modal-dialog {
        min-width: 0;
        box-shadow: 0 28px 88px rgba(0, 0, 0, 0.5);
      }

      .v2-team-modal-header,
      .v2-team-modal-tabs,
      .v2-team-modal-body,
      .v2-team-modal-games,
      .v2-team-game-detail,
      .v2-team-profile-full,
      .v2-team-profile-compact {
        min-width: 0;
      }

      .v2-team-modal-tabs {
        overflow-x: auto;
        scrollbar-width: thin;
      }

      .v2-team-modal-tabs button {
        flex: 0 0 auto;
      }

      .v2-team-modal-game-row {
        min-width: 0;
      }

      .v2-team-game-detail-tabs {
        overflow-x: auto;
        scrollbar-width: thin;
      }

      .v2-team-game-detail-tabs button {
        flex: 0 0 auto;
      }

      .v2-team-profile-header {
        min-width: 0;
      }

      .v2-team-roster,
      .v2-roster-leaders,
      .v2-roster-grid,
      .v2-pitch-view,
      .v2-pitch-stage,
      .v2-pitch-reserves,
      .v2-match-timeline,
      .v2-match-timeline-summary,
      .v2-match-timeline-axis,
      .v2-match-event-row,
      .v2-match-event-card {
        min-width: 0;
      }

      .v2-roster-player-card,
      .v2-pitch-player-card {
        max-width: calc(100vw - 16px);
        max-height: calc(100vh - 16px);
        overflow: auto;
      }

      .v2-match-event-card {
        overflow: hidden;
        overflow-wrap: anywhere;
      }

      .v2-match-event-card span {
        min-width: 0;
      }

      .v2-game-slider.is-compact {
        justify-content: flex-end;
      }

      .v2-game-count {
        flex: 0 0 auto;
      }

      .v2-race-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
        min-width: 0;
      }

      .v2-race-list-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
        min-width: 0;
      }

      .v2-race-metric-label {
        display: inline-flex;
        align-items: center;
        color: #8b949e;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0;
        min-width: 0;
      }

      .v2-race-empty {
        color: #8b949e;
        font-size: 13px;
        padding: 16px 0;
      }

      .v2-race-rows {
        display: flex;
        flex-direction: column;
        gap: 5px;
        min-width: 0;
      }

      .v2-race-row {
        width: 100%;
        display: grid;
        grid-template-columns: 24px 22px minmax(138px, 170px) minmax(0, 1fr) minmax(54px, 64px);
        align-items: center;
        column-gap: 8px;
        padding: 5px 8px;
        border-radius: 7px;
        cursor: pointer;
        text-align: left;
        font-family: inherit;
        min-width: 0;
      }

      .v2-race-row:hover {
        background: rgba(88, 166, 255, 0.07);
      }

      .v2-race-flag {
        width: 22px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
      }

      .v2-race-team {
        min-width: 0;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        overflow: hidden;
        color: #e6edf3;
        font-size: 13px;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .v2-race-bar {
        width: 100%;
        min-width: 0;
        height: 20px;
        position: relative;
      }

      .v2-race-value {
        width: 64px;
        color: #e6edf3;
        font-size: 12px;
        font-weight: 700;
        text-align: right;
        white-space: nowrap;
      }

      .v2-snapshot-label {
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 6px;
        color: #b7c7dc;
        font-size: 13px;
        flex-wrap: wrap;
      }

      .v2-snapshot-match {
        min-width: 0;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        color: #f0f6fc;
        font-weight: 800;
      }

      .v2-snapshot-match span {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .v2-race-workspace {
        display: grid;
        grid-template-columns: minmax(520px, 1fr) 10px min(50vw, var(--v2-sidebar-width, 392px));
        gap: 12px;
        align-items: start;
      }

      .v2-race-stage {
        min-width: 0;
        border-radius: 8px;
        padding: 8px;
        margin: -8px;
      }

      .v2-race-workspace.has-selection .v2-race-stage {
        background: linear-gradient(180deg, #03060c 0%, #060910 100%);
        box-shadow:
          inset 0 0 0 1px rgba(88, 166, 255, 0.11),
          inset -80px 0 120px rgba(0, 0, 0, 0.26),
          0 18px 54px rgba(0, 0, 0, 0.18);
      }

      .v2-sidebar-resizer {
        position: sticky;
        top: 12px;
        align-self: stretch;
        width: 10px;
        min-height: calc(100vh - 176px);
        border: 0;
        border-radius: 8px;
        background: transparent;
        cursor: col-resize;
        padding: 0;
        touch-action: none;
      }

      .v2-sidebar-resizer::before {
        content: "";
        display: block;
        width: 2px;
        height: 100%;
        min-height: calc(100vh - 176px);
        margin: 0 auto;
        border-radius: 999px;
        background: #21262d;
        transition: background 160ms ease, box-shadow 160ms ease, width 160ms ease;
      }

      .v2-sidebar-resizer:hover::before,
      .v2-sidebar-resizer:focus-visible::before {
        width: 4px;
        background: #58a6ff;
        box-shadow: 0 0 0 4px rgba(88, 166, 255, 0.13);
      }

      .v2-selection-sidebar {
        position: sticky;
        top: 12px;
        min-height: calc(100vh - 176px);
        max-height: calc(100vh - 104px);
        overflow: auto;
        scrollbar-width: thin;
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        box-shadow: 0 18px 48px rgba(0, 0, 0, 0.18);
      }

      .v2-sidebar-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding-bottom: 10px;
        border-bottom: 1px solid #21262d;
      }

      .v2-sidebar-head div {
        min-width: 0;
      }

      .v2-sidebar-head span,
      .v2-compare-caption {
        display: block;
        color: #8b949e;
        font-size: 10px;
        font-weight: 900;
        letter-spacing: 0;
        text-transform: uppercase;
      }

      .v2-sidebar-head strong {
        display: block;
        color: #f0f6fc;
        font-size: 13px;
        margin-top: 3px;
        white-space: nowrap;
      }

      .v2-sidebar-head button {
        background: #161b22;
        border: 1px solid #30363d;
        color: #79c0ff;
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 11px;
        cursor: pointer;
        font-family: inherit;
      }

      .v2-side-panel {
        display: grid;
        gap: 8px;
        padding-bottom: 12px;
        border-bottom: 1px solid #21262d;
      }

      .v2-side-panel:last-child {
        border-bottom: 0;
        padding-bottom: 0;
      }

      .v2-side-toggle {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        background: transparent;
        border: 0;
        color: #b7c7dc;
        padding: 0;
        cursor: pointer;
        font-family: inherit;
        text-align: left;
      }

      .v2-side-toggle span {
        color: #8b949e;
        font-size: 10px;
        font-weight: 900;
        text-transform: uppercase;
      }

      .v2-side-toggle i {
        width: 22px;
        height: 22px;
        border: 1px solid #30363d;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: #79c0ff;
        font-style: normal;
        flex: 0 0 auto;
      }

      .v2-side-toggle:hover span,
      .v2-side-toggle:focus-visible span {
        color: #f0f6fc;
      }

      .v2-side-toggle:hover i,
      .v2-side-toggle:focus-visible i {
        border-color: #58a6ff;
        color: #f0f6fc;
      }

      .v2-side-body {
        display: grid;
        gap: 11px;
        animation: v2-detail-slide 180ms ease-out both;
      }

      .v2-side-empty {
        margin: 0;
        color: #8b949e;
        font-size: 12px;
        line-height: 1.4;
        font-style: italic;
      }

      .v2-side-open-button {
        min-height: 30px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 7px;
        background: #10213a;
        border: 1px solid #1f6feb;
        color: #79c0ff;
        border-radius: 7px;
        cursor: pointer;
        font-family: inherit;
        font-size: 11px;
        font-weight: 850;
      }

      .v2-side-open-button:hover,
      .v2-side-open-button:focus-visible {
        transform: translateY(-1px);
        border-color: #79c0ff;
        color: #f0f6fc;
        box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.18);
      }

      .v2-selected-chip-list {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }

      .v2-selected-chip {
        max-width: 100%;
        min-width: 0;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: #10213a;
        border: 1px solid #1f6feb;
        color: #f0f6fc;
        border-radius: 6px;
        padding: 5px 7px;
        font-size: 11px;
        font-weight: 800;
        cursor: pointer;
        font-family: inherit;
      }

      .v2-selected-chip span:not(.v2-live-dot) {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .v2-live-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #3fb950;
        box-shadow: 0 0 0 3px rgba(63, 185, 80, 0.13);
        flex: 0 0 auto;
      }

      .v2-focus-controls {
        display: grid;
        gap: 7px;
      }

      .v2-focus-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }

      .v2-focus-head span {
        color: #8b949e;
        font-size: 10px;
        font-weight: 900;
        text-transform: uppercase;
      }

      .v2-focus-head button {
        background: transparent;
        border: 1px solid #30363d;
        border-radius: 999px;
        color: #79c0ff;
        cursor: pointer;
        font-family: inherit;
        font-size: 10px;
        font-weight: 850;
        padding: 2px 7px;
      }

      .v2-focus-chip-list {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }

      .v2-focus-chip {
        max-width: 100%;
        min-width: 0;
        display: inline-flex;
        align-items: center;
        overflow: hidden;
        border: 1px solid #253041;
        border-radius: 7px;
        background: #111824;
      }

      .v2-focus-chip.is-active {
        border-color: color-mix(in srgb, var(--team-color, #58a6ff) 68%, #253041);
        background: color-mix(in srgb, var(--team-color, #58a6ff) 12%, #111824);
      }

      .v2-focus-chip.is-muted {
        opacity: 0.42;
      }

      .v2-focus-main,
      .v2-focus-remove {
        border: 0;
        background: transparent;
        color: #f0f6fc;
        cursor: pointer;
        font-family: inherit;
      }

      .v2-focus-main {
        min-width: 0;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 5px 6px;
        font-size: 11px;
        font-weight: 850;
      }

      .v2-focus-main b {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .v2-focus-remove {
        align-self: stretch;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        border-left: 1px solid #253041;
        color: #8b949e;
      }

      .v2-focus-remove:hover,
      .v2-focus-remove:focus-visible,
      .v2-focus-head button:hover,
      .v2-focus-head button:focus-visible {
        color: #f0f6fc;
        border-color: #58a6ff;
      }

      .v2-focus-controls.is-modal .v2-focus-main {
        font-size: 12px;
        padding: 6px 8px;
      }

      .v2-side-meta-grid {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 6px 10px;
        padding: 8px 0 0;
        border-top: 1px solid #21262d;
      }

      .v2-side-meta-grid span,
      .v2-compare-row em {
        color: #8b949e;
        font-size: 11px;
        font-style: normal;
      }

      .v2-side-meta-grid strong {
        color: #f0f6fc;
        font-size: 12px;
        text-align: right;
      }

      .v2-compare-list {
        display: grid;
        gap: 9px;
      }

      .v2-compare-row {
        display: grid;
        gap: 5px;
        padding-top: 9px;
        border-top: 1px solid #21262d;
      }

      .v2-compare-row:first-of-type {
        border-top: 0;
        padding-top: 0;
      }

      .v2-compare-row-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        min-width: 0;
      }

      .v2-compare-row-head span {
        min-width: 0;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        color: #e6edf3;
        font-size: 12px;
        font-weight: 750;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .v2-compare-row-head strong {
        color: #79c0ff;
        font-size: 12px;
        flex: 0 0 auto;
      }

      .v2-compare-track {
        height: 6px;
        overflow: hidden;
        border-radius: 999px;
        background: #111722;
      }

      .v2-compare-track span {
        display: block;
        height: 100%;
        border-radius: inherit;
        background: linear-gradient(90deg, #58a6ff, #3fb950);
        transition: width 360ms cubic-bezier(.2, .8, .2, 1);
      }

      .v2-team-color-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--team-color, #58a6ff);
        box-shadow: 0 0 0 3px color-mix(in srgb, var(--team-color, #58a6ff) 15%, transparent);
        flex: 0 0 auto;
      }

      .v2-traj-mode {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 5px;
        background: #060910;
        border: 1px solid #21262d;
        border-radius: 7px;
        padding: 4px;
      }

      .v2-traj-mode button {
        min-height: 26px;
        border: 1px solid transparent;
        border-radius: 5px;
        background: transparent;
        color: #8b949e;
        cursor: pointer;
        font-family: inherit;
        font-size: 11px;
        font-weight: 850;
      }

      .v2-traj-mode button:hover,
      .v2-traj-mode button:focus-visible,
      .v2-traj-mode button.is-active {
        background: #10213a;
        border-color: #1f6feb;
        color: #f0f6fc;
      }

      .v2-mini-chart {
        border: 1px solid #21262d;
        border-radius: 8px;
        background: linear-gradient(180deg, #0b1018, #090d14);
        overflow: hidden;
      }

      .v2-mini-chart > svg,
      .v2-mini-chart .recharts-surface {
        width: 100%;
        height: 100%;
        display: block;
      }

      .v2-mini-chart rect {
        fill: #0f1724;
        stroke: #1d293a;
      }

      .v2-mini-chart text {
        fill: #8b949e;
        font-size: 9px;
        font-weight: 800;
      }

      .v2-mini-chart .v2-mini-grid {
        stroke: #253041;
        stroke-width: 1;
        stroke-dasharray: 3 5;
        opacity: 0.68;
      }

      .v2-mini-chart .v2-mini-current {
        stroke: #79c0ff;
        stroke-width: 1.2;
        stroke-dasharray: 4 5;
        opacity: 0.72;
      }

      .v2-mini-chart .v2-mini-current-label {
        fill: #79c0ff;
      }

      .v2-mini-chart.is-wide {
        min-height: 420px;
      }

      .v2-mini-chart.is-wide text {
        font-size: 11px;
      }

      .v2-trajectory-legend {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-wrap: wrap;
        gap: 9px 16px;
        padding: 0 12px 14px;
      }

      .v2-trajectory-legend-item {
        min-width: 0;
        max-width: 210px;
        display: grid;
        grid-template-columns: 10px minmax(0, 1fr) auto;
        align-items: center;
        gap: 6px;
        color: #c9d7e6;
        font-size: 12px;
        font-weight: 850;
        line-height: 1;
      }

      .v2-trajectory-legend-item i {
        width: 10px;
        height: 10px;
        flex: 0 0 auto;
        border-radius: 2px;
        background: var(--team-color, #58a6ff);
        box-shadow: 0 0 0 1px rgba(240, 246, 252, 0.12), 0 0 0 3px color-mix(in srgb, var(--team-color, #58a6ff) 14%, transparent);
      }

      .v2-trajectory-legend-item b {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-weight: 850;
      }

      .v2-trajectory-legend-item em {
        color: #79c0ff;
        font-style: normal;
        font-weight: 950;
      }

      .v2-trajectory-summary {
        display: grid;
        gap: 6px;
      }

      .v2-trajectory-summary.is-wide {
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      }

      .v2-trajectory-row {
        display: grid;
        grid-template-columns: 10px minmax(0, 1fr) auto auto;
        align-items: center;
        gap: 7px;
        background: #111824;
        border: 1px solid #253041;
        border-radius: 7px;
        padding: 7px 8px;
      }

      .v2-trajectory-team {
        min-width: 0;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        color: #e6edf3;
        font-size: 11px;
        font-weight: 800;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .v2-trajectory-row strong {
        color: #f0f6fc;
        font-size: 12px;
        white-space: nowrap;
      }

      .v2-trajectory-row em {
        min-width: 36px;
        justify-self: end;
        border: 1px solid #30363d;
        border-radius: 999px;
        padding: 2px 6px;
        color: #8b949e;
        font-size: 10px;
        font-style: normal;
        font-weight: 900;
        text-align: center;
      }

      .v2-trajectory-row.good em {
        color: #56d364;
        border-color: #1f6f3a;
        background: #0d2618;
      }

      .v2-trajectory-row.bad em {
        color: #ff7b72;
        border-color: #7d2827;
        background: #2a1114;
      }

      .v2-pcmp {
        display: grid;
        gap: 8px;
      }

      .v2-pcmp-head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 10px;
      }

      .v2-pcmp-head span {
        color: #79c0ff;
        font-size: 10px;
        font-weight: 900;
        text-transform: uppercase;
      }

      .v2-pcmp-head strong {
        color: #8b949e;
        font-size: 11px;
        font-weight: 650;
        text-align: right;
      }

      .v2-pcmp-scroll {
        max-width: 100%;
        overflow-x: auto;
        scrollbar-width: thin;
      }

      .v2-pcmp-grid {
        display: grid;
        min-width: 100%;
        border: 1px solid #253041;
        border-radius: 8px;
        overflow: hidden;
        background: #0b1018;
      }

      .v2-pcmp-corner,
      .v2-pcmp-team-head,
      .v2-pcmp-metric,
      .v2-pcmp-cell {
        min-height: 34px;
        border-right: 1px solid #21262d;
        border-bottom: 1px solid #21262d;
        padding: 7px 8px;
      }

      .v2-pcmp-team-head,
      .v2-pcmp-cell {
        min-width: 92px;
      }

      .v2-pcmp-corner,
      .v2-pcmp-team-head {
        background: #111824;
        color: #8b949e;
        font-size: 10px;
        font-weight: 900;
        text-transform: uppercase;
      }

      .v2-pcmp-team-head {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        min-width: 0;
      }

      .v2-pcmp-team-head b {
        min-width: 0;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .v2-pcmp-metric {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
        background: #0d1117;
        border-left: 0;
        color: #b7c7dc;
        cursor: pointer;
        font-family: inherit;
        font-size: 11px;
        font-weight: 850;
        text-align: left;
      }

      .v2-pcmp-metric span {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .v2-pcmp-metric i {
        flex: 0 0 auto;
        border: 1px solid #30363d;
        border-radius: 999px;
        padding: 1px 5px;
        color: #79c0ff;
        font-size: 9px;
        font-style: normal;
        font-weight: 900;
        text-transform: uppercase;
      }

      .v2-pcmp-metric:hover,
      .v2-pcmp-metric:focus-visible,
      .v2-pcmp-metric.is-active,
      .v2-pcmp-metric.is-sort {
        background: #10213a;
        color: #f0f6fc;
        box-shadow: inset 3px 0 0 #58a6ff;
      }

      .v2-pcmp-cell {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
        gap: 6px;
        background: color-mix(in srgb, var(--team-color, #58a6ff) 7%, #0d1117);
      }

      .v2-pcmp-cell strong {
        min-width: 0;
        color: #f0f6fc;
        font-size: 11px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .v2-pcmp-cell span {
        border: 1px solid color-mix(in srgb, var(--team-color, #58a6ff) 48%, #30363d);
        border-radius: 999px;
        color: #79c0ff;
        font-size: 10px;
        font-weight: 900;
        padding: 1px 5px;
      }

      .v2-pcmp.is-modal .v2-pcmp-grid {
        min-width: max-content;
      }

      .v2-pcmp.is-modal .v2-pcmp-corner,
      .v2-pcmp.is-modal .v2-pcmp-team-head,
      .v2-pcmp.is-modal .v2-pcmp-metric,
      .v2-pcmp.is-modal .v2-pcmp-cell {
        min-height: 42px;
        padding: 9px 10px;
      }

      .v2-pcmp.is-modal .v2-pcmp-team-head,
      .v2-pcmp.is-modal .v2-pcmp-cell {
        min-width: 132px;
      }

      .v2-pcmp.is-modal .v2-pcmp-metric,
      .v2-pcmp.is-modal .v2-pcmp-cell strong {
        font-size: 12px;
      }

      .v2-pcmp-bars {
        border: 1px solid #253041;
        border-radius: 8px;
        background: linear-gradient(180deg, #0b1018, #090d14);
        overflow: hidden;
      }

      .v2-pcmp-table {
        width: 100%;
        min-width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        overflow: hidden;
        background: #0b1018;
        border: 1px solid #253041;
        border-radius: 8px;
      }

      .v2-pcmp-table th,
      .v2-pcmp-table td {
        border-right: 1px solid #21262d;
        border-bottom: 1px solid #21262d;
        padding: 0;
        text-align: left;
        vertical-align: middle;
      }

      .v2-pcmp-table thead th {
        position: sticky;
        top: 0;
        z-index: 2;
        background: #111824;
        height: 48px;
        padding: 0 10px;
        color: #8b949e;
        font-size: 10px;
        font-weight: 900;
        text-transform: uppercase;
      }

      .v2-pcmp-table thead th:first-child,
      .v2-pcmp-table tbody th {
        position: sticky;
        left: 0;
        z-index: 3;
      }

      .v2-pcmp-table tbody th {
        background: #0d1117;
      }

      .v2-pcmp-table tbody td {
        min-width: 132px;
        background: var(--rank-bg, #0d1117);
      }

      .v2-pcmp-table thead th:first-child,
      .v2-pcmp-table tbody th {
        width: 146px;
        min-width: 146px;
        max-width: 146px;
      }

      .v2-pcmp-table tr.is-active .v2-pcmp-metric,
      .v2-pcmp-table tr.is-sort .v2-pcmp-metric {
        background: #10213a;
        color: #f0f6fc;
        box-shadow: inset 3px 0 0 #58a6ff;
      }

      .v2-pcmp-table .v2-pcmp-team-head {
        min-height: 48px;
        min-width: 0;
        width: 100%;
        border: 0;
        padding: 0;
        background: transparent;
      }

      .v2-pcmp-table .v2-pcmp-metric {
        width: 100%;
        height: 46px;
        min-height: 46px;
        border: 0;
        padding: 0 10px;
      }

      .v2-pcmp-table .v2-pcmp-cell {
        min-height: 46px;
        min-width: 0;
        width: 100%;
        height: 46px;
        border: 0;
        padding: 0 12px;
        background: transparent;
      }

      .v2-pcmp-table .v2-pcmp-cell strong {
        color: #f0f6fc;
      }

      .v2-pcmp-cell em {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 3px;
        min-width: 34px;
        border: 1px solid var(--rank-border, #30363d);
        border-radius: 999px;
        color: var(--rank-color, #79c0ff);
        font-size: 10px;
        font-style: normal;
        font-weight: 900;
        padding: 1px 5px;
      }

      .v2-pcmp-cell em b {
        font-size: 12px;
        line-height: 1;
      }

      .v2-pcmp.is-modal .v2-pcmp-table thead th:first-child,
      .v2-pcmp.is-modal .v2-pcmp-table tbody th {
        width: 156px;
        min-width: 156px;
        max-width: 156px;
      }

      .v2-pcmp.is-modal .v2-pcmp-table tbody td {
        min-width: 150px;
      }

      .v2-pcmp.is-modal .v2-pcmp-table .v2-pcmp-cell {
        height: 48px;
        min-height: 48px;
        padding: 0 12px;
      }

      .v2-pcmp.is-modal .v2-pcmp-table .v2-pcmp-metric {
        height: 48px;
        min-height: 48px;
      }

      .v2-recharts-tooltip {
        display: grid;
        gap: 6px;
        min-width: 150px;
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 8px;
        box-shadow: 0 16px 42px rgba(0, 0, 0, 0.34);
        padding: 9px 10px;
        color: #e6edf3;
      }

      .v2-recharts-tooltip > strong {
        color: #8b949e;
        font-size: 11px;
      }

      .v2-recharts-tooltip-title {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: #b7c7dc !important;
      }

      .v2-recharts-tooltip span {
        display: grid;
        grid-template-columns: 8px minmax(0, 1fr) auto;
        align-items: center;
        gap: 7px;
      }

      .v2-recharts-tooltip i {
        width: 8px;
        height: 8px;
        border-radius: 3px;
        background: var(--team-color, #58a6ff);
      }

      .v2-recharts-tooltip b,
      .v2-recharts-tooltip em {
        font-size: 12px;
        font-style: normal;
      }

      .v2-recharts-tooltip b {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .v2-recharts-tooltip em {
        color: #79c0ff;
        font-weight: 900;
      }

      .v2-analysis-backdrop {
        position: fixed;
        inset: 0;
        z-index: 70;
        padding: 16px;
        background: rgba(0, 0, 0, 0.68);
        backdrop-filter: blur(3px);
        animation: v2-guide-fade 180ms ease-out both;
      }

      .v2-analysis-dialog {
        position: absolute;
        display: grid;
        grid-template-rows: auto 1fr;
        overflow: hidden;
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 10px;
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
        animation: v2-guide-pop 240ms cubic-bezier(.2, .9, .2, 1) both;
      }

      .v2-analysis-dialog.is-wide {
        min-width: 0;
      }

      .v2-analysis-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 14px 16px;
        border-bottom: 1px solid #253041;
        cursor: grab;
        touch-action: none;
        user-select: none;
      }

      .v2-analysis-header:active {
        cursor: grabbing;
      }

      .v2-analysis-header button {
        cursor: pointer;
      }

      .v2-analysis-header h2 {
        margin: 0;
        color: #f0f6fc;
        font-size: 16px;
        line-height: 1.2;
      }

      .v2-analysis-header span {
        display: block;
        margin-top: 4px;
        color: #8b949e;
        font-size: 12px;
      }

      .v2-analysis-body {
        min-height: 0;
        overflow: auto;
        padding: 14px 16px 22px;
        display: grid;
        gap: 13px;
        scrollbar-width: thin;
      }

      .v2-analysis-resize {
        position: absolute;
        right: 7px;
        bottom: 7px;
        width: 26px;
        height: 26px;
        border: 0;
        border-radius: 7px;
        background: transparent;
        cursor: nwse-resize;
        opacity: 0.82;
      }

      .v2-analysis-resize::before {
        content: "";
        position: absolute;
        right: 6px;
        bottom: 6px;
        width: 12px;
        height: 12px;
        border-right: 2px solid #79c0ff;
        border-bottom: 2px solid #79c0ff;
        border-radius: 1px;
      }

      .v2-analysis-resize:hover,
      .v2-analysis-resize:focus-visible {
        background: rgba(88, 166, 255, 0.12);
        outline: none;
        opacity: 1;
      }

      .v2-modal-toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
      }

      .v2-modal-toolbar .v2-traj-mode {
        min-width: 190px;
      }

      .v2-modal-metric-select {
        flex: 0 0 auto;
        min-height: 36px;
        padding: 4px 8px;
        border: 1px solid #253041;
        border-radius: 8px;
        background: #111824;
        color: #b7c7dc !important;
        font-weight: 850;
      }

      .v2-modal-metric-select select {
        outline: none;
      }

      .v2-modal-metric-select select:focus-visible {
        border-color: #58a6ff !important;
        box-shadow: 0 0 0 2px rgba(88, 166, 255, 0.18);
      }

      .v2-modal-team-chip {
        max-width: 180px;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #111824;
        border: 1px solid #253041;
        border-radius: 7px;
        color: #f0f6fc;
        padding: 5px 8px;
        font-size: 12px;
        font-weight: 850;
      }

      .v2-modal-team-chip b {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .v2-weight-pill,
      .v2-weight-help,
      .v2-race-stage,
      .v2-sidebar-resizer,
      .v2-selection-sidebar,
      .v2-sidebar-head button,
      .v2-side-panel,
      .v2-side-toggle,
      .v2-side-open-button,
      .v2-selected-chip,
      .v2-compare-row,
      .v2-traj-mode button,
      .v2-trajectory-row,
      .v2-pcmp-metric,
      .v2-pcmp-cell,
      .v2-analysis-dialog,
      .v2-modal-team-chip,
      .v2-guide-tab,
      .v2-guide-weight-tile,
      .v2-selected-weight-panel,
      .v2-component-chip,
      .v2-tag-explained,
      .v2-guide-card,
      .v2-guide-question,
      .v2-close-button {
        transition:
          transform 160ms ease,
          border-color 160ms ease,
          background 160ms ease,
          color 160ms ease,
          box-shadow 160ms ease,
          opacity 160ms ease;
      }

      .v2-weight-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #161b22;
        border: 1px solid #30363d;
        color: #8b949e;
        border-radius: 6px;
        padding: 3px 9px;
        font-size: 11px;
        cursor: pointer;
        font-family: inherit;
        white-space: nowrap;
      }

      .v2-weight-pill b {
        color: #79c0ff;
      }

      .v2-weight-pill:hover,
      .v2-weight-pill:focus-visible {
        transform: translateY(-1px);
        border-color: var(--weight-color);
        color: #e6edf3;
        box-shadow: 0 0 0 3px color-mix(in srgb, var(--weight-color) 22%, transparent);
      }

      .v2-weight-pill.is-active {
        background: color-mix(in srgb, var(--weight-color) 18%, #161b22);
        border-color: var(--weight-color);
        color: #f0f6fc;
        animation: v2-active-glow 2.6s ease-in-out infinite;
      }

      .v2-weight-dot {
        width: 9px;
        height: 9px;
        border-radius: 3px;
        background: var(--weight-color, #58a6ff);
        box-shadow: 0 0 12px color-mix(in srgb, var(--weight-color, #58a6ff) 62%, transparent);
        flex: 0 0 auto;
      }

      .v2-weight-help {
        width: 28px;
        height: 28px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: #10213a;
        border: 1px solid #1f6feb;
        color: #79c0ff;
        border-radius: 6px;
        cursor: pointer;
        font-family: inherit;
        flex-shrink: 0;
        margin-left: 2px;
        animation: v2-help-pulse 2.2s ease-in-out infinite;
      }

      .v2-weight-help:hover,
      .v2-weight-help:focus-visible,
      .v2-sidebar-head button:hover,
      .v2-sidebar-head button:focus-visible,
      .v2-selected-chip:hover,
      .v2-selected-chip:focus-visible,
      .v2-close-button:hover,
      .v2-close-button:focus-visible {
        transform: translateY(-1px) scale(1.04);
        border-color: #79c0ff;
        color: #f0f6fc;
        box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.22);
      }

      .v2-guide-backdrop {
        animation: v2-guide-fade 180ms ease-out both;
        backdrop-filter: blur(3px);
      }

      .v2-guide-dialog {
        animation: v2-guide-pop 260ms cubic-bezier(.2, .9, .2, 1) both;
      }

      .v2-guide-tab:hover,
      .v2-guide-tab:focus-visible {
        transform: translateX(3px);
        border-color: #1f6feb !important;
        color: #f0f6fc !important;
      }

      .v2-guide-tab.is-active {
        box-shadow: inset 3px 0 0 #58a6ff;
      }

      .v2-donut-button {
        justify-self: center;
        width: 210px;
        aspect-ratio: 1 / 1;
        border: 0;
        border-radius: 50%;
        padding: 34px;
        position: relative;
        cursor: pointer;
        color: inherit;
        font-family: inherit;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.05), 0 16px 40px rgba(0,0,0,0.22);
        animation: v2-donut-in 650ms cubic-bezier(.2, .85, .2, 1) both;
        transition: transform 220ms ease, filter 220ms ease, box-shadow 220ms ease;
      }

      .v2-donut-button::before {
        content: "";
        position: absolute;
        inset: -7px;
        border-radius: inherit;
        border: 1px solid var(--selected-color);
        opacity: 0.28;
        animation: v2-ring-pulse 2.8s ease-in-out infinite;
      }

      .v2-donut-button:hover,
      .v2-donut-button:focus-visible {
        transform: rotate(2deg) scale(1.04);
        filter: saturate(1.12);
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08), 0 20px 52px rgba(0,0,0,0.32);
      }

      .v2-donut-core {
        width: 100%;
        height: 100%;
        border-radius: 50%;
        background: #0d1117;
        border: 2px solid #253041;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        position: relative;
        z-index: 1;
      }

      .v2-donut-core strong {
        color: #f0f6fc;
        font-size: 24px;
        line-height: 1;
      }

      .v2-donut-core span {
        margin-top: 6px;
        color: var(--selected-color);
        font-size: 10px;
        font-weight: 900;
        text-transform: uppercase;
      }

      .v2-guide-weight-tile {
        background: #111824;
        border: 1px solid #253041;
        border-radius: 8px;
        padding: 10px 12px;
        display: grid;
        grid-template-columns: 12px 1fr auto;
        align-items: center;
        gap: 9px;
        cursor: pointer;
        font-family: inherit;
        text-align: left;
      }

      .v2-guide-weight-tile:hover,
      .v2-guide-weight-tile:focus-visible {
        transform: translateY(-2px);
        border-color: var(--weight-color);
        box-shadow: 0 10px 30px color-mix(in srgb, var(--weight-color) 16%, transparent);
      }

      .v2-guide-weight-tile.is-active {
        border-color: var(--weight-color);
        background: color-mix(in srgb, var(--weight-color) 14%, #111824);
      }

      .v2-selected-weight-panel {
        border: 1px solid color-mix(in srgb, var(--selected-color) 62%, #253041);
        border-radius: 8px;
        background: linear-gradient(135deg, color-mix(in srgb, var(--selected-color) 16%, #111824), #111824 72%);
        padding: 13px 15px;
        text-align: left;
        font-family: inherit;
        color: #dbe7f3;
        animation: v2-detail-slide 260ms ease-out both;
      }

      .v2-component-focus {
        border: 1px solid #253041;
        border-left: 3px solid var(--selected-color);
        border-radius: 8px;
        background: #111824;
        padding: 10px 12px;
        text-align: left;
        font-family: inherit;
        color: #dbe7f3;
        animation: v2-detail-slide 220ms ease-out both;
      }

      .v2-selected-weight-panel {
        cursor: pointer;
      }

      .v2-selected-weight-panel:hover,
      .v2-selected-weight-panel:focus-visible {
        transform: translateY(-2px);
        box-shadow: 0 14px 36px color-mix(in srgb, var(--selected-color) 18%, transparent);
      }

      .v2-selected-weight-panel strong,
      .v2-component-focus strong {
        display: block;
        color: #f0f6fc;
        font-size: 16px;
        margin: 3px 0 5px;
      }

      .v2-selected-weight-panel span,
      .v2-component-focus span {
        display: block;
      }

      .v2-selected-weight-kicker,
      .v2-component-focus > span:first-child {
        color: var(--selected-color);
        font-size: 11px;
        font-weight: 900;
        text-transform: uppercase;
      }

      .v2-component-focus p {
        margin: 0;
        color: #b7c7dc;
        font-size: 12px;
        line-height: 1.45;
      }

      .v2-component-picker {
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 7px;
      }

      .v2-component-chip {
        display: grid;
        grid-template-columns: 12px minmax(0, 1fr) auto;
        align-items: center;
        gap: 8px;
        background: #111824;
        border: 1px solid #253041;
        border-radius: 7px;
        min-height: 38px;
        padding: 8px 11px;
        color: #dbe7f3;
        text-align: left;
        font-family: inherit;
        cursor: pointer;
      }

      .v2-component-chip span:not(.v2-weight-dot) {
        min-width: 0;
        white-space: nowrap;
        font-size: 11.5px;
        font-weight: 750;
      }

      .v2-component-chip b {
        color: #79c0ff;
        font-size: 12px;
      }

      .v2-component-chip:hover,
      .v2-component-chip:focus-visible {
        transform: translateY(-1px);
        border-color: var(--weight-color);
        background: color-mix(in srgb, var(--weight-color) 10%, #111824);
        box-shadow: 0 8px 22px color-mix(in srgb, var(--weight-color) 12%, transparent);
      }

      .v2-component-chip.is-active {
        border-color: var(--weight-color);
        background: color-mix(in srgb, var(--weight-color) 16%, #111824);
        box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--weight-color) 24%, transparent);
      }

      .v2-tags-panel {
        border: 1px solid color-mix(in srgb, var(--selected-color) 45%, #253041);
        border-radius: 8px;
        background: #111824;
        padding: 12px;
        animation: v2-detail-slide 220ms ease-out both;
      }

      .v2-tags-panel-head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 5px;
      }

      .v2-tags-panel-head span {
        color: var(--selected-color);
        font-size: 11px;
        font-weight: 900;
        text-transform: uppercase;
      }

      .v2-tags-panel-head strong {
        color: #f0f6fc;
        font-size: 13px;
      }

      .v2-tags-summary {
        margin: 0 0 10px;
        color: #b7c7dc;
        font-size: 12px;
        line-height: 1.4;
      }

      .v2-tags-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: 8px;
      }

      .v2-tag-explained {
        border: 1px solid #30363d;
        border-left: 3px solid var(--selected-color);
        border-radius: 7px;
        background: #0d1117;
        padding: 8px 9px;
        min-height: 62px;
      }

      .v2-tag-explained:hover {
        transform: translateY(-1px);
        border-color: color-mix(in srgb, var(--selected-color) 55%, #30363d);
        box-shadow: 0 8px 22px color-mix(in srgb, var(--selected-color) 12%, transparent);
      }

      .v2-tag-explained b {
        display: block;
        color: #f0f6fc;
        font-size: 12px;
        margin-bottom: 3px;
      }

      .v2-tag-explained span {
        display: block;
        color: #8b949e;
        font-size: 11px;
        line-height: 1.35;
      }

      .v2-guide-card,
      .v2-guide-question {
        background: #111824;
        border: 1px solid #253041;
        border-radius: 8px;
        padding: 14px;
        text-align: left;
        font-family: inherit;
        cursor: pointer;
      }

      .v2-guide-card {
        padding: 12px 14px;
      }

      .v2-guide-card:hover,
      .v2-guide-card:focus-visible,
      .v2-guide-question:hover,
      .v2-guide-question:focus-visible {
        transform: translateY(-2px);
        border-color: var(--weight-color, #58a6ff);
        box-shadow: 0 12px 34px rgba(0, 0, 0, 0.22);
      }

      .v2-guide-question {
        display: grid;
        gap: 0;
        padding: 0;
        overflow: hidden;
      }

      .v2-guide-question > span {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 13px 14px;
      }

      .v2-guide-question strong {
        color: #f0f6fc;
        font-size: 14px;
      }

      .v2-guide-question i {
        width: 22px;
        height: 22px;
        border: 1px solid #30363d;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: #79c0ff;
        font-style: normal;
        flex: 0 0 auto;
        transition: transform 180ms ease, border-color 180ms ease;
      }

      .v2-guide-question p {
        max-height: 0;
        opacity: 0;
        overflow: hidden;
        margin: 0;
        padding: 0 14px;
        color: #b7c7dc;
        font-size: 13px;
        line-height: 1.5;
        transition: max-height 220ms ease, opacity 180ms ease, padding 220ms ease;
      }

      .v2-guide-question.is-open {
        border-color: #58a6ff;
        background: #10213a;
      }

      .v2-guide-question.is-open i {
        transform: rotate(180deg);
        border-color: #58a6ff;
      }

      .v2-guide-question.is-open p {
        max-height: 140px;
        opacity: 1;
        padding: 0 14px 14px;
      }

      .v2-team-score-card-shell {
        max-height: calc(100vh - 20px);
      }

      .v2-team-score-card {
        max-height: inherit;
      }

      .v2-team-score-head,
      .v2-team-score-tabs,
      .v2-team-score-legend {
        min-width: 0;
      }

      .v2-team-score-name,
      .v2-team-score-meta {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      @media (min-width: 1920px) {
        .v2-main {
          max-width: 1840px;
        }

        .v2-main.is-race {
          max-width: none;
        }

        .v2-race-workspace {
          grid-template-columns: minmax(720px, 1fr) 10px min(32vw, var(--v2-sidebar-width, 460px));
        }
      }

      @media (max-width: 980px) {
        .v2-dashboard-header {
          align-items: flex-start;
        }

        .v2-primary-tabs {
          order: 1;
          flex: 1 1 100%;
          padding-bottom: 2px;
        }

        .v2-weight-strip {
          order: 2;
          justify-content: flex-start;
          min-width: 0;
          overflow-x: auto;
          flex-wrap: nowrap;
          padding-bottom: 2px;
        }

        .v2-weight-pill,
        .v2-weight-help {
          flex: 0 0 auto;
        }

        .v2-game-slider.is-compact {
          order: 3;
          flex-basis: 100% !important;
          max-width: none !important;
          justify-content: flex-start;
        }

        .v2-filter-control {
          flex: 1 1 170px;
        }

        .v2-filter-control select,
        .v2-metric-select {
          width: 100%;
        }

        .v2-predictive-shell {
          grid-template-columns: minmax(0, 1fr) !important;
          justify-content: stretch !important;
        }

        .v2-predictive-track {
          position: static !important;
        }
      }

      @media (max-width: 1180px) {
        .v2-teams-grid {
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        }

        .v2-groups-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .v2-race-workspace {
          grid-template-columns: minmax(0, 1fr);
        }

        .v2-sidebar-resizer {
          display: none;
        }

        .v2-selection-sidebar {
          position: static;
          min-height: 0;
          max-height: none;
          order: -1;
        }

        .v2-race-workspace.has-selection .v2-race-stage {
          box-shadow: inset 0 0 0 1px rgba(88, 166, 255, 0.11);
        }
      }

      @media (max-width: 760px) {
        .v2-dashboard-sticky {
          top: 52px;
        }

        .v2-dashboard-header {
          padding: 8px 10px;
          gap: 8px;
        }

        .v2-primary-tabs button {
          padding: 5px 10px !important;
        }

        .v2-filter-bar {
          align-items: stretch;
          gap: 8px;
          padding: 8px 10px;
        }

        .v2-filter-control {
          flex: 1 1 calc(50% - 4px);
          min-width: 150px;
          align-items: stretch;
          flex-direction: column;
          gap: 4px;
        }

        .v2-sort-button {
          flex: 1 1 150px;
          justify-content: center;
        }

        .v2-search-box {
          flex: 1 1 100%;
          max-width: none;
        }

        .v2-filter-fill {
          display: none;
        }

        .v2-api-status {
          flex: 1 1 100%;
        }

        .v2-progress-shell {
          padding: 5px 6px;
        }

        .v2-fixed-pager {
          justify-content: flex-start !important;
          padding: 8px 10px !important;
          gap: 6px !important;
        }

        .v2-fixed-pager-count {
          display: none;
        }

        .v2-progress-legend {
          flex-wrap: nowrap !important;
          gap: 10px !important;
          padding: 2px 6px 7px !important;
        }

        .v2-progress-legend span {
          flex: 0 0 auto;
          white-space: nowrap;
        }

        .v2-progress-scroll {
          scroll-snap-type: x proximity;
          padding: 7px 4px 10px !important;
        }

        .v2-progress-group {
          padding-inline: 10px !important;
        }

        .v2-main,
        .v2-main.is-race {
          padding: 14px 10px 20px;
        }

        .v2-analytics-tabs {
          justify-content: flex-start;
          flex-wrap: nowrap;
          overflow-x: auto;
          padding-bottom: 2px;
          scrollbar-width: thin;
        }

        .v2-analytics-tabs button {
          flex: 0 0 auto;
          padding: 5px 10px !important;
        }

        .v2-team-focus-bar {
          align-items: flex-start;
          gap: 7px;
        }

        .v2-team-focus-popover {
          position: fixed;
          left: 10px;
          right: 10px;
          top: 122px;
          width: auto;
          max-width: none;
          max-height: calc(100vh - 144px);
        }

        .v2-team-focus-options {
          grid-template-columns: repeat(2, minmax(0, 1fr));
          max-height: min(360px, calc(100vh - 220px));
        }

        .v2-predictive-stat-grid,
        .v2-predictive-reality-grid {
          grid-template-columns: minmax(0, 1fr) !important;
        }

        .v2-advice-grid {
          grid-template-columns: minmax(0, 1fr);
        }

        .v2-advice-strip {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .v2-teams-summary,
        .v2-players-toolbar {
          align-items: stretch;
          gap: 8px;
        }

        .v2-teams-summary > span:last-child,
        .v2-players-count {
          margin-left: 0;
          flex: 1 1 100%;
        }

        .v2-players-control {
          flex: 1 1 180px;
          align-items: stretch;
          flex-direction: column;
          gap: 4px;
        }

        .v2-players-control select {
          width: 100%;
        }

        .v2-players-segments {
          flex: 1 1 100%;
        }

        .v2-player-card-shell {
          left: 8px !important;
          right: 8px !important;
          top: 64px !important;
          width: auto !important;
          max-width: none !important;
        }

        .v2-roster-player-card,
        .v2-pitch-player-card {
          left: 8px !important;
          right: 8px !important;
          top: 64px !important;
          width: auto !important;
          max-width: none !important;
          max-height: calc(100vh - 80px) !important;
          border-radius: 10px !important;
        }

        .v2-roster-player-stats {
          grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        }

        .v2-pitch-reserves {
          grid-template-columns: minmax(0, 1fr) !important;
          gap: 12px !important;
        }

        .v2-pitch-player-card-stats {
          grid-template-columns: minmax(0, 1fr) !important;
          gap: 5px 10px !important;
        }

        .v2-match-timeline-summary {
          padding: 10px 12px !important;
        }

        .v2-match-event-row {
          grid-template-columns: minmax(0, 1fr) 52px minmax(0, 1fr) !important;
          gap: 4px !important;
        }

        .v2-match-event-card {
          gap: 5px !important;
          padding: 4px 7px !important;
        }

        .v2-team-modal-overlay {
          align-items: stretch !important;
          justify-content: stretch !important;
          padding: 8px !important;
        }

        .v2-team-modal-dialog {
          max-width: none !important;
          max-height: none !important;
          height: calc(100vh - 16px);
          border-radius: 10px !important;
        }

        .v2-team-modal-header {
          padding: 12px 14px !important;
          gap: 10px !important;
        }

        .v2-team-modal-header h2 {
          font-size: 17px !important;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .v2-team-modal-tabs {
          padding: 0 10px !important;
        }

        .v2-team-modal-tabs button {
          padding: 9px 12px !important;
        }

        .v2-team-modal-body {
          padding: 14px 12px !important;
        }

        .v2-team-modal-summary-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        }

        .v2-team-modal-identity {
          align-items: flex-start !important;
        }

        .v2-team-modal-info-grid {
          grid-template-columns: minmax(0, 1fr) !important;
        }

        .v2-team-modal-game-row {
          align-items: flex-start !important;
          flex-wrap: wrap;
        }

        .v2-team-modal-game-row > span:last-child {
          flex: 1 1 100%;
        }

        .v2-team-game-detail {
          padding: 10px !important;
        }

        .v2-team-profile-header {
          align-items: flex-start !important;
          flex-wrap: wrap;
        }

        .v2-race-stage {
          padding: 0;
          margin: 0;
        }

        .v2-race-list-head {
          gap: 8px;
        }

        .v2-race-metric-label {
          width: 100%;
        }

        .v2-race-row {
          grid-template-columns: 24px 22px minmax(0, 1fr) auto;
          grid-template-rows: auto auto;
          row-gap: 5px;
          padding: 8px;
        }

        .v2-race-bar {
          grid-column: 3 / 5;
          height: 9px;
        }

        .v2-race-value {
          width: auto;
          min-width: 54px;
        }

        .v2-snapshot-label {
          width: 100%;
          font-size: 12px;
        }

        .v2-snapshot-match {
          width: 100%;
        }

        .v2-selection-sidebar {
          padding: 10px;
          gap: 10px;
        }

        .v2-team-score-card-shell {
          left: 8px !important;
          right: 8px !important;
          top: 64px !important;
          width: auto !important;
          height: auto !important;
          max-width: none !important;
          max-height: calc(100vh - 78px);
        }

        .v2-team-score-card {
          max-height: calc(100vh - 78px);
        }

        .v2-team-score-head {
          cursor: default !important;
          touch-action: auto !important;
          flex-wrap: wrap;
          padding: 9px 10px !important;
        }

        .v2-team-score-name {
          flex: 1 1 160px;
        }

        .v2-team-score-meta {
          order: 4;
          flex: 1 1 100%;
        }

        .v2-team-score-tabs {
          padding: 8px !important;
        }

        .v2-team-score-body {
          max-height: calc(100vh - 240px) !important;
          padding: 8px 10px 10px !important;
        }

        .v2-team-score-legend {
          gap: 7px 10px !important;
          padding: 7px 10px !important;
        }

        .v2-team-score-legend span:last-child {
          display: none !important;
        }

        .v2-team-score-resize {
          display: none !important;
        }

        .v2-game-slider.is-compact {
          gap: 7px;
        }

        .v2-game-speed {
          display: none;
        }

        .v2-analysis-backdrop {
          padding: 8px;
        }

        .v2-analysis-dialog,
        .v2-analysis-dialog.is-wide {
          max-height: none;
        }

        .v2-modal-toolbar {
          align-items: stretch;
          flex-direction: column;
        }

        .v2-mini-chart.is-wide {
          min-height: 260px;
        }

        .v2-weight-strip {
          min-width: 0;
          justify-content: flex-start !important;
        }

        .v2-weight-strip-label {
          display: none;
        }

        .v2-guide-dialog > div {
          grid-template-columns: 1fr !important;
        }

        .v2-guide-dialog aside {
          display: flex;
          gap: 8px;
          overflow-x: auto;
          border-right: 0 !important;
          border-bottom: 1px solid #253041;
        }

        .v2-guide-tab {
          min-width: max-content;
        }

        .v2-component-picker {
          grid-template-columns: repeat(auto-fit, minmax(172px, 1fr));
        }
      }

      @media (max-width: 520px) {
        .v2-filter-control,
        .v2-sort-button {
          flex-basis: 100%;
        }

        .v2-dashboard-header {
          padding-inline: 8px;
        }

        .v2-game-count {
          min-width: 66px;
        }

        .v2-game-range {
          min-width: 80px !important;
        }

        .v2-race-row {
          grid-template-columns: 22px 20px minmax(0, 1fr) auto;
          column-gap: 6px;
        }

        .v2-race-team {
          font-size: 12px;
        }

        .v2-race-value {
          font-size: 11px;
          min-width: 46px;
        }

        .v2-team-focus-options {
          grid-template-columns: minmax(0, 1fr);
        }

        .v2-advice-strip {
          grid-template-columns: minmax(0, 1fr);
        }

        .v2-teams-grid {
          grid-template-columns: minmax(0, 1fr);
          gap: 10px;
        }

        .v2-players-table {
          min-width: 820px;
        }

        .v2-team-modal-summary-grid {
          grid-template-columns: minmax(0, 1fr) !important;
        }

        .v2-team-profile-compact-metrics {
          grid-template-columns: minmax(0, 1fr) !important;
          gap: 6px !important;
        }

        .v2-roster-grid {
          grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)) !important;
          gap: 8px !important;
        }

        .v2-roster-player-stats {
          grid-template-columns: minmax(0, 1fr) !important;
        }

        .v2-match-event-row {
          grid-template-columns: minmax(0, 1fr) 46px minmax(0, 1fr) !important;
        }

        .v2-match-event-card {
          font-size: 11px !important;
        }

        .v2-groups-grid {
          grid-template-columns: minmax(0, 1fr);
          gap: 12px;
        }

        .v2-groups-legend span:last-child {
          margin-left: 0 !important;
          flex: 1 1 100%;
        }

        .v2-bracket-board {
          margin: 0;
        }

        .v2-bracket-column {
          min-width: 148px;
        }

        .v2-bracket-center {
          min-width: 210px;
        }
      }

      @keyframes v2-guide-fade {
        from { opacity: 0; }
        to { opacity: 1; }
      }

      @keyframes v2-guide-pop {
        from { opacity: 0; transform: translateY(10px) scale(.985); }
        to { opacity: 1; transform: translateY(0) scale(1); }
      }

      @keyframes v2-donut-in {
        from { opacity: 0; transform: rotate(-16deg) scale(.92); }
        to { opacity: 1; transform: rotate(0) scale(1); }
      }

      @keyframes v2-detail-slide {
        from { opacity: 0; transform: translateY(6px); }
        to { opacity: 1; transform: translateY(0); }
      }

      @keyframes v2-ring-pulse {
        0%, 100% { opacity: .22; transform: scale(.99); }
        50% { opacity: .48; transform: scale(1.03); }
      }

      @keyframes v2-help-pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(88, 166, 255, .24); }
        50% { box-shadow: 0 0 0 5px rgba(88, 166, 255, 0); }
      }

      @keyframes v2-active-glow {
        0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--weight-color) 0%, transparent); }
        50% { box-shadow: 0 0 0 3px color-mix(in srgb, var(--weight-color) 20%, transparent); }
      }
    `}</style>
  );
}

function tabStyle(active: boolean): React.CSSProperties {
  return {
    background: active ? "#1a2233" : "#161b22",
    border: `1px solid ${active ? "#58a6ff" : "#30363d"}`,
    color: active ? "#e6edf3" : "#8b949e",
    borderRadius: 6,
    padding: "5px 12px",
    fontSize: 13,
    cursor: "pointer",
    fontFamily: "inherit",
  };
}

function FilterSelect({ label, value, onChange, options, suggested }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][]; suggested?: Map<string, { team: string; color: string }[]> }) {
  const hasSug = suggested && suggested.size > 0;
  return (
    <label className="v2-filter-control">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ borderColor: hasSug ? "#3fb950" : "#30363d" }}
      >
        <option value="">Todas</option>
        {options.map(([v, l]) => {
          const sug = suggested?.get(v);
          const teamLabel = sug ? (sug.length === 1 ? ` · ${sug[0].team}` : ` · ${sug.length} seleções`) : "";
          const color = sug && sug.length === 1 ? sug[0].color : undefined;
          return (
            <option key={v} value={v} style={color ? { color, fontWeight: 800 } : undefined}>
              {sug ? "★ " : ""}{l}{teamLabel}
            </option>
          );
        })}
      </select>
    </label>
  );
}

function MetricSelect({
  value,
  onChange,
  label = "Métrica",
  variant = "filters",
}: {
  value: string;
  onChange: (v: string) => void;
  label?: string;
  variant?: "filters" | "modal";
}) {
  const isModal = variant === "modal";
  return (
    <label
      className={isModal ? "v2-modal-metric-select" : "v2-filter-control v2-metric-control"}
    >
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={isModal ? undefined : "v2-metric-select"}
        style={isModal ? { background: "#161b22", color: "#e6edf3", border: "1px solid #30363d", borderRadius: 6, padding: "6px 10px", fontSize: 12, fontFamily: "inherit", minWidth: 190 } : undefined}
      >
        {METRIC_OPTIONS.map((g) => (
          <optgroup key={g.group} label={g.group}>
            {g.items.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}
