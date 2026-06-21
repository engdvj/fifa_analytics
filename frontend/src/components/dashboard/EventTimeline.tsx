"use client";

import { MatchEvent } from "@/lib/api";

function parseMinute(m: string | null): number {
  if (!m) return 999;
  const clean = m.replace(/'/g, "").replace("+", ".");
  return parseFloat(clean) || 999;
}

function eventIcon(e: MatchEvent): string {
  if (e.event_type === "goal") return "⚽";
  if (e.event_type === "substitution") return "🔄";
  const d = (e.detail ?? "").toLowerCase();
  if (d.includes("yellow") || d.includes("amarelo")) return "🟨";
  if (d.includes("red") || d.includes("vermelho")) return "🟥";
  return "🟨";
}

interface EventTimelineProps {
  events: MatchEvent[];
  homeTeam: string;
  awayTeam: string;
  homeIdTeam: string;
}

export default function EventTimeline({ events, homeIdTeam }: EventTimelineProps) {
  const sorted = [...events].sort((a, b) => parseMinute(a.minute) - parseMinute(b.minute));

  if (sorted.length === 0) {
    return <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Nenhum evento registrado.</p>;
  }

  return (
    <div style={{ position: "relative", padding: "0 8px" }}>
      <div style={{
        position: "absolute",
        left: "50%",
        top: 0,
        bottom: 0,
        width: 1,
        background: "var(--border)",
        transform: "translateX(-50%)",
        pointerEvents: "none",
      }} />

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {sorted.map((evt, i) => {
          const isHome = evt.id_team === homeIdTeam;
          const icon = eventIcon(evt);

          const playerLabel =
            evt.event_type === "substitution" ? (
              <span>
                <span style={{ color: "var(--red)" }}>{evt.player_name ?? "?"}</span>
                {evt.player2_name && (
                  <span style={{ color: "var(--green)" }}> / {evt.player2_name}</span>
                )}
              </span>
            ) : (
              <span>{evt.player_name ?? "?"}</span>
            );

          return (
            <div key={i} style={{
              display: "grid",
              gridTemplateColumns: "1fr 56px 1fr",
              alignItems: "center",
              gap: 6,
            }}>
              <div style={{ textAlign: "right", fontSize: 12, color: "var(--text)" }}>
                {isHome ? playerLabel : null}
              </div>

              <div style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 2,
                zIndex: 1,
              }}>
                <div style={{
                  background: "var(--surface2)",
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  padding: "2px 7px",
                  fontSize: 11,
                  color: "var(--text-muted)",
                  whiteSpace: "nowrap",
                }}>
                  {evt.minute ?? "?"}
                </div>
                <span style={{ fontSize: 14, lineHeight: 1 }}>{icon}</span>
              </div>

              <div style={{ textAlign: "left", fontSize: 12, color: "var(--text)" }}>
                {!isHome ? playerLabel : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
