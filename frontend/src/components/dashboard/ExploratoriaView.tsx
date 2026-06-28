"use client";

import React from "react";
import { ExploratoryData, Match, TeamSnapshot } from "@/lib/api";
import { useExploratory, useTeamSnapshots } from "@/lib/hooks";
import Flag from "@/components/ui/Flag";
import Spinner from "@/components/ui/Spinner";
import EstilosMapa from "@/components/dashboard/EstilosMapa";
import TeamProfile from "@/components/dashboard/TeamProfile";
import { STYLE_COLOR, STYLE_ORDER, styleDescription, styleName } from "@/lib/styleMeta";

type StyleRow = NonNullable<ExploratoryData["estilo_resultado"]>[number];
type StylePoint = NonNullable<ExploratoryData["estilos_mapa"]>[number];
type TeamStyleDetail = NonNullable<StyleRow["times_detalhe"]>[number];
type StyleMatchup = NonNullable<ExploratoryData["confrontos_estilo"]>[number];
type TeamGame = {
  matchId: string;
  matchNumber: number;
  opponent: string;
  opponentStyle: string;
  stage: string | null;
  score: string;
  result: "V" | "E" | "D";
  gf: number | null;
  ga: number | null;
};

const num = (v: number | null | undefined, d = 2) =>
  typeof v === "number" ? v.toFixed(d).replace(".", ",") : "—";

export default function ExploratoriaView({
  snapshot,
  enabled,
  matches = [],
  selectedTeams = [],
  onToggleTeam,
}: {
  snapshot: number;
  enabled: boolean;
  matches?: Match[];
  selectedTeams?: string[];
  onToggleTeam?: (t: string) => void;
}) {
  const { explore, isLoading } = useExploratory(snapshot, enabled);
  const { snapshots: teamSnaps } = useTeamSnapshots(snapshot);
  const [selectedStyle, setSelectedStyle] = React.useState<string | null>(null);
  const [compareFocus, setCompareFocus] = React.useState<"a" | "b">("a");
  const [pickedAnalysisMode, setPickedAnalysisMode] = React.useState<"single" | "compare" | null>(null);
  const analysisMode = pickedAnalysisMode ?? (selectedTeams.length >= 2 ? "compare" : "single");

  const chooseAnalysisMode = React.useCallback((mode: "single" | "compare") => {
    setPickedAnalysisMode(mode);
  }, []);

  if (isLoading) {
    return <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}><Spinner /></div>;
  }
  if (!explore || !explore.estilo_resultado?.length) {
    return <Aviso texto="Amostra ainda insuficiente para comparar estilos — avance no tempo ou rode uma coleta." />;
  }

  const rows = explore.estilo_resultado;
  const mapRows = explore.estilos_mapa ?? [];
  const teamDetails = rows.flatMap((r) => r.times_detalhe ?? []);
  const allTeamDetails = Array.from(new Set([
    ...teamDetails.map((d) => d.team),
    ...mapRows.map((r) => r.team),
    ...teamSnaps.map((s) => s.team),
  ]))
    .map((team) => resolveTeamDetail(team, teamDetails, teamSnaps, mapRows, matches, snapshot))
    .filter((d): d is TeamStyleDetail => !!d)
    .sort((a, b) => b.pts_jogo - a.pts_jogo || a.team.localeCompare(b.team, "pt-BR"));
  const selectedDetails = selectedTeams
    .map((team) => resolveTeamDetail(team, teamDetails, teamSnaps, mapRows, matches, snapshot))
    .filter((d): d is TeamStyleDetail => !!d);
  const selectedTeamStyle = selectedDetails.length === 1 ? selectedDetails[0].arquetipo : null;
  const activeStyle = selectedTeamStyle ?? (rows.some((r) => r.arquetipo === selectedStyle) ? selectedStyle! : rows[0].arquetipo);
  const active = rows.find((r) => r.arquetipo === activeStyle) ?? rows[0];
  const activeTeams = selectedDetails.length > 0
    ? selectedDetails.map((d) => d.team)
    : active.times ?? mapRows.filter((r) => r.arquetipo === activeStyle).map((r) => r.team);
  const teamNames = allTeamDetails.map((team) => team.team);
  const defaultSingleTeam = selectedTeams.find((team) => teamNames.includes(team)) ?? teamNames[0] ?? "";
  const singleTeam = defaultSingleTeam;
  const defaultTeamA = selectedTeams.find((team) => teamNames.includes(team)) ?? singleTeam ?? teamNames[0] ?? "";
  const teamA = defaultTeamA;
  const defaultTeamB = selectedTeams.find((team) => team !== teamA && teamNames.includes(team)) ?? teamNames.find((team) => team !== teamA) ?? teamA;
  const teamB = defaultTeamB;
  const focusTeam = (team: string) => {
    if (!onToggleTeam) return;
    selectedTeams.filter((t) => t !== team).forEach((t) => onToggleTeam(t));
    if (!selectedTeams.includes(team)) onToggleTeam(team);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <AnalysisModePicker mode={analysisMode} onChange={chooseAnalysisMode} />

      {analysisMode === "single" ? (
        <SingleTeamAnalysis
          team={singleTeam}
          teams={allTeamDetails}
          styleRows={rows}
          matches={matches}
          snapshot={snapshot}
        />
      ) : (
        <TwoTeamAnalysis
          teamA={teamA}
          teamB={teamB}
          focus={compareFocus}
          teams={allTeamDetails}
          styleRows={rows}
          rows={explore!.confrontos_estilo ?? []}
          matches={matches}
          snapshot={snapshot}
          onFocusChange={setCompareFocus}
        />
      )}

      {false && (
      <>
      <StyleMatchups
        rows={explore!.confrontos_estilo ?? []}
        styleRows={rows}
        teams={allTeamDetails}
        activeStyle={activeStyle}
        onPickStyle={setSelectedStyle}
        onPickTeam={focusTeam}
      />

      <Panel
        titulo={`Mapa de estilos: ${selectedDetails.length ? "seleções em foco" : styleName(activeStyle)}`}
        leitura={`Bandeiras destacadas: ${activeTeams.join(", ") || "nenhuma seleção neste recorte"}.`}
        sub="Mapa de apoio para localizar cada selecao por posse, verticalidade e estilo dominante."
      >
        <div style={{ padding: "10px 12px 8px" }}>
          <StyleLegend />
          <EstilosMapa rows={mapRows} selected={selectedTeams} activeStyle={selectedDetails.length ? null : activeStyle} onToggle={onToggleTeam ?? (() => {})} />
        </div>
      </Panel>

      <StyleLeaderboard rows={rows} teams={allTeamDetails} activeStyle={activeStyle} activeTeam={selectedDetails.length === 1 ? selectedDetails[0].team : null} onPickStyle={setSelectedStyle} onPickTeam={focusTeam} />
      </>
      )}
    </div>
  );
}

function AnalysisModePicker({ mode, onChange }: { mode: "single" | "compare"; onChange: (mode: "single" | "compare") => void }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))", gap: 10 }}>
      <button
        type="button"
        onClick={() => onChange("single")}
        style={{
          border: `1px solid ${mode === "single" ? "var(--accent)" : "var(--surface2)"}`,
          borderRadius: 8,
          background: mode === "single" ? "color-mix(in srgb, var(--accent) 12%, var(--background))" : "var(--background)",
          color: "var(--text)",
          padding: "12px 14px",
          cursor: "pointer",
          fontFamily: "inherit",
          textAlign: "left",
        }}
      >
        <span style={{ display: "block", fontSize: 14, fontWeight: 900 }}>1 seleção</span>
        <span style={{ display: "block", color: "var(--text-muted)", fontSize: 12, marginTop: 3 }}>Ver estilo, rendimento e adversários do time escolhido.</span>
      </button>
      <button
        type="button"
        onClick={() => onChange("compare")}
        style={{
          border: `1px solid ${mode === "compare" ? "var(--accent)" : "var(--surface2)"}`,
          borderRadius: 8,
          background: mode === "compare" ? "color-mix(in srgb, var(--accent) 12%, var(--background))" : "var(--background)",
          color: "var(--text)",
          padding: "12px 14px",
          cursor: "pointer",
          fontFamily: "inherit",
          textAlign: "left",
        }}
      >
        <span style={{ display: "block", fontSize: 14, fontWeight: 900 }}>2 seleções</span>
        <span style={{ display: "block", color: "var(--text-muted)", fontSize: 12, marginTop: 3 }}>Comparar estilos, métricas e histórico de uma das duas.</span>
      </button>
    </div>
  );
}

