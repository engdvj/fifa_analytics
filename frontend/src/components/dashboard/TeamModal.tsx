"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import useSWR from "swr";
import { analytics, Match, LineupPlayer, TeamStat } from "@/lib/api";
import { TeamSummary, getKit } from "@/lib/teamUtils";
import Flag from "@/components/ui/Flag";
import TeamRoster from "./TeamRoster";
import PitchView from "./PitchView";
import MatchTimeline from "./MatchTimeline";
import { DefinitionBubble } from "@/components/DefinitionLink";
import { styleDescription, styleName } from "@/lib/styleMeta";

// métrica FIFA (chave do data hub) → id de conceito. Só inclui as que têm
// definição na Central; o resto fica sem bolinha.
const FIFA_DEF_ID: Record<string, string> = {
  Possession: "posse",
  PitchControl: "pitch_control",
  FinalThirdPitchControl: "final_third_control",
  XG: "xg",
  Threat: "threat",
  Corners: "escanteios",
  CompletedBallProgressions: "progressoes_bola",
  Sprints: "sprints",
  GoalkeeperSaves: "save_pct",
  AttemptAtGoalOnTarget: "chutes_no_alvo",
  ForcedTurnovers: "turnovers_forcados",
};
function fifaDefId(metric: string): string | null {
  return FIFA_DEF_ID[metric] ?? null;
}

const TABS = ["resumo", "jogos", "elenco", "estilo"] as const;
type Tab = typeof TABS[number];

const TAB_LABEL: Record<Tab, string> = {
  resumo: "Resumo",
  jogos: "Jogos",
  elenco: "Elenco",
  estilo: "Estilo",
};

// 6 arquétipos de estilo (do `estilo_jogo` no snapshot) — rótulo + descrição +
// id da definição ESPECÍFICA daquele estilo (não a genérica "estilo_jogo").
const ARCHETYPES: Record<string, { emoji: string; desc: string; def: string }> = {
  "Posse": { emoji: "🎯", desc: styleDescription("Posse"), def: "estilo_posse" },
  "Pressão Alta": { emoji: "🔥", desc: styleDescription("Pressão Alta"), def: "estilo_pressao_alta" },
  "Contra-ataque": { emoji: "⚡", desc: styleDescription("Contra-ataque"), def: "estilo_contra_ataque" },
  "Retranca": { emoji: "🧱", desc: styleDescription("Retranca"), def: "estilo_retranca" },
  "Jogo Direto": { emoji: "🚀", desc: styleDescription("Jogo Direto"), def: "estilo_jogo_direto" },
  "Bola Parada": { emoji: "⛳", desc: styleDescription("Bola Parada"), def: "estilo_bola_parada" },
};
// 4 eixos bipolares do snapshot (z-score 0-100, 50 = média do torneio).
// `hint` explica o eixo em uma linha; low/high são os polos.
const STYLE_AXES: { key: string; label: string; low: string; high: string; hint: string }[] = [
  { key: "estilo_posse", label: "Construção", low: "Jogo direto", high: "Posse apoiada", hint: "Como leva a bola ao ataque: chutão/lançamento vs. trocar passes e progredir com posse." },
  { key: "estilo_pressao", label: "Linha de pressão", low: "Bloco recuado", high: "Pressão alta", hint: "Onde defende: espera no campo de defesa vs. pressiona a saída de bola adversária." },
  { key: "estilo_verticalidade", label: "Ritmo de ataque", low: "Cadenciado", high: "Vertical", hint: "Velocidade ao atacar: circula com calma (toque a toque) vs. busca o gol rápido em transição/bola longa." },
  { key: "estilo_bola_parada", label: "Bola parada", low: "Rara", high: "Frequente", hint: "Quanto do perigo vem de escanteios e faltas em vez de jogadas com a bola rolando." },
];

const DISPLAY_METRICS: [string, string][] = [
  ["Possession", "Posse"],
  ["XG", "xG"],
  ["AttemptAtGoal", "Finalizações"],
  ["AttemptAtGoalOnTarget", "No alvo"],
  ["Corners", "Escanteios"],
  ["FoulsFor", "Faltas"],
  ["PitchControl", "Controle de campo"],
];

