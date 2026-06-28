"use client";

import React from "react";
import { ExploratoryData, Match, TeamSnapshot } from "@/lib/api";
import { useExploratory, useTeamSnapshots } from "@/lib/hooks";
import Flag from "@/components/ui/Flag";
import Spinner from "@/components/ui/Spinner";
import EstilosMapa from "@/components/dashboard/EstilosMapa";
import { getKit } from "@/lib/teamUtils";
import { STYLE_COLOR, STYLE_ORDER, styleDescription, styleName } from "@/lib/styleMeta";

type StyleRow = NonNullable<ExploratoryData["estilo_resultado"]>[number];
type StylePoint = NonNullable<ExploratoryData["estilos_mapa"]>[number];
type TeamStyleDetail = NonNullable<StyleRow["times_detalhe"]>[number];
type StyleMatchup = NonNullable<ExploratoryData["confrontos_estilo"]>[number];
type TeamGame = {
  matchId: string; matchNumber: number; opponent: string; opponentStyle: string;
  stage: string | null; score: string; result: "V" | "E" | "D"; gf: number | null; ga: number | null;
};

const num = (v: number | null | undefined, d = 2) =>
  typeof v === "number" ? v.toFixed(d).replace(".", ",") : "—";

/* ════════════════════════════════════════════════════════════════════════════
   SELEÇÕES & CONFRONTOS — uma tela que reage ao foco:
     0 times → mapa de estilos (didático, ponto de entrada)
     1 time  → raio-x do time (um cartão, hierarquizado)
     2 times → frente a frente (tabela divergente + confronto de estilos + H2H)
   Sem "modo": a tela segue quem está em foco no rail de seleções.
   ════════════════════════════════════════════════════════════════════════════ */

export default function ExploratoriaView({
  snapshot,
  enabled,
  matches = [],
  selectedTeams = [],
  onToggleTeam,
  onFocusTeams,
}: {
  snapshot: number;
  enabled: boolean;
  matches?: Match[];
  selectedTeams?: string[];
  onToggleTeam?: (t: string) => void;
  onFocusTeams?: (teams: string[]) => void;
}) {
  const { explore, isLoading } = useExploratory(snapshot, enabled);
  const { snapshots: teamSnaps } = useTeamSnapshots(snapshot);

  if (isLoading) {
    return <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}><Spinner /></div>;
  }
  if (!explore || !explore.estilo_resultado?.length) {
    return <Aviso texto="Amostra ainda insuficiente para ler estilos — avance no tempo ou rode uma coleta." />;
  }

  const rows = explore.estilo_resultado;
  const mapRows = explore.estilos_mapa ?? [];
  const matchups = explore.confrontos_estilo ?? [];
  const teamDetails = rows.flatMap((r) => r.times_detalhe ?? []);

  const resolve = (team: string) => resolveTeamDetail(team, teamDetails, teamSnaps, mapRows, matches, snapshot);
  const focus = selectedTeams.map(resolve).filter((d): d is TeamStyleDetail => !!d);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Mapa de estilos — SEMPRE no topo. Destaca quem está em foco. */}
      <StyleMapHero mapRows={mapRows} selected={selectedTeams} onToggle={onToggleTeam} />

      {/* Detalhe abaixo: raio-x (1) ou frente a frente (2). */}
      {focus.length >= 2 ? (
        <Versus a={focus[0]} b={focus[1]} matchups={matchups} matches={matches} snapshot={snapshot} details={teamDetails} onFocusTeams={onFocusTeams} />
      ) : focus.length === 1 ? (
        <TeamDeepDive detail={focus[0]} matches={matches} snapshot={snapshot} details={teamDetails} onFocusTeams={onFocusTeams} />
      ) : null}
    </div>
  );
}

/* ── Mapa de estilos — cabeçalho fixo da tela ────────────────────────────── */

