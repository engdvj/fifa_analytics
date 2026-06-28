"use client";

import React from "react";
import { Match } from "@/lib/api";
import { useInsights, useInsightNarrative } from "@/lib/hooks";
import Flag from "@/components/ui/Flag";
import Spinner from "@/components/ui/Spinner";
import PreditivaView from "@/components/dashboard/PreditivaView";
import GamePlan from "@/components/dashboard/GamePlan";
import GameReport from "@/components/dashboard/GameReport";

/**
 * Aba "O Jogo" — a casa de tudo sobre UMA partida, no eixo do tempo:
 *   - jogo FUTURO  → Previsão (PreditivaView) + Plano de jogo (ações/riscos).
 *   - jogo PASSADO → toggle Diagnóstico (o que aconteceu) | Como prevíamos
 *     (a previsão congelada × realidade).
 *
 * O jogo exibido é o do snapshot atual (bolinha), com um seletor de busca para
 * pular direto a qualquer confronto. Detecta quando um jogo que era futuro passa
 * a ter resultado e avisa.
 */

interface Props {
  matches: Match[];
  activeSnapshot: number;
  isAdmin: boolean;
  selectedTeams: string[];
  onSnapshotChange?: (snap: number) => void;
}

type PastView = "diagnostico" | "previa";

export default function JogoView({ matches, activeSnapshot, isAdmin, selectedTeams, onSnapshotChange }: Props) {
  const [pastView, setPastView] = React.useState<PastView>("diagnostico");

  // Ordem cronológica (mesma base das bolinhas): índice = snapshot do jogo.
  const ordered = React.useMemo(
    () => [...matches].sort((a, b) => String(a.date_utc).localeCompare(String(b.date_utc))),
    [matches],
  );
  const snapToMatch = React.useMemo(() => {
    const m = new Map<number, Match>();
    ordered.forEach((mt, i) => m.set(i + 1, mt));
    return m;
  }, [ordered]);
  const matchToSnap = React.useMemo(() => {
    const m = new Map<string, number>();
    ordered.forEach((mt, i) => m.set(mt.match_id, i + 1));
    return m;
  }, [ordered]);

  const activeMatch = snapToMatch.get(activeSnapshot) ?? null;
  const focusSet = React.useMemo(() => new Set(selectedTeams), [selectedTeams]);
  const focusGames = React.useMemo(
    () =>
      selectedTeams.length
        ? ordered.filter((m) => focusSet.has(m.home_team ?? "") || focusSet.has(m.away_team ?? ""))
        : [],
    [focusSet, ordered, selectedTeams.length],
  );
  const isFocusMode = selectedTeams.length > 0;
  const activeBelongsToFocus = !!activeMatch && (
    focusSet.has(activeMatch.home_team ?? "") || focusSet.has(activeMatch.away_team ?? "")
  );
  const match = isFocusMode ? (activeBelongsToFocus ? activeMatch : null) : activeMatch;
  const isFinal = match?.status === "finalizado";

  // Aviso "novo resultado": guarda o status visto por jogo e detecta a virada.
  const prevStatus = React.useRef<Map<string, string>>(new Map());
  const [justFinished, setJustFinished] = React.useState<Match | null>(null);
  React.useEffect(() => {
    const next = new Map<string, string>();
    let flipped: Match | null = null;
    for (const m of matches) {
      next.set(m.match_id, m.status);
      const before = prevStatus.current.get(m.match_id);
      if (before && before !== "finalizado" && m.status === "finalizado") flipped = m;
    }
    if (prevStatus.current.size > 0 && flipped) setJustFinished(flipped);
    prevStatus.current = next;
  }, [matches]);

  if (!isAdmin) return <Aviso texto="Acesso restrito a administradores." />;

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", justifyContent: isFocusMode ? "center" : "flex-start", flexWrap: "wrap" }}>
        {!isFocusMode && (
          <MatchSearch
            ordered={ordered}
            activeMatchId={match?.match_id}
            onPick={(mt) => {
              const snap = matchToSnap.get(mt.match_id) ?? 0;
              if (snap > 0) onSnapshotChange?.(snap);
            }}
          />
        )}
        {match && (
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
            {match.home_team} × {match.away_team} · {isFinal ? "finalizado" : "a acontecer"}
          </div>
        )}
      </div>

      {isFocusMode && (
        <FocusedGamePicker
          games={focusGames}
          activeMatchId={match?.match_id}
          onPick={(mt) => {
            const snap = matchToSnap.get(mt.match_id) ?? 0;
            if (snap > 0) onSnapshotChange?.(snap);
          }}
        />
      )}

      {justFinished && justFinished.match_id !== match?.match_id && (
        <NewResultBanner
          match={justFinished}
          onGo={() => {
            const snap = matchToSnap.get(justFinished.match_id) ?? 0;
            if (snap > 0) onSnapshotChange?.(snap);
            setJustFinished(null);
          }}
          onDismiss={() => setJustFinished(null)}
        />
      )}

      {isFocusMode && focusGames.length === 0 ? (
        <Aviso texto="Nenhum jogo encontrado para as selecoes em foco." />
      ) : !match ? (
        <Aviso texto={`Sem jogo na posição ${activeSnapshot}. Use as bolinhas ou a busca acima.`} />
      ) : isFinal ? (
        <FinishedGame
          match={match}
          view={pastView}
          onView={setPastView}
          activeSnapshot={activeSnapshot}
          isAdmin={isAdmin}
        />
      ) : (
        <UpcomingGame match={match} activeSnapshot={activeSnapshot} isAdmin={isAdmin} matches={matches} selectedTeams={selectedTeams} />
      )}
    </div>
  );
}

