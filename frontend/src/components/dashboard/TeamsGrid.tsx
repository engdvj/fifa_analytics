"use client";

import { useState, useMemo } from "react";
import { useMatches } from "@/lib/hooks";
import { deriveTeams, TeamSummary, CONFEDERATION, flag, getKit } from "@/lib/teamUtils";
import TeamModal from "./TeamModal";
import { DefinitionBubble } from "@/components/DefinitionLink";

const ALL_CONFS = ["UEFA", "CONMEBOL", "CAF", "AFC", "CONCACAF", "OFC"];

function TeamCard({ team, onClick }: { team: TeamSummary; onClick: () => void }) {
  const [hovered, setHovered] = useState(false);
  const kit = getKit(team.name);
  const gd = team.gf - team.ga;

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: "var(--surface)",
        border: `1px solid ${hovered ? kit.main + "88" : "var(--border)"}`,
        borderRadius: 12,
        padding: 0,
        cursor: "pointer",
        transition: "border-color 0.15s, box-shadow 0.15s",
        overflow: "hidden",
        boxShadow: hovered ? `0 8px 26px ${kit.main}22` : "none",
      }}
    >
      {/* Topo colorido com gradiente do kit */}
      <div style={{
        background: `linear-gradient(135deg, ${kit.main}33, ${kit.main}11)`,
        borderBottom: `1px solid ${kit.main}33`,
        padding: "12px 14px",
        display: "flex", alignItems: "center", gap: 10,
      }}>
        {/* Bandeira grande */}
        <span style={{ fontSize: 28, lineHeight: 1, flexShrink: 0 }}>{flag(team.name)}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            color: "var(--text)", fontWeight: 700, fontSize: 14, margin: 0,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {team.name}
          </p>
          <p style={{ color: "var(--text-muted)", fontSize: 11, margin: "2px 0 0" }}>
            {team.confederation}{team.group ? ` · Grupo ${team.group}` : ""}
          </p>
        </div>
        {/* Mini jersey com pontos */}
        {team.played > 0 && (
          <div style={{
            width: 32, height: 32, borderRadius: 6,
            background: kit.main, border: `2px solid ${kit.border}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14, fontWeight: 800, color: kit.text, flexShrink: 0,
          }}>
            {team.points}
          </div>
        )}
      </div>

      {/* Corpo */}
      <div style={{ padding: "10px 14px" }}>
        {team.played > 0 ? (
          <>
            {/* V/E/D row */}
            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              {[
                { label: "V", value: team.wins, color: "var(--green)" },
                { label: "E", value: team.draws, color: "var(--yellow)" },
                { label: "D", value: team.losses, color: "var(--red)" },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ textAlign: "center", flex: 1 }}>
                  <div style={{ fontSize: 16, fontWeight: 700, color }}>{value}</div>
                  <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{label}</div>
                </div>
              ))}
              <div style={{ width: 1, background: "var(--border)", margin: "2px 0" }} />
              <div style={{ textAlign: "center", flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text)" }}>
                  {team.gf}:{team.ga}
                </div>
                <div style={{ fontSize: 10, color: "var(--text-muted)" }}>Gols</div>
              </div>
              <div style={{ textAlign: "center", flex: 1 }}>
                <div style={{
                  fontSize: 14, fontWeight: 700,
                  color: gd > 0 ? "var(--green)" : gd < 0 ? "var(--red)" : "var(--text-muted)",
                }}>
                  {gd > 0 ? `+${gd}` : gd}
                </div>
                <div style={{ fontSize: 10, color: "var(--text-muted)" }}>Saldo<DefinitionBubble id="saldo_gols" size={11} /></div>
              </div>
            </div>

            {/* Barra de pontos */}
            <div style={{ height: 4, background: "var(--surface2)", borderRadius: 2, overflow: "hidden" }}>
              <div style={{
                height: "100%",
                width: `${Math.min(100, (team.points / (team.played * 3)) * 100)}%`,
                background: kit.main,
                borderRadius: 2,
              }} />
            </div>
            <p style={{ fontSize: 10, color: "var(--text-muted)", margin: "4px 0 0", textAlign: "right" }}>
              {team.played} {team.played === 1 ? "jogo" : "jogos"}
            </p>
          </>
        ) : (
          <p style={{ color: "var(--text-muted)", fontSize: 12, textAlign: "center", padding: "8px 0" }}>
            Aguardando jogos
          </p>
        )}
      </div>
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