function SingleTeamAnalysis({
  team,
  teams,
  styleRows,
  matches,
  snapshot,
}: {
  team: string;
  teams: TeamStyleDetail[];
  styleRows: StyleRow[];
  matches: Match[];
  snapshot: number;
}) {
  const detail = teams.find((item) => item.team === team) ?? teams[0] ?? null;
  const styleRow = detail ? styleRows.find((row) => row.arquetipo === detail.arquetipo) ?? null : null;
  const color = detail ? STYLE_COLOR[detail.arquetipo] ?? "var(--accent)" : "var(--accent)";
  const games = detail ? teamGames(detail.team, matches, snapshot, teams) : [];

  return (
    <Panel
      titulo="1 selecao"
      leitura={detail ? `${detail.team}: estilo ${styleName(detail.arquetipo)}, rendimento e adversarios enfrentados.` : "Escolha uma selecao para analisar."}
      sub="Tudo aqui fala apenas do time escolhido."
    >
      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>
        {detail && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))", gap: 12, alignItems: "start" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <TeamProfileCard detail={detail} title="Raio-x do time" />
              <OpponentList title="Jogos e estilos enfrentados" games={games} accent={color} compact />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))", gap: 12, alignItems: "start" }}>
              <StyleIdentityCard detail={detail} />
              <StyleImpactCard detail={detail} styleRow={styleRow} />
              <OpponentStyleSummary games={games} />
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

function TwoTeamAnalysis({
  teamA,
  teamB,
  focus,
  teams,
  styleRows,
  rows,
  matches,
  snapshot,
  onFocusChange,
}: {
  teamA: string;
  teamB: string;
  focus: "a" | "b";
  teams: TeamStyleDetail[];
  styleRows: StyleRow[];
  rows: StyleMatchup[];
  matches: Match[];
  snapshot: number;
  onFocusChange: (side: "a" | "b") => void;
}) {
  const detailA = teams.find((item) => item.team === teamA) ?? teams[0] ?? null;
  const detailB = teams.find((item) => item.team === teamB) ?? teams.find((item) => item.team !== detailA?.team) ?? null;
  const styleA = detailA?.arquetipo ?? "";
  const styleB = detailB?.arquetipo ?? "";
  const colorA = STYLE_COLOR[styleA] ?? "var(--accent)";
  const colorB = STYLE_COLOR[styleB] ?? "var(--accent)";
  const styleRowA = styleRows.find((row) => row.arquetipo === styleA) ?? null;
  const styleRowB = styleRows.find((row) => row.arquetipo === styleB) ?? null;
  const matchup = rows.find((row) => row.estilo === styleA && row.contra === styleB) ?? null;
  const reverse = rows.find((row) => row.estilo === styleB && row.contra === styleA) ?? null;
  const focusDetail = focus === "a" ? detailA : detailB;
  const otherDetail = focus === "a" ? detailB : detailA;
  const focusGames = focusDetail ? teamGames(focusDetail.team, matches, snapshot, teams) : [];
  const directGames = detailA && detailB ? headToHeadGames(detailA.team, detailB.team, matches, snapshot, teams) : [];

  return (
    <Panel
      titulo="2 selecoes"
      leitura={detailA && detailB ? `${detailA.team} (${styleName(styleA)}) contra ${detailB.team} (${styleName(styleB)}).` : "Escolha duas selecoes para comparar."}
      sub="Tudo aqui compara A contra B. O historico exibido mostra os adversarios de uma das duas."
    >
      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>
        {detailA && detailB && (
          <>
            <CompareHeader detailA={detailA} detailB={detailB} />
            <PairReadingCard detailA={detailA} detailB={detailB} matchup={matchup} reverse={reverse} />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))", gap: 12 }}>
              <TeamProfileCard detail={detailA} title="Selecao A" />
              <StyleVersusCard matchup={matchup} reverse={reverse} styleA={styleA} styleB={styleB} colorA={colorA} colorB={colorB} rowA={styleRowA} rowB={styleRowB} />
              <TeamProfileCard detail={detailB} title="Selecao B" />
            </div>

            <label style={{ display: "flex", flexDirection: "column", gap: 5, maxWidth: 360 }}>
              <span style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>Mostrar historico de</span>
              <select
                value={focus}
                onChange={(event) => onFocusChange(event.target.value as "a" | "b")}
                style={{
                  minHeight: 38,
                  width: "100%",
                  background: "var(--surface)",
                  color: "var(--text)",
                  border: "1px solid var(--surface2)",
                  borderRadius: 8,
                  padding: "0 10px",
                  fontFamily: "inherit",
                  fontSize: 13,
                  fontWeight: 800,
                  outline: "none",
                }}
              >
                <option value="a">{detailA.team}</option>
                <option value="b">{detailB.team}</option>
              </select>
            </label>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", gap: 12, alignItems: "start" }}>
              <OpponentList
                title={focusDetail ? `Adversarios de ${focusDetail.team}` : "Adversarios"}
                games={focusGames}
                accent={STYLE_COLOR[focusDetail?.arquetipo ?? ""] ?? "var(--accent)"}
                highlightTeam={otherDetail?.team}
              />
              <OpponentList
                title="Confronto entre as duas"
                games={directGames}
                accent="var(--accent)"
                empty="Ainda nao houve confronto direto finalizado no recorte."
              />
            </div>
          </>
        )}
      </div>
    </Panel>
  );
}

function TeamSelect({ label, value, teams, onChange, blocked }: { label: string; value: string; teams: TeamStyleDetail[]; onChange: (team: string) => void; blocked?: string }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <span style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        style={{
          minHeight: 38,
          width: "100%",
          background: "var(--surface)",
          color: "var(--text)",
          border: "1px solid var(--surface2)",
          borderRadius: 8,
          padding: "0 10px",
          fontFamily: "inherit",
          fontSize: 13,
          fontWeight: 800,
          outline: "none",
        }}
      >
        {teams.map((team) => (
          <option key={team.team} value={team.team} disabled={team.team === blocked}>
            {team.team} - {styleName(team.arquetipo)}
          </option>
        ))}
      </select>
    </label>
  );
}

function CompareHeader({ detailA, detailB }: { detailA: TeamStyleDetail; detailB: TeamStyleDetail }) {
  const colorA = STYLE_COLOR[detailA.arquetipo] ?? "var(--accent)";
  const colorB = STYLE_COLOR[detailB.arquetipo] ?? "var(--accent)";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 10, alignItems: "center", background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "10px 12px" }}>
      <CompareHeaderTeam detail={detailA} color={colorA} align="left" />
      <span style={{ color: "var(--text-muted)", fontSize: 11, fontWeight: 900, textTransform: "uppercase", letterSpacing: 0.4 }}>vs</span>
      <CompareHeaderTeam detail={detailB} color={colorB} align="right" />
    </div>
  );
}

