"use client";

import { useState } from "react";
import useSWR from "swr";
import { analytics, PowerRankingPlayer } from "@/lib/api";

function changeArrow(v: number | null) {
  if (v == null) return null;
  if (v > 0) return <span style={{ color: "#3fb950", fontSize: "0.7rem" }}>▲{v}</span>;
  if (v < 0) return <span style={{ color: "#f85149", fontSize: "0.7rem" }}>▼{Math.abs(v)}</span>;
  return <span style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>—</span>;
}

function score(v: number | null) {
  if (v == null) return "—";
  const pct = Math.min(100, Math.max(0, v * 10));
  const color =
    pct >= 70 ? "#3fb950" : pct >= 50 ? "#d29922" : "#f85149";
  return <span style={{ color, fontWeight: 700 }}>{v.toFixed(1)}</span>;
}

type PlayerType = "outfield" | "goalkeeper";
type SortKey = "attacking_score" | "defensive_score" | "creativity_score";

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "attacking_score", label: "Ataque" },
  { key: "defensive_score", label: "Defesa" },
  { key: "creativity_score", label: "Criatividade" },
];

export default function PowerRankingTab() {
  const [playerType, setPlayerType] = useState<PlayerType>("outfield");
  const [sortKey, setSortKey] = useState<SortKey>("attacking_score");
  const [search, setSearch] = useState("");

  const { data, isLoading, error } = useSWR(
    ["power-ranking", playerType],
    () => analytics.powerRanking({ player_type: playerType })
  );

  const filtered = (data ?? [])
    .filter((p) => {
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        (p.player_name ?? "").toLowerCase().includes(q) ||
        (p.team_name ?? "").toLowerCase().includes(q)
      );
    })
    .sort((a, b) => {
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      return bv - av;
    });

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <h2 className="text-lg font-semibold mr-2">Power Ranking FIFA</h2>

        <div style={{ display: "flex", gap: 4 }}>
          {(["outfield", "goalkeeper"] as PlayerType[]).map((t) => (
            <button
              key={t}
              onClick={() => setPlayerType(t)}
              style={{
                background: playerType === t ? "var(--accent)" : "var(--surface2)",
                color: playerType === t ? "#0d1117" : "var(--text-muted)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                padding: "4px 12px",
                fontSize: "0.78rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {t === "outfield" ? "Linha" : "Goleiros"}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", gap: 4 }}>
          {SORT_OPTIONS.filter((o) => playerType === "outfield" || o.key !== "creativity_score").map(
            (o) => (
              <button
                key={o.key}
                onClick={() => setSortKey(o.key)}
                style={{
                  background: sortKey === o.key ? "var(--surface2)" : "transparent",
                  border: `1px solid ${sortKey === o.key ? "var(--accent)" : "var(--border)"}`,
                  color: sortKey === o.key ? "var(--accent2)" : "var(--text-muted)",
                  borderRadius: 6,
                  padding: "4px 12px",
                  fontSize: "0.78rem",
                  cursor: "pointer",
                }}
              >
                {o.label}
              </button>
            )
          )}
        </div>

        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar jogador ou time…"
          style={{
            background: "var(--surface2)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "5px 12px",
            color: "var(--text)",
            fontSize: "0.82rem",
            outline: "none",
            marginLeft: "auto",
          }}
          className="w-52"
        />
      </div>

      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-10 rounded animate-pulse" style={{ background: "var(--surface2)" }} />
          ))}
        </div>
      )}

      {error && (
        <p style={{ color: "var(--text-muted)" }}>
          Power Ranking não disponível. Rode <code>fifa-analytics fifa-coletar</code> primeiro.
        </p>
      )}

      {!isLoading && !error && (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83rem" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-muted)", fontSize: "0.72rem" }}>
              <th className="py-2 text-left w-8">#</th>
              <th className="py-2 text-left">Jogador</th>
              <th className="py-2 text-left">Seleção</th>
              <th className="py-2 text-right">
                {playerType === "goalkeeper" ? "Jogo de bola" : "Ataque"}
              </th>
              <th className="py-2 text-right">
                {playerType === "goalkeeper" ? "Defesa do gol" : "Defesa"}
              </th>
              {playerType === "outfield" && <th className="py-2 text-right">Criatividade</th>}
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 100).map((p, i) => (
              <tr
                key={p.id_player}
                style={{ borderBottom: "1px solid var(--border)" }}
                className="hover:bg-white/[0.02] transition-colors"
              >
                <td className="py-2.5 text-left" style={{ color: "var(--text-muted)" }}>
                  {i + 1}
                </td>
                <td className="py-2.5 font-medium">{p.player_name ?? "—"}</td>
                <td className="py-2.5" style={{ color: "var(--text-muted)" }}>
                  {p.team_name ?? "—"}
                </td>
                <td className="py-2.5 text-right">
                  <span className="inline-flex items-center gap-1.5">
                    {score(p.attacking_score)}
                    {changeArrow(p.attacking_rank_change)}
                  </span>
                </td>
                <td className="py-2.5 text-right">
                  <span className="inline-flex items-center gap-1.5">
                    {score(p.defensive_score)}
                    {changeArrow(p.defensive_rank_change)}
                  </span>
                </td>
                {playerType === "outfield" && (
                  <td className="py-2.5 text-right">
                    <span className="inline-flex items-center gap-1.5">
                      {score(p.creativity_score)}
                      {changeArrow(p.creativity_rank_change)}
                    </span>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!isLoading && !error && filtered.length === 0 && (
        <p style={{ color: "var(--text-muted)" }}>Nenhum jogador encontrado.</p>
      )}
    </div>
  );
}
