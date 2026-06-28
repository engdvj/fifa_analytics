"use client";

import React from "react";
import { Match } from "@/lib/api";
import Flag from "@/components/ui/Flag";

// Fixed 2026 knockout topology. Real teams, dates and scores come from dim_match
// as the tournament advances; unresolved slots keep their possible feeder labels.
type Feeder = { label: string } | { win: number } | { lose: number };
interface BMatch { n: number; a: Feeder; b: Feeder }
type BracketPhase = { id: string; label: string; matches: BMatch[] };

const L = (s: string): Feeder => ({ label: s });
const W = (n: number): Feeder => ({ win: n });

const LEFT: { label: string; matches: BMatch[] }[] = [
  {
    label: "16 avos",
    matches: [
      { n: 74, a: L("1?"), b: L("3ABCDF") },
      { n: 77, a: L("1I"), b: L("3CDFGH") },
      { n: 73, a: L("2A"), b: L("2B") },
      { n: 75, a: L("1F"), b: L("2C") },
      { n: 83, a: L("2K"), b: L("2L") },
      { n: 84, a: L("1H"), b: L("2J") },
      { n: 81, a: L("1?"), b: L("3BEFIJ") },
      { n: 82, a: L("1G"), b: L("3AEHIJ") },
    ],
  },
  {
    label: "Oitavas",
    matches: [
      { n: 89, a: W(74), b: W(77) },
      { n: 90, a: W(73), b: W(75) },
      { n: 93, a: W(83), b: W(84) },
      { n: 94, a: W(81), b: W(82) },
    ],
  },
  { label: "Quartas", matches: [{ n: 97, a: W(89), b: W(90) }, { n: 98, a: W(93), b: W(94) }] },
];

const RIGHT: { label: string; matches: BMatch[] }[] = [
  { label: "Quartas", matches: [{ n: 99, a: W(91), b: W(92) }, { n: 100, a: W(95), b: W(96) }] },
  {
    label: "Oitavas",
    matches: [
      { n: 91, a: W(76), b: W(78) },
      { n: 92, a: W(79), b: W(80) },
      { n: 95, a: W(86), b: W(88) },
      { n: 96, a: W(85), b: W(87) },
    ],
  },
  {
    label: "16 avos",
    matches: [
      { n: 76, a: L("1C"), b: L("2F") },
      { n: 78, a: L("2E"), b: L("2I") },
      { n: 79, a: L("1?"), b: L("3CEFHI") },
      { n: 80, a: L("1L"), b: L("3EHIJK") },
      { n: 86, a: L("1?"), b: L("2H") },
      { n: 88, a: L("2D"), b: L("2G") },
      { n: 85, a: L("1B"), b: L("3EFGIJ") },
      { n: 87, a: L("1K"), b: L("3DEIJL") },
    ],
  },
];

const SF_LEFT: BMatch = { n: 101, a: W(97), b: W(98) };
const SF_RIGHT: BMatch = { n: 102, a: W(99), b: W(100) };
const FINAL: BMatch = { n: 104, a: W(101), b: W(102) };
const THIRD: BMatch = { n: 103, a: { lose: 101 }, b: { lose: 102 } };

const PHASES: BracketPhase[] = [
  { id: "r32", label: "16 avos", matches: [...LEFT[0].matches, ...RIGHT[2].matches] },
  { id: "r16", label: "Oitavas", matches: [...LEFT[1].matches, ...RIGHT[1].matches] },
  { id: "qf", label: "Quartas", matches: [...LEFT[2].matches, ...RIGHT[0].matches] },
  { id: "sf", label: "Semifinais", matches: [SF_LEFT, SF_RIGHT] },
  { id: "final", label: "Final", matches: [FINAL, THIRD] },
];

function fmtDateTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

interface Resolved { team: string | null; text: string; score: number | null; winner: boolean }

interface Props {
  matches: Match[];
  selectedTeams: string[];
  onToggleTeam: (team: string) => void;
  search?: string;
}