function getStat(stats: TeamStat[], metric: string): string {
  const s = stats.find(x => x.metric === metric);
  return s?.value != null ? Number(s.value).toFixed(2) : "—";
}

function statNum(stats: TeamStat[], metric: string): number | null {
  const s = stats.find(x => x.metric === metric);
  return s?.value != null ? Number(s.value) : null;
}

// % a exibir: Possession/PitchControl já vêm 0-1 → ×100.
const STAT_PCT = new Set(["Possession", "PitchControl", "FinalThirdPitchControl"]);
function fmtStat(v: number | null, metric: string): string {
  if (v == null) return "—";
  if (STAT_PCT.has(metric)) return `${Math.round((v <= 1 ? v * 100 : v))}%`;
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}

// Barra comparativa estilo placar profissional (FotMob): valor casa | rótulo | valor fora,
// com barra dividida proporcional. homeColor destaca a seleção em foco.
// Barra de posse no estilo FIFA: 3 segmentos (time · em disputa · oponente).
// A `Possession` da FIFA não soma 100% entre os dois — o resto é a posse contestada.
function PossessionBar({ home, away, homeColor }: { home: number | null; away: number | null; homeColor: string }) {
  const h = home != null ? (home <= 1 ? home * 100 : home) : 0;
  const a = away != null ? (away <= 1 ? away * 100 : away) : 0;
  const contested = Math.max(0, 100 - h - a);
  return (
    <div style={{ marginBottom: 11 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: h >= a ? "var(--text)" : "var(--text-muted)" }}>{h.toFixed(0)}%</span>
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Posse de bola<DefinitionBubble id="posse" size={12} /></span>
        <span style={{ fontSize: 13, fontWeight: 700, color: a > h ? "var(--text)" : "var(--text-muted)" }}>{a.toFixed(0)}%</span>
      </div>
      <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", background: "var(--surface2)" }}>
        <div style={{ width: `${h}%`, background: homeColor }} />
        <div style={{ width: `${contested}%`, background: "#f0883e" }} />
        <div style={{ width: `${a}%`, background: "#6b7280", opacity: 0.7 }} />
      </div>
      {contested > 0.5 && (
        <div style={{ position: "relative", height: 13, marginTop: 3 }}>
          <span style={{ position: "absolute", left: `${h + contested / 2}%`, transform: "translateX(-50%)", fontSize: 10, color: "#f0883e", whiteSpace: "nowrap" }}>{contested.toFixed(0)}% em disputa</span>
        </div>
      )}
    </div>
  );
}

function StatCompareBar({ label, home, away, metric, homeColor }: { label: string; home: number | null; away: number | null; metric: string; homeColor: string }) {
  const h = home ?? 0;
  const a = away ?? 0;
  const total = h + a;
  const homePct = total > 0 ? (h / total) * 100 : 50;
  const lead = h === a ? "tie" : h > a ? "home" : "away";
  return (
    <div style={{ marginBottom: 11 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: lead === "home" ? "var(--text)" : "var(--text-muted)" }}>{fmtStat(home, metric)}</span>
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{label}{fifaDefId(metric) && <DefinitionBubble id={fifaDefId(metric)!} size={12} />}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: lead === "away" ? "var(--text)" : "var(--text-muted)" }}>{fmtStat(away, metric)}</span>
      </div>
      <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", background: "var(--surface2)" }}>
        <div style={{ width: `${homePct}%`, background: homeColor, transition: "width 0.4s ease" }} />
        <div style={{ width: `${100 - homePct}%`, background: "#6b7280", opacity: 0.7, transition: "width 0.4s ease" }} />
      </div>
    </div>
  );
}