/* ── jogo futuro: previsão + plano ──────────────────────────────────────── */

function UpcomingGame({ match, activeSnapshot, isAdmin, matches, selectedTeams }: {
  match: Match; activeSnapshot: number; isAdmin: boolean; matches: Match[]; selectedTeams: string[];
}) {
  // Foco do plano: os dois times do jogo.
  const planTeams = [match.home_team, match.away_team].filter((t): t is string => !!t);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <PreditivaView snapshot={activeSnapshot} enabled={isAdmin} />
      <GamePlan snapshot={activeSnapshot} enabled={isAdmin} matches={matches} selectedTeams={planTeams.length ? planTeams : selectedTeams} />
    </div>
  );
}

/* ── jogo passado: toggle diagnóstico | como prevíamos ──────────────────── */

function FinishedGame({ match, view, onView, activeSnapshot, isAdmin }: {
  match: Match; view: PastView; onView: (v: PastView) => void; activeSnapshot: number; isAdmin: boolean;
}) {
  const { insights, isLoading, error } = useInsights({ tipo: "diagnostica", snapshot: activeSnapshot, enabled: isAdmin });
  const { narrative } = useInsightNarrative({ tipo: "diagnostica", snapshot: activeSnapshot, enabled: isAdmin });
  const items = React.useMemo(() => insights.filter((i) => i.snapshot === activeSnapshot), [insights, activeSnapshot]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
        <Toggle active={view === "diagnostico"} onClick={() => onView("diagnostico")} label="Diagnóstico" />
        <Toggle active={view === "previa"} onClick={() => onView("previa")} label="Como prevíamos" />
      </div>

      {view === "diagnostico" ? (
        error ? <Aviso texto={`Erro ao carregar análise: ${String(error)}`} />
        : isLoading ? <Centered><Spinner /></Centered>
        : items.length === 0 ? <Aviso texto={`Sem diagnóstico para este jogo ainda.`} />
        : <GameReport match={match} matchId={match.match_id}
            items={items}
            narrative={narrative?.exists && narrative.snapshot === activeSnapshot ? narrative.paragraphs : []}
            tipoLabel="Jogo a Jogo" enabled={isAdmin} />
      ) : (
        // "Como prevíamos": a Preditiva já mostra Previsão × Realidade para jogo
        // finalizado (palpite congelado vs resultado real).
        <PreditivaView snapshot={activeSnapshot} enabled={isAdmin} />
      )}
    </div>
  );
}

/* ── peças de UI ────────────────────────────────────────────────────────── */