export default function BracketTab({ matches, selectedTeams, onToggleTeam, search = "" }: Props) {
  const rootRef = React.useRef<HTMLDivElement>(null);
  const layout = useBracketLayout(rootRef);
  const byNum = React.useMemo(() => {
    const m = new Map<number, Match>();
    for (const g of matches) m.set(g.match_number, g);
    return m;
  }, [matches]);

  const currentPhaseIndex = React.useMemo(() => {
    const index = PHASES.findIndex((phase) => phase.matches.some((bm) => byNum.get(bm.n)?.status !== "finalizado"));
    return index >= 0 ? index : PHASES.length - 1;
  }, [byNum]);

  const visiblePhases = React.useMemo(
    () => phaseWindow(currentPhaseIndex, layout.maxVisiblePhases),
    [currentPhaseIndex, layout.maxVisiblePhases],
  );

  const outcome = React.useCallback((n: number): { winner: string | null; loser: string | null } => {
    const m = byNum.get(n);
    if (!m || m.status !== "finalizado" || m.home_score == null || m.away_score == null || !m.home_team || !m.away_team) {
      return { winner: null, loser: null };
    }
    let homeWins = m.home_score > m.away_score;
    if (m.home_score === m.away_score) {
      const hp = m.home_penalty ?? 0;
      const ap = m.away_penalty ?? 0;
      if (hp === ap) return { winner: null, loser: null };
      homeWins = hp > ap;
    }
    return homeWins ? { winner: m.home_team, loser: m.away_team } : { winner: m.away_team, loser: m.home_team };
  }, [byNum]);

  const resolve = React.useCallback((bm: BMatch, side: "a" | "b"): Resolved => {
    const m = byNum.get(bm.n);
    const feeder = bm[side];
    const decided = m?.status === "finalizado" && m.home_score != null && m.away_score != null;
    const score = decided ? (side === "a" ? m.home_score : m.away_score) : null;
    const realTeam = side === "a" ? m?.home_team ?? null : m?.away_team ?? null;
    let team = realTeam;
    let text = realTeam ?? "";
    if (!team) {
      if ("label" in feeder) text = feeder.label;
      else if ("win" in feeder) {
        const o = outcome(feeder.win);
        team = o.winner;
        text = team ?? `Vc. J${feeder.win}`;
      } else {
        const o = outcome(feeder.lose);
        team = o.loser;
        text = team ?? `Pd. J${feeder.lose}`;
      }
    }
    const winner = !!team && outcome(bm.n).winner === team;
    return { team, text, score, winner };
  }, [byNum, outcome]);

  const q = search.trim().toLowerCase();
  const card = (bm: BMatch, opts?: { final?: boolean }) => (
    <MatchCard
      key={bm.n}
      bm={bm}
      resolve={resolve}
      q={q}
      selectedTeams={selectedTeams}
      onToggleTeam={onToggleTeam}
      date={fmtDateTime(byNum.get(bm.n)?.date_utc ?? null)}
      final={opts?.final}
    />
  );

  const PhasePanel = (phase: BracketPhase) => (
    <section key={phase.id} className={`v2-bracket-phase-panel${phase.id === PHASES[currentPhaseIndex].id ? " is-current" : ""}`}>
      <div className="v2-bracket-phase-head">
        <ColHead>{phase.label}</ColHead>
        {phase.id === PHASES[currentPhaseIndex].id && <span>fase atual</span>}
      </div>
      <div className="v2-bracket-matches-grid">
        {phase.matches.map((bm) => card(bm, { final: bm.n === FINAL.n }))}
      </div>
    </section>
  );

  const Column = (col: { label: string; matches: BMatch[] }, key: string) => (
    <div key={key} className="v2-bracket-column">
      <ColHead>{col.label}</ColHead>
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-around", flex: 1, gap: 8 }}>
        {col.matches.map((bm) => card(bm))}
      </div>
    </div>
  );

  return (
    <div ref={rootRef} className="v2-bracket-tab">
      <p className="v2-bracket-summary">
        {layout.showFull
          ? "Chave do mata-mata - os confrontos se preenchem conforme a fase de grupos e cada jogo termina."
          : `Mata-mata - ${PHASES[currentPhaseIndex].label} em foco - confrontos possiveis`}
      </p>
      <div className="v2-bracket-scroll">
        {layout.showFull ? (
          <div className="v2-bracket-board is-full">
            {LEFT.map((c, i) => Column(c, `L${i}`))}
            <div className="v2-bracket-center">
              <div>
                <ColHead>Final</ColHead>
                {card(FINAL, { final: true })}
              </div>
              <div>
                <ColHead>Semifinais</ColHead>
                <div style={{ display: "flex", gap: 10 }}>
                  <div style={{ flex: 1 }}>{card(SF_LEFT)}</div>
                  <div style={{ flex: 1 }}>{card(SF_RIGHT)}</div>
                </div>
              </div>
              <div>
                <ColHead>Decisao do 3o lugar</ColHead>
                {card(THIRD)}
              </div>
            </div>
            {RIGHT.map((c, i) => Column(c, `R${i}`))}
          </div>
        ) : (
          <div className="v2-bracket-board">
            {visiblePhases.map(PhasePanel)}
          </div>
        )}
      </div>
    </div>
  );
}

