"use client";

import React from "react";
import { Match, TeamSnapshot } from "@/lib/api";
import GruposTab from "./GruposTab";
import BracketTab from "./BracketTab";

type View = "tabela" | "chave";

interface Props {
  matches: Match[];
  snapshots: TeamSnapshot[];
  activeSnapshot: number;
  matchSnapshot: Map<string, number>;
  filters: { group: string; confed: string; stage: string };
  passesFilters: (team: string) => boolean;
  selectedTeams: string[];
  onToggleTeam: (team: string) => void;
  metric: string;
  search?: string;
}

const SUBTABS: { id: View; label: string }[] = [
  { id: "tabela", label: "Grupos" },
  { id: "chave", label: "Chave do mata-mata" },
];

export default function GruposChaveTab(props: Props) {
  const [view, setView] = React.useState<View>("tabela");
  return (
    <div>
      <div style={{ display: "inline-flex", gap: 4, background: "#0d1117", border: "1px solid #21262d", borderRadius: 9, padding: 4, marginBottom: 16 }}>
        {SUBTABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setView(t.id)}
            style={{
              border: 0, borderRadius: 6, padding: "6px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer", fontFamily: "inherit",
              background: view === t.id ? "#1f6feb" : "transparent", color: view === t.id ? "#fff" : "#8b949e",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>
      {view === "tabela" ? (
        <GruposTab {...props} />
      ) : (
        <BracketTab
          matches={props.matches}
          selectedTeams={props.selectedTeams}
          onToggleTeam={props.onToggleTeam}
          search={props.search}
        />
      )}
    </div>
  );
}