function CompareHeaderTeam({ detail, color, align }: { detail: TeamStyleDetail; color: string; align: "left" | "right" }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: align === "right" ? "flex-end" : "flex-start", gap: 8, minWidth: 0, textAlign: align }}>
      {align === "left" && <Flag team={detail.team} height={15} />}
      <span style={{ minWidth: 0 }}>
        <b style={{ display: "block", color: "var(--text)", fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{detail.team}</b>
        <span style={{ display: "block", color, fontSize: 11.5, fontWeight: 800, marginTop: 2 }}>{styleName(detail.arquetipo)}</span>
      </span>
      {align === "right" && <Flag team={detail.team} height={15} />}
    </div>
  );
}

// Adaptador fino: usa o componente compartilhado TeamProfile (variant compact),
// montando um TeamSnapshot mínimo + overlay a partir do TeamStyleDetail.
function TeamProfileCard({ detail, title }: { detail: TeamStyleDetail; title: string }) {
  const snapshot = {
    team: detail.team,
    jogos: detail.jogos ?? null,
    points: detail.points ?? null,
    saldo_gols: null,
    estilo_jogo: detail.arquetipo,
  } as unknown as TeamSnapshot;
  return (
    <TeamProfile
      snapshot={snapshot}
      variant="compact"
      title={title}
      overlay={{
        arquetipo: detail.arquetipo,
        vitorias: detail.vitorias,
        empates: detail.empates,
        derrotas: detail.derrotas,
        pts_jogo: detail.pts_jogo,
        saldo_pj: detail.saldo_pj,
        aproveitamento_pct: detail.aproveitamento,
      }}
    />
  );
}

function StyleIdentityCard({ detail }: { detail: TeamStyleDetail }) {
  const color = STYLE_COLOR[detail.arquetipo] ?? "var(--accent)";
  const metrics = identityMetrics(detail);
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "12px 13px", minWidth: 0 }}>
      <div style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>Por que esse estilo</div>
      <div style={{ color, fontSize: 16, fontWeight: 900, marginTop: 7 }}>{styleName(detail.arquetipo)}</div>
      <div style={{ color: "var(--text-muted)", fontSize: 11.5, lineHeight: 1.45, marginTop: 5 }}>{styleDescription(detail.arquetipo)}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 7, marginTop: 11 }}>
        {metrics.map((metric) => (
          <div key={metric.label} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "center" }}>
            <span style={{ color: "var(--text-muted)", fontSize: 11 }}>{metric.label}</span>
            <b style={{ color, fontSize: 12.5 }}>{fmtMetric(metric)}</b>
          </div>
        ))}
      </div>
    </div>
  );
}

function StyleImpactCard({ detail, styleRow }: { detail: TeamStyleDetail; styleRow: StyleRow | null }) {
  const color = STYLE_COLOR[detail.arquetipo] ?? "var(--accent)";
  const metrics = [
    { label: "Pts/jogo", team: detail.pts_jogo, style: styleRow?.pts_jogo },
    { label: "Aproveit.", team: detail.aproveitamento, style: styleRow?.aproveitamento, suffix: "%" },
    { label: "Saldo/jogo", team: detail.saldo_pj, style: styleRow?.saldo_pj },
    { label: "xG/jogo", team: detail.xg_pj, style: styleRow?.xg_pj },
  ];
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "12px 13px", minWidth: 0 }}>
      <div style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>Resultado dentro do estilo</div>
      <div style={{ color: "var(--text)", fontSize: 13, fontWeight: 800, marginTop: 7 }}>{styleResultSentence(detail, styleRow)}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 7, marginTop: 11 }}>
        {metrics.map((metric) => {
          const diff = typeof metric.team === "number" && typeof metric.style === "number" ? metric.team - metric.style : null;
          return (
            <div key={metric.label} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "center" }}>
              <span style={{ color: "var(--text-muted)", fontSize: 11 }}>{metric.label}</span>
              <b style={{ color, fontSize: 12.5 }}>
                {formatMetricValue(metric.team, metric.suffix)} <span style={{ color: "var(--text-muted)", fontWeight: 700 }}>vs {formatMetricValue(metric.style, metric.suffix)}</span>
                {diff != null && <span style={{ color: diff >= 0 ? "var(--green)" : "var(--red)", marginLeft: 6 }}>{diff >= 0 ? "+" : ""}{num(diff)}</span>}
              </b>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PairReadingCard({ detailA, detailB, matchup, reverse }: { detailA: TeamStyleDetail; detailB: TeamStyleDetail; matchup: StyleMatchup | null; reverse: StyleMatchup | null }) {
  const colorA = STYLE_COLOR[detailA.arquetipo] ?? "var(--accent)";
  const colorB = STYLE_COLOR[detailB.arquetipo] ?? "var(--accent)";
  const edge = teamEdge(detailA, detailB);
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "12px 13px", minWidth: 0 }}>
      <div style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>Leitura do duelo</div>
      <div style={{ color: "var(--text)", fontSize: 13, fontWeight: 800, lineHeight: 1.45, marginTop: 7 }}>
        {edge.team} chega melhor em resultado recente ({num(edge.diff)} pts/jogo de vantagem). O duelo de estilos e <b style={{ color: colorA }}>{styleName(detailA.arquetipo)}</b> contra <b style={{ color: colorB }}>{styleName(detailB.arquetipo)}</b>.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8, marginTop: 11 }}>
        <SmallMetric label={`${detailA.team} pts/jogo`} value={num(detailA.pts_jogo)} color={colorA} />
        <SmallMetric label={`${detailB.team} pts/jogo`} value={num(detailB.pts_jogo)} color={colorB} />
        <SmallMetric label="Estilo A vs B" value={matchup ? `${num(matchup.pts_jogo)} pts/jogo` : "sem base"} color={colorA} />
        <SmallMetric label="Estilo B vs A" value={reverse ? `${num(reverse.pts_jogo)} pts/jogo` : "sem base"} color={colorB} />
      </div>
    </div>
  );
}

function StyleVersusCard({
  matchup,
  reverse,
  styleA,
  styleB,
  colorA,
  colorB,
  rowA,
  rowB,
}: {
  matchup: StyleMatchup | null;
  reverse: StyleMatchup | null;
  styleA: string;
  styleB: string;
  colorA: string;
  colorB: string;
  rowA: StyleRow | null;
  rowB: StyleRow | null;
}) {
  const styleEdge = matchup && reverse
    ? matchup.pts_jogo === reverse.pts_jogo
      ? "Os dois estilos ficaram equilibrados neste recorte."
      : matchup.pts_jogo > reverse.pts_jogo
        ? `${styleName(styleA)} performou melhor contra ${styleName(styleB)}.`
        : `${styleName(styleB)} performou melhor contra ${styleName(styleA)}.`
    : "Ainda falta base historica suficiente para cravar vantagem entre estes estilos.";
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "12px 13px", minWidth: 0 }}>
      <div style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>Comparativo de estilos</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
        <b style={{ color: colorA }}>{styleName(styleA)}</b>
        <span style={{ color: "var(--text-muted)", fontSize: 12 }}>vs</span>
        <b style={{ color: colorB }}>{styleName(styleB)}</b>
      </div>
      <div style={{ color: "var(--text)", fontSize: 12.5, fontWeight: 800, lineHeight: 1.4, marginTop: 7 }}>{styleEdge}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 8, marginTop: 10 }}>
        <SmallMetric label="A pts/jogo" value={num(rowA?.pts_jogo)} color={colorA} />
        <SmallMetric label="B pts/jogo" value={num(rowB?.pts_jogo)} color={colorB} />
        <SmallMetric label="A aproveit." value={rowA ? `${rowA.aproveitamento}%` : "—"} color={colorA} />
        <SmallMetric label="B aproveit." value={rowB ? `${rowB.aproveitamento}%` : "—"} color={colorB} />
      </div>
      <div style={{ borderTop: "1px solid var(--surface2)", marginTop: 11, paddingTop: 10 }}>
        {matchup ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
            <SmallMetric label="A vs B" value={num(matchup.pts_jogo)} color={colorA} />
            <SmallMetric label="Aproveit." value={`${matchup.aproveitamento}%`} color={colorA} />
            <SmallMetric label="Jogos" value={`${matchup.jogos}`} color={colorA} />
          </div>
        ) : (
          <div style={{ color: "var(--text-muted)", fontSize: 12 }}>Sem base finalizada desse estilo contra o outro.</div>
        )}
        {reverse && (
          <div style={{ marginTop: 8, color: "var(--text-muted)", fontSize: 11 }}>
            Inverso: <b style={{ color: colorB }}>{num(reverse.pts_jogo)}</b> pts/jogo para {styleName(styleB)}.
          </div>
        )}
      </div>
    </div>
  );
}

