"use client";

import React from "react";
import * as echarts from "echarts";
import { flagUrl } from "@/lib/teamUtils";
import { ExploratoryData } from "@/lib/api";

const PERFIL_COLOR: Record<string, string> = {
  "Elite": "#3fb950", "Oportunistas": "#58a6ff", "Frustrados": "#d29922", "Em apuros": "#f85149", "Neutro": "#8b949e",
};

type Q = NonNullable<ExploratoryData["quadrante"]>;

// Mapa de seleções (ECharts): cria perigo (x) × converte (y), bandeiras como
// marcadores, 4 quadrantes + zona neutra. Clique numa bandeira seleciona.
export default function QuadranteMapa({ data, selected, onToggle }: { data: Q; selected: string[]; onToggle: (t: string) => void }) {
  const elRef = React.useRef<HTMLDivElement>(null);
  const chartRef = React.useRef<echarts.ECharts | null>(null);
  const onToggleRef = React.useRef(onToggle);
  onToggleRef.current = onToggle;

  React.useEffect(() => {
    if (!elRef.current) return;
    const chart = echarts.init(elRef.current, null, { renderer: "canvas" });
    chartRef.current = chart;
    chart.on("click", (p) => {
      const team = (p as { data?: { team?: string } }).data?.team;
      if (team) onToggleRef.current(team);
    });
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(elRef.current);
    return () => { ro.disconnect(); chart.dispose(); chartRef.current = null; };
  }, []);

  React.useEffect(() => {
    chartRef.current?.setOption(buildOption(data, selected), true);
  }, [data, selected]);

  return <div ref={elRef} style={{ width: "100%", height: 460 }} />;
}

function buildOption(data: Q, selected: string[]): echarts.EChartsOption {
  const pontos = data.pontos;
  const ref = data.cria_ref ?? 1;
  const mx = data.mx ?? 0;
  const my = data.my ?? 0;
  const maxX = Math.ceil(Math.max(1, ...pontos.map((p) => p.cria)) * 10) / 10;
  const maxY = Math.max(1, ...pontos.map((p) => Math.abs(p.converte)));
  const sel = new Set(selected);
  const hasSel = selected.length > 0;

  const scatterData = pontos.map((p) => {
    const on = sel.has(p.team);
    const url = flagUrl(p.team, 40);
    return {
      value: [p.cria, p.converte],
      team: p.team,
      perfil: p.perfil,
      symbol: url ? `image://${url}` : "circle",
      symbolSize: on ? [34, 23] : [22, 15],
      itemStyle: {
        opacity: hasSel && !on ? 0.28 : 1,
        borderColor: PERFIL_COLOR[p.perfil] ?? "#8b949e",
        borderWidth: on ? 2.5 : 1,
        borderRadius: 3,
      },
      label: {
        show: on,
        position: "bottom" as const,
        formatter: p.team,
        color: "#e6edf3",
        fontSize: 11,
        fontWeight: 700,
        backgroundColor: "rgba(13,17,23,0.85)",
        padding: [2, 5] as [number, number],
        borderRadius: 4,
        distance: 6,
      },
      z: on ? 10 : 2,
    };
  });

  const tint = (perfil: string) => ({ color: PERFIL_COLOR[perfil], opacity: 0.07 });
  const corner = (perfil: string, position: string) => ({
    show: true, position, distance: 8, formatter: perfil,
    color: PERFIL_COLOR[perfil], fontSize: 12.5, fontWeight: 700 as const, opacity: 0.75,
  });

  return {
    backgroundColor: "transparent",
    grid: { left: 56, right: 26, top: 20, bottom: 46 },
    tooltip: {
      trigger: "item",
      backgroundColor: "#161b22",
      borderColor: "#30363d",
      textStyle: { color: "#e6edf3", fontSize: 12 },
      formatter: (params) => {
        const d = (params as unknown as { data: { team: string; perfil: string; value: [number, number] } }).data;
        return `<b>${d.team}</b><br/>perfil: <b style="color:${PERFIL_COLOR[d.perfil] ?? "#8b949e"}">${d.perfil}</b>`
          + `<br/>cria: ${d.value[0].toFixed(2)} xG/jogo`
          + `<br/>converte: ${d.value[1] >= 0 ? "+" : ""}${d.value[1].toFixed(2)}`;
      },
    },
    xAxis: {
      type: "value", min: 0, max: maxX,
      name: "cria perigo (xG/jogo) →", nameLocation: "middle", nameGap: 30, nameTextStyle: { color: "#8b949e", fontSize: 11 },
      axisLine: { lineStyle: { color: "#30363d" } },
      axisTick: { lineStyle: { color: "#30363d" } },
      axisLabel: { color: "#8b949e", fontSize: 10 },
      splitLine: { lineStyle: { color: "#161b22" } },
    },
    yAxis: {
      type: "value", min: -maxY, max: maxY,
      name: "converte (gols − xG) →", nameLocation: "middle", nameGap: 38, nameTextStyle: { color: "#8b949e", fontSize: 11 },
      axisLine: { lineStyle: { color: "#30363d" } },
      axisTick: { lineStyle: { color: "#30363d" } },
      axisLabel: { color: "#8b949e", fontSize: 10, formatter: (v: number) => (v > 0 ? "+" : "") + v.toFixed(1) },
      splitLine: { lineStyle: { color: "#161b22" } },
    },
    series: [
      {
        type: "scatter",
        data: scatterData,
        cursor: "pointer",
        emphasis: { scale: 1.15 },
        markArea: {
          silent: true,
          data: [
            [{ coord: [0, 0], itemStyle: tint("Oportunistas"), label: corner("Oportunistas", "insideTopLeft") }, { coord: [ref, maxY] }],
            [{ coord: [ref, 0], itemStyle: tint("Elite"), label: corner("Elite", "insideTopRight") }, { coord: [maxX, maxY] }],
            [{ coord: [0, -maxY], itemStyle: tint("Em apuros"), label: corner("Em apuros", "insideBottomLeft") }, { coord: [ref, 0] }],
            [{ coord: [ref, -maxY], itemStyle: tint("Frustrados"), label: corner("Frustrados", "insideBottomRight") }, { coord: [maxX, 0] }],
            [{ coord: [ref - mx, -my], itemStyle: { color: "#6e7681", opacity: 0.18 },
               label: { show: true, position: "inside", formatter: "zona neutra", color: "#8b949e", fontSize: 10, fontWeight: 700 } },
             { coord: [ref + mx, my] }],
          ],
        } as echarts.SeriesOption["markArea"],
        markLine: {
          silent: true, symbol: "none",
          lineStyle: { type: "dashed", color: "#6e7681", width: 1 },
          label: { show: false },
          data: [{ xAxis: ref }, { yAxis: 0 }],
        } as echarts.SeriesOption["markLine"],
      },
    ],
  };
}
