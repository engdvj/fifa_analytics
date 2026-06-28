"use client";

import React from "react";
import * as echarts from "echarts";
import { ExploratoryData } from "@/lib/api";
import Flag from "@/components/ui/Flag";
import { STYLE_COLOR, styleDescription, styleName } from "@/lib/styleMeta";

type Row = NonNullable<ExploratoryData["estilos_mapa"]>[number];

interface PlotPoint {
  team: string;
  arquetipo: string;
  jogos?: number;
  color: string;
  value: [number, number];
  rawValue: [number, number];
  active: boolean;
  selected: boolean;
}

interface FlagPoint extends PlotPoint {
  x: number;
  y: number;
}

export default function EstilosMapa({
  rows,
  selected,
  activeStyle,
  onToggle,
}: {
  rows: Row[];
  selected: string[];
  activeStyle?: string | null;
  onToggle: (team: string) => void;
}) {
  const elRef = React.useRef<HTMLDivElement>(null);
  const chartRef = React.useRef<echarts.ECharts | null>(null);
  const onToggleRef = React.useRef(onToggle);
  const [flags, setFlags] = React.useState<FlagPoint[]>([]);

  React.useEffect(() => {
    onToggleRef.current = onToggle;
  }, [onToggle]);

  const points = React.useMemo(() => buildPoints(rows, selected, activeStyle), [rows, selected, activeStyle]);

  const updateFlagPositions = React.useCallback(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const next = points
      .filter((p) => p.active || p.selected)
      .map((p) => {
        const pixel = chart.convertToPixel({ xAxisIndex: 0, yAxisIndex: 0 }, p.value) as [number, number];
        return { ...p, x: pixel[0], y: pixel[1] };
      })
      .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
    setFlags(next);
  }, [points]);

  React.useEffect(() => {
    if (!elRef.current) return;
    const chart = echarts.init(elRef.current, null, { renderer: "canvas" });
    chartRef.current = chart;
    chart.on("click", (p) => {
      const team = (p as { data?: { team?: string } }).data?.team;
      if (team) onToggleRef.current(team);
    });
    const ro = new ResizeObserver(() => {
      chart.resize();
      updateFlagPositions();
    });
    ro.observe(elRef.current);
    return () => {
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, [updateFlagPositions]);

  React.useEffect(() => {
    chartRef.current?.setOption(buildOption(points), true);
    window.setTimeout(updateFlagPositions, 0);
  }, [points, updateFlagPositions]);

  return (
    <div style={{ position: "relative", width: "100%", height: "clamp(320px, 38vw, 420px)" }}>
      <div ref={elRef} style={{ width: "100%", height: "100%" }} />
      {flags.map((p) => (
        <button
          key={p.team}
          type="button"
          onClick={() => onToggle(p.team)}
          title={`${p.team} · ${styleName(p.arquetipo)}\n${styleDescription(p.arquetipo)}\nposse ${p.rawValue[0].toFixed(1)} · verticalidade ${p.rawValue[1].toFixed(1)}`}
          style={{
            position: "absolute",
            left: p.x,
            top: p.y,
            transform: "translate(-50%, -50%)",
            width: 42,
            height: 30,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 0,
            background: "rgba(13,17,23,0.88)",
            border: `2px solid ${p.selected ? "#f0f6fc" : p.color}`,
            borderRadius: 5,
            boxShadow: p.selected ? "0 0 0 3px rgba(240,246,252,0.18)" : "0 6px 16px rgba(0,0,0,0.34)",
            cursor: "pointer",
            zIndex: p.selected ? 4 : 3,
          }}
        >
          <Flag team={p.team} height={20} />
        </button>
      ))}
    </div>
  );
}

function buildPoints(rows: Row[], selected: string[], activeStyle?: string | null): PlotPoint[] {
  const sel = new Set(selected);
  const hasSelected = selected.length > 0;
  const hasActiveStyle = !!activeStyle;
  const styleOffsets = new Map<string, number>();

  return rows.map((r) => {
    const arquetipo = r.arquetipo ?? "Sem arquétipo";
    const selectedTeam = sel.has(r.team);
    const inStyle = !activeStyle || arquetipo === activeStyle;
    const active = hasSelected ? selectedTeam : !hasActiveStyle || inStyle;
    const styleIndex = styleOffsets.get(arquetipo) ?? 0;
    styleOffsets.set(arquetipo, styleIndex + 1);
    const offset = active ? spreadOffset(styleIndex) : [0, 0];
    return {
      team: r.team,
      arquetipo,
      jogos: r.jogos,
      color: STYLE_COLOR[arquetipo] ?? "#8b949e",
      value: [clamp(r.posse + offset[0]), clamp(r.verticalidade + offset[1])],
      rawValue: [r.posse, r.verticalidade],
      active,
      selected: selectedTeam,
    };
  });
}

function buildOption(points: PlotPoint[]): echarts.EChartsOption {
  const data = points.map((p) => ({
    ...p,
    symbolSize: p.active ? 22 : 8,
    itemStyle: {
      color: p.color,
      opacity: p.active ? 0.38 : 0.12,
      borderColor: "#0d1117",
      borderWidth: 1,
    },
  }));
  return {
    backgroundColor: "transparent",
    grid: { left: 56, right: 28, top: 22, bottom: 48 },
    tooltip: {
      trigger: "item",
      backgroundColor: "#161b22",
      borderColor: "#30363d",
      textStyle: { color: "#e6edf3", fontSize: 12 },
      formatter: (params) => {
        const d = (params as unknown as { data: PlotPoint }).data;
        const jogos = d.jogos != null ? `<br/>amostra: ${d.jogos} jogo${d.jogos === 1 ? "" : "s"}` : "";
        return `<b>${d.team}</b><br/>estilo: <b>${styleName(d.arquetipo)}</b>`
          + `<br/><span style="color:#8b949e">${styleDescription(d.arquetipo)}</span>`
          + `<br/>posse: ${d.rawValue[0].toFixed(1)}`
          + `<br/>verticalidade: ${d.rawValue[1].toFixed(1)}${jogos}`;
      },
    },
    xAxis: {
      type: "value",
      min: 0,
      max: 100,
      name: "posse e controle ->",
      nameLocation: "middle",
      nameGap: 30,
      nameTextStyle: { color: "#8b949e", fontSize: 11 },
      axisLine: { lineStyle: { color: "#30363d" } },
      axisTick: { lineStyle: { color: "#30363d" } },
      axisLabel: { color: "#8b949e", fontSize: 10 },
      splitLine: { lineStyle: { color: "#161b22" } },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      name: "verticalidade ->",
      nameLocation: "middle",
      nameGap: 38,
      nameTextStyle: { color: "#8b949e", fontSize: 11 },
      axisLine: { lineStyle: { color: "#30363d" } },
      axisTick: { lineStyle: { color: "#30363d" } },
      axisLabel: { color: "#8b949e", fontSize: 10 },
      splitLine: { lineStyle: { color: "#161b22" } },
    },
    series: [
      {
        type: "scatter",
        data,
        cursor: "pointer",
        symbol: "circle",
        emphasis: { scale: 1.15 },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { type: "dashed", color: "#6e7681", width: 1 },
          label: { show: false },
          data: [{ xAxis: 50 }, { yAxis: 50 }],
        } as echarts.SeriesOption["markLine"],
      },
    ],
  };
}

function clamp(v: number) {
  return Math.max(1, Math.min(99, v));
}

function spreadOffset(index: number): [number, number] {
  const ring = Math.floor(index / 8) + 1;
  const angle = (index % 8) * (Math.PI / 4);
  const radius = ring * 2.8;
  return [Math.cos(angle) * radius, Math.sin(angle) * radius];
}
