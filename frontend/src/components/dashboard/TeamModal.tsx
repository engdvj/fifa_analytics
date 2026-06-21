"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import useSWR from "swr";
import { analytics, Match, LineupPlayer, TeamStat } from "@/lib/api";
import { TeamSummary, flag, getKit } from "@/lib/teamUtils";
import PitchView from "./PitchView";
import EventTimeline from "./EventTimeline";

const TABS = ["resumo", "jogos", "elenco", "estilo"] as const;
type Tab = typeof TABS[number];

const TAB_LABEL: Record<Tab, string> = {
  resumo: "Resumo",
  jogos: "Jogos",
  elenco: "Elenco",
  estilo: "Estilo",
};

const DISPLAY_METRICS: [string, string][] = [
  ["Possession", "Posse (%)"],
  ["XG", "xG"],
  ["ShotsTotal", "Finalizações"],
  ["ShotsOnTarget", "Chutes no alvo"],
  ["Corners", "Escanteios"],
  ["FoulsFor", "Faltas"],
  ["PitchControl", "Controle de campo"],
];

function getStat(stats: TeamStat[], metric: string): string {
  const s = stats.find(x => x.metric === metric);
  return s?.value != null ? Number(s.value).toFixed(2) : "—";
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
  const [subTab, setSubTab] = useState<"stats" | "lineup" | "timeline">("stats");

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
        {(["stats", "lineup", "timeline"] as const).map(t => (
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
            {t === "stats" ? "Estatísticas" : t === "lineup" ? "Escalação" : "Timeline"}
          </button>
        ))}
      </div>

      {subTab === "stats" && (
        !statsData ? (
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Carregando...</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr>
                <th style={{ padding: "4px 8px", textAlign: "center", color: "var(--accent)" }}>
                  {team.name}
                </th>
                <th style={{ padding: "4px 8px", textAlign: "center", color: "var(--text-muted)" }}>
                  Métrica
                </th>
                <th style={{ padding: "4px 8px", textAlign: "center", color: "var(--text-muted)" }}>
                  {oppName}
                </th>
              </tr>
            </thead>
            <tbody>
              {DISPLAY_METRICS.map(([metric, label]) => (
                <tr key={metric} style={{ borderTop: "1px solid var(--border)" }}>
                  <td style={{ padding: "4px 8px", textAlign: "center", color: "var(--text)", fontWeight: 600 }}>
                    {getStat(teamStats, metric)}
                  </td>
                  <td style={{ padding: "4px 8px", textAlign: "center", color: "var(--text-muted)" }}>
                    {label}
                  </td>
                  <td style={{ padding: "4px 8px", textAlign: "center", color: "var(--text)" }}>
                    {getStat(oppStats, metric)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
          />
        )
      )}

      {subTab === "timeline" && (
        !events ? (
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Carregando...</p>
        ) : events.length === 0 ? (
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Sem eventos registrados.</p>
        ) : (
          <EventTimeline
            events={events}
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
}

export default function TeamModal({ team, onClose }: TeamModalProps) {
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

  // Elenco: fetch filtered lineups per game
  const { data: elencoData, isLoading: elencoLoading } = useSWR(
    activeTab === "elenco" && finalized.length > 0 ? `elenco-${team.name}` : null,
    async () => {
      const results = await Promise.all(
        finalized.map(async m => {
          const side = m.home_team === team.name ? "home" : "away";
          const players = await analytics.matchLineups(m.match_id).catch(() => [] as LineupPlayer[]);
          return players.filter(p => p.team_side === side);
        })
      );
      return results.flat();
    }
  );

  // Estilo / Resumo metrics: need id_team from first game lineup
  const { data: firstLineups } = useSWR(
    (activeTab === "resumo" || activeTab === "estilo") && firstGame
      ? `lineups-first-${team.name}`
      : null,
    () => analytics.matchLineups(firstGame!.match_id)
  );
  const teamIdTeam = useMemo(() => {
    if (!firstLineups || !firstGame) return null;
    const side = firstGame.home_team === team.name ? "home" : "away";
    return firstLineups.find(p => p.team_side === side)?.id_team ?? null;
  }, [firstLineups, firstGame, team.name]);

  // Aggregate stats for Resumo metrics
  const { data: avgMetrics } = useSWR(
    (activeTab === "resumo" || activeTab === "estilo") && teamIdTeam && finalized.length > 0
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

  const roster = useMemo(() => {
    if (!elencoData) return [];
    const seen = new Map<string, { player: LineupPlayer; games: number }>();
    for (const p of elencoData) {
      if (seen.has(p.id_player)) {
        seen.get(p.id_player)!.games++;
      } else {
        seen.set(p.id_player, { player: p, games: 1 });
      }
    }
    const posOrder: Record<string, number> = { G: 0, D: 1, M: 2, F: 3 };
    return Array.from(seen.values()).sort((a, b) => {
      const pa = posOrder[(a.player.position ?? "Z")[0]] ?? 4;
      const pb = posOrder[(b.player.position ?? "Z")[0]] ?? 4;
      return pa - pb || b.games - a.games;
    });
  }, [elencoData]);

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
          maxWidth: 780,
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
          {/* Jersey/Camisa visual */}
          <div style={{
            width: 52,
            height: 52,
            borderRadius: 10,
            background: kit.main,
            border: `3px solid ${kit.border}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 22,
            fontWeight: 900,
            color: kit.text,
            flexShrink: 0,
            boxShadow: `0 4px 14px ${kit.main}55`,
          }}>
            {flag(team.name)}
          </div>
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
                  { label: "Pontos", value: team.points, color: team.points > 0 ? "var(--green)" : "var(--text)" },
                  { label: "V / E / D", value: `${team.wins}/${team.draws}/${team.losses}`, color: undefined },
                  { label: "Gols", value: `${team.gf}:${team.ga}`, color: undefined },
                  { label: "Saldo", value: gd >= 0 ? `+${gd}` : String(gd), color: gd > 0 ? "var(--green)" : gd < 0 ? "var(--red)" : "var(--text-muted)" },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{
                    background: "var(--surface2)",
                    border: `1px solid ${color ?? "var(--border)"}22`,
                    borderLeft: `3px solid ${color ?? "var(--border)"}`,
                    borderRadius: 8,
                    padding: "12px 16px",
                    textAlign: "center",
                  }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: color ?? "var(--text)" }}>{value}</div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{label}</div>
                  </div>
                ))}
              </div>

              {finalized.length > 0 && (
                <div>
                  <p style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 10 }}>
                    Médias por jogo ({finalized.length} {finalized.length === 1 ? "jogo" : "jogos"})
                  </p>
                  {avgMetrics ? (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                      {DISPLAY_METRICS.map(([metric, label]) => {
                        const v = avgMetrics[metric];
                        return (
                          <div key={metric} style={{
                            background: "var(--surface2)",
                            border: "1px solid var(--border)",
                            borderRadius: 6,
                            padding: "8px 12px",
                          }}>
                            <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text)" }}>
                              {v != null ? v.toFixed(2) : "—"}
                            </div>
                            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{label}</div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Carregando métricas...</p>
                  )}
                </div>
              )}
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
                          <span style={{ fontSize: 16 }}>{flag(team.name)}</span>
                          <span style={{ fontWeight: 700, color: "var(--text)", fontSize: 14 }}>
                            {m.status === "finalizado" && gf != null ? gf : "—"}
                          </span>
                          <span style={{ color: "var(--text-muted)", fontSize: 12 }}>×</span>
                          <span style={{ fontWeight: 700, color: "var(--text)", fontSize: 14 }}>
                            {m.status === "finalizado" && ga != null ? ga : "—"}
                          </span>
                          <span style={{ fontSize: 16 }}>{flag(opp ?? null)}</span>
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
            <div>
              {elencoLoading && (
                <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Carregando elenco...</p>
              )}
              {!elencoLoading && roster.length === 0 && (
                <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Sem dados de escalação disponíveis.</p>
              )}
              {roster.length > 0 && (() => {
                const mostGames = roster.reduce((best, r) => r.games > best.games ? r : best, roster[0]);
                const captains = roster.filter(r => r.player.captain);
                const gks = roster.filter(r => (r.player.position ?? "").toUpperCase().startsWith("G"));

                const leaders = [
                  { label: "Mais jogos", value: mostGames?.games, name: mostGames?.player.player_name },
                  { label: "Capitão", value: captains[0]?.player.shirt_number ? `#${captains[0].player.shirt_number}` : "—", name: captains[0]?.player.player_name },
                  { label: "Goleiro", value: gks[0]?.player.shirt_number ? `#${gks[0].player.shirt_number}` : "—", name: gks[0]?.player.player_name },
                  { label: "Jogadores", value: roster.length, name: "no torneio" },
                ];

                return (
                  <>
                    {/* Leader cards */}
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 16 }}>
                      {leaders.map(l => (
                        <div key={l.label} style={{
                          background: "var(--surface2)",
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          padding: "10px 12px",
                          textAlign: "center",
                        }}>
                          <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>{l.label}</div>
                          <div style={{ fontSize: 18, fontWeight: 700, color: "var(--accent)" }}>{l.value ?? "—"}</div>
                          <div style={{ fontSize: 11, color: "var(--text)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {l.name ?? "—"}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Tabela do elenco */}
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--border)" }}>
                          {["#", "Jogador", "Pos", "Jogos"].map(h => (
                            <th key={h} style={{ padding: "6px 10px", textAlign: "left", color: "var(--text-muted)", fontSize: 11, fontWeight: 600 }}>
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {roster.map(({ player: p, games }) => (
                          <tr key={p.id_player} style={{ borderBottom: "1px solid var(--border)" }}>
                            <td style={{ padding: "6px 10px", color: "var(--text-muted)", textAlign: "center" }}>
                              {/* Jersey visual */}
                              <span style={{
                                display: "inline-flex",
                                alignItems: "center",
                                justifyContent: "center",
                                width: 24,
                                height: 24,
                                borderRadius: 4,
                                background: kit.main,
                                color: kit.text,
                                fontSize: 10,
                                fontWeight: 700,
                                border: `1px solid ${kit.border}`,
                              }}>
                                {p.shirt_number ?? "?"}
                              </span>
                            </td>
                            <td style={{ padding: "6px 10px", color: "var(--text)", fontWeight: p.captain ? 700 : 400 }}>
                              {p.player_name ?? "?"}{p.captain && " ©"}
                              {p.is_starter === false && (
                                <span style={{ fontSize: 10, color: "var(--text-muted)", marginLeft: 4 }}>res.</span>
                              )}
                            </td>
                            <td style={{ padding: "6px 10px", color: "var(--text-muted)" }}>
                              {p.position ?? "—"}
                            </td>
                            <td style={{ padding: "6px 10px", color: "var(--text-muted)", textAlign: "center" }}>
                              {games}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                );
              })()}
            </div>
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
                    Baseado em médias de {finalized.length} {finalized.length === 1 ? "jogo" : "jogos"}.
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
                          <span style={{ fontSize: 13, color: "var(--text)", fontWeight: 600 }}>{label}</span>
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