function StyleMapHero({ mapRows, selected, onToggle }: { mapRows: StylePoint[]; selected: string[]; onToggle?: (t: string) => void }) {
  const hint = selected.length >= 2
    ? "Comparando as duas seleções em destaque. Clique numa bandeira para trocar o foco."
    : selected.length === 1
      ? "Seleção em destaque abaixo. Clique em outra bandeira para comparar as duas."
      : "Clique numa bandeira para abrir o raio-x; clique em duas para comparar.";
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "14px 16px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 800 }}>Mapa de estilos</div>
        <div style={{ fontSize: 13, color: "var(--text)", marginTop: 4, lineHeight: 1.45, fontWeight: 650 }}>
          Cada seleção no quadrante do seu jeito de jogar: <b>reativo ↔ proativo</b> (quem toma a iniciativa)
          × <b>direto ↔ elaborado</b> (como chega ao gol). {hint}
        </div>
      </div>
      <div style={{ padding: "12px 12px 6px" }}>
        <EstilosMapa rows={mapRows} selected={selected} activeStyle={null} onToggle={onToggle ?? (() => {})} />
        <StyleLegend />
      </div>
    </section>
  );
}

/* ── 1 time: raio-x ──────────────────────────────────────────────────────── */

function TeamDeepDive({ detail, matches, snapshot, details, onFocusTeams }: { detail: TeamStyleDetail; matches: Match[]; snapshot: number; details: TeamStyleDetail[]; onFocusTeams?: (teams: string[]) => void }) {
  const color = STYLE_COLOR[detail.arquetipo] ?? "var(--accent)";
  const games = teamGames(detail.team, matches, snapshot, details);
  const metrics = detail.metricas_chave ?? [];

  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      {/* HERO: identidade do time */}
      <header style={{ padding: "16px 18px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Flag team={detail.team} height={30} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 19, fontWeight: 900, color: "var(--text)", lineHeight: 1.1 }}>{detail.team}</div>
            <div style={{ fontSize: 13, fontWeight: 800, color, marginTop: 2 }}>{styleName(detail.arquetipo)}</div>
          </div>
          <div style={{ flex: 1 }} />
          <RecordPill detail={detail} />
        </div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 10, lineHeight: 1.5 }}>{styleDescription(detail.arquetipo)}</div>
      </header>

      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        {/* NÚMEROS DO TIME */}
        <Block title="Números do time">
          <StatGrid stats={[
            ["Pts/jogo", num(detail.pts_jogo)],
            ["Aproveitamento", `${detail.aproveitamento}%`],
            ["Gols/jogo", num(detail.gols_pj)],
            ["Saldo/jogo", num(detail.saldo_pj)],
            ["xG criado/jogo", num(detail.xg_pj)],
            ["xG sofrido/jogo", num(detail.xg_sofrido_pj)],
          ]} accent={color} />
        </Block>

        {/* O QUE DEFINE O ESTILO */}
        {metrics.length > 0 && (
          <Block title="O que define o estilo" hint="As métricas que mais caracterizam o jeito de jogar deste time.">
            <StatGrid
              stats={metrics.map((m) => [m.label, `${num(m.valor, m.decimals ?? 2)}${m.unit ?? ""}`])}
              accent={color}
            />
          </Block>
        )}

        {/* JOGOS — clicar foca os dois times daquele confronto */}
        <Block title="Jogos disputados" hint="Clique num jogo para comparar com aquele adversário.">
          <GamesStrip games={games} onPick={onFocusTeams ? (opp) => onFocusTeams([detail.team, opp]) : undefined} />
        </Block>
      </div>
    </section>
  );
}

/* ── 2 times: frente a frente ────────────────────────────────────────────── */