function useBracketLayout(ref: React.RefObject<HTMLDivElement | null>) {
  const [layout, setLayout] = React.useState({ showFull: true, maxVisiblePhases: 3 });
  React.useEffect(() => {
    const measure = () => {
      const width = ref.current?.getBoundingClientRect().width ?? window.innerWidth;
      setLayout({
        showFull: width >= 1280,
        maxVisiblePhases: width < 760 ? 1 : width < 1180 ? 2 : 3,
      });
    };
    measure();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(measure) : null;
    if (ref.current && observer) observer.observe(ref.current);
    window.addEventListener("resize", measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [ref]);
  return layout;
}

function phaseWindow(currentIndex: number, maxVisible: number) {
  const safeMax = Math.max(1, Math.min(maxVisible, PHASES.length));
  let start = currentIndex;
  let end = currentIndex + 1;
  while (end - start < safeMax && end < PHASES.length) end += 1;
  while (end - start < safeMax && start > 0) start -= 1;
  return PHASES.slice(start, end);
}

function ColHead({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 800, color: "#8b949e", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 0, textAlign: "center" }}>
      {children}
    </div>
  );
}

function MatchCard({
  bm, resolve, q, selectedTeams, onToggleTeam, date, final = false,
}: {
  bm: BMatch;
  resolve: (bm: BMatch, side: "a" | "b") => Resolved;
  q: string;
  selectedTeams: string[];
  onToggleTeam: (team: string) => void;
  date: string;
  final?: boolean;
}) {
  const a = resolve(bm, "a");
  const b = resolve(bm, "b");
  return (
    <div className="v2-bracket-match-card" style={{ borderColor: final ? "#3b5070" : undefined }}>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 8px", fontSize: 9.5, color: "#6e7681", background: "#0a0e14" }}>
        <span>J{bm.n}</span>
        <span>{date}</span>
      </div>
      <Slot {...a} selected={!!a.team && selectedTeams.includes(a.team)} hl={!!q && !!a.team && a.team.toLowerCase().includes(q)} onClick={() => a.team && onToggleTeam(a.team)} />
      <div style={{ height: 1, background: "#161b22" }} />
      <Slot {...b} selected={!!b.team && selectedTeams.includes(b.team)} hl={!!q && !!b.team && b.team.toLowerCase().includes(q)} onClick={() => b.team && onToggleTeam(b.team)} />
    </div>
  );
}

function Slot({
  team, text, score, winner, selected, hl, onClick,
}: Resolved & { selected: boolean; hl: boolean; onClick: () => void }) {
  return (
    <div
      onClick={team ? onClick : undefined}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 7,
        padding: "7px 9px",
        cursor: team ? "pointer" : "default",
        background: selected ? "rgba(88,166,255,0.14)" : hl ? "rgba(210,153,34,0.12)" : "transparent",
      }}
    >
      {team ? <Flag team={team} height={12} /> : <span style={{ width: 16, height: 11, borderRadius: 2, background: "#161b22", flexShrink: 0 }} />}
      <span style={{
        flex: 1,
        minWidth: 0,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
        fontSize: 12.5,
        fontWeight: winner ? 800 : team ? 600 : 400,
        color: winner ? "#3fb950" : team ? (selected ? "#58a6ff" : "#e6edf3") : "#6e7681",
        fontStyle: team ? "normal" : "italic",
      }}>{text}</span>
      {score != null && (
        <span style={{ fontSize: 12.5, fontWeight: 800, color: winner ? "#3fb950" : "#8b949e", minWidth: 12, textAlign: "right" }}>{score}</span>
      )}
    </div>
  );
}
