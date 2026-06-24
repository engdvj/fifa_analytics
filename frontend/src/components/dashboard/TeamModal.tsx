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
  const homeIdTeam = lineups?.find(p => p.team_side === "home")?.id_team ?? "";

  const teamStats = statsData?.teams?.[teamIdTeam] ?? [];
  const oppStats = statsData?.teams?.[oppIdTeam] ?? [];

  const homePlayers: LineupPlayer[] = lineups?.filter(p => p.team_side === "home") ?? [];
  const awayPlayers: LineupPlayer[] = lineups?.filter(p => p.team_side === "away") ?? [];
  const oppName = teamSide === "home" ? match.away_team : match.home_team;

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
            homePlayers={homePlayers}
            awayPlayers={awayPlayers}
            homeTeam={match.home_team ?? ""}
            awayTeam={match.away_team ?? ""}
            events={events ?? []}
            homeIdTeam={homeIdTeam}
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
            homePlayers={homePlayers}
            awayPlayers={awayPlayers}
            homeTeam={match.home_team ?? ""}
            awayTeam={match.away_team ?? ""}
            homeIdTeam={homeIdTeam}
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

  // Estilo metrics: need id_team from first game lineup
  const { data: firstLineups } = useSWR(
    activeTab === "estilo" && firstGame
      ? `lineups-first-${team.name}`
      : null,
    () => analytics.matchLineups(firstGame!.match_id)
  );
  const teamIdTeam = useMemo(() => {
    if (!firstLineups || !firstGame) return null;
    const side = firstGame.home_team === team.name ? "home" : "away";
    return firstLineups.find(p => p.team_side === side)?.id_team ?? null;
  }, [firstLineups, firstGame, team.name]);

  // Aggregate stats for Estilo metrics
  const { data: avgMetrics } = useSWR(
    activeTab === "estilo" && teamIdTeam && finalized.length > 0
      ? `avg-metrics-${team.name}`
      : null,
    async () => {
      const results = await Promise.all(
        finalized.map(m => analytics.matchStats(m.match_id).catch(() => null))
      );
      const sums = new Map<string, { sum: number; count: number }>();
      for (const r of results) {
        if (!r || !teamIdTeam) continue;
        for (const s of r.teams[teamIdTeam] ?? []) {
          if (s.value == null) continue;
          const cur = sums.get(s.metric) ?? { sum: 0, count: 0 };
          cur.sum += s.value;
          cur.count++;
          sums.set(s.metric, cur);
        }
      }
      const avgs: Record<string, number> = {};
      for (const [k, v] of sums) avgs[k] = v.sum / v.count;
      return avgs;
    }
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
                <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
                  Sem jogos finalizados para análise de estilo.
                </p>
              ) : !avgMetrics ? (
                <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Calculando...</p>
              ) : (
                <div>
                  <p style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 16 }}>
                    Estilo de jogo<DefinitionBubble id="estilo_jogo" size={12} /> · baseado em médias de {finalized.length} {finalized.length === 1 ? "jogo" : "jogos"}.
                  </p>

                  {/* Eixos de estilo */}
                  {[
                    { metric: "Possession", label: "Posse de bola", lowLabel: "Jogo direto", highLabel: "Posse alta", max: 100 },
                    { metric: "XG", label: "Criação de chances", lowLabel: "Discreta", highLabel: "Ofensivo", max: 4 },
                    { metric: "PitchControl", label: "Controle territorial", lowLabel: "Reativo", highLabel: "Dominante", max: 100 },
                    { metric: "ForcedTurnovers", label: "Pressão alta", lowLabel: "Baixa", highLabel: "Intensa", max: 20 },
                  ].map(({ metric, label, lowLabel, highLabel, max }) => {
                    const v = avgMetrics?.[metric];
                    const pct = v != null ? Math.min(100, (v / max) * 100) : null;
                    return (
                      <div key={metric} style={{ marginBottom: 20 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                          <span style={{ fontSize: 13, color: "var(--text)", fontWeight: 600 }}>{label}{fifaDefId(metric) && <DefinitionBubble id={fifaDefId(metric)!} size={12} />}</span>
                          {v != null && (
                            <span style={{ fontSize: 12, color: "var(--accent)", fontWeight: 700 }}>
                              {v.toFixed(1)}
                            </span>
                          )}
                        </div>
                        {/* Track com dot deslizante */}
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 11, color: "var(--text-muted)", width: 60, textAlign: "right", flexShrink: 0 }}>{lowLabel}</span>
                          <div style={{ flex: 1, height: 8, background: "var(--surface2)", borderRadius: 4, position: "relative" }}>
                            {/* Linha central */}
                            <div style={{ position: "absolute", top: 2, bottom: 2, left: "50%", width: 1, background: "var(--border)", transform: "translateX(-50%)" }} />
                            {pct != null ? (
                              <div style={{
                                position: "absolute",
                                top: "50%",
                                left: `${pct}%`,
                                width: 14,
                                height: 14,
                                borderRadius: "50%",
                                background: "var(--accent)",
                                border: "2px solid var(--background)",
                                transform: "translate(-50%, -50%)",
                                transition: "left 0.4s ease",
                                boxShadow: "0 0 6px var(--accent)88",
                              }} />
                            ) : (
                              <div style={{ position: "absolute", inset: 0, borderRadius: 4, background: "var(--surface2)", opacity: 0.5 }} />
                            )}
                          </div>
                          <span style={{ fontSize: 11, color: "var(--text-muted)", width: 60, flexShrink: 0 }}>{highLabel}</span>
                        </div>
                      </div>
                    );
                  })}

                  {/* Texto descritivo */}
                  <div style={{
                    marginTop: 8,
                    padding: "12px 16px",
                    background: "var(--surface2)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    fontSize: 13,
                    color: "var(--text)",
                    lineHeight: 1.6,
                  }}>
                    {(() => {
                      const pos = avgMetrics["Possession"] ?? 50;
                      const xg = avgMetrics["XG"] ?? 1;
                      const ctrl = avgMetrics["PitchControl"] ?? 50;
                      const tags: string[] = [];
                      if (pos >= 55) tags.push("posse elevada");
                      else if (pos < 45) tags.push("jogo direto");
                      if (xg >= 2.0) tags.push("ataque eficiente");
                      else if (xg < 1.0) tags.push("fase ofensiva discreta");
                      if (ctrl >= 55) tags.push("domínio territorial");
                      return tags.length > 0
                        ? `${team.name}: ${tags.join(", ")}.`
                        : `Estilo de jogo equilibrado com base nas médias do torneio.`;
                    })()}
                  </div>
                </div>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