function Versus({ a, b, matchups, matches, snapshot, details, onFocusTeams }: {
  a: TeamStyleDetail; b: TeamStyleDetail; matchups: StyleMatchup[]; matches: Match[]; snapshot: number; details: TeamStyleDetail[]; onFocusTeams?: (teams: string[]) => void;
}) {
  const colorA = getKit(a.team).main;
  const colorB = getKit(b.team).main;
  const h2h = headToHeadGames(a.team, b.team, matches, snapshot, details);

  const styleMatch = matchups.find((r) => r.estilo === a.arquetipo && r.contra === b.arquetipo) ?? null;
  const styleReverse = matchups.find((r) => r.estilo === b.arquetipo && r.contra === a.arquetipo) ?? null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* PARTE 1: raio-x de cada time, lado a lado */}
      <div className="v2-versus-deepdives" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))", gap: 16, alignItems: "start" }}>
        <TeamDeepDive detail={a} matches={matches} snapshot={snapshot} details={details} onFocusTeams={onFocusTeams} />
        <TeamDeepDive detail={b} matches={matches} snapshot={snapshot} details={details} onFocusTeams={onFocusTeams} />
      </div>

      {/* PARTE 2: o confronto entre os dois */}
      <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <header style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 10, alignItems: "center", padding: "16px 18px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <VersusTeam detail={a} color={colorA} align="left" />
        <span style={{ fontSize: 12, fontWeight: 900, color: "var(--text-muted)", textTransform: "uppercase" }}>vs</span>
        <VersusTeam detail={b} color={colorB} align="right" />
      </header>

      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        {/* CONFRONTO DE ESTILOS */}
        <Block title="Confronto de estilos">
          <StyleMatchupReading a={a} b={b} matchup={styleMatch} reverse={styleReverse} />
        </Block>

        {/* HISTÓRICO DIRETO */}
        <Block title="Histórico entre as duas">
          {h2h.length > 0 ? <GamesStrip games={h2h} /> : <Empty texto="Ainda não se enfrentaram neste recorte." />}
        </Block>
      </div>
      </section>
    </div>
  );
}

function StyleMatchupReading({ a, b, matchup, reverse }: {
  a: TeamStyleDetail; b: TeamStyleDetail; matchup: StyleMatchup | null; reverse: StyleMatchup | null;
}) {
  const styleColorA = STYLE_COLOR[a.arquetipo] ?? "var(--accent)";
  const styleColorB = STYLE_COLOR[b.arquetipo] ?? "var(--accent)";

  // Mesmo estilo: não há duelo tático de estilos.
  if (a.arquetipo === b.arquetipo) {
    return (
      <div>
        <StyleVsHeader a={a} b={b} ca={styleColorA} cb={styleColorB} />
        <p style={{ fontSize: 12.5, color: "var(--text)", lineHeight: 1.5, margin: "8px 0 0" }}>
          As duas jogam no mesmo estilo (<b style={{ color: styleColorA }}>{styleName(a.arquetipo)}</b>) — o duelo se decide
          na execução e nos detalhes, não no choque de jeitos de jogar.
        </p>
      </div>
    );
  }

  if (!matchup) {
    return (
      <div>
        <StyleVsHeader a={a} b={b} ca={styleColorA} cb={styleColorB} />
        <p style={{ fontSize: 12.5, color: "var(--text-muted)", lineHeight: 1.5, margin: "8px 0 0" }}>
          Ainda não houve jogos suficientes entre {styleName(a.arquetipo)} e {styleName(b.arquetipo)} neste recorte para
          cravar uma tendência.
        </p>
      </div>
    );
  }

  // matchup = estilo de A contra estilo de B (ótica de A).
  const aproveit = matchup.aproveitamento;
  const saldo = matchup.saldo_pj ?? 0;
  const xgDiff = matchup.xg_diff_pj ?? 0;
  const n = matchup.jogos;
  const edgeScore = (aproveit - 50) / 50 + saldo * 0.5 + xgDiff * 0.5;
  const leansA = edgeScore > 0.25;
  const leansB = edgeScore < -0.25;
  const leadColor = leansA ? styleColorA : leansB ? styleColorB : "var(--text-muted)";
  const leadStyle = leansA ? styleName(a.arquetipo) : leansB ? styleName(b.arquetipo) : null;

  // Veredito SUAVIZADO pela amostra: poucos jogos viram "indício", não tendência.
  const conf = n >= 8 ? "alta" : n >= 4 ? "média" : "baixa";
  const confLabel = conf === "alta" ? "boa amostra" : conf === "média" ? "amostra moderada" : "amostra pequena";
  const confColor = conf === "alta" ? "#3fb950" : conf === "média" ? "#d29922" : "#8b949e";
  const verdict = !leadStyle
    ? "Esse choque de estilos costuma ficar equilibrado."
    : conf === "baixa"
      ? `Leve indício a favor de ${leadStyle} — mas com poucos jogos, ainda é incerto.`
      : conf === "média"
        ? `${leadStyle} tem levado a melhor neste choque de estilos.`
        : `${leadStyle} costuma dominar este choque de estilos.`;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* TOPO: veredito + selo de confiança em destaque */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <b style={{ color: styleColorA, fontSize: 14 }}>{styleName(a.arquetipo)}</b>
          <span style={{ color: "var(--text-muted)", fontSize: 12 }}>vs</span>
          <b style={{ color: styleColorB, fontSize: 14 }}>{styleName(b.arquetipo)}</b>
          <span style={{ marginLeft: "auto", fontSize: 10.5, fontWeight: 800, color: confColor, background: "var(--surface)", border: `1px solid ${confColor}55`, borderRadius: 12, padding: "2px 9px" }}>
            confiança {conf} · {n} jogo{n === 1 ? "" : "s"}
          </span>
        </div>
        <div style={{ fontSize: 13.5, fontWeight: 800, color: leadColor, lineHeight: 1.45, marginTop: 8 }}>{verdict}</div>
      </div>

      {/* DUAS COLUNAS: cada estilo, simétrico (ótica de cada lado) */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <StyleColumn detailStyle={a.arquetipo} color={styleColorA} row={matchup} oppStyle={b.arquetipo} highlight={leansA} />
        <StyleColumn detailStyle={b.arquetipo} color={styleColorB} row={reverse} oppStyle={a.arquetipo} highlight={leansB} />
      </div>

      <p style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5, margin: 0 }}>
        Base: confrontos entre times de cada estilo neste recorte ({confLabel}). Saldo e diferença de xG são por jogo.
      </p>
    </div>
  );
}

