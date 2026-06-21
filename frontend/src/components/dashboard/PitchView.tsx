"use client";

import { useState } from "react";
import { LineupPlayer, MatchEvent } from "@/lib/api";
import { getKit } from "@/lib/teamUtils";

const W = 620;
const H = 420;
const PAD = 28;

function defaultXY(position: string | null, idx: number): [number, number] {
  const p = (position ?? "").toUpperCase();
  if (p.startsWith("G")) return [50, 5];
  if (p.includes("CB") || p.includes("CD") || (p.startsWith("D") && !p.includes("M"))) {
    const xs = [25, 42, 58, 75];
    return [xs[idx % xs.length] ?? 50, 25];
  }
  if (p.includes("LB") || p.includes("LE") || p.includes("LI")) return [15, 32];
  if (p.includes("RB") || p.includes("RD") || p.includes("RE")) return [85, 32];
  if (p.includes("DM") || p.includes("MDC") || p.includes("VOL")) return [50, 42];
  if (p.includes("LM") || p.includes("ME")) return [15, 52];
  if (p.includes("RM")) return [85, 52];
  if (p.includes("CM") || p.includes("MC") || p.startsWith("M")) {
    const xs = [35, 50, 65];
    return [xs[idx % xs.length] ?? 50, 52];
  }
  if (p.includes("AM") || p.includes("CAM") || p.includes("MEA")) return [50, 66];
  if (p.includes("LW") || p.includes("ED") || p.includes("EA")) return [18, 76];
  if (p.includes("RW") || p.includes("ED")) return [82, 76];
  if (p.includes("CF") || p.includes("CA") || p.startsWith("F") || p.includes("SS")) {
    const xs = [38, 62];
    return [xs[idx % xs.length] ?? 50, 82];
  }
  return [50, 50];
}

function toSVG(
  lx: number | null,
  ly: number | null,
  position: string | null,
  idx: number,
  side: "home" | "away"
): [number, number] {
  const [dx, dy] =
    lx != null && ly != null ? [lx, ly] : defaultXY(position, idx);

  const svgY = PAD + (dx / 100) * (H - PAD * 2);

  if (side === "home") {
    const svgX = PAD + (dy / 100) * (W / 2 - PAD);
    return [svgX, svgY];
  }
  const svgX = W - PAD - (dy / 100) * (W / 2 - PAD);
  return [svgX, svgY];
}

function shortName(name: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(" ");
  return parts[parts.length - 1].slice(0, 8);
}

interface PitchViewProps {
  homePlayers: LineupPlayer[];
  awayPlayers: LineupPlayer[];
  homeTeam: string;
  awayTeam: string;
  events: MatchEvent[];
  homeIdTeam: string;
}

