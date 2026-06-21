"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

interface DataPoint {
  game: number;
  value: number | null;
}

interface TrajectoryChartProps {
  teams: string[];
  metric: string;
  mode: "rank" | "value";
  onModeChange: (m: "rank" | "value") => void;
  onRemoveTeam: (t: string) => void;
  dataByTeam: Record<string, DataPoint[]>;
}

function teamColor(index: number): string {
  const hue = Math.round((index * 360) / 16) % 360;
  return `hsl(${hue}, 75%, 58%)`;
}

interface TooltipPayloadEntry {
  name: string;
  value: number | null;
  color: string;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "var(--surface2)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: "8px 12px",
        fontSize: "0.78rem",
        color: "var(--text)",
        minWidth: 140,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 4, color: "var(--text-muted)" }}>
        Jogo {label}
      </div>
      {payload.map((entry) => (
        <div key={entry.name} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <span style={{ color: entry.color, fontSize: "0.9em" }}>●</span>
          <span style={{ flex: 1 }}>{entry.name}</span>
          <span style={{ fontWeight: 600, color: entry.color }}>
            {entry.value != null ? entry.value.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) : "—"}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function TrajectoryChart({
  teams,
  metric,
  mode,
  onModeChange,
  onRemoveTeam,
  dataByTeam,
}: TrajectoryChartProps) {
  if (teams.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: 200,
          color: "var(--text-muted)",
          fontSize: "0.85rem",
          gap: 8,
          border: "1px dashed var(--border)",
          borderRadius: 8,
        }}
      >
        <span style={{ fontSize: "1.4rem" }}>📈</span>
        Clique em um time no ranking para ver a trajetória aqui
      </div>
    );
  }

  // Build recharts data: array of { game, team1, team2, ... }
  const allGames = new Set<number>();
  for (const team of teams) {
    for (const pt of dataByTeam[team] ?? []) {
      if (pt.value != null) allGames.add(pt.game);
    }
  }
  const gameNumbers = [...allGames].sort((a, b) => a - b);

  // For rank mode: compute rank per game
  const rankData: Record<number, Record<string, number>> = {};
  if (mode === "rank") {
    for (const g of gameNumbers) {
      const values = teams
        .map((t) => {
          const pt = (dataByTeam[t] ?? []).find((p) => p.game === g);
          return { team: t, value: pt?.value ?? null };
        })
        .filter((x): x is { team: string; value: number } => x.value != null)
        .sort((a, b) => b.value - a.value);
      rankData[g] = {};
      values.forEach((v, i) => {
        rankData[g][v.team] = i + 1;
      });
    }
  }

  const chartData = gameNumbers.map((g) => {
    const row: Record<string, number | null | undefined> & { game: number } = { game: g };
    for (const team of teams) {
      if (mode === "value") {
        const pt = (dataByTeam[team] ?? []).find((p) => p.game === g);
        row[team] = pt?.value ?? null;
      } else {
        row[team] = rankData[g]?.[team] ?? null;
      }
    }
    return row;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
          Trajetória — {metric}
        </span>
        <div style={{ display: "flex", gap: 4, marginLeft: "auto" }}>
          {(["value", "rank"] as const).map((m) => (
            <button
              key={m}
              onClick={() => onModeChange(m)}
              style={{
                padding: "3px 10px",
                borderRadius: 6,
                fontSize: "0.75rem",
                fontWeight: 600,
                cursor: "pointer",
                border: `1px solid ${mode === m ? "var(--accent)" : "var(--border)"}`,
                background: mode === m ? "rgba(88,166,255,0.12)" : "var(--surface2)",
                color: mode === m ? "var(--accent)" : "var(--text-muted)",
              }}
            >
              {m === "value" ? "Valor" : "Ranking"}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" strokeOpacity={0.4} />
          <XAxis
            dataKey="game"
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            label={{ value: "Jogo", position: "insideBottomRight", offset: -4, fill: "var(--text-muted)", fontSize: 11 }}
          />
          <YAxis
            reversed={mode === "rank"}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            width={36}
          />
          <Tooltip content={<CustomTooltip />} />
          {teams.map((team, idx) => (
            <Line
              key={team}
              type="monotone"
              dataKey={team}
              name={team}
              stroke={teamColor(idx)}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {teams.map((team, idx) => (
          <div
            key={team}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              background: "var(--surface2)",
              borderRadius: 6,
              padding: "3px 8px",
              fontSize: "0.75rem",
            }}
          >
            <span style={{ color: teamColor(idx), fontSize: "0.9em" }}>●</span>
            <span>{team}</span>
            <button
              onClick={() => onRemoveTeam(team)}
              style={{
                color: "var(--text-muted)",
                background: "none",
                border: "none",
                cursor: "pointer",
                fontSize: "0.8rem",
                padding: "0 0 0 2px",
                lineHeight: 1,
              }}
              aria-label={`Remover ${team}`}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
