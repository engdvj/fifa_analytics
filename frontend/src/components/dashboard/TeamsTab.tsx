"use client";

import { useState } from "react";
import useSWR from "swr";
import { analytics, Match, MatchStatsResponse, LineupPlayer, MatchEvent } from "@/lib/api";

interface TeamSummary {
  team: string;
  code: string | null;
  games: Match[];
  wins: number;
  draws: number;
  losses: number;
  gf: number;
  ga: number;
}

function buildTeamSummaries(matches: Match[]): TeamSummary[] {
  const map = new Map<string, TeamSummary>();

  for (const m of matches) {
    if (m.status !== "finalizado") continue;
    const home = m.home_team;
    const away = m.away_team;
    if (!home || !away) continue;

    const init = (team: string, code: string | null): TeamSummary =>
      map.get(team) ?? { team, code, games: [], wins: 0, draws: 0, losses: 0, gf: 0, ga: 0 };

    const hEntry = init(home, m.home_team_code);
    const aEntry = init(away, m.away_team_code);

    hEntry.games.push(m);
    aEntry.games.push(m);

    const hs = m.home_score ?? 0;
    const as_ = m.away_score ?? 0;
    hEntry.gf += hs; hEntry.ga += as_;
    aEntry.gf += as_; aEntry.ga += hs;

    if (hs > as_) { hEntry.wins++; aEntry.losses++; }
    else if (hs < as_) { aEntry.wins++; hEntry.losses++; }
    else { hEntry.draws++; aEntry.draws++; }

    map.set(home, hEntry);
    map.set(away, aEntry);
  }

  return [...map.values()].sort((a, b) => {
    const pa = a.wins * 3 + a.draws;
    const pb = b.wins * 3 + b.draws;
    if (pb !== pa) return pb - pa;
    return (b.gf - b.ga) - (a.gf - a.ga);
  });
}

function TeamCard({ summary, onClick }: { summary: TeamSummary; onClick: () => void }) {
  const pts = summary.wins * 3 + summary.draws;
  const gd = summary.gf - summary.ga;
  return (
    <button
      onClick={onClick}
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        cursor: "pointer",
        textAlign: "left",
        transition: "border-color 0.15s",
      }}
      className="p-4 flex flex-col gap-2 hover:border-blue-500/50 w-full"
    >
      <div className="font-semibold text-sm truncate">{summary.team}</div>
      <div className="flex gap-3 text-xs" style={{ color: "var(--text-muted)" }}>
        <span>{summary.games.length} jogos</span>
        <span style={{ color: "#3fb950" }}>{pts} pts</span>
        <span>{summary.wins}V {summary.draws}E {summary.losses}D</span>
        <span style={{ color: gd >= 0 ? "#3fb950" : "#f85149" }}>
          {gd > 0 ? "+" : ""}{gd} SG
        </span>
      </div>
    </button>
  );
}

function TeamModal({ team, onClose }: { team: TeamSummary; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)" }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          maxWidth: 560,
          width: "100%",
          maxHeight: "80vh",
          overflow: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
        className="p-6"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">{team.team}</h2>
          <button
            onClick={onClose}
            style={{ color: "var(--text-muted)" }}
            className="text-xl leading-none"
          >
            ✕
          </button>
        </div>

        <div
          className="grid grid-cols-4 gap-3 mb-6 text-center"
          style={{ background: "var(--surface2)", borderRadius: 8, padding: 16 }}
        >
          {[
            ["Jogos", team.games.length],
            ["Pts", team.wins * 3 + team.draws],
            ["Gols", `${team.gf}/${team.ga}`],
            ["Saldo", team.gf - team.ga > 0 ? `+${team.gf - team.ga}` : team.gf - team.ga],
          ].map(([label, value]) => (
            <div key={label as string}>
              <div style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>{label}</div>
              <div style={{ fontWeight: 700, fontSize: "1.1rem" }}>{value}</div>
            </div>
          ))}
        </div>

        <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-muted)" }}>
          Jogos disputados
        </h3>
        <div className="space-y-2">
          {team.games.map((m) => {
            const isHome = m.home_team === team.team;
            const opp = isHome ? m.away_team : m.home_team;
            const myScore = isHome ? m.home_score : m.away_score;
            const oppScore = isHome ? m.away_score : m.home_score;
            const result =
              myScore != null && oppScore != null
                ? myScore > oppScore
                  ? "V"
                  : myScore < oppScore
                  ? "D"
                  : "E"
                : "—";
            const resultColor =
              result === "V" ? "#3fb950" : result === "D" ? "#f85149" : "#d29922";
            return (
              <div
                key={m.match_id}
                style={{
                  background: "var(--surface2)",
                  borderRadius: 6,
                  padding: "8px 12px",
                  fontSize: "0.82rem",
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                }}
              >
                <span style={{ color: resultColor, fontWeight: 700, minWidth: 16 }}>{result}</span>
                <span style={{ flex: 1 }}>{opp ?? "—"}</span>
                <span style={{ fontWeight: 600 }}>
                  {myScore ?? "—"} – {oppScore ?? "—"}
                </span>
                <span style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>
                  {m.group ? `Grupo ${m.group}` : m.stage ?? ""}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function TeamsTab() {
  const { data: matches, isLoading, error } = useSWR("matches-all", () => analytics.matches());
  const [selected, setSelected] = useState<TeamSummary | null>(null);
  const [search, setSearch] = useState("");

  if (isLoading)
    return (
      <div className="p-6 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="h-20 rounded-lg animate-pulse" style={{ background: "var(--surface2)" }} />
        ))}
      </div>
    );

  if (error || !matches)
    return (
      <div className="flex items-center justify-center h-64">
        <p style={{ color: "var(--text-muted)" }}>Backend não disponível.</p>
      </div>
    );

  const summaries = buildTeamSummaries(matches);
  const filtered = search
    ? summaries.filter((s) => s.team.toLowerCase().includes(search.toLowerCase()))
    : summaries;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4 gap-4">
        <h2 className="text-lg font-semibold">Seleções</h2>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar seleção…"
          style={{
            background: "var(--surface2)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "6px 12px",
            color: "var(--text)",
            fontSize: "0.82rem",
            outline: "none",
          }}
          className="w-48"
        />
      </div>

      {filtered.length === 0 ? (
        <p style={{ color: "var(--text-muted)" }}>
          {summaries.length === 0
            ? "Nenhum jogo finalizado ainda."
            : "Nenhuma seleção encontrada."}
        </p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {filtered.map((s) => (
            <TeamCard key={s.team} summary={s} onClick={() => setSelected(s)} />
          ))}
        </div>
      )}

      {selected && <TeamModal team={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
