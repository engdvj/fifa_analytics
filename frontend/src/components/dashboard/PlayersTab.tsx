"use client";

import React from "react";
import useSWR from "swr";
import { analytics, PlayerSnapshot } from "@/lib/api";
import Flag from "@/components/ui/Flag";
import { DefinitionBubble } from "@/components/DefinitionLink";

const PAGE_SIZE = 20;

// Mapeia a chave da métrica do jogador → id da definição. Sem id → sem bolinha.
const DEF_BY_KEY: Record<string, string> = {
  score_geral: "powerranking",
  participacoes_gol: "participacoes_gol",
  expected_goals: "xg",
  shots_on_target: "chutes_no_alvo",
};

// rótulos de todas as métricas usadas (ordenação/colunas)
const LABEL: Record<string, string> = {
  goals: "Gols", assists: "Assistências", participacoes_gol: "Participações em gol",
  expected_goals: "xG", key_passes: "Passes-chave", shots: "Finalizações", shots_on_target: "No alvo",
  dribbles_won: "Dribles", tackles_won: "Desarmes", interceptions: "Interceptações",
  ball_recovery: "Recuperações", duels_won: "Duelos", saves: "Defesas", goals_conceded: "Gols sofridos",
  score_geral: "PR FIFA",
};
const DEC: Record<string, number> = { expected_goals: 2, score_geral: 1 };

// "Ordenar por" RELEVANTE a cada perfil (default = stat concreta; PR FIFA por último, só onde existe)
const SORT_BY_PERFIL: Record<string, string[]> = {
  "": ["goals", "assists", "participacoes_gol", "key_passes", "dribbles_won", "tackles_won", "interceptions", "duels_won", "score_geral"],
  goleiro: ["saves", "goals_conceded", "ball_recovery", "duels_won", "score_geral"],
  defensor: ["tackles_won", "interceptions", "ball_recovery", "duels_won", "goals", "assists", "score_geral"],
  meio: ["assists", "key_passes", "goals", "dribbles_won", "participacoes_gol", "tackles_won", "interceptions", "score_geral"],
  atacante: ["goals", "expected_goals", "shots", "shots_on_target", "assists", "key_passes", "dribbles_won", "score_geral"],
};

const PERFIS: { key: string; label: string }[] = [
  { key: "", label: "Todos" }, { key: "goleiro", label: "Goleiros" }, { key: "defensor", label: "Defensores" },
  { key: "meio", label: "Meias" }, { key: "atacante", label: "Atacantes" },
];
const PERFIL_ABBR: Record<string, string> = { goleiro: "GOL", defensor: "DEF", meio: "MEI", atacante: "ATA" };

// colunas de stat por perfil (só métricas FIFA-disponíveis e coerentes)
type Col = [key: string, label: string, dec?: number];
const STAT_COLS: Record<string, Col[]> = {
  "": [["goals", "Gols"], ["assists", "Assist"]],
  goleiro: [["saves", "Defesas"], ["goals_conceded", "Sofridos"]],
  defensor: [["tackles_won", "Desarmes"], ["interceptions", "Intercept."], ["ball_recovery", "Recup."]],
  meio: [["assists", "Assist"], ["key_passes", "P-chave"], ["goals", "Gols"]],
  atacante: [["goals", "Gols"], ["expected_goals", "xG", 2], ["shots_on_target", "No alvo"]],
};

const DETAIL: Col[] = [
  ["goals", "Gols"], ["assists", "Assist."], ["expected_goals", "xG", 2], ["shots", "Finalizações"],
  ["shots_on_target", "No alvo"], ["key_passes", "Passes-chave"], ["dribbles_won", "Dribles"],
  ["tackles_won", "Desarmes"], ["interceptions", "Intercept."], ["ball_recovery", "Recuperações"],
  ["duels_won", "Duelos"], ["saves", "Defesas"], ["goals_conceded", "Gols sofridos"],
  ["fouls_committed", "Faltas"], ["yellow_cards", "Amarelos"], ["red_cards", "Vermelhos"],
];

function num(p: PlayerSnapshot, k: string): number | null {
  const v = p[k];
  return typeof v === "number" ? v : null;
}

