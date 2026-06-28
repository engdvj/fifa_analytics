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
  activeStage?: string | null;
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

function viewForStage(stage?: string | null): View | null {
  if (!stage) return null;
  const normalized = stage
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  return normalized === "first stage" || normalized.includes("grupo") || normalized.includes("group")
    ? "tabela"
    : "chave";
}

export default function GruposChaveTab(props: Props) {
  const autoView = React.useMemo(() => viewForStage(props.activeStage), [props.activeStage]);
  const [manualView, setManualView] = React.useState<{ snapshot: number; view: View } | null>(null);
  const view = manualView?.snapshot === props.activeSnapshot ? manualView.view : autoView ?? "tabela";

  return (
    <div className="v2-groups-shell">
      <div className="v2-groups-subtabs">
        {SUBTABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setManualView({ snapshot: props.activeSnapshot, view: t.id })}
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
