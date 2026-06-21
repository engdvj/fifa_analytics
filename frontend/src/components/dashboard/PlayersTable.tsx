"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import { analytics, PowerRankingPlayer } from "@/lib/api";
import { scoreColor, positionLabel, compositeScore, rankLabel } from "@/lib/playerUtils";
import PlayerModal from "@/components/dashboard/PlayerModal";

const PAGE_SIZE = 25;

type SortKey =
  | "attacking_score"
  | "defensive_score"
  | "creativity_score"
  | "composite"
  | "player_name"
  | "team_name";
type SortDir = "asc" | "desc";

function ScoreCell({ value, change }: { value: number | null; change: number | null }) {
  const { arrow, color } = rankLabel(null, change);
  return (
    <span className="inline-flex items-center gap-1">
      <span style={{ color: scoreColor(value), fontWeight: 700 }}>
        {value !== null ? value.toFixed(1) : "—"}
      </span>
      {change !== null && change !== 0 && (
        <span style={{ fontSize: "0.7rem", color, fontWeight: 600 }}>
          {arrow}{Math.abs(change)}
        </span>
      )}
    </span>
  );
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: PAGE_SIZE }).map((_, i) => (
        <tr key={i}>
          {Array.from({ length: 8 }).map((_, j) => (
            <td key={j} className="py-2.5 px-2">
              <div
                className="h-4 rounded animate-pulse"
                style={{ background: "var(--surface2)", width: j === 1 ? 120 : j === 2 ? 80 : 40 }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export default function PlayersTable() {
  const [playerType, setPlayerType] = useState<"" | "outfield" | "goalkeeper">("");
  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("attacking_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<PowerRankingPlayer | null>(null);

  const { data, isLoading, error } = useSWR(
    ["power-ranking-table", playerType],
    () => analytics.powerRanking(playerType ? { player_type: playerType } : undefined)
  );

  const allPlayers = data ?? [];

  const teams = useMemo(() => {
    const s = new Set(allPlayers.map((p) => p.team_name).filter(Boolean) as string[]);
    return Array.from(s).sort();
  }, [allPlayers]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return allPlayers.filter((p) => {
      if (q && !(p.player_name ?? "").toLowerCase().includes(q) && !(p.team_name ?? "").toLowerCase().includes(q)) return false;
      if (teamFilter && p.team_name !== teamFilter) return false;
      return true;
    });
  }, [allPlayers, search, teamFilter]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let av: number | string | null;
      let bv: number | string | null;
      if (sortKey === "composite") {
        av = compositeScore(a);
        bv = compositeScore(b);
      } else if (sortKey === "player_name" || sortKey === "team_name") {
        av = a[sortKey] ?? "";
        bv = b[sortKey] ?? "";
      } else {
        av = a[sortKey];
        bv = b[sortKey];
      }
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const pageSlice = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
    setPage(1);
  }

  function handleFilter(fn: () => void) {
    fn();
    setPage(1);
  }

  const thStyle = (key: SortKey): React.CSSProperties => ({
    cursor: "pointer",
    userSelect: "none",
    color: sortKey === key ? "var(--accent)" : "var(--text-muted)",
    fontWeight: sortKey === key ? 700 : 500,
    background: sortKey === key ? "rgba(88,166,255,0.06)" : "transparent",
    padding: "8px 8px",
    fontSize: "0.72rem",
    whiteSpace: "nowrap",
  });

  const sortArrow = (key: SortKey) =>
    sortKey === key ? (sortDir === "desc" ? " ↓" : " ↑") : "";

  const inputStyle: React.CSSProperties = {
    background: "var(--surface2)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    padding: "5px 10px",
    color: "var(--text)",
    fontSize: "0.82rem",
    outline: "none",
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <h2 className="text-lg font-semibold" style={{ color: "var(--text)" }}>
          Jogadores
        </h2>
        {!isLoading && (
          <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
            {filtered.length} jogadores
          </span>
        )}
        <div style={{ display: "flex", gap: 4 }}>
          {([
            ["", "Todos"],
            ["outfield", "Linha"],
            ["goalkeeper", "Goleiros"],
          ] as Array<["" | "outfield" | "goalkeeper", string]>).map(([val, label]) => (
            <button
              key={val}
              onClick={() => handleFilter(() => setPlayerType(val))}
              style={{
                background: playerType === val ? "var(--accent)" : "var(--surface2)",
                color: playerType === val ? "#0d1117" : "var(--text-muted)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                padding: "4px 12px",
                fontSize: "0.78rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <select
          value={teamFilter}
          onChange={(e) => handleFilter(() => setTeamFilter(e.target.value))}
          style={{ ...inputStyle, minWidth: 140 }}
        >
          <option value="">Todas as seleções</option>
          {teams.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <input
          type="text"
          value={search}
          onChange={(e) => handleFilter(() => setSearch(e.target.value))}
          placeholder="Buscar jogador ou time…"
          style={{ ...inputStyle, marginLeft: "auto", width: 220 }}
        />
      </div>
      {error && (
        <p style={{ color: "var(--text-muted)" }}>
          Dados não disponíveis. Rode <code>fifa-analytics fifa-coletar</code> primeiro.
        </p>
      )}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83rem", minWidth: 640 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th style={{ ...thStyle("player_name"), textAlign: "left", width: 32 }}>#</th>
              <th
                style={{ ...thStyle("player_name"), textAlign: "left" }}
                onClick={() => handleSort("player_name")}
              >
                Jogador{sortArrow("player_name")}
              </th>
              <th
                style={{ ...thStyle("team_name"), textAlign: "left" }}
                onClick={() => handleSort("team_name")}
              >
                Seleção{sortArrow("team_name")}
              </th>
              <th style={{ ...thStyle("player_name"), textAlign: "left", width: 60 }}>Tipo</th>
              <th
                style={{ ...thStyle("attacking_score"), textAlign: "right" }}
                onClick={() => handleSort("attacking_score")}
              >
                Ataque{sortArrow("attacking_score")}
              </th>
              <th
                style={{ ...thStyle("defensive_score"), textAlign: "right" }}
                onClick={() => handleSort("defensive_score")}
              >
                Defesa{sortArrow("defensive_score")}
              </th>
              <th
                style={{ ...thStyle("creativity_score"), textAlign: "right" }}
                onClick={() => handleSort("creativity_score")}
              >
                Criatividade{sortArrow("creativity_score")}
              </th>
              <th
                style={{ ...thStyle("composite"), textAlign: "right" }}
                onClick={() => handleSort("composite")}
              >
                Score{sortArrow("composite")}
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonRows />
            ) : pageSlice.length === 0 ? (
              <tr>
                <td
                  colSpan={8}
                  style={{ padding: "32px 8px", color: "var(--text-muted)", textAlign: "center" }}
                >
                  Nenhum jogador encontrado.
                </td>
              </tr>
            ) : (
              pageSlice.map((p, idx) => {
                const rowNum = (page - 1) * PAGE_SIZE + idx + 1;
                const comp = compositeScore(p);
                const isGoalkeeper = p.player_type === "goalkeeper";
                return (
                  <tr
                    key={p.id_player}
                    onClick={() => setSelected(p)}
                    style={{ borderBottom: "1px solid var(--border)", cursor: "pointer" }}
                    className="hover:bg-white/[0.02] transition-colors"
                  >
                    <td className="py-2.5 px-2" style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                      {rowNum}
                    </td>
                    <td className="py-2.5 px-2 font-medium" style={{ color: "var(--text)" }}>
                      {p.player_name ?? "—"}
                    </td>
                    <td className="py-2.5 px-2" style={{ color: "var(--text-muted)" }}>
                      {p.team_name ?? "—"}
                    </td>
                    <td className="py-2.5 px-2" style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                      {positionLabel(p.player_type)}
                    </td>
                    <td className="py-2.5 px-2 text-right">
                      <ScoreCell value={p.attacking_score} change={p.attacking_rank_change} />
                    </td>
                    <td className="py-2.5 px-2 text-right">
                      <ScoreCell value={p.defensive_score} change={p.defensive_rank_change} />
                    </td>
                    <td className="py-2.5 px-2 text-right">
                      {isGoalkeeper ? (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      ) : (
                        <ScoreCell value={p.creativity_score} change={p.creativity_rank_change} />
                      )}
                    </td>
                    <td className="py-2.5 px-2 text-right">
                      <span style={{ color: scoreColor(comp), fontWeight: 700 }}>
                        {comp !== null ? comp.toFixed(1) : "—"}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      {!isLoading && totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-5">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              background: "var(--surface2)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              padding: "5px 14px",
              color: page === 1 ? "var(--text-muted)" : "var(--text)",
              cursor: page === 1 ? "not-allowed" : "pointer",
              fontSize: "0.85rem",
            }}
          >
            ‹
          </button>
          <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={{
              background: "var(--surface2)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              padding: "5px 14px",
              color: page === totalPages ? "var(--text-muted)" : "var(--text)",
              cursor: page === totalPages ? "not-allowed" : "pointer",
              fontSize: "0.85rem",
            }}
          >
            ›
          </button>
        </div>
      )}
      {selected && (
        <PlayerModal
          player={selected}
          allPlayers={allPlayers}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
