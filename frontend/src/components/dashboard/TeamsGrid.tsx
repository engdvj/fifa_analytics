"use client";

import { useState, useMemo } from "react";
import { useMatches } from "@/lib/hooks";
import { deriveTeams, TeamSummary, CONFEDERATION } from "@/lib/teamUtils";
import TeamModal from "./TeamModal";

const ALL_CONFS = ["UEFA", "CONMEBOL", "CAF", "AFC", "CONCACAF", "OFC"];

function TeamCard({ team, onClick }: { team: TeamSummary; onClick: () => void }) {
  const gd = team.gf - team.ga;
  return (
    <div
      onClick={onClick}
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "14px 16px",
        cursor: "pointer",
        transition: "border-color 0.15s, background 0.15s",
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "var(--accent)";
        (e.currentTarget as HTMLDivElement).style.background = "var(--surface2)";
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border)";
        (e.currentTarget as HTMLDivElement).style.background = "var(--surface)";
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div>
          <p style={{ color: "var(--text)", fontWeight: 600, fontSize: 14, margin: 0 }}>{team.name}</p>
          <p style={{ color: "var(--text-muted)", fontSize: 11, margin: "2px 0 0" }}>
            {team.confederation}{team.group ? ` · Grupo ${team.group}` : ""}
          </p>
        </div>
        {team.played > 0 && (
          <span style={{
            background: team.points >= team.played * 2 ? "var(--green)"
              : team.points >= team.played ? "var(--yellow)"
                : "var(--surface2)",
            color: team.points >= team.played ? "white" : "var(--text-muted)",
            borderRadius: 6,
            padding: "2px 8px",
            fontSize: 12,
            fontWeight: 700,
            flexShrink: 0,
          }}>
            {team.points} pts
          </span>
        )}
      </div>

      {team.played > 0 ? (
        <div style={{ marginTop: 10, display: "flex", gap: 12, fontSize: 12 }}>
          <span style={{ color: "var(--text-muted)" }}>
            {team.wins}V {team.draws}E {team.losses}D
          </span>
          <span style={{ color: "var(--text-muted)" }}>
            {team.gf}:{team.ga}
            <span style={{ marginLeft: 4, color: gd > 0 ? "var(--green)" : gd < 0 ? "var(--red)" : "var(--text-muted)" }}>
              ({gd > 0 ? "+" : ""}{gd})
            </span>
          </span>
        </div>
      ) : (
        <p style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 8 }}>Sem jogos</p>
      )}
    </div>
  );
}

export default function TeamsGrid() {
  const { matches, isLoading } = useMatches();

  const [search, setSearch] = useState("");
  const [groupFilter, setGroupFilter] = useState("Todos");
  const [confFilter, setConfFilter] = useState("Todas");
  const [onlyWithGames, setOnlyWithGames] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState<TeamSummary | null>(null);

  const teams = useMemo(() => deriveTeams(matches), [matches]);

  const groups = useMemo(() => {
    const gs = new Set<string>();
    for (const t of teams) if (t.group) gs.add(t.group);
    return Array.from(gs).sort();
  }, [teams]);

  const filtered = useMemo(() => {
    return teams.filter(t => {
      if (search && !t.name.toLowerCase().includes(search.toLowerCase())) return false;
      if (groupFilter !== "Todos" && t.group !== groupFilter) return false;
      if (confFilter !== "Todas" && t.confederation !== confFilter) return false;
      if (onlyWithGames && t.played === 0) return false;
      return true;
    });
  }, [teams, search, groupFilter, confFilter, onlyWithGames]);

  if (isLoading) {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 10 }}>
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 10,
            height: 90,
            animation: "pulse 1.5s infinite",
          }} />
        ))}
      </div>
    );
  }

  return (
    <div>
      {/* Filters */}
      <div style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 10,
        marginBottom: 16,
        alignItems: "center",
      }}>
        <input
          type="text"
          placeholder="Buscar seleção..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            background: "var(--surface2)",
            border: "1px solid var(--border)",
            borderRadius: 7,
            padding: "6px 12px",
            color: "var(--text)",
            fontSize: 13,
            outline: "none",
            width: 200,
          }}
        />

        <select
          value={groupFilter}
          onChange={e => setGroupFilter(e.target.value)}
          style={{
            background: "var(--surface2)",
            border: "1px solid var(--border)",
            borderRadius: 7,
            padding: "6px 10px",
            color: "var(--text)",
            fontSize: 13,
          }}
        >
          <option value="Todos">Todos os grupos</option>
          {groups.map(g => <option key={g} value={g}>Grupo {g}</option>)}
        </select>

        <select
          value={confFilter}
          onChange={e => setConfFilter(e.target.value)}
          style={{
            background: "var(--surface2)",
            border: "1px solid var(--border)",
            borderRadius: 7,
            padding: "6px 10px",
            color: "var(--text)",
            fontSize: 13,
          }}
        >
          <option value="Todas">Todas as confederações</option>
          {ALL_CONFS.map(c => <option key={c} value={c}>{c}</option>)}
        </select>

        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--text-muted)", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={onlyWithGames}
            onChange={e => setOnlyWithGames(e.target.checked)}
            style={{ accentColor: "var(--accent)" }}
          />
          Só com jogos
        </label>

        <span style={{ color: "var(--text-muted)", fontSize: 12, marginLeft: "auto" }}>
          {filtered.length} {filtered.length === 1 ? "seleção" : "seleções"}
        </span>
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Nenhuma seleção encontrada.</p>
      ) : (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 10,
        }}>
          {filtered.map(t => (
            <TeamCard key={t.name} team={t} onClick={() => setSelectedTeam(t)} />
          ))}
        </div>
      )}

      {/* Modal */}
      {selectedTeam && (
        <TeamModal team={selectedTeam} onClose={() => setSelectedTeam(null)} />
      )}
    </div>
  );
}