function fmt(v: number | null, dec?: number): string {
  if (v == null) return "—";
  if (dec != null) return v.toFixed(dec);
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}
// Power Ranking FIFA é escala 0-100 (oficial, só ~244 jogadores).
function prColor(v: number | null): string {
  if (v == null) return "#8b949e";
  return v >= 65 ? "#3fb950" : v >= 55 ? "#56d364" : v >= 50 ? "#d29922" : "#f85149";
}

interface Props {
  activeSnapshot: number;
  passesFilters: (team: string) => boolean;
  selectedTeams: string[];
  search?: string;
}

export default function PlayersTab({ activeSnapshot, passesFilters, selectedTeams, search = "" }: Props) {
  const { data, isLoading } = useSWR(["players", activeSnapshot], () => analytics.playerSnapshots({ snapshot: activeSnapshot }));
  const [sortKey, setSortKey] = React.useState("goals");
  const [sortDir, setSortDir] = React.useState<"asc" | "desc">("desc");
  const [perfil, setPerfil] = React.useState("");
  const [onlyPlayed, setOnlyPlayed] = React.useState(true);
  const [onlySelected, setOnlySelected] = React.useState(true);
  const [page, setPage] = React.useState(0);
  const [openCards, setOpenCards] = React.useState<PlayerSnapshot[]>([]);
  const openSet = React.useMemo(() => new Set(openCards.map((p) => p.player_slug ?? p.id_player)), [openCards]);
  const openCard = (p: PlayerSnapshot) => {
    const id = p.player_slug ?? p.id_player;
    setOpenCards((prev) => (prev.some((x) => (x.player_slug ?? x.id_player) === id) ? prev : [...prev, p]));
  };
  const closeCard = (id: string) => setOpenCards((prev) => prev.filter((x) => (x.player_slug ?? x.id_player) !== id));
  const selSet = React.useMemo(() => new Set(selectedTeams), [selectedTeams]);
  const useSelection = onlySelected && selSet.size > 0;

  const sortOptions = SORT_BY_PERFIL[perfil] ?? SORT_BY_PERFIL[""];
  // ao trocar de perfil, se a métrica de ordenação não fizer sentido, volta p/ a 1ª
  React.useEffect(() => {
    if (!sortOptions.includes(sortKey)) setSortKey(sortOptions[0]);
    setPage(0);
  }, [perfil]); // eslint-disable-line react-hooks/exhaustive-deps
  React.useEffect(() => { setPage(0); }, [search, sortKey, sortDir, onlyPlayed, activeSnapshot, useSelection]);

  const statCols = STAT_COLS[perfil] ?? STAT_COLS[""];
  const baseKeys = new Set(["score_geral", "jogos", ...statCols.map((c) => c[0])]);
  const metricCol = baseKeys.has(sortKey) ? null : sortKey;

  const players = React.useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = (data ?? [])
      .filter((p) => p.team && passesFilters(p.team))
      .filter((p) => !useSelection || (p.team != null && selSet.has(p.team)))
      .filter((p) => !perfil || (p.perfil ?? "").toLowerCase() === perfil)
      .filter((p) => !q || (p.player_name ?? "").toLowerCase().includes(q) || (p.team ?? "").toLowerCase().includes(q))
      .filter((p) => !onlyPlayed || (num(p, "jogos") ?? 0) > 0);
    list.sort((a, b) => {
      const av = num(a, sortKey), bv = num(b, sortKey);
      if (av == null && bv == null) return (a.player_name ?? "").localeCompare(b.player_name ?? "", "pt-BR");
      if (av == null) return 1;
      if (bv == null) return -1;
      if (av === bv) return (a.player_name ?? "").localeCompare(b.player_name ?? "", "pt-BR");
      return sortDir === "asc" ? av - bv : bv - av;
    });
    return list;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, search, sortKey, sortDir, perfil, onlyPlayed, passesFilters, useSelection, selSet]);

  const rankBy = React.useMemo(() => {
    const ranked = players.map((p) => ({ id: p.player_slug ?? p.id_player, v: num(p, sortKey) })).filter((x) => x.v != null) as { id: string; v: number }[];
    const m = new Map<string, number>();
    ranked.forEach((x, i) => m.set(x.id, i > 0 && x.v === ranked[i - 1].v ? m.get(ranked[i - 1].id)! : i + 1));
    return m;
  }, [players, sortKey]);

  const pageCount = Math.max(1, Math.ceil(players.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageItems = players.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  const sortByCol = (key: string) => {
    if (key === sortKey) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortKey(key); setSortDir("desc"); }
  };
  const arrow = (key: string) => (key === sortKey ? (sortDir === "asc" ? " ▲" : " ▼") : "");

  return (
    <div>
      {/* filtros */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#8b949e" }}>
          Ordenar por
          <select value={sortKey} onChange={(e) => { setSortKey(e.target.value); setSortDir("desc"); }} style={selStyle}>
            {sortOptions.map((k) => <option key={k} value={k}>{LABEL[k] ?? k}</option>)}
          </select>
        </label>
        <button
          onClick={() => setSortDir((d) => (d === "desc" ? "asc" : "desc"))}
          title={sortDir === "desc" ? "Maior primeiro (clique para inverter)" : "Menor primeiro (clique para inverter)"}
          style={{ display: "inline-flex", alignItems: "center", gap: 5, background: "#161b22", color: "#c9d1d9", border: "1px solid #30363d", borderRadius: 6, padding: "4px 10px", fontSize: 12, cursor: "pointer", fontFamily: "inherit", whiteSpace: "nowrap" }}
        >
          <span style={{ fontSize: 13 }}>{sortDir === "desc" ? "↓" : "↑"}</span>
          {sortDir === "desc" ? "Maior" : "Menor"}
        </button>
        <div style={{ display: "inline-flex", gap: 3, background: "#0d1117", border: "1px solid #21262d", borderRadius: 8, padding: 3 }}>
          {PERFIS.map((pf) => (
            <button key={pf.key} onClick={() => setPerfil(pf.key)} style={{
              border: 0, borderRadius: 6, padding: "4px 10px", fontSize: 11.5, fontWeight: 700, cursor: "pointer", fontFamily: "inherit",
              background: perfil === pf.key ? "#1f6feb" : "transparent", color: perfil === pf.key ? "#fff" : "#8b949e",
            }}>{pf.label}</button>
          ))}
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "#8b949e", cursor: "pointer" }}>
          <input type="checkbox" checked={onlyPlayed} onChange={(e) => setOnlyPlayed(e.target.checked)} /> só quem jogou
        </label>
        {selSet.size > 0 && (
          <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: onlySelected ? "#58a6ff" : "#8b949e", cursor: "pointer", fontWeight: 700 }} title="Mostrar só jogadores das seleções selecionadas na Ranking Race / Seleções">
            <input type="checkbox" checked={onlySelected} onChange={(e) => setOnlySelected(e.target.checked)} /> só selecionadas ({selSet.size})
          </label>
        )}
        <span style={{ color: "#8b949e", fontSize: 12, marginLeft: "auto" }}>{players.length} jogadores · pág. {safePage + 1}/{pageCount}</span>
      </div>

      {isLoading ? (
        <p style={{ color: "#8b949e", fontSize: 13 }}>Carregando jogadores…</p>
      ) : players.length === 0 ? (
        <p style={{ color: "#8b949e", fontSize: 13 }}>Nenhum jogador com esses filtros neste snapshot.</p>
      ) : (
        <div style={{ overflowX: "auto", border: "1px solid #21262d", borderRadius: 8 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#0d1117" }}>
                <Th align="right" w={40}>#</Th>
                <Th align="center" w={36}>Nº</Th>
                <Th>Jogador</Th>
                <Th>Time</Th>
                <Th w={48}>Pos</Th>
                {metricCol && <ThSort active onClick={() => sortByCol(metricCol)} metric>{LABEL[metricCol] ?? metricCol}{arrow(metricCol)}</ThSort>}
                <ThSort active={sortKey === "score_geral"} onClick={() => sortByCol("score_geral")} title="Power Ranking FIFA (oficial · só ~244 jogadores)">PR FIFA<DefinitionBubble id="powerranking" size={13} />{arrow("score_geral")}</ThSort>
                {statCols.map((c) => <ThSort key={c[0]} active={sortKey === c[0]} onClick={() => sortByCol(c[0])}>{c[1]}{arrow(c[0])}</ThSort>)}
                <ThSort active={sortKey === "jogos"} onClick={() => sortByCol("jogos")}>Jogos{arrow("jogos")}</ThSort>
              </tr>
            </thead>
            <tbody>
              {pageItems.map((p) => {
                const id = p.player_slug ?? p.id_player;
                const active = openSet.has(id);
                const rk = rankBy.get(id);
                const pr = num(p, "score_geral");
                return (
                  <tr key={id} onClick={() => openCard(p)} style={{ cursor: "pointer", background: active ? "#11233f" : "transparent", borderBottom: "1px solid #161b22" }}>
                    <Td align="right" dim>{rk ?? ""}</Td>
                    <Td align="center" dim>{p.shirt_number ?? ""}</Td>
                    <Td><span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "#e6edf3", fontWeight: 600 }}><Flag team={p.team} height={12} />{p.player_name}</span></Td>
                    <Td><span style={{ color: "#9db3cf" }}>{p.team}</span></Td>
                    <Td dim>{PERFIL_ABBR[(p.perfil ?? "").toLowerCase()] ?? (p.position ?? "")}</Td>
                    {metricCol && <Td align="right" metric><b>{fmt(num(p, metricCol), DEC[metricCol])}</b></Td>}
                    <Td align="right"><span style={{ color: prColor(pr), fontWeight: 700 }}>{fmt(pr, 1)}</span></Td>
                    {statCols.map((c) => <Td key={c[0]} align="right">{fmt(num(p, c[0]), c[2])}</Td>)}
                    <Td align="right" dim>{fmt(num(p, "jogos"))}</Td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!isLoading && pageCount > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 14 }}>
          <PageBtn disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>← Anterior</PageBtn>
          <span style={{ color: "#8b949e", fontSize: 12, alignSelf: "center" }}>{safePage + 1} / {pageCount}</span>
          <PageBtn disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}>Próxima →</PageBtn>
        </div>
      )}

      {openCards.map((p, i) => (
        <PlayerCard key={p.player_slug ?? p.id_player} player={p} index={i} onClose={() => closeCard(p.player_slug ?? p.id_player)} />
      ))}
    </div>
  );
}