// Uma coluna do confronto: o cartel + métricas de UM estilo contra o outro,
// mais os times que jogam assim. Lado destacado quando leva vantagem.
function StyleColumn({ detailStyle, color, row, oppStyle, highlight }: {
  detailStyle: string; color: string; row: StyleMatchup | null; oppStyle: string; highlight: boolean;
}) {
  const side = highlight ? color : "var(--surface2)";
  return (
    <div style={{
      background: "var(--surface)",
      borderTop: `3px solid ${color}`,
      borderRight: `1px solid ${side}`,
      borderBottom: `1px solid ${side}`,
      borderLeft: `1px solid ${side}`,
      borderRadius: 8, padding: "11px 12px", display: "flex", flexDirection: "column", gap: 9, minWidth: 0,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <b style={{ color, fontSize: 13.5 }}>{styleName(detailStyle)}</b>
        {highlight && <span style={{ fontSize: 10, fontWeight: 800, color, background: `${color}22`, borderRadius: 4, padding: "1px 6px" }}>leva vantagem</span>}
      </div>
      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>contra {styleName(oppStyle)}</div>

      {row ? (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <RecordBar v={row.vitorias} e={row.empates} d={row.derrotas} />
            <span style={{ fontSize: 12, color: "var(--text)", fontWeight: 700 }}>{row.vitorias}V {row.empates}E {row.derrotas}D</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            <MatchupStat label="Aproveit." value={`${row.aproveitamento}%`} good={row.aproveitamento >= 55} bad={row.aproveitamento <= 45} />
            <MatchupStat label="Pts/jogo" value={num(row.pts_jogo)} good={row.pts_jogo >= 1.6} bad={row.pts_jogo <= 1.0} />
            <MatchupStat label="Saldo/jogo" value={fmtSigned(row.saldo_pj ?? 0)} good={(row.saldo_pj ?? 0) > 0.3} bad={(row.saldo_pj ?? 0) < -0.3} />
            <MatchupStat label="Dif. xG/jogo" value={fmtSigned(row.xg_diff_pj ?? 0)} good={(row.xg_diff_pj ?? 0) > 0.2} bad={(row.xg_diff_pj ?? 0) < -0.2} />
          </div>
        </>
      ) : (
        <div style={{ fontSize: 11.5, color: "var(--text-muted)" }}>Sem confrontos registrados nesta direção.</div>
      )}

      {(row?.times?.length ?? 0) > 0 && (
        <div>
          <MiniLabel texto="Quem joga assim" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 5 }}>
            {(row!.times ?? []).map((t) => (
              <span key={t} title={t} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, background: "var(--background)", border: `1px solid ${color}44`, borderRadius: 12, padding: "2px 7px 2px 4px", color: "var(--text)" }}>
                <Flag team={t} height={10} />
                <span style={{ maxWidth: 90, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function RecordBar({ v, e, d }: { v: number; e: number; d: number }) {
  const total = v + e + d || 1;
  return (
    <div style={{ display: "flex", height: 8, width: 140, borderRadius: 4, overflow: "hidden", background: "var(--surface2)" }}>
      <div style={{ width: `${(v / total) * 100}%`, background: "#3fb950" }} />
      <div style={{ width: `${(e / total) * 100}%`, background: "#8b949e" }} />
      <div style={{ width: `${(d / total) * 100}%`, background: "#f85149" }} />
    </div>
  );
}

function MatchupStat({ label, value, good, bad }: { label: string; value: string; good?: boolean; bad?: boolean }) {
  const color = good ? "#3fb950" : bad ? "#f85149" : "var(--text)";
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "8px 10px", minWidth: 0 }}>
      <div style={{ fontSize: 10.5, color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 850, color, marginTop: 3, fontVariantNumeric: "tabular-nums" }}>{value}</div>
    </div>
  );
}

function StyleVsHeader({ a, b, ca, cb }: { a: TeamStyleDetail; b: TeamStyleDetail; ca: string; cb: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
      <b style={{ color: ca, fontSize: 14 }}>{styleName(a.arquetipo)}</b>
      <span style={{ color: "var(--text-muted)", fontSize: 12 }}>vs</span>
      <b style={{ color: cb, fontSize: 14 }}>{styleName(b.arquetipo)}</b>
    </div>
  );
}

function MiniLabel({ texto }: { texto: string }) {
  return <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>{texto}</div>;
}

function fmtSigned(v: number) {
  const s = num(Math.abs(v));
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : s;
}

/* ── peças compartilhadas ────────────────────────────────────────────────── */

function VersusTeam({ detail, color, align }: { detail: TeamStyleDetail; color: string; align: "left" | "right" }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: align === "right" ? "flex-end" : "flex-start", minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexDirection: align === "right" ? "row-reverse" : "row" }}>
        <Flag team={detail.team} height={22} />
        <span style={{ fontSize: 16, fontWeight: 900, color: "var(--text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{detail.team}</span>
      </div>
      <span style={{ fontSize: 12, fontWeight: 800, color, marginTop: 3 }}>{styleName(detail.arquetipo)}</span>
    </div>
  );
}

function RecordPill({ detail }: { detail: TeamStyleDetail }) {
  const hasRecord = detail.vitorias != null || detail.empates != null || detail.derrotas != null;
  const txt = hasRecord ? `${detail.vitorias ?? 0}V ${detail.empates ?? 0}E ${detail.derrotas ?? 0}D` : `${detail.jogos ?? 0} jogos`;
  return (
    <span style={{ fontSize: 13, fontWeight: 800, color: "var(--text)", background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "6px 11px", whiteSpace: "nowrap" }}>{txt}</span>
  );
}

function StatGrid({ stats, accent }: { stats: [string, string][]; accent: string }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8 }}>
      {stats.map(([label, value]) => (
        <div key={label} style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "9px 10px", minWidth: 0 }}>
          <div style={{ fontSize: 10.5, color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</div>
          <div style={{ fontSize: 16, fontWeight: 850, color: accent, marginTop: 3, fontVariantNumeric: "tabular-nums" }}>{value}</div>
        </div>
      ))}
    </div>
  );
}