// lâmpada de curiosidade: ícone no canto, texto só no hover/foco (estilo legacy)
function CuriosityLamp({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <div
      tabIndex={0}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)}
      onBlur={() => setShow(false)}
      aria-label={text}
      style={{ position: "relative", flexShrink: 0, alignSelf: "center", cursor: "help", fontSize: 18, lineHeight: 1, outline: "none" }}
    >
      💡
      {show && (
        <div style={{
          position: "absolute", top: "50%", right: "calc(100% + 12px)", transform: "translateY(-50%)",
          width: 260, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8,
          padding: "10px 12px", fontSize: 12, lineHeight: 1.45, color: "var(--text-muted)", fontStyle: "italic",
          boxShadow: "0 8px 24px rgba(0,0,0,0.55)", zIndex: 20, whiteSpace: "normal", textAlign: "left",
        }}>
          {text}
        </div>
      )}
    </div>
  );
}

// linha chave/valor para os blocos de Resumo (História em Copas / Nesta Copa)
function KV({ k, v }: { k: string; v: string | number }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", padding: "4px 0", borderBottom: "1px solid var(--border)", fontSize: 12.5 }}>
      <span style={{ color: "var(--text-muted)" }}>{k}</span>
      <span style={{ color: "var(--text)", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{v}</span>
    </div>
  );
}

function resultBadge(win: boolean, draw: boolean) {
  const label = win ? "V" : draw ? "E" : "D";
  const color = win ? "var(--green)" : draw ? "var(--yellow)" : "var(--red)";
  return (
    <span style={{
      display: "inline-block",
      background: color,
      color: "white",
      borderRadius: 4,
      padding: "1px 7px",
      fontSize: 11,
      fontWeight: 700,
      marginRight: 6,
    }}>{label}</span>
  );
}

function formatDate(d: string | null) {
  if (!d) return "";
  try {
    return new Date(d).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  } catch { return d; }
}

// ─── Per-game expanded row ────────────────────────────────────────────────────

function GameDetailRow({ match, team }: { match: Match; team: TeamSummary }) {
  const [subTab, setSubTab] = useState<"lineup" | "stats" | "timeline">("lineup");

  const { data: lineups } = useSWR(
    `lineups-${match.match_id}`,
    () => analytics.matchLineups(match.match_id)
  );
  const { data: events } = useSWR(
    `events-${match.match_id}`,
    () => analytics.matchEvents(match.match_id)
  );
  const { data: statsData } = useSWR(
    `stats-${match.match_id}`,
    () => analytics.matchStats(match.match_id)
  );
  const { data: playerStatsData } = useSWR(
    `pstats-${match.match_id}`,
    () => analytics.matchPlayerStats(match.match_id)
  );
  const playerStatsMap = useMemo(() => {
    const m = new Map<string, Record<string, number>>();
    if (playerStatsData) {
      for (const [id, arr] of Object.entries(playerStatsData.players)) {
        const rec: Record<string, number> = {};
        for (const s of arr) if (s.value != null) rec[s.metric] = s.value;
        m.set(id, rec);
      }
    }
    return m;
  }, [playerStatsData]);

  // Nota (score_geral) por jogador dos DOIS times (snapshot mais recente).
  const { data: homeSnaps } = useSWR(match.home_team ? `psnap-${match.home_team}` : null, () => analytics.playerSnapshots({ team: match.home_team! }));
  const { data: awaySnaps } = useSWR(match.away_team ? `psnap-${match.away_team}` : null, () => analytics.playerSnapshots({ team: match.away_team! }));
  const scoreById = useMemo(() => {
    const m = new Map<string, number>();
    for (const p of [...(homeSnaps ?? []), ...(awaySnaps ?? [])]) if (p.score_geral != null) m.set(p.id_player, p.score_geral);
    return m;
  }, [homeSnaps, awaySnaps]);

  const teamSide = match.home_team === team.name ? "home" : "away";
  const teamIdTeam = lineups?.find(p => p.team_side === teamSide)?.id_team ?? "";
  const oppIdTeam = lineups?.find(p => p.team_side !== teamSide)?.id_team ?? "";

  const teamStats = statsData?.teams?.[teamIdTeam] ?? [];
  const oppStats = statsData?.teams?.[oppIdTeam] ?? [];

  const homePlayers: LineupPlayer[] = lineups?.filter(p => p.team_side === "home") ?? [];
  const awayPlayers: LineupPlayer[] = lineups?.filter(p => p.team_side === "away") ?? [];
  const oppName = teamSide === "home" ? match.away_team : match.home_team;

  // Campo e linha do tempo orientam o TIME VISTO à esquerda (igual ao cabeçalho,
  // que lista a seleção do modal primeiro). Se o time visto é o visitante,
  // inverte os lados — como lineup_x/y vêm nulos, o layout é simétrico.
  const viewedIsHome = teamSide === "home";
  const leftPlayers = viewedIsHome ? homePlayers : awayPlayers;
  const rightPlayers = viewedIsHome ? awayPlayers : homePlayers;
  const leftTeam = team.name;
  const rightTeam = oppName ?? "";

  return (
    <div style={{
      padding: "12px 16px",
      borderTop: "1px solid var(--border)",
      background: "var(--background)",
    }}>
      <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
        {(["lineup", "stats", "timeline"] as const).map(t => (
          <button key={t}
            onClick={() => setSubTab(t)}
            style={{
              background: subTab === t ? "var(--accent)" : "var(--surface2)",
              color: subTab === t ? "white" : "var(--text-muted)",
              border: "none",
              borderRadius: 6,
              padding: "4px 14px",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            {t === "lineup" ? "Escalação" : t === "stats" ? "Estatísticas" : "Linha do tempo"}
          </button>
        ))}
      </div>

      {subTab === "stats" && (
        !statsData ? (
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Carregando...</p>
        ) : (
          <div>
            {/* Cabeçalho com os dois times */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, fontSize: 12, fontWeight: 700 }}>
              <span style={{ color: "var(--accent)" }}>{team.name}</span>
              <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>Comparativo</span>
              <span style={{ color: "var(--text)" }}>{oppName}</span>
            </div>
            <PossessionBar home={statNum(teamStats, "Possession")} away={statNum(oppStats, "Possession")} homeColor="var(--accent)" />
            {DISPLAY_METRICS.filter(([m]) => m !== "Possession").map(([metric, label]) => (
              <StatCompareBar
                key={metric}
                label={label}
                metric={metric}
                home={statNum(teamStats, metric)}
                away={statNum(oppStats, metric)}
                homeColor="var(--accent)"
              />
            ))}
          </div>
        )
      )}

      {subTab === "lineup" && (
        !lineups ? (
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Carregando...</p>
        ) : lineups.length === 0 ? (
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Sem dados de escalação.</p>
        ) : (
          <PitchView
            homePlayers={leftPlayers}
            awayPlayers={rightPlayers}
            homeTeam={leftTeam}
            awayTeam={rightTeam}
            events={events ?? []}
            homeIdTeam={teamIdTeam}
            playerStats={playerStatsMap}
            playerScores={scoreById}
          />
        )
      )}

      {subTab === "timeline" && (
        !events ? (
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Carregando...</p>
        ) : (
          <MatchTimeline
            events={events}
            homePlayers={leftPlayers}
            awayPlayers={rightPlayers}
            homeTeam={leftTeam}
            awayTeam={rightTeam}
            homeIdTeam={teamIdTeam}
          />
        )
      )}

    </div>
  );
}

// ─── Main Modal ───────────────────────────────────────────────────────────────

interface TeamModalProps {
  team: TeamSummary;
  onClose: () => void;
  snapshot?: number; // snapshot atual — limita os dados de jogador ao momento
}

export default function TeamModal({ team, onClose, snapshot }: TeamModalProps) {
  const [activeTab, setActiveTab] = useState<Tab>("resumo");
  const [expandedGame, setExpandedGame] = useState<string | null>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  const kit = getKit(team.name);

  useEffect(() => {
    const fn = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", fn);
    return () => document.removeEventListener("keydown", fn);
  }, [onClose]);

  const finalized = team.games.filter(m => m.status === "finalizado");
  const firstGame = finalized[0] ?? null;

  // Infos curadas (identidade) — alimentam o Resumo
  const { data: teamInfo } = useSWR(
    activeTab === "resumo" ? `team-info-${team.name}` : null,
    () => analytics.teamsInfo(team.name)
  );

  // Estilo: usa os eixos JÁ normalizados do snapshot (z-score 0-100, 50=média),
  // não os stats crus — assim a bolinha fica na posição certa e comparável.
  const { data: teamSnaps } = useSWR(
    activeTab === "estilo" ? `team-snaps-${snapshot ?? "last"}` : null,
    () => analytics.teamSnapshots(snapshot)
  );
  const estilo = useMemo(
    () => teamSnaps?.find((s) => s.team === team.name) ?? null,
    [teamSnaps, team.name]
  );

  // Stats por jogador (elenco rico + artilheiro do Resumo) — do snapshot atual
  const { data: playerStats, isLoading: playerStatsLoading } = useSWR(
    activeTab === "elenco" || activeTab === "resumo" ? `player-snap-${team.name}-${snapshot ?? "last"}` : null,
    () => analytics.playerSnapshots({ team: team.name, snapshot })
  );

  // Artilheiro da seleção nesta Copa (jogador com mais gols)
  const artilheiro = useMemo(() => {
    if (!playerStats?.length) return null;
    let top: { name: string; gols: number } | null = null;
    for (const p of playerStats) {
      const g = typeof p.gols === "number" ? p.gols : 0;
      if (g > 0 && (!top || g > top.gols)) top = { name: p.player_name ?? "—", gols: g };
    }
    return top;
  }, [playerStats]);


  const gd = team.gf - team.ga;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.74)" }}
      onClick={e => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          width: "100%",
          maxWidth: 1000,
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header com camisa kit */}
        <div style={{
          background: "linear-gradient(135deg, var(--surface2), var(--background))",
          borderBottom: "1px solid var(--border)",
          padding: "16px 24px",
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexShrink: 0,
        }}>
          {/* Só a bandeira, maior (sem a caixa do kit) */}
          <Flag team={team.name} height={46} style={{ flexShrink: 0, borderRadius: 4, boxShadow: "0 3px 12px rgba(0,0,0,0.5)" }} />
          <div style={{ flex: 1 }}>
            <h2 style={{ color: "var(--text)", fontSize: 20, fontWeight: 700, margin: 0 }}>
              {team.name}
            </h2>
            <p style={{ color: "var(--text-muted)", fontSize: 12, margin: "3px 0 0" }}>
              {team.confederation}{team.group ? ` · Grupo ${team.group}` : ""}{team.code ? ` · ${team.code}` : ""}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", color: "var(--text-muted)", fontSize: 20, cursor: "pointer", padding: "4px 8px" }}
          >
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div style={{
          display: "flex",
          gap: 2,
          padding: "0 24px",
          borderBottom: "1px solid var(--border)",
          flexShrink: 0,
        }}>
          {TABS.map(t => (
            <button key={t}
              onClick={() => setActiveTab(t)}
              style={{
                background: "none",
                border: "none",
                borderBottom: activeTab === t ? "2px solid var(--accent)" : "2px solid transparent",
                color: activeTab === t ? "var(--accent)" : "var(--text-muted)",
                padding: "10px 16px",
                fontSize: 13,
                cursor: "pointer",
                fontWeight: activeTab === t ? 600 : 400,
                transition: "color 0.1s",
              }}
            >
              {TAB_LABEL[t]}
              {t === "jogos" && finalized.length > 0 ? ` (${finalized.length})` : ""}
              {t === "elenco" && playerStats && playerStats.length > 0 ? ` (${playerStats.length})` : ""}
            </button>
          ))}
        </div>

        {/* Body */}
        <div style={{ overflow: "auto", flex: 1, padding: "20px 24px" }}>

          {/* ── RESUMO ── */}
          {activeTab === "resumo" && (
            <div>
              {/* Grid de stats campanha com bordas coloridas */}
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(4, 1fr)",
                gap: 8,
                marginBottom: 20,
              }}>
                {[
                  { label: "Pontos", value: team.points, color: team.points > 0 ? "var(--green)" : "var(--text)", def: "pontos" },
                  { label: "V / E / D", value: `${team.wins}/${team.draws}/${team.losses}`, color: undefined, def: null },
                  { label: "Gols", value: `${team.gf}:${team.ga}`, color: undefined, def: null },
                  { label: "Saldo", value: gd >= 0 ? `+${gd}` : String(gd), color: gd > 0 ? "var(--green)" : gd < 0 ? "var(--red)" : "var(--text-muted)", def: "saldo_gols" },
                ].map(({ label, value, color, def }) => (
                  <div key={label} style={{
                    background: "var(--surface2)",
                    border: `1px solid ${color ?? "var(--border)"}22`,
                    borderLeft: `3px solid ${color ?? "var(--border)"}`,
                    borderRadius: 8,
                    padding: "12px 16px",
                    textAlign: "center",
                  }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: color ?? "var(--text)" }}>{value}</div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{label}{def && <DefinitionBubble id={def} size={12} />}</div>
                  </div>
                ))}
              </div>

              {/* Identidade: apelido · técnico · 💡 curiosidade */}
              {(teamInfo?.apelido || teamInfo?.tecnico || teamInfo?.curiosidade) && (
                <div style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 10, padding: "14px 16px", marginBottom: 16, display: "flex", alignItems: "center", gap: 16 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {teamInfo?.apelido && <div style={{ fontSize: 15, fontWeight: 800, color: "var(--accent2)" }}>{teamInfo.apelido}</div>}
                    <div style={{ fontSize: 12.5, color: "var(--text-muted)", marginTop: 3 }}>
                      {[teamInfo?.tecnico ? `Téc. ${teamInfo.tecnico}` : null, team.confederation, team.group ? `Grupo ${team.group}` : null].filter(Boolean).join(" · ")}
                    </div>
                  </div>
                  {teamInfo?.curiosidade && <CuriosityLamp text={teamInfo.curiosidade} />}
                </div>
              )}

              {/* Duas colunas: História em Copas | Nesta Copa */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 10, padding: "14px 16px" }}>
                  <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--accent)", marginBottom: 10 }}>História em Copas</div>
                  {teamInfo?.titulos_copa != null && <KV k={teamInfo.titulos_copa === 1 ? "Título mundial" : "Títulos mundiais"} v={teamInfo.titulos_copa} />}
                  {teamInfo?.vices_copa != null && <KV k={teamInfo.vices_copa === 1 ? "Vice-campeonato" : "Vice-campeonatos"} v={teamInfo.vices_copa} />}
                  {teamInfo?.participacoes != null && <KV k="Participações" v={teamInfo.participacoes} />}
                  {teamInfo?.estreia != null && <KV k="Estreia em Copas" v={teamInfo.estreia} />}
                  {teamInfo && teamInfo.titulos_copa == null && teamInfo.participacoes == null && (
                    <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>sem dados</p>
                  )}
                  {teamInfo?.melhor_campanha && (
                    <div style={{ marginTop: 10, padding: "8px 10px", background: "var(--surface)", borderRadius: 7, fontSize: 12.5, color: "var(--text)" }}>🏆 {teamInfo.melhor_campanha}</div>
                  )}
                </div>

                <div style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 10, padding: "14px 16px" }}>
                  <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--accent)", marginBottom: 10 }}>Nesta Copa</div>
                  {finalized.length > 0 ? (
                    <>
                      <KV k="Jogos" v={finalized.length} />
                      <KV k="Pontos" v={team.points} />
                      <KV k="Gols (pró–contra)" v={`${team.gf}–${team.ga}`} />
                      <KV k="Saldo de gols" v={gd >= 0 ? `+${gd}` : String(gd)} />
                      {artilheiro && (
                        <div style={{ marginTop: 10, padding: "8px 10px", background: "var(--surface)", borderRadius: 7, fontSize: 12.5, color: "var(--text)" }}>
                          ⚽ {artilheiro.name} <span style={{ color: "var(--text-muted)" }}>({artilheiro.gols} {artilheiro.gols === 1 ? "gol" : "gols"})</span>
                        </div>
                      )}
                    </>
                  ) : (
                    <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>Ainda não entrou em campo.</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ── JOGOS ── */}
          {activeTab === "jogos" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {[...team.games]
                .sort((a, b) => (a.match_number ?? 0) - (b.match_number ?? 0))
                .map(m => {
                  const isHome = m.home_team === team.name;
                  const opp = isHome ? m.away_team : m.home_team;
                  const gf = isHome ? m.home_score : m.away_score;
                  const ga = isHome ? m.away_score : m.home_score;
                  const win = gf != null && ga != null && gf > ga;
                  const draw = gf != null && ga != null && gf === ga;
                  const expanded = expandedGame === m.match_id;

                  return (
                    <div key={m.match_id} style={{
                      background: "var(--surface2)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      overflow: "hidden",
                    }}>
                      <div
                        style={{
                          padding: "10px 14px",
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          cursor: m.status === "finalizado" ? "pointer" : "default",
                        }}
                        onClick={() => {
                          if (m.status !== "finalizado") return;
                          setExpandedGame(expanded ? null : m.match_id);
                        }}
                      >
                        {/* Badge resultado */}
                        {m.status === "finalizado" ? resultBadge(win, draw) : (
                          <span style={{
                            display: "inline-block",
                            background: "var(--surface)",
                            color: "var(--text-muted)",
                            borderRadius: 4,
                            padding: "1px 7px",
                            fontSize: 11,
                            fontWeight: 600,
                            marginRight: 6,
                          }}>
                            {m.status === "agendado" ? "—" : "AO VIVO"}
                          </span>
                        )}

                        {/* Confronto com bandeiras */}
                        <div style={{ display: "flex", alignItems: "center", gap: 6, flex: 1 }}>
                          <Flag team={team.name} height={14} />
                          <span style={{ fontWeight: 700, color: "var(--text)", fontSize: 14 }}>
                            {m.status === "finalizado" && gf != null ? gf : "—"}
                          </span>
                          <span style={{ color: "var(--text-muted)", fontSize: 12 }}>×</span>
                          <span style={{ fontWeight: 700, color: "var(--text)", fontSize: 14 }}>
                            {m.status === "finalizado" && ga != null ? ga : "—"}
                          </span>
                          <Flag team={opp ?? null} height={14} />
                          <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
                            {opp ?? "?"}
                          </span>
                        </div>

                        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                          {m.group ? `Gr.${m.group}` : m.stage ?? ""} · {formatDate(m.date_utc)}
                        </span>
                        {m.status === "finalizado" && (
                          <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
                            {expanded ? "▲" : "▼"}
                          </span>
                        )}
                      </div>
                      {expanded && <GameDetailRow match={m} team={team} />}
                    </div>
                  );
                })}
            </div>
          )}

          {/* ── ELENCO ── */}
          {activeTab === "elenco" && (
            <TeamRoster players={playerStats ?? []} loading={playerStatsLoading} kit={kit} />
          )}

          {/* ── ESTILO ── */}
          {activeTab === "estilo" && (
            <div>
              {finalized.length === 0 ? (
                <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Sem jogos finalizados para análise de estilo.</p>
              ) : !estilo ? (
                <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Calculando…</p>
              ) : !estilo.estilo_jogo ? (
                <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Sem dados de estilo (métricas de fase indisponíveis para esta seleção).</p>
              ) : (
                <div>
                  {/* Arquétipo dominante */}
                  {(() => {
                    const arch = String(estilo.estilo_jogo);
                    const info = ARCHETYPES[arch] ?? { emoji: "🎲", desc: "Estilo equilibrado, sem traço dominante.", def: "estilo_jogo" };
                    return (
                      <div style={{ display: "flex", alignItems: "center", gap: 14, background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 10, padding: "14px 16px", marginBottom: 18 }}>
                        <span style={{ fontSize: 30, lineHeight: 1, flexShrink: 0 }}>{info.emoji}</span>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                            <span title={info.desc} style={{ fontSize: 17, fontWeight: 800, color: "var(--accent2)", cursor: "help" }}>{styleName(arch)}</span>
                            <DefinitionBubble id={info.def} size={13} />
                          </div>
                          <div style={{ fontSize: 12.5, color: "var(--text-muted)", marginTop: 3, lineHeight: 1.4 }}>{info.desc}</div>
                        </div>
                      </div>
                    );
                  })()}

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--accent)" }}>Perfil tático</span>
                    <span style={{ fontSize: 10.5, color: "var(--text-muted)" }}>50 = média do torneio · {finalized.length} {finalized.length === 1 ? "jogo" : "jogos"}</span>
                  </div>

                  {/* Eixos bipolares (z-score 0-100, 50 = média; barra do centro até o valor) */}
                  {STYLE_AXES.map(({ key, label, low, high, hint }) => {
                    const raw = estilo[key];
                    const v = typeof raw === "number" ? raw : null;
                    const pct = v != null ? Math.max(0, Math.min(100, v)) : null;
                    const above = v != null && v >= 50;
                    return (
                      <div key={key} style={{ marginBottom: 16 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                          <span title={hint} style={{ fontSize: 13, color: "var(--text)", fontWeight: 600, cursor: "help", borderBottom: "1px dotted var(--text-muted)" }}>{label}</span>
                          {v != null && <span style={{ fontSize: 12, color: above ? "var(--accent)" : "var(--text-muted)", fontWeight: 700 }}>{Math.round(v)}</span>}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 11, color: "var(--text-muted)", width: 78, textAlign: "right", flexShrink: 0 }}>{low}</span>
                          <div style={{ flex: 1, height: 8, background: "var(--surface2)", borderRadius: 4, position: "relative" }}>
                            <div style={{ position: "absolute", top: -2, bottom: -2, left: "50%", width: 1, background: "var(--border)", transform: "translateX(-50%)" }} />
                            {pct != null && (
                              <>
                                <div style={{ position: "absolute", top: 0, bottom: 0, borderRadius: 4, background: "var(--accent)", opacity: 0.22, left: `${Math.min(50, pct)}%`, width: `${Math.abs(pct - 50)}%` }} />
                                <div style={{ position: "absolute", top: "50%", left: `${pct}%`, width: 14, height: 14, borderRadius: "50%", background: "var(--accent)", border: "2px solid var(--background)", transform: "translate(-50%, -50%)", transition: "left 0.4s ease", boxShadow: "0 0 6px var(--accent)88" }} />
                              </>
                            )}
                          </div>
                          <span style={{ fontSize: 11, color: "var(--text-muted)", width: 78, flexShrink: 0 }}>{high}</span>
                        </div>
                      </div>
                    );
                  })}

                  {/* Leitura: traduz o perfil em uma frase */}
                  {(() => {
                    const ax = (k: string) => (typeof estilo[k] === "number" ? (estilo[k] as number) : 50);
                    const reads: string[] = [];
                    const p = ax("estilo_posse");
                    if (p >= 58) reads.push("constrói com posse apoiada"); else if (p <= 42) reads.push("prefere o jogo direto");
                    const pr = ax("estilo_pressao");
                    if (pr >= 58) reads.push("pressiona alto"); else if (pr <= 42) reads.push("defende em bloco recuado");
                    const ve = ax("estilo_verticalidade");
                    if (ve >= 58) reads.push("ataca vertical, em transição rápida"); else if (ve <= 42) reads.push("ataca com cadência, em ritmo controlado");
                    const bp = ax("estilo_bola_parada");
                    if (bp >= 58) reads.push("explora bem a bola parada"); else if (bp <= 42) reads.push("depende pouco de bola parada");
                    const frase = reads.length
                      ? `${team.name} ${reads.join(", ")}.`
                      : `${team.name} tem um perfil equilibrado, sem um traço tático que se destaque da média.`;
                    return (
                      <div style={{ marginTop: 6, padding: "12px 14px", background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, lineHeight: 1.55, color: "var(--text)" }}>
                        <span style={{ color: "var(--text-muted)", fontWeight: 700, fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.5px", display: "block", marginBottom: 4 }}>Leitura</span>
                        {frase}
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
