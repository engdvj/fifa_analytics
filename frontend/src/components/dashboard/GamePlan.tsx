"use client";

import React from "react";
import { Match } from "@/lib/api";
import PrescritivaView from "@/components/dashboard/PrescritivaView";
import PreventivaView from "@/components/dashboard/PreventivaView";

/**
 * "Plano de jogo" — funde as antigas abas Prescritiva (ações) e Preventiva
 * (riscos) numa seção única, lado a lado. Ambas já consomem os mesmos dados
 * (snapshot + previsão), então aqui só as compomos sob um cabeçalho comum.
 *
 * Aparece apenas para jogos FUTUROS (faz sentido planejar antes do jogo).
 */
export default function GamePlan({
  snapshot,
  enabled,
  matches,
  selectedTeams,
}: {
  snapshot: number;
  enabled: boolean;
  matches: Match[];
  selectedTeams: string[];
}) {
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 10, overflow: "hidden" }}>
      <div style={{ padding: "12px 16px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 800 }}>
          Plano de jogo
        </div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 3, lineHeight: 1.4 }}>
          O que fazer (ações) e o que evitar (riscos), orientado pela previsão deste jogo.
        </div>
      </div>
      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 18 }}>
        <PlanSection title="O que fazer">
          <PrescritivaView snapshot={snapshot} enabled={enabled} matches={matches} selectedTeams={selectedTeams} />
        </PlanSection>
        <PlanSection title="O que evitar">
          <PreventivaView snapshot={snapshot} enabled={enabled} matches={matches} selectedTeams={selectedTeams} />
        </PlanSection>
      </div>
    </section>
  );
}

function PlanSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 12.5, fontWeight: 800, color: "var(--text)", marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  );
}
