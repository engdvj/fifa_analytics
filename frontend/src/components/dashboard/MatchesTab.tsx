"use client";

import useSWR from "swr";
import { analytics, Match } from "@/lib/api";

function statusBadge(status: Match["status"]) {
  const map = {
    finalizado: { label: "FIM", color: "#3fb950" },
    em_andamento: { label: "AO VIVO", color: "#d29922" },
    agendado: { label: "—", color: "#8b949e" },
  } as const;
  const { label, color } = map[status] ?? map.agendado;
  return (
    <span style={{ color, fontWeight: 700, fontSize: "0.7rem", letterSpacing: "0.05em" }}>
      {label}
    </span>
  );
}

function scoreCell(a: number | null, b: number | null) {
  if (a == null || b == null) return <span style={{ color: "var(--text-muted)" }}>vs</span>;
  return (
    <span style={{ fontWeight: 700, fontSize: "1rem" }}>
      {a} – {b}
    </span>
  );
}

export default function MatchesTab() {
  const { data: matches, error, isLoading } = useSWR("matches", () => analytics.matches());

  if (isLoading) return <Skeleton />;
  if (error || !matches)
    return <Empty text="Não foi possível carregar os jogos. O backend está rodando?" />;

  const byStage: Record<string, Match[]> = {};
  for (const m of matches) {
    const s = m.stage ?? "Sem fase";
    (byStage[s] ??= []).push(m);
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--text)" }}>
        Calendário — Copa 2026
      </h2>

      {Object.entries(byStage).map(([stage, games]) => (
        <section key={stage} className="mb-8">
          <h3
            className="text-xs font-bold uppercase tracking-widest mb-3"
            style={{ color: "var(--text-muted)" }}
          >
            {stage}
          </h3>
          <div className="grid gap-2">
            {games.map((m) => (
              <div
                key={m.match_id}
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
                className="flex items-center px-4 py-3 gap-4"
              >
                <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", minWidth: 20 }}>
                  {m.match_number}
                </span>

                <span className="flex-1 text-right text-sm font-medium truncate">
                  {m.home_team ?? "—"}
                </span>

                <div className="flex flex-col items-center gap-0.5 min-w-[80px] text-center">
                  {scoreCell(m.home_score, m.away_score)}
                  <div>{statusBadge(m.status)}</div>
                </div>

                <span className="flex-1 text-left text-sm font-medium truncate">
                  {m.away_team ?? "—"}
                </span>

                <span style={{ color: "var(--text-muted)", fontSize: "0.72rem", minWidth: 80, textAlign: "right" }}>
                  {m.group ? `Grupo ${m.group}` : m.stage ?? ""}
                </span>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-2">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="h-12 rounded-lg animate-pulse"
          style={{ background: "var(--surface2)" }}
        />
      ))}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="flex items-center justify-center h-64">
      <p style={{ color: "var(--text-muted)" }}>{text}</p>
    </div>
  );
}