function GamesStrip({ games, onPick }: { games: TeamGame[]; onPick?: (opponent: string) => void }) {
  if (games.length === 0) return <Empty texto="Sem jogos finalizados neste recorte." />;
  const resColor = (r: TeamGame["result"]) => (r === "V" ? "#3fb950" : r === "D" ? "#f85149" : "#8b949e");
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
      {games.map((g) => {
        const clickable = !!onPick && !!g.opponent;
        return (
          <button key={g.matchId} type="button" disabled={!clickable}
            onClick={() => clickable && onPick!(g.opponent)}
            title={clickable ? `Comparar com ${g.opponent}` : `${g.opponent} · ${styleName(g.opponentStyle)}`}
            style={{ display: "flex", alignItems: "center", gap: 7, background: "var(--surface)", border: "1px solid var(--surface2)", borderLeft: `3px solid ${resColor(g.result)}`, borderRadius: 6, padding: "6px 9px", cursor: clickable ? "pointer" : "default", fontFamily: "inherit" }}>
            <Flag team={g.opponent} height={13} />
            <span style={{ fontSize: 12, color: "var(--text-muted)", maxWidth: 110, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{g.opponent}</span>
            <b style={{ fontSize: 13, color: "var(--text)", fontVariantNumeric: "tabular-nums" }}>{g.score}</b>
            <span style={{ fontSize: 11, fontWeight: 800, color: resColor(g.result) }}>{g.result}</span>
          </button>
        );
      })}
    </div>
  );
}

function Block({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 800, marginBottom: 8 }}>{title}</div>
      {children}
      {hint && <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6, lineHeight: 1.4, opacity: 0.85 }}>{hint}</div>}
    </div>
  );
}