// Card flutuante arrastável (estilo o do campo do jogo), seções por posição.
const CARD_SECTIONS: { title: string; gk?: boolean; out?: boolean; rows: Col[] }[] = [
  { title: "Finalização", out: true, rows: [["goals", "Gols"], ["shots", "Finalizações"], ["shots_on_target", "No alvo"], ["expected_goals", "xG", 2]] },
  { title: "Criação", out: true, rows: [["assists", "Assistências"], ["key_passes", "Passes-chave"], ["dribbles_won", "Dribles"], ["participacoes_gol", "Participações em gol"]] },
  { title: "Goleiro", gk: true, rows: [["saves", "Defesas"], ["goals_conceded", "Gols sofridos"], ["ball_recovery", "Recuperações"]] },
  { title: "Defesa / Físico", rows: [["tackles_won", "Desarmes"], ["interceptions", "Interceptações"], ["ball_recovery", "Recuperações"], ["duels_won", "Duelos ganhos"]] },
  { title: "Disciplina", rows: [["fouls_committed", "Faltas"], ["fouls_drawn", "Faltas sofridas"], ["yellow_cards", "Amarelos"], ["red_cards", "Vermelhos"]] },
];

function PlayerCard({ player, index = 0, onClose }: { player: PlayerSnapshot; index?: number; onClose: () => void }) {
  const [pos, setPos] = React.useState({ x: (typeof window !== "undefined" ? Math.max(20, window.innerWidth / 2 - 200) : 200) + index * 32, y: 70 + index * 32 });
  const drag = React.useRef<{ dx: number; dy: number } | null>(null);
  const onDown = (e: React.PointerEvent) => { drag.current = { dx: e.clientX - pos.x, dy: e.clientY - pos.y }; (e.target as HTMLElement).setPointerCapture(e.pointerId); };
  const onMove = (e: React.PointerEvent) => { if (drag.current) setPos({ x: e.clientX - drag.current.dx, y: e.clientY - drag.current.dy }); };
  const onUp = () => { drag.current = null; };

  const isGK = (player.perfil ?? "").toLowerCase() === "goleiro";
  const pr = num(player, "score_geral");
  const sections = CARD_SECTIONS.filter((s) => (isGK ? s.gk || (!s.out && !s.gk) : !s.gk));

  return (
    <div style={{ position: "fixed", left: pos.x, top: pos.y, zIndex: 80, width: 400, maxWidth: "96vw" }}>
      <div style={{ background: "#010409", border: "1px solid #30363d", borderRadius: 12, boxShadow: "0 20px 60px rgba(0,0,0,0.55)", overflow: "hidden" }}>
        {/* cabeçalho (arrasta) */}
        <div onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp}
          style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 14px", background: "#0d1117", borderBottom: "1px solid #21262d", cursor: "grab", touchAction: "none" }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "#8b949e", minWidth: 22 }}>{player.shirt_number != null ? `#${player.shirt_number}` : ""}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Flag team={player.team} height={14} />
              <span style={{ fontSize: 15, fontWeight: 800, color: "#f0f6fc", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{player.player_name}</span>
            </div>
            <div style={{ fontSize: 11, color: "#8b949e", marginTop: 1 }}>{player.team} · {PERFIL_ABBR[(player.perfil ?? "").toLowerCase()] ?? player.position} · {fmt(num(player, "jogos"))} jogos</div>
          </div>
          <div style={{ textAlign: "center" }} title="Power Ranking FIFA (oficial · só ~244 jogadores)">
            <div style={{ fontSize: 20, fontWeight: 800, color: prColor(pr) }}>{fmt(pr, 1)}</div>
            <div style={{ fontSize: 9, color: "#8b949e", textTransform: "uppercase" }}>PR FIFA<DefinitionBubble id="powerranking" size={11} /></div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#8b949e", fontSize: 20, cursor: "pointer", padding: 2, lineHeight: 1 }}>×</button>
        </div>

        {/* seções */}
        <div style={{ padding: "10px 13px 13px", maxHeight: "72vh", overflowY: "auto" }}>
          {sections.map((s) => (
            <div key={s.title} style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 10, fontWeight: 800, color: "#58a6ff", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>{s.title}</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1px 18px" }}>
                {s.rows.map((c) => (
                  <div key={c[0]} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 2px" }}>
                    <span style={{ fontSize: 12, color: "#9aa4af" }}>{c[1]}{DEF_BY_KEY[c[0]] && <DefinitionBubble id={DEF_BY_KEY[c[0]]} size={12} />}</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: "#e6edf3" }}>{fmt(num(player, c[0]), c[2])}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const selStyle: React.CSSProperties = { background: "#161b22", color: "#e6edf3", border: "1px solid #30363d", borderRadius: 6, padding: "4px 8px", fontSize: 12, fontFamily: "inherit" };
const thBase: React.CSSProperties = { padding: "8px 10px", borderBottom: "1px solid #21262d", color: "#8b949e", fontWeight: 700, fontSize: 11.5, textTransform: "uppercase", letterSpacing: "0.03em", whiteSpace: "nowrap" };

function Th({ children, align = "left", w }: { children?: React.ReactNode; align?: "left" | "right" | "center"; w?: number }) {
  return <th style={{ ...thBase, textAlign: align, width: w }}>{children}</th>;
}
function ThSort({ children, active, metric, onClick, title }: { children: React.ReactNode; active: boolean; metric?: boolean; onClick: () => void; title?: string }) {
  return <th onClick={onClick} title={title} style={{ ...thBase, textAlign: "right", cursor: "pointer", userSelect: "none", color: active || metric ? "#58a6ff" : "#8b949e", background: metric ? "#1f6feb12" : undefined }}>{children}</th>;
}
function Td({ children, align = "left", dim, metric }: { children?: React.ReactNode; align?: "left" | "right" | "center"; dim?: boolean; metric?: boolean }) {
  return <td style={{ padding: "7px 10px", textAlign: align, whiteSpace: "nowrap", color: dim ? "#8b949e" : "#e6edf3", background: metric ? "#1f6feb12" : undefined }}>{children}</td>;
}
function PageBtn({ children, disabled, onClick }: { children: React.ReactNode; disabled: boolean; onClick: () => void }) {
  return <button onClick={onClick} disabled={disabled} style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 6, color: disabled ? "#484f58" : "#e6edf3", padding: "6px 12px", fontSize: 12, cursor: disabled ? "default" : "pointer", fontFamily: "inherit" }}>{children}</button>;
}