function OpponentStyleSummary({ games }: { games: TeamGame[] }) {
  const rows = opponentStyleSummary(games);
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "12px 13px", minWidth: 0 }}>
      <div style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>Resultado contra estilos</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 7, marginTop: 9 }}>
        {rows.map((row) => {
          const color = STYLE_COLOR[row.style] ?? "var(--accent)";
          return (
            <div key={row.style} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "center" }}>
              <span>
                <span style={{ display: "block", color, fontSize: 12.5, fontWeight: 800 }}>{styleName(row.style)}</span>
                <span style={{ display: "block", color: "var(--text-muted)", fontSize: 10.5 }}>{row.games} jogo(s) - {row.record}</span>
              </span>
              <b style={{ color, fontSize: 12.5 }}>{num(row.ptsPerGame)} pts/jogo</b>
            </div>
          );
        })}
        {!rows.length && <div style={{ color: "var(--text-muted)", fontSize: 12 }}>Sem jogos finalizados para resumir.</div>}
      </div>
    </div>
  );
}

function OpponentList({ title, games, accent, highlightTeam, compact = false, empty = "Sem jogos finalizados nesse recorte." }: { title: string; games: TeamGame[]; accent: string; highlightTeam?: string; compact?: boolean; empty?: string }) {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "12px 13px", minWidth: 0 }}>
      <div style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>{title}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 9, maxHeight: compact ? 210 : 300, overflowY: "auto", paddingRight: 2 }}>
        {games.map((game) => {
          const highlighted = game.opponent === highlightTeam;
          const resultColor = game.result === "V" ? "var(--green)" : game.result === "D" ? "var(--red)" : "var(--text-muted)";
          return (
            <div key={`${game.matchId}-${game.opponent}`} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "center", border: `1px solid ${highlighted ? accent : "var(--surface2)"}`, borderRadius: 7, background: "var(--background)", padding: "7px 8px" }}>
              <span style={{ minWidth: 0 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 7, color: "var(--text)", fontSize: 12.5, fontWeight: 800 }}>
                  <Flag team={game.opponent} height={12} />{game.opponent}
                </span>
                <span style={{ display: "block", color: STYLE_COLOR[game.opponentStyle] ?? "var(--text-muted)", fontSize: 10.5, marginTop: 2 }}>{styleName(game.opponentStyle)}{game.stage ? ` - ${game.stage}` : ""}</span>
              </span>
              <span style={{ textAlign: "right" }}>
                <b style={{ color: resultColor, fontSize: 12.5 }}>{game.result} {game.score}</b>
                <span style={{ display: "block", color: "var(--text-muted)", fontSize: 10.5 }}>Jogo {game.matchNumber}</span>
              </span>
            </div>
          );
        })}
        {!games.length && <div style={{ color: "var(--text-muted)", fontSize: 12, padding: "8px 2px" }}>{empty}</div>}
      </div>
    </div>
  );
}