function StyleLegend() {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 12, padding: "10px 4px 4px", fontSize: 11, color: "var(--text-muted)" }}>
      {STYLE_ORDER.map((s) => (
        <span key={s} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 9, height: 9, borderRadius: "50%", background: STYLE_COLOR[s] ?? "#8b949e" }} />
          {styleName(s)}
        </span>
      ))}
    </div>
  );
}

function Empty({ texto }: { texto: string }) {
  return <div style={{ fontSize: 12.5, color: "var(--text-muted)", padding: "10px 0", textAlign: "center" }}>{texto}</div>;
}

function Aviso({ texto }: { texto: string }) {
  return <div style={{ padding: "32px 16px", textAlign: "center", fontSize: 13, color: "var(--text-muted)", lineHeight: 1.5 }}>{texto}</div>;
}

/* ════════════════════════════════════════════════════════════════════════════
   HELPERS DE DADOS (mantidos da versão anterior — funcionam e já testados)
   ════════════════════════════════════════════════════════════════════════════ */

function finishedMatchesUpTo(matches: Match[], snapshot: number) {
  return matches
    .filter((m) => m.status === "finalizado")
    .sort((a, b) => {
      const dateCmp = String(a.date_utc ?? "").localeCompare(String(b.date_utc ?? ""));
      return dateCmp || (a.match_number ?? 0) - (b.match_number ?? 0);
    })
    .slice(0, snapshot);
}

function teamGames(team: string, matches: Match[], snapshot: number, details: TeamStyleDetail[]): TeamGame[] {
  const detailByTeam = new Map(details.map((detail) => [detail.team, detail]));
  return finishedMatchesUpTo(matches, snapshot)
    .filter((match) => match.home_team === team || match.away_team === team)
    .map((match) => {
      const isHome = match.home_team === team;
      const opponent = (isHome ? match.away_team : match.home_team) ?? "";
      const gf = isHome ? match.home_score : match.away_score;
      const ga = isHome ? match.away_score : match.home_score;
      const result: TeamGame["result"] = gf == null || ga == null ? "E" : gf > ga ? "V" : gf < ga ? "D" : "E";
      return {
        matchId: match.match_id,
        matchNumber: match.match_number,
        opponent,
        opponentStyle: detailByTeam.get(opponent)?.arquetipo ?? "Sem estilo",
        stage: match.stage,
        score: gf == null || ga == null ? "-" : `${gf}-${ga}`,
        result,
        gf,
        ga,
      };
    });
}