function MatchSearch({ ordered, activeMatchId, onPick }: { ordered: Match[]; activeMatchId?: string; onPick: (m: Match) => void }) {
  const [q, setQ] = React.useState("");
  const [open, setOpen] = React.useState(false);
  const results = React.useMemo(() => {
    const term = q.trim().toLowerCase();
    const base = term
      ? ordered.filter((m) => `${m.home_team} ${m.away_team}`.toLowerCase().includes(term))
      : ordered;
    return base.slice(0, 40);
  }, [q, ordered]);

  return (
    <div style={{ position: "relative", minWidth: 260 }}>
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Buscar confronto…"
        style={{ width: "100%", background: "var(--surface)", color: "var(--text)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "8px 11px", fontSize: 13, fontFamily: "inherit", outline: "none" }}
      />
      {open && results.length > 0 && (
        <div style={{ position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 30, maxHeight: 320, overflowY: "auto", background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 8, boxShadow: "0 8px 24px rgba(0,0,0,0.4)" }}>
          {results.map((m) => {
            const on = m.match_id === activeMatchId;
            const score = m.status === "finalizado" ? `${m.home_score}–${m.away_score}` : "vs";
            return (
              <button key={m.match_id} onMouseDown={() => onPick(m)}
                style={{ width: "100%", display: "flex", alignItems: "center", gap: 8, padding: "8px 11px", border: "none", borderBottom: "1px solid var(--surface)", background: on ? "var(--surface)" : "transparent", color: "var(--text)", cursor: "pointer", textAlign: "left", fontSize: 12.5 }}>
                <Flag team={m.home_team ?? ""} height={12} />
                <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.home_team} {score} {m.away_team}</span>
                <span style={{ color: "var(--text-muted)", fontSize: 11 }}>{m.status === "finalizado" ? "✓" : "·"}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function FocusedGamePicker({ games, activeMatchId, onPick }: { games: Match[]; activeMatchId?: string; onPick: (m: Match) => void }) {
  if (games.length === 0) return null;
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center", padding: "0 0 4px" }}>
      {games.map((m) => {
        const on = m.match_id === activeMatchId;
        const score = m.status === "finalizado" ? `${m.home_score}-${m.away_score}` : "vs";
        return (
          <button
            key={m.match_id}
            onClick={() => onPick(m)}
            title={`${m.home_team} x ${m.away_team}`}
            style={{
              flex: "0 0 auto",
              display: "flex",
              alignItems: "center",
              gap: 7,
              padding: "7px 10px",
              borderRadius: 8,
              border: `1px solid ${on ? "#58a6ff" : "var(--surface2)"}`,
              background: on ? "#10213a" : "var(--surface)",
              color: on ? "var(--text)" : "var(--text-muted)",
              cursor: "pointer",
              fontFamily: "inherit",
              fontSize: 12,
            }}
          >
            <FlagBox team={m.home_team ?? ""} />
            <span style={{ fontWeight: 700, color: on ? "var(--text)" : "var(--text-muted)" }}>{score}</span>
            <FlagBox team={m.away_team ?? ""} />
          </button>
        );
      })}
    </div>
  );
}

function FlagBox({ team }: { team: string }) {
  return (
    <span style={{ width: 18, height: 12, display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0, overflow: "hidden" }}>
      <Flag team={team} height={12} style={{ maxWidth: 18, width: "auto", height: 12, objectFit: "contain" }} />
    </span>
  );
}

function NewResultBanner({ match, onGo, onDismiss }: { match: Match; onGo: () => void; onDismiss: () => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, background: "rgba(63,185,80,0.1)", border: "1px solid #3fb95055", borderRadius: 8, padding: "9px 12px", fontSize: 12.5, color: "var(--text)" }}>
      <span style={{ color: "#3fb950", fontWeight: 800 }}>⚡ novo resultado</span>
      <span style={{ flex: 1, minWidth: 0 }}>{match.home_team} <b>{match.home_score}–{match.away_score}</b> {match.away_team}</span>
      <button onClick={onGo} style={{ background: "#3fb950", color: "#0d1117", border: "none", borderRadius: 6, padding: "5px 10px", fontWeight: 800, fontSize: 12, cursor: "pointer" }}>ver</button>
      <button onClick={onDismiss} style={{ background: "transparent", color: "var(--text-muted)", border: "none", cursor: "pointer", fontSize: 16 }}>×</button>
    </div>
  );
}

function Toggle({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button onClick={onClick} style={{
      background: active ? "#1a2233" : "#161b22", border: `1px solid ${active ? "#58a6ff" : "#30363d"}`,
      color: active ? "#e6edf3" : "#8b949e", borderRadius: 6, padding: "6px 14px", fontSize: 13, fontWeight: active ? 700 : 500, cursor: "pointer", fontFamily: "inherit",
    }}>{label}</button>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}>{children}</div>;
}

function Aviso({ texto }: { texto: string }) {
  return <div style={{ padding: "32px 16px", textAlign: "center", fontSize: 13, color: "var(--text-muted)", lineHeight: 1.5 }}>{texto}</div>;
}