function StyleMatchups({
  rows,
  styleRows,
  teams,
  activeStyle,
  onPickStyle,
  onPickTeam,
}: {
  rows: StyleMatchup[];
  styleRows: StyleRow[];
  teams: TeamStyleDetail[];
  activeStyle: string;
  onPickStyle: (style: string) => void;
  onPickTeam: (team: string) => void;
}) {
  if (!rows.length && !styleRows.length) return null;
  const orderedStyles: readonly string[] = STYLE_ORDER;
  const stylesInRows = new Set([...rows.flatMap((r) => [r.estilo, r.contra]), ...styleRows.map((r) => r.arquetipo)]);
  const knownStyles = orderedStyles.filter((style) => stylesInRows.has(style));
  const otherStyles = [...rows.flatMap((r) => [r.estilo, r.contra]), ...styleRows.map((r) => r.arquetipo)]
    .filter((style) => !knownStyles.includes(style));
  const allStyles = React.useMemo(
    () => [...knownStyles, ...Array.from(new Set(otherStyles)).sort((a, b) => styleName(a).localeCompare(styleName(b), "pt-BR"))],
    [knownStyles.join("|"), otherStyles.join("|")],
  );
  const defaultFirst = allStyles.includes(activeStyle) ? activeStyle : allStyles[0];
  const styleKey = allStyles.join("|");
  const bestOpponentFor = React.useCallback((style: string) => {
    const options = rows
      .filter((r) => r.estilo === style)
      .sort((a, b) => b.jogos - a.jogos || b.pts_jogo - a.pts_jogo || (b.saldo_pj ?? 0) - (a.saldo_pj ?? 0));
    return options[0]?.contra ?? allStyles.find((candidate) => candidate !== style) ?? style;
  }, [rows, styleKey]);
  const [firstStyle, setFirstStyle] = React.useState(defaultFirst);
  const [secondStyle, setSecondStyle] = React.useState(() => bestOpponentFor(defaultFirst));

  React.useEffect(() => {
    if (!allStyles.includes(firstStyle)) {
      setFirstStyle(defaultFirst);
      setSecondStyle(bestOpponentFor(defaultFirst));
    }
  }, [allStyles, bestOpponentFor, defaultFirst, firstStyle]);

  const firstColor = STYLE_COLOR[firstStyle] ?? "var(--accent)";
  const secondColor = STYLE_COLOR[secondStyle] ?? "var(--accent)";
  const firstRow = styleRows.find((r) => r.arquetipo === firstStyle) ?? null;
  const secondRow = styleRows.find((r) => r.arquetipo === secondStyle) ?? null;
  const firstTeams = teams.filter((team) => team.arquetipo === firstStyle).sort((a, b) => b.pts_jogo - a.pts_jogo || a.team.localeCompare(b.team, "pt-BR"));
  const secondTeams = teams.filter((team) => team.arquetipo === secondStyle).sort((a, b) => b.pts_jogo - a.pts_jogo || a.team.localeCompare(b.team, "pt-BR"));
  const matchup = rows.find((r) => r.estilo === firstStyle && r.contra === secondStyle) ?? null;
  const reverse = rows.find((r) => r.estilo === secondStyle && r.contra === firstStyle) ?? null;
  const handleFirst = (style: string) => {
    setFirstStyle(style);
    if (style === secondStyle) setSecondStyle(bestOpponentFor(style));
    onPickStyle(style);
  };
  const handleSecond = (style: string) => {
    setSecondStyle(style);
  };
  const swapStyles = () => {
    setFirstStyle(secondStyle);
    setSecondStyle(firstStyle);
    onPickStyle(secondStyle);
  };
  const readable = matchup
    ? `${styleName(firstStyle)} contra ${styleName(secondStyle)}: ${num(matchup.pts_jogo)} pts/jogo, ${matchup.aproveitamento}% de aproveitamento, ${num(matchup.saldo_pj)} saldo/jogo em ${matchup.jogos} jogos.`
    : firstStyle === secondStyle
      ? "Escolha dois estilos diferentes para comparar os grupos."
      : `Ainda nao ha jogos finalizados de ${styleName(firstStyle)} contra ${styleName(secondStyle)} neste recorte.`;

  return (
    <Panel
      titulo="Comparar estilos"
      leitura={readable}
      sub="Dois grupos de selecoes, um confronto direto."
    >
      <div style={{ padding: 14, display: "flex", gap: 10, alignItems: "end", flexWrap: "wrap" }}>
        <StyleSelect label="Estilo A" value={firstStyle} options={allStyles} color={firstColor} onChange={handleFirst} />
        <button
          type="button"
          onClick={swapStyles}
          title="Trocar lados"
          style={{
            minHeight: 38,
            border: "1px solid var(--surface2)",
            borderRadius: 8,
            background: "var(--surface)",
            color: "var(--text)",
            padding: "0 12px",
            cursor: "pointer",
            fontFamily: "inherit",
            fontSize: 12,
            fontWeight: 800,
          }}
        >
          Trocar
        </button>
        <StyleSelect label="Estilo B" value={secondStyle} options={allStyles} color={secondColor} onChange={handleSecond} blocked={firstStyle} />
      </div>

      <div style={{ padding: "0 14px 14px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 300px), 1fr))", gap: 12, alignItems: "start" }}>
        <StyleCompareSide
          title="Grupo A"
          selected={firstStyle}
          color={firstColor}
          row={firstRow}
          teams={firstTeams}
          onPickTeam={onPickTeam}
        />

        <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "12px 13px", minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
            <div>
              <div style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>confronto direto</div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 3, flexWrap: "wrap" }}>
                <b style={{ color: firstColor, fontSize: 15 }}>{styleName(firstStyle)}</b>
                <span style={{ color: "var(--text-muted)", fontSize: 12 }}>contra</span>
                <b style={{ color: secondColor, fontSize: 15 }}>{styleName(secondStyle)}</b>
              </div>
            </div>
            {matchup && <span style={{ color: "var(--text-muted)", fontSize: 11, fontWeight: 800 }}>{matchup.jogos} jogos</span>}
          </div>

          {matchup ? (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(96px, 1fr))", gap: 8, marginTop: 12 }}>
                <BigMetric label="Pts/jogo" value={num(matchup.pts_jogo)} color={firstColor} />
                <BigMetric label="Aproveit." value={`${matchup.aproveitamento}%`} color={firstColor} />
                <BigMetric label="Campanha" value={`${matchup.vitorias}V ${matchup.empates}E ${matchup.derrotas}D`} color={firstColor} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(96px, 1fr))", gap: 8, marginTop: 8 }}>
                <SmallMetric label="Saldo/jogo" value={num(matchup.saldo_pj)} color={firstColor} />
                <SmallMetric label="xG +/-" value={num(matchup.xg_diff_pj)} color={firstColor} />
                <SmallMetric label="Score +/-" value={num(matchup.score_diff_medio, 1)} color={firstColor} />
              </div>
              {!!matchup.times?.length && (
                <div style={{ marginTop: 12, color: "var(--text-muted)", fontSize: 11, lineHeight: 1.45 }}>
                  <b style={{ color: "var(--text)", fontSize: 11.5 }}>Selecoes na amostra:</b> {matchup.times.join(", ")}
                </div>
              )}
              {reverse && (
                <div style={{ marginTop: 12, borderTop: "1px solid var(--surface2)", paddingTop: 10 }}>
                  <div style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>lado inverso</div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(86px, 1fr))", gap: 8, marginTop: 8 }}>
                    <SmallMetric label="Pts/jogo" value={num(reverse.pts_jogo)} color={secondColor} />
                    <SmallMetric label="Aproveit." value={`${reverse.aproveitamento}%`} color={secondColor} />
                    <SmallMetric label="Saldo/jogo" value={num(reverse.saldo_pj)} color={secondColor} />
                    <SmallMetric label="xG +/-" value={num(reverse.xg_diff_pj)} color={secondColor} />
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ marginTop: 12, color: "var(--text-muted)", fontSize: 12, lineHeight: 1.5 }}>
              Sem base finalizada para esse par no snapshot atual.
            </div>
          )}
        </div>

        <StyleCompareSide
          title="Grupo B"
          selected={secondStyle}
          color={secondColor}
          row={secondRow}
          teams={secondTeams}
          onPickTeam={onPickTeam}
        />
      </div>

      {/*
      <div style={{ padding: "0 14px 14px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", gap: 12 }}>
        <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "10px 11px" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>o que mais pesou</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 9 }}>
            {influences.slice(0, 4).map((item) => (
              <div key={item.fator} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 10, alignItems: "center" }} title={item.nota}>
                <span>
                  <span style={{ display: "block", color: "var(--text)", fontSize: 12.5, fontWeight: 800 }}>{item.fator}</span>
                  <span style={{ display: "block", color: "var(--text-muted)", fontSize: 10.5 }}>{item.leitura}{item.n ? ` · ${item.n} obs.` : ""}</span>
                </span>
                <b style={{ color: item.corr == null ? "var(--text-muted)" : color, fontSize: 14 }}>{item.corr == null ? "—" : `${item.corr > 0 ? "+" : ""}${num(item.corr)}`}</b>
              </div>
            ))}
          </div>
        </div>
      </div>
      */}
    </Panel>
  );
}

function StyleCompareSide({
  title,
  selected,
  color,
  row,
  teams,
  onPickTeam,
}: {
  title: string;
  selected: string;
  color: string;
  row: StyleRow | null;
  teams: TeamStyleDetail[];
  onPickTeam: (team: string) => void;
}) {
  const record = row && (row.vitorias != null || row.empates != null || row.derrotas != null)
    ? `${row.vitorias ?? 0}V ${row.empates ?? 0}E ${row.derrotas ?? 0}D`
    : null;
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "12px 13px", minWidth: 0 }}>
      <div style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>{title}</div>

      <div style={{ marginTop: 8, display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 10 }}>
        <div>
          <div style={{ color, fontSize: 18, lineHeight: 1.1, fontWeight: 900 }}>{styleName(selected)}</div>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 3 }}>{teams.length} selecoes{record ? ` - ${record}` : ""}</div>
        </div>
        <div style={{ textAlign: "right", flex: "0 0 auto" }}>
          <b style={{ color, fontSize: 17 }}>{row ? num(row.pts_jogo) : "-"}</b>
          <span style={{ display: "block", color: "var(--text-muted)", fontSize: 10.5 }}>pts/jogo</span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8, marginTop: 10 }}>
        <SmallMetric label="Aproveit." value={row ? `${row.aproveitamento}%` : "-"} color={color} />
        <SmallMetric label="Saldo/jogo" value={row ? num(row.saldo_pj) : "-"} color={color} />
        <SmallMetric label="xG/jogo" value={row ? num(row.xg_pj) : "-"} color={color} />
      </div>

      <div style={{ marginTop: 12 }}>
        <div style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>selecoes</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 7, maxHeight: 220, overflowY: "auto", paddingRight: 2 }}>
          {teams.map((team) => (
            <button
              key={team.team}
              type="button"
              onClick={() => onPickTeam(team.team)}
              title={`${team.team} - ${styleName(team.arquetipo)}`}
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto",
                alignItems: "center",
                gap: 8,
                width: "100%",
                border: "1px solid var(--surface2)",
                borderRadius: 7,
                background: "var(--background)",
                color: "var(--text)",
                padding: "7px 8px",
                cursor: "pointer",
                fontFamily: "inherit",
                textAlign: "left",
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: 7, minWidth: 0, fontSize: 12.5, fontWeight: 800 }}>
                <Flag team={team.team} height={12} />{team.team}
              </span>
              <span style={{ color, fontSize: 12, fontWeight: 800 }}>{num(team.pts_jogo)}</span>
            </button>
          ))}
          {!teams.length && (
            <div style={{ color: "var(--text-muted)", fontSize: 12, padding: "8px 2px" }}>Sem selecoes nesse estilo no snapshot atual.</div>
          )}
        </div>
      </div>
    </div>
  );
}