function headToHeadGames(teamA: string, teamB: string, matches: Match[], snapshot: number, details: TeamStyleDetail[]) {
  return teamGames(teamA, matches, snapshot, details).filter((game) => game.opponent === teamB);
}

function resolveTeamDetail(team: string, details: TeamStyleDetail[], snapshots: TeamSnapshot[], points: StylePoint[], matches: Match[], snapshot: number): TeamStyleDetail | null {
  const fromApi = details.find((d) => d.team === team) ?? null;
  const fromSnapshot = detailFromSnapshot(team, snapshots, points, matches, snapshot);
  if (!fromApi) return fromSnapshot;
  if (!fromSnapshot) return fromApi;
  const apiGames = fromApi.jogos ?? 0;
  const snapshotGames = fromSnapshot.jogos ?? 0;
  if (snapshotGames <= apiGames) return fromApi;
  return {
    ...fromApi,
    jogos: fromSnapshot.jogos,
    points: fromSnapshot.points,
    pts_jogo: fromSnapshot.pts_jogo,
    aproveitamento: fromSnapshot.aproveitamento,
    vitorias: fromSnapshot.vitorias,
    empates: fromSnapshot.empates,
    derrotas: fromSnapshot.derrotas,
    gols_pj: fromSnapshot.gols_pj ?? fromApi.gols_pj,
    xg_pj: fromSnapshot.xg_pj ?? fromApi.xg_pj,
    xg_sofrido_pj: fromSnapshot.xg_sofrido_pj ?? fromApi.xg_sofrido_pj,
    saldo_pj: fromSnapshot.saldo_pj ?? fromApi.saldo_pj,
    metricas_chave: fromSnapshot.metricas_chave?.length ? fromSnapshot.metricas_chave : fromApi.metricas_chave,
  };
}

function detailFromSnapshot(team: string, snapshots: TeamSnapshot[], points: StylePoint[], matches: Match[], snapshot: number): TeamStyleDetail | null {
  const snap = snapshots.find((s) => s.team === team);
  if (!snap) return null;
  const point = points.find((p) => p.team === team);
  const arquetipo = (typeof snap.estilo_jogo === "string" && snap.estilo_jogo) || point?.arquetipo || "Sem estilo";
  const jogos = toNum(snap.jogos) ?? point?.jogos ?? 0;
  const pointsTotal = toNum(snap.points) ?? 0;
  const ptsJogo = jogos > 0 ? pointsTotal / jogos : 0;
  const record = recordForTeam(team, matches, snapshot);
  return {
    team,
    arquetipo,
    jogos,
    points: pointsTotal,
    pts_jogo: ptsJogo,
    aproveitamento: toNum(snap.aproveitamento) != null
      ? Math.round((toNum(snap.aproveitamento) as number) * 100)
      : jogos > 0 ? Math.round((pointsTotal / (jogos * 3)) * 100) : 0,
    vitorias: record?.vitorias,
    empates: record?.empates,
    derrotas: record?.derrotas,
    gols_pj: perGameSnap(snap, "gols", "gols_pj"),
    xg_pj: perGameSnap(snap, "xg", "xg_pj"),
    xg_sofrido_pj: perGameSnap(snap, "xg_sofrido", "xg_sofrido_pj"),
    saldo_pj: perGameSnap(snap, "saldo_gols", "saldo_gols_pj"),
    metricas_chave: metricsFromSnapshot(snap, arquetipo),
  };
}

function recordForTeam(team: string, matches: Match[], snapshot: number) {
  const finished = finishedMatchesUpTo(matches, snapshot);
  let vitorias = 0, empates = 0, derrotas = 0;
  for (const m of finished) {
    const isHome = m.home_team === team;
    const isAway = m.away_team === team;
    if (!isHome && !isAway) continue;
    const gf = isHome ? m.home_score : m.away_score;
    const ga = isHome ? m.away_score : m.home_score;
    if (gf == null || ga == null) continue;
    if (gf > ga) vitorias += 1;
    else if (gf === ga) empates += 1;
    else derrotas += 1;
  }
  const total = vitorias + empates + derrotas;
  return total > 0 ? { vitorias, empates, derrotas } : null;
}