export default function PitchView({
  homePlayers,
  awayPlayers,
  homeTeam,
  awayTeam,
  events,
  homeIdTeam,
}: PitchViewProps) {
  const [hovered, setHovered] = useState<string | null>(null);

  const homeKit = getKit(homeTeam);
  const awayKit = getKit(awayTeam);

  const goalPlayers = new Set(events.filter(e => e.event_type === "goal").map(e => e.id_player));
  const yellowCards = new Set(
    events
      .filter(e => e.event_type === "card" &&
        (e.detail ?? "").toLowerCase().includes("yellow") ||
        (e.detail ?? "").toLowerCase().includes("amarelo"))
      .map(e => e.id_player)
  );
  const redCards = new Set(
    events
      .filter(e => e.event_type === "card" &&
        ((e.detail ?? "").toLowerCase().includes("red") ||
          (e.detail ?? "").toLowerCase().includes("vermelho")))
      .map(e => e.id_player)
  );

  const subInMinute = new Map<string, string>();
  for (const e of events) {
    if (e.event_type === "substitution" && e.id_player2) {
      subInMinute.set(e.id_player2, e.minute ?? "?");
    }
  }

  const starters = {
    home: homePlayers.filter(p => p.is_starter),
    away: awayPlayers.filter(p => p.is_starter),
  };
  const subs = {
    home: homePlayers.filter(p => !p.is_starter),
    away: awayPlayers.filter(p => !p.is_starter),
  };

  function renderPlayer(p: LineupPlayer, side: "home" | "away", idx: number) {
    const [cx, cy] = toSVG(p.lineup_x, p.lineup_y, p.position, idx, side);
    const isHovered = hovered === p.id_player;
    const kit = side === "home" ? homeKit : awayKit;
    const r = isHovered ? 19 : 15;

    return (
      <g
        key={p.id_player}
        onMouseEnter={() => setHovered(p.id_player)}
        onMouseLeave={() => setHovered(null)}
        style={{ cursor: "default" }}
      >
        <circle
          cx={cx} cy={cy} r={r}
          fill={kit.main}
          stroke={isHovered ? "#58a6ff" : kit.border}
          strokeWidth={isHovered ? 2.5 : 2}
          style={{ transition: "r 0.12s, stroke 0.12s" }}
        />
        <text x={cx} y={cy + 4} textAnchor="middle" fill={kit.text} fontSize={9.5} fontWeight="700">
          {p.shirt_number ?? "?"}
        </text>
        <text x={cx} y={cy + 27} textAnchor="middle" fill={`${kit.text}99`} fontSize={8}>
          {shortName(p.player_name)}
        </text>
        {p.captain && (
          <text x={cx + r - 2} y={cy - r + 6} fontSize={8} fill="#fbbf24">©</text>
        )}
        {goalPlayers.has(p.id_player) && (
          <text x={cx + r} y={cy - r + 5} fontSize={10}>⚽</text>
        )}
        {yellowCards.has(p.id_player) && !redCards.has(p.id_player) && (
          <text x={cx + r} y={cy + 4} fontSize={10}>🟨</text>
        )}
        {redCards.has(p.id_player) && (
          <text x={cx + r} y={cy + 4} fontSize={10}>🟥</text>
        )}
        {isHovered && (
          <g>
            <rect x={cx - 58} y={cy - 48} width={116} height={20} rx={4}
              fill="#21262d" stroke="#30363d" strokeWidth={1} />
            <text x={cx} y={cy - 34} textAnchor="middle" fill="#e6edf3" fontSize={10}>
              {p.player_name ?? "?"} {p.captain ? "©" : ""}
            </text>
          </g>
        )}
      </g>
    );
  }

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", maxWidth: W, display: "block", margin: "0 auto", borderRadius: 8 }}
      >
        <defs>
          <pattern id="pitch-stripes" patternUnits="userSpaceOnUse" width="100%" height={H / 9}>
            <rect width="100%" height={H / 9} fill="#166534" />
            <rect y={H / 18} width="100%" height={H / 18} fill="#14532d" />
          </pattern>
        </defs>

        {/* Grass with stripes */}
        <rect width={W} height={H} fill="url(#pitch-stripes)" rx={8} />

        {/* Pitch lines */}
        <rect x={PAD} y={PAD} width={W - PAD * 2} height={H - PAD * 2}
          fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth={1.5} />
        <line x1={W / 2} y1={PAD} x2={W / 2} y2={H - PAD}
          stroke="rgba(255,255,255,0.25)" strokeWidth={1.5} />
        <circle cx={W / 2} cy={H / 2} r={52}
          fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth={1.5} />
        <circle cx={W / 2} cy={H / 2} r={3} fill="rgba(255,255,255,0.4)" />

        {/* Penalty areas */}
        <rect x={PAD} y={H / 2 - 72} width={82} height={144}
          fill="none" stroke="rgba(255,255,255,0.22)" strokeWidth={1} />
        <rect x={W - PAD - 82} y={H / 2 - 72} width={82} height={144}
          fill="none" stroke="rgba(255,255,255,0.22)" strokeWidth={1} />
        {/* Goals */}
        <rect x={PAD - 12} y={H / 2 - 32} width={12} height={64}
          fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth={1.5} />
        <rect x={W - PAD} y={H / 2 - 32} width={12} height={64}
          fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth={1.5} />

        {/* Team labels */}
        <text x={PAD + 10} y={PAD + 16} fill="rgba(255,255,255,0.45)" fontSize={10}>
          {homeTeam}
        </text>
        <text x={W - PAD - 10} y={PAD + 16} textAnchor="end" fill="rgba(255,255,255,0.45)" fontSize={10}>
          {awayTeam}
        </text>

        {/* Players */}
        {starters.home.map((p, i) => renderPlayer(p, "home", i))}
        {starters.away.map((p, i) => renderPlayer(p, "away", i))}
      </svg>

      {/* Subs */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
        {(["home", "away"] as const).map(side => (
          <div key={side}>
            <p style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }}>
              Reservas — {side === "home" ? homeTeam : awayTeam}
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {subs[side].map(p => {
                const minute = subInMinute.get(p.id_player);
                return (
                  <span key={p.id_player} style={{
                    background: "var(--surface2)",
                    border: "1px solid var(--border)",
                    borderRadius: 4,
                    padding: "2px 7px",
                    fontSize: 11,
                    color: minute ? "var(--green)" : "var(--text-muted)",
                  }}>
                    {p.shirt_number ? `#${p.shirt_number} ` : ""}{p.player_name}
                    {minute && ` ↑${minute}`}
                  </span>
                );
              })}
              {subs[side].length === 0 && (
                <span style={{ fontSize: 11, color: "var(--text-muted)" }}>—</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Event Timeline below */}
      {events.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <p style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 8 }}>Eventos</p>
          <div style={{ position: "relative" }}>
            <div style={{
              position: "absolute", left: "50%", top: 0, bottom: 0,
              width: 1, background: "var(--border)", transform: "translateX(-50%)",
            }} />
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[...events]
                .sort((a, b) => {
                  const parse = (m: string | null) => parseFloat((m ?? "999").replace(/'/g, "").replace("+", ".")) || 999;
                  return parse(a.minute) - parse(b.minute);
                })
                .map((evt, i) => {
                  const isHome = evt.id_team === homeIdTeam;
                  const icon = evt.event_type === "goal" ? "⚽"
                    : evt.event_type === "substitution" ? "🔄"
                      : (evt.detail ?? "").toLowerCase().includes("yellow") ? "🟨" : "🟥";
                  const label = evt.event_type === "substitution"
                    ? <span><span style={{ color: "var(--red)" }}>{evt.player_name}</span>{evt.player2_name && <span style={{ color: "var(--green)" }}> / {evt.player2_name}</span>}</span>
                    : <span>{evt.player_name}</span>;
                  return (
                    <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 52px 1fr", alignItems: "center", gap: 4 }}>
                      <div style={{ textAlign: "right", fontSize: 11, color: "var(--text)" }}>{isHome ? label : null}</div>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1, zIndex: 1 }}>
                        <span style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 10, padding: "1px 6px", fontSize: 10, color: "var(--text-muted)" }}>{evt.minute}</span>
                        <span style={{ fontSize: 12 }}>{icon}</span>
                      </div>
                      <div style={{ textAlign: "left", fontSize: 11, color: "var(--text)" }}>{!isHome ? label : null}</div>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