function StyleSelect({
  label,
  value,
  options,
  color,
  onChange,
  blocked,
}: {
  label: string;
  value: string;
  options: string[];
  color: string;
  onChange: (style: string) => void;
  blocked?: string;
}) {
  return (
    <label style={{ display: "flex", flex: "1 1 260px", minWidth: 220, flexDirection: "column", gap: 5 }}>
      <span style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>{label}</span>
      <span style={{ display: "grid", gridTemplateColumns: "10px 1fr", alignItems: "center", gap: 8, background: "var(--surface)", border: `1px solid ${color}`, borderRadius: 8, padding: "0 10px" }}>
        <span style={{ width: 9, height: 9, borderRadius: 5, background: color }} />
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          style={{
            minHeight: 36,
            width: "100%",
            border: "none",
            outline: "none",
            background: "transparent",
            color: "var(--text)",
            fontFamily: "inherit",
            fontSize: 13,
            fontWeight: 800,
            cursor: "pointer",
          }}
        >
          {options.map((style) => (
            <option key={style} value={style} disabled={style === blocked}>
              {styleName(style)}
            </option>
          ))}
        </select>
      </span>
    </label>
  );
}

function BigMetric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "9px 10px", minWidth: 0 }}>
      <div style={{ fontSize: 10.5, color: "var(--text-muted)" }}>{label}</div>
      <div style={{ marginTop: 3, color, fontSize: 18, fontWeight: 900, lineHeight: 1.1, overflowWrap: "anywhere" }}>{value}</div>
    </div>
  );
}

function SmallMetric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div>
      <div style={{ fontSize: 10.5, color: "var(--text-muted)" }}>{label}</div>
      <div style={{ marginTop: 2, color, fontSize: 13, fontWeight: 800 }}>{value}</div>
    </div>
  );
}

function StyleLeaderboard({
  rows,
  teams,
  activeStyle,
  activeTeam,
  onPickStyle,
  onPickTeam,
}: {
  rows: StyleRow[];
  teams: TeamStyleDetail[];
  activeStyle: string;
  activeTeam: string | null;
  onPickStyle: (style: string) => void;
  onPickTeam: (team: string) => void;
}) {
  const [mode, setMode] = React.useState<"styles" | "teams">("styles");
  const [teamQuery, setTeamQuery] = React.useState("");
  const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const filteredTeams = teamQuery
    ? teams.filter((team) => norm(team.team).includes(norm(teamQuery)) || norm(styleName(team.arquetipo)).includes(norm(teamQuery)))
    : teams;
  const maxStyle = Math.max(...rows.map((r) => r.pts_jogo), 3);
  const maxTeam = Math.max(...teams.map((t) => t.pts_jogo), 3);
  return (
    <Panel
      titulo={mode === "styles" ? "Ranking de rendimento por estilo" : "Ranking de rendimento por seleção"}
      leitura={mode === "styles"
        ? `${styleName(rows[0].arquetipo)} lidera em pontos por jogo; ${styleName(rows[rows.length - 1].arquetipo)} é o estilo que menos entregou resultado até aqui.`
        : `${teams[0]?.team ?? "—"} lidera em pontos por jogo; clique em uma seleção para abrir o raio-x dela.`}
      sub={mode === "styles"
        ? "Ordenado por pontos por jogo. V/E/D usa os jogos acumulados das seleções classificadas em cada arquétipo."
        : "Ordenado por pontos por jogo no snapshot atual. A cor indica o estilo dominante da seleção."}
    >
      <div style={{ padding: "8px 12px 12px", display: "flex", flexDirection: "column", gap: 7 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 3 }}>
          <div style={{ display: "inline-flex", background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 7, padding: 2 }}>
            <ModeButton active={mode === "styles"} label="Estilos" onClick={() => setMode("styles")} />
            <ModeButton active={mode === "teams"} label="Times" onClick={() => setMode("teams")} />
          </div>
          {mode === "teams" && (
            <input
              value={teamQuery}
              onChange={(e) => setTeamQuery(e.target.value)}
              placeholder="Buscar time ou estilo..."
              style={{
                flex: "1 1 220px",
                minWidth: 180,
                background: "var(--surface)",
                color: "var(--text)",
                border: "1px solid var(--surface2)",
                borderRadius: 8,
                padding: "7px 10px",
                fontSize: 12.5,
                outline: "none",
                fontFamily: "inherit",
              }}
            />
          )}
        </div>
        {mode === "styles" ? rows.map((r) => {
          const active = r.arquetipo === activeStyle;
          const color = STYLE_COLOR[r.arquetipo] ?? "var(--accent)";
          return (
            <button
              key={r.arquetipo}
              onClick={() => onPickStyle(r.arquetipo)}
              title={styleDescription(r.arquetipo)}
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(116px, 150px) 1fr auto",
                alignItems: "center",
                gap: 10,
                width: "100%",
                background: active ? "color-mix(in srgb, var(--accent) 12%, var(--background))" : "var(--background)",
                border: `1px solid ${active ? "var(--accent)" : "var(--surface2)"}`,
                borderRadius: 8,
                padding: "9px 10px",
                color: "var(--text)",
                cursor: "pointer",
                fontFamily: "inherit",
                textAlign: "left",
              }}
            >
              <span style={{ minWidth: 0 }}>
                <span style={{ display: "block", color, fontSize: 13, fontWeight: 800 }}>{styleName(r.arquetipo)}</span>
                <span style={{ display: "block", color: "var(--text-muted)", fontSize: 10.5 }}>{r.n} seleções · {styleGames(r)} jogos</span>
              </span>
              <span style={{ height: 10, background: "var(--surface2)", borderRadius: 5, overflow: "hidden" }}>
                <span style={{ display: "block", width: `${Math.max(4, (r.pts_jogo / maxStyle) * 100)}%`, height: "100%", background: color }} />
              </span>
              <span style={{ textAlign: "right", minWidth: 92 }}>
                <b style={{ color }}>{num(r.pts_jogo)}</b>
                <span style={{ display: "block", color: "var(--text-muted)", fontSize: 10.5 }}>pts/jogo</span>
              </span>
            </button>
          );
        }) : filteredTeams.map((team) => {
          const active = team.team === activeTeam;
          const color = STYLE_COLOR[team.arquetipo] ?? "var(--accent)";
          const record = team.vitorias != null || team.empates != null || team.derrotas != null
            ? `${team.vitorias ?? 0}V ${team.empates ?? 0}E ${team.derrotas ?? 0}D`
            : `${team.jogos ?? "—"} jogos`;
          return (
            <button
              key={team.team}
              onClick={() => onPickTeam(team.team)}
              title={`${team.team} · ${styleName(team.arquetipo)}`}
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(150px, 190px) 1fr auto",
                alignItems: "center",
                gap: 10,
                width: "100%",
                background: active ? "color-mix(in srgb, var(--accent) 12%, var(--background))" : "var(--background)",
                border: `1px solid ${active ? "var(--accent)" : "var(--surface2)"}`,
                borderRadius: 8,
                padding: "9px 10px",
                color: "var(--text)",
                cursor: "pointer",
                fontFamily: "inherit",
                textAlign: "left",
              }}
            >
              <span style={{ minWidth: 0 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 7, color: "var(--text)", fontSize: 13, fontWeight: 800 }}>
                  <Flag team={team.team} height={13} />{team.team}
                </span>
                <span style={{ display: "block", color, fontSize: 10.5, marginTop: 2 }}>{styleName(team.arquetipo)} · {record}</span>
              </span>
              <span style={{ height: 10, background: "var(--surface2)", borderRadius: 5, overflow: "hidden" }}>
                <span style={{ display: "block", width: `${Math.max(4, (team.pts_jogo / maxTeam) * 100)}%`, height: "100%", background: color }} />
              </span>
              <span style={{ textAlign: "right", minWidth: 92 }}>
                <b style={{ color }}>{num(team.pts_jogo)}</b>
                <span style={{ display: "block", color: "var(--text-muted)", fontSize: 10.5 }}>pts/jogo</span>
              </span>
            </button>
          );
        })}
        {mode === "teams" && filteredTeams.length === 0 && (
          <div style={{ padding: "14px 10px", color: "var(--text-muted)", fontSize: 12.5, textAlign: "center" }}>Nenhum time encontrado.</div>
        )}
      </div>
    </Panel>
  );
}

function ModeButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        border: "none",
        borderRadius: 5,
        padding: "4px 10px",
        background: active ? "var(--accent)" : "transparent",
        color: active ? "#0d1117" : "var(--text-muted)",
        fontSize: 11.5,
        fontWeight: 800,
        cursor: "pointer",
        fontFamily: "inherit",
      }}
    >
      {label}
    </button>
  );
}

function StyleDetail({ row }: { row: StyleRow }) {
  const color = STYLE_COLOR[row.arquetipo] ?? "var(--accent)";
  const hasRecord = row.vitorias != null || row.empates != null || row.derrotas != null;
  const record = hasRecord ? `${row.vitorias ?? 0}V ${row.empates ?? 0}E ${row.derrotas ?? 0}D` : "—";
  const keyMetrics = row.metricas_chave ?? fallbackStyleMetrics(row);
  const title = row.times?.length === 1 ? row.times[0] : row.times && row.times.length > 1 && row.n === row.times.length ? `${row.times.length} seleções` : styleName(row.arquetipo);
  return (
    <Panel
      titulo={`Raio-x: ${title}`}
      leitura={styleReading(row)}
      sub="O detalhe usa métricas que combinam com o estilo selecionado, não um pacote fixo para todos."
    >
      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
          <MetricTile label="Aproveitamento" value={`${row.aproveitamento}%`} color={color} />
          <MetricTile label="Campanha" value={record} color={color} />
          <MetricTile label="Pontos/jogo" value={num(row.pts_jogo)} color={color} />
          {keyMetrics.map((metric) => (
            <div key={metric.label} style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "9px 10px" }}>
              <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{metric.label}</div>
              <div style={{ marginTop: 3, color, fontWeight: 800, fontSize: 15 }}>{fmtMetric(metric)}</div>
            </div>
          ))}
        </div>
        {row.metricas_chave == null && (
          <div style={{ border: "1px solid var(--surface2)", borderRadius: 8, padding: "9px 10px", fontSize: 12, color: "var(--text-muted)", lineHeight: 1.4 }}>
            As métricas específicas por estilo dependem da versão nova do endpoint exploratório. Se a API local já estava aberta, reinicie o backend para carregar o cálculo atualizado.
          </div>
        )}
        {!!row.times?.length && (
          <div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 800, marginBottom: 7 }}>Seleções neste estilo</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {row.times.map((team) => (
                <span key={team} style={{ display: "inline-flex", alignItems: "center", gap: 5, border: "1px solid var(--surface2)", borderRadius: 6, padding: "3px 8px", fontSize: 12, color: "var(--text)" }}>
                  <Flag team={team} height={12} />{team}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

function MetricTile({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "9px 10px" }}>
      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{label}</div>
      <div style={{ marginTop: 3, color, fontWeight: 800, fontSize: 15 }}>{value}</div>
    </div>
  );
}

function fmtMetric(metric: NonNullable<StyleRow["metricas_chave"]>[number]) {
  const decimals = metric.decimals ?? 2;
  return `${num(metric.valor, decimals)}${metric.unit ?? ""}`;
}

function fallbackStyleMetrics(row: StyleRow): NonNullable<StyleRow["metricas_chave"]> {
  return [
    { label: "Saldo/jogo", valor: row.saldo_pj ?? Number.NaN },
    { label: "Gols/jogo", valor: row.gols_pj ?? Number.NaN },
    { label: "xG/jogo", valor: row.xg_pj ?? Number.NaN },
    { label: "xG sofrido/jogo", valor: row.xg_sofrido_pj ?? Number.NaN },
  ].filter((m) => Number.isFinite(m.valor));
}

function identityMetrics(detail: TeamStyleDetail): NonNullable<TeamStyleDetail["metricas_chave"]> {
  if (detail.metricas_chave?.length) return detail.metricas_chave.slice(0, 4);
  return [
    { label: "Pts/jogo", valor: detail.pts_jogo },
    { label: "xG/jogo", valor: detail.xg_pj ?? Number.NaN },
    { label: "xG sofrido/jogo", valor: detail.xg_sofrido_pj ?? Number.NaN },
    { label: "Saldo/jogo", valor: detail.saldo_pj ?? Number.NaN },
  ].filter((metric) => Number.isFinite(metric.valor));
}

function styleResultSentence(detail: TeamStyleDetail, styleRow: StyleRow | null) {
  if (!styleRow) return `${detail.team} ainda nao tem base suficiente para comparar com a media do estilo.`;
  const diff = detail.pts_jogo - styleRow.pts_jogo;
  const direction = diff >= 0.25 ? "acima" : diff <= -0.25 ? "abaixo" : "em linha";
  if (direction === "em linha") {
    return `${detail.team} entrega resultado parecido com a media de ${styleName(detail.arquetipo)}.`;
  }
  return `${detail.team} esta ${direction} da media de ${styleName(detail.arquetipo)} em pontos por jogo.`;
}

function teamEdge(a: TeamStyleDetail, b: TeamStyleDetail) {
  const diff = a.pts_jogo - b.pts_jogo;
  if (diff === 0) return { team: "As duas selecoes", diff: 0 };
  return { team: diff > 0 ? a.team : b.team, diff: Math.abs(diff) };
}

function opponentStyleSummary(games: TeamGame[]) {
  const map = new Map<string, { style: string; games: number; points: number; v: number; e: number; d: number }>();
  for (const game of games) {
    const row = map.get(game.opponentStyle) ?? { style: game.opponentStyle, games: 0, points: 0, v: 0, e: 0, d: 0 };
    row.games += 1;
    if (game.result === "V") {
      row.points += 3;
      row.v += 1;
    } else if (game.result === "E") {
      row.points += 1;
      row.e += 1;
    } else {
      row.d += 1;
    }
    map.set(game.opponentStyle, row);
  }
  return Array.from(map.values())
    .map((row) => ({ ...row, ptsPerGame: row.games ? row.points / row.games : 0, record: `${row.v}V ${row.e}E ${row.d}D` }))
    .sort((a, b) => b.games - a.games || b.ptsPerGame - a.ptsPerGame);
}

function styleRowFromTeam(detail: TeamStyleDetail): StyleRow {
  return {
    arquetipo: detail.arquetipo,
    n: 1,
    pts_jogo: detail.pts_jogo,
    aproveitamento: detail.aproveitamento,
    jogos: detail.jogos ?? 0,
    vitorias: detail.vitorias,
    empates: detail.empates,
    derrotas: detail.derrotas,
    gols_pj: detail.gols_pj,
    xg_pj: detail.xg_pj,
    xg_sofrido_pj: detail.xg_sofrido_pj,
    saldo_pj: detail.saldo_pj,
    metricas_chave: detail.metricas_chave,
    times: [detail.team],
  };
}

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

function formatMetricValue(value: number | null | undefined, suffix = "") {
  return typeof value === "number" ? `${num(value)}${suffix}` : "—";
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
  const finished = matches
    .filter((m) => m.status === "finalizado")
    .sort((a, b) => String(a.date_utc ?? "").localeCompare(String(b.date_utc ?? "")))
    .slice(0, snapshot);
  let vitorias = 0;
  let empates = 0;
  let derrotas = 0;
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

function aggregateTeamDetails(details: TeamStyleDetail[]): StyleRow {
  const jogos = details.reduce((acc, d) => acc + (d.jogos ?? 0), 0);
  const points = details.reduce((acc, d) => acc + (d.points ?? (d.pts_jogo * (d.jogos ?? 0))), 0);
  const vitorias = details.reduce((acc, d) => acc + (d.vitorias ?? 0), 0);
  const empates = details.reduce((acc, d) => acc + (d.empates ?? 0), 0);
  const derrotas = details.reduce((acc, d) => acc + (d.derrotas ?? 0), 0);
  const hasRecord = details.some((d) => d.vitorias != null || d.empates != null || d.derrotas != null);
  const sameStyle = details.every((d) => d.arquetipo === details[0].arquetipo);
  const arquetipo = sameStyle ? details[0].arquetipo : "Recorte misto";
  const weighted = (key: "gols_pj" | "xg_pj" | "xg_sofrido_pj" | "saldo_pj") => {
    const valid = details.filter((d) => typeof d[key] === "number" && (d.jogos ?? 0) > 0);
    const weight = valid.reduce((acc, d) => acc + (d.jogos ?? 0), 0);
    if (!weight) return null;
    return valid.reduce((acc, d) => acc + (d[key] as number) * (d.jogos ?? 0), 0) / weight;
  };
  return {
    arquetipo,
    n: details.length,
    pts_jogo: jogos > 0 ? points / jogos : 0,
    aproveitamento: jogos > 0 ? Math.round((points / (jogos * 3)) * 100) : 0,
    jogos,
    vitorias: hasRecord ? vitorias : undefined,
    empates: hasRecord ? empates : undefined,
    derrotas: hasRecord ? derrotas : undefined,
    gols_pj: weighted("gols_pj"),
    xg_pj: weighted("xg_pj"),
    xg_sofrido_pj: weighted("xg_sofrido_pj"),
    saldo_pj: weighted("saldo_pj"),
    metricas_chave: aggregateKeyMetrics(details),
    times: details.map((d) => d.team),
  };
}

function aggregateKeyMetrics(details: TeamStyleDetail[]): NonNullable<StyleRow["metricas_chave"]> {
  if (details.length === 1) return details[0].metricas_chave ?? [];
  const sameStyle = details.every((d) => d.arquetipo === details[0].arquetipo);
  if (!sameStyle) {
    return fallbackStyleMetrics(aggregateTeamDetailsWithoutMetrics(details));
  }
  const labels = new Set(details.flatMap((d) => d.metricas_chave?.map((m) => m.label) ?? []));
  return Array.from(labels).map((label) => {
    const candidates = details
      .map((d) => ({ item: d.metricas_chave?.find((m) => m.label === label), jogos: d.jogos ?? 0 }))
      .filter((d): d is { item: NonNullable<TeamStyleDetail["metricas_chave"]>[number]; jogos: number } => !!d.item && d.jogos > 0);
    const weight = candidates.reduce((acc, d) => acc + d.jogos, 0);
    const first = candidates[0]?.item;
    return {
      label,
      valor: weight ? candidates.reduce((acc, d) => acc + d.item.valor * d.jogos, 0) / weight : first?.valor ?? 0,
      unit: first?.unit,
      decimals: first?.decimals,
    };
  });
}

function aggregateTeamDetailsWithoutMetrics(details: TeamStyleDetail[]): StyleRow {
  const jogos = details.reduce((acc, d) => acc + (d.jogos ?? 0), 0);
  const points = details.reduce((acc, d) => acc + (d.points ?? (d.pts_jogo * (d.jogos ?? 0))), 0);
  const weighted = (key: "gols_pj" | "xg_pj" | "xg_sofrido_pj" | "saldo_pj") => {
    const valid = details.filter((d) => typeof d[key] === "number" && (d.jogos ?? 0) > 0);
    const weight = valid.reduce((acc, d) => acc + (d.jogos ?? 0), 0);
    if (!weight) return null;
    return valid.reduce((acc, d) => acc + (d[key] as number) * (d.jogos ?? 0), 0) / weight;
  };
  return {
    arquetipo: "Recorte misto",
    n: details.length,
    pts_jogo: jogos > 0 ? points / jogos : 0,
    aproveitamento: jogos > 0 ? Math.round((points / (jogos * 3)) * 100) : 0,
    jogos,
    gols_pj: weighted("gols_pj"),
    xg_pj: weighted("xg_pj"),
    xg_sofrido_pj: weighted("xg_sofrido_pj"),
    saldo_pj: weighted("saldo_pj"),
  };
}

function styleGames(row: StyleRow) {
  const byRecord = (row.vitorias ?? 0) + (row.empates ?? 0) + (row.derrotas ?? 0);
  return row.jogos ?? (byRecord || "—");
}

function styleReading(row: StyleRow) {
  const subject = row.times?.length === 1 ? `${row.times[0]} (${styleName(row.arquetipo)})` : styleName(row.arquetipo);
  const result = row.pts_jogo >= 1.8 ? "está entregando resultado forte" :
    row.pts_jogo >= 1.2 ? "tem retorno competitivo" :
    "ainda entrega pouco resultado";
  const styleNote: Record<string, string> = {
    "Pressão Alta": "O ponto-chave é se a recuperação/pressão vira chance sem abrir espaço atrás.",
    "Posse": "O ponto-chave é transformar construção em território útil e limitar transições.",
    "Retranca": "O ponto-chave é compactar, controlar risco e atacar quando aparece espaço.",
    "Jogo Direto": "O ponto-chave é ganhar campo rápido sem virar só devolução de posse.",
    "Contra-ataque": "O ponto-chave é se a transição rápida cria perigo suficiente para compensar o tempo defendendo.",
    "Bola Parada": "O ponto-chave é transformar bolas paradas em volume real de chance e gol.",
  };
  return `${subject} ${result}: ${num(row.pts_jogo)} pts/jogo e ${row.aproveitamento}% de aproveitamento. ${styleNote[row.arquetipo] ?? ""}`.trim();
}

function StyleLegend() {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
      {STYLE_ORDER.map((style) => (
        <span
          key={style}
          title={styleDescription(style)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            border: "1px solid var(--surface2)",
            borderRadius: 6,
            padding: "4px 8px",
            color: "var(--text)",
            background: "var(--background)",
            fontSize: 11.5,
            cursor: "help",
          }}
        >
          <span style={{ width: 8, height: 8, borderRadius: 4, background: STYLE_COLOR[style] }} />
          {styleName(style)}
        </span>
      ))}
    </div>
  );
}

function Panel({ titulo, leitura, sub, children }: { titulo: string; leitura?: string; sub?: string; children: React.ReactNode }) {
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "10px 16px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 800 }}>{titulo}</div>
        {leitura && <div style={{ fontSize: 13, color: "var(--text)", marginTop: 4, lineHeight: 1.45, fontWeight: 600 }}>{leitura}</div>}
        {sub && <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 3, lineHeight: 1.4 }}>{sub}</div>}
      </div>
      {children}
    </section>
  );
}

function Aviso({ texto }: { texto: string }) {
  return <div style={{ padding: "24px 0", textAlign: "center", fontSize: 13, color: "var(--text-muted)" }}>{texto}</div>;
}