function metricsFromSnapshot(snap: TeamSnapshot, arquetipo: string): NonNullable<TeamStyleDetail["metricas_chave"]> {
  const metric = (label: string, value: number | null, unit = "", decimals = 2) =>
    value == null ? null : { label, valor: value, unit, decimals };
  const pct = (key: string) => {
    const v = toNum(snap[key]);
    if (v == null) return null;
    return v <= 1 ? v * 100 : v;
  };
  const raw = (key: string) => toNum(snap[key]);
  const per = (total: string, pj: string) => perGameSnap(snap, total, pj);
  const saldo = per("saldo_gols", "saldo_gols_pj");

  const map: Record<string, Array<ReturnType<typeof metric>>> = {
    "Pressão Alta": [
      metric("Pressão alta", raw("fase_pressao_alta"), "", 1),
      metric("Roubadas/jogo", per("turnovers_forcados", "turnovers_forcados_pj")),
      metric("xG sofrido/jogo", per("xg_sofrido", "xg_sofrido_pj")),
      metric("Saldo/jogo", saldo),
    ],
    "Posse": [
      metric("Posse média", pct("posse"), "%", 1),
      metric("Controle terço final", pct("final_third_control"), "%", 1),
      metric("Precisão passe", pct("precisao_passes"), "%", 1),
      metric("xG sofrido/jogo", per("xg_sofrido", "xg_sofrido_pj")),
    ],
    "Retranca": [
      metric("xG sofrido/jogo", per("xg_sofrido", "xg_sofrido_pj")),
      metric("Gols sofridos/jogo", per("gols_contra", "gols_contra_pj")),
      metric("Clean sheets", cleanSheetPct(snap), "%", 1),
      metric("Chutes no alvo sofridos/jogo", per("chutes_sofridos_no_alvo", "chutes_sofridos_no_alvo_pj")),
    ],
    "Jogo Direto": [
      metric("Bola longa", raw("fase_bola_longa"), "", 1),
      metric("Quebras de linha/jogo", per("linebreaks", "linebreaks_pj")),
      metric("Progressões/jogo", per("progressoes_bola", "progressoes_bola_pj")),
      metric("xG/jogo", per("xg", "xg_pj")),
    ],
    "Contra-ataque": [
      metric("Contra-ataque", raw("fase_contra_ataque"), "", 1),
      metric("Verticalidade", raw("estilo_verticalidade"), "", 1),
      metric("xG/jogo", per("xg", "xg_pj")),
      metric("Saldo/jogo", saldo),
    ],
    "Bola Parada": [
      metric("Bola parada", raw("fase_bola_parada"), "", 1),
      metric("Escanteios/jogo", per("escanteios", "escanteios_pj")),
      metric("xG/jogo", per("xg", "xg_pj")),
      metric("Gols/jogo", per("gols", "gols_pj")),
    ],
  };
  return (map[arquetipo] ?? [
    metric("Gols/jogo", per("gols", "gols_pj")),
    metric("xG/jogo", per("xg", "xg_pj")),
    metric("xG sofrido/jogo", per("xg_sofrido", "xg_sofrido_pj")),
    metric("Saldo/jogo", saldo),
  ]).filter((m): m is NonNullable<typeof m> => !!m);
}

function perGameSnap(snap: TeamSnapshot, totalKey: string, pjKey: string) {
  const pj = toNum(snap[pjKey]);
  if (pj != null) return pj;
  const total = toNum(snap[totalKey]);
  const jogos = toNum(snap.jogos);
  return total != null && jogos && jogos > 0 ? total / jogos : null;
}

function cleanSheetPct(snap: TeamSnapshot) {
  const clean = toNum(snap.clean_sheet);
  const jogos = toNum(snap.jogos);
  return clean != null && jogos && jogos > 0 ? (clean / jogos) * 100 : null;
}

function toNum(v: unknown) {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
