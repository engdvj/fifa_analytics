"use client";

// Registro de um bolão JÁ ENCERRADO (mais para manter histórico).
// Fluxo em 2 passos: (1) configurar bolão + participantes; (2) preencher a grade
// jogos × participantes e salvar. A pontuação é calculada no backend a partir do
// resultado real dos jogos (tabela matches). Só o dono registra.

import { useState, useEffect } from "react";
import {
  bolao, users as usersApi, analytics,
  type Pool, type PoolMatch, type ScoringRule, type AppUser, type Match,
  type RegistroItem, type RankingRow, type PoolScope,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { FLAGS } from "@/lib/teamUtils";
import { STAGE_ORDER, stageLabel } from "@/lib/stages";
import { scoring, type ScoringCriterion } from "@/lib/api";
import RulesModal from "../RulesModal";

type Situacao = "ao_vivo" | "andamento" | "encerrado";
const SITUACAO_INFO: Record<Situacao, { label: string; help: string }> = {
  ao_vivo: { label: "Começando agora", help: "Os jogos ainda vão acontecer — você palpita daqui pra frente." },
  andamento: { label: "Em andamento", help: "Parte dos jogos já rolou. Preencha os palpites passados (pontuam na hora) e siga com os futuros." },
  encerrado: { label: "Já encerrado", help: "Todos os jogos já aconteceram. Registre os palpites de cada um." },
};

const card: React.CSSProperties = { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10 };
const inputStyle: React.CSSProperties = { background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 6, padding: "9px 12px", color: "var(--text)", fontSize: "0.9rem", outline: "none", boxSizing: "border-box" };
const btn: React.CSSProperties = { background: "var(--accent)", color: "#0d1117", border: "none", borderRadius: 6, padding: "10px 16px", fontWeight: 700, fontSize: "0.9rem", cursor: "pointer" };
const ghost: React.CSSProperties = { background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, padding: "9px 14px", fontSize: "0.85rem", cursor: "pointer" };

function slugUsername(name: string): string {
  const base = name.trim().toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "p";
  return `${base}-${Date.now().toString(36).slice(-4)}`;
}

// chave da célula da grade
type Cell = { home: string; away: string };
const cellKey = (matchId: string, userId: number) => `${matchId}|${userId}`;

export default function RegistrarBolaoPage() {
  const { token, user } = useAuth();
  const [step, setStep] = useState<"config" | "grade" | "done">("config");

  // config
  const [name, setName] = useState("");
  const [rules, setRules] = useState<ScoringRule[]>([]);
  const [ruleId, setRuleId] = useState<number | null>(null);
  const [scopeType, setScopeType] = useState<"all" | "stage" | "matches">("all");
  const [stages, setStages] = useState<string[]>([]);
  const [matchIds, setMatchIds] = useState<string[]>([]);
  const [allMatches, setAllMatches] = useState<Match[]>([]);
  const [allUsers, setAllUsers] = useState<AppUser[]>([]);
  const [selected, setSelected] = useState<AppUser[]>([]);
  const [newName, setNewName] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const [situacao, setSituacao] = useState<Situacao>("ao_vivo");
  const [criteria, setCriteria] = useState<ScoringCriterion[]>([]);
  const [modes, setModes] = useState<string[]>([]);
  const [rulesOpen, setRulesOpen] = useState(false);

  // grade
  const [pool, setPool] = useState<Pool | null>(null);
  const [matches, setMatches] = useState<PoolMatch[]>([]);
  const [grid, setGrid] = useState<Record<string, Cell>>({});
  const [ranking, setRanking] = useState<RankingRow[]>([]);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    Promise.all([bolao.rules(), usersApi.list(), scoring.criteria(), analytics.matches()]).then(([rs, us, cr, ms]) => {
      setRules(rs);
      setRuleId(rs[0]?.id ?? null);
      setAllUsers(us);
      setCriteria(cr.criteria);
      setModes(cr.modes);
      setAllMatches(ms);
    }).catch(() => {});
  }, [token]);

  if (!token) return null;

  const scope = (): PoolScope =>
    scopeType === "stage" ? { type: "stage", stages }
    : scopeType === "matches" ? { type: "matches", match_ids: matchIds }
    : { type: "all" };

  async function addParticipant() {
    const nm = newName.trim();
    if (!nm) return;
    setBusy(true); setError("");
    try {
      const u = await usersApi.create({ username: slugUsername(nm), name: nm });
      setAllUsers(prev => [...prev, u]);
      setSelected(prev => [...prev, u]);
      setNewName("");
    } catch (e) { setError(e instanceof Error ? e.message : "Erro ao criar participante"); }
    finally { setBusy(false); }
  }

  function toggleUser(u: AppUser) {
    setSelected(prev => prev.some(x => x.id === u.id) ? prev.filter(x => x.id !== u.id) : [...prev, u]);
  }

  async function goToGrade() {
    if (!name.trim() || !ruleId) { setError("Dê um nome e escolha a regra."); return; }
    if (selected.length === 0) { setError("Adicione ao menos um participante."); return; }
    if (scopeType === "stage" && stages.length === 0) { setError("Escolha ao menos uma fase."); return; }
    if (scopeType === "matches" && matchIds.length === 0) { setError("Escolha ao menos um jogo."); return; }
    setBusy(true); setError("");
    try {
      const p = await bolao.createPool({ name: name.trim(), rule_id: ruleId, scope: scope() });
      const ms = await bolao.poolMatches(p.id);
      setPool(p);
      setMatches(ms);
      setStep("grade");
    } catch (e) { setError(e instanceof Error ? e.message : "Erro ao criar bolão"); }
    finally { setBusy(false); }
  }

  // "Ao vivo": cria o bolão e segue pros meus bolões (palpita depois).
  async function createAndGo() {
    if (!name.trim() || !ruleId) { setError("Dê um nome e escolha a regra."); return; }
    if (scopeType === "stage" && stages.length === 0) { setError("Escolha ao menos uma fase."); return; }
    if (scopeType === "matches" && matchIds.length === 0) { setError("Escolha ao menos um jogo."); return; }
    setBusy(true); setError("");
    try {
      await bolao.createPool({ name: name.trim(), rule_id: ruleId, scope: scope() });
      window.location.href = "/bolao";
    } catch (e) { setError(e instanceof Error ? e.message : "Erro ao criar bolão"); }
    finally { setBusy(false); }
  }

  function setCell(matchId: string, userId: number, side: "home" | "away", v: string) {
    const k = cellKey(matchId, userId);
    setGrid(prev => ({ ...prev, [k]: { ...(prev[k] ?? { home: "", away: "" }), [side]: v.replace(/[^0-9]/g, "").slice(0, 2) } }));
  }

  async function saveRegistro() {
    if (!pool) return;
    const items: RegistroItem[] = [];
    for (const m of matches) {
      for (const u of selected) {
        const c = grid[cellKey(m.match_id, u.id)];
        if (!c) continue;
        if (c.home === "" || c.away === "") continue;
        items.push({ user_id: u.id, match_id: m.match_id, home_score: Number(c.home), away_score: Number(c.away) });
      }
    }
    if (items.length === 0) { setError("Preencha ao menos um palpite."); return; }
    setBusy(true); setError("");
    try {
      const res = await bolao.registro(pool.id, items);
      setRanking(res.ranking);
      setStep("done");
    } catch (e) { setError(e instanceof Error ? e.message : "Erro ao salvar registro"); }
    finally { setBusy(false); }
  }

  // ── Passo 1: configuração ───────────────────────────────────────────────────
  if (step === "config") {
    const stageList = STAGE_ORDER;
    return (
      <>
      <Shell title="Novo bolão" subtitle="Crie um bolão da Copa 2026 — começando agora, em andamento ou já encerrado.">
        <Field label="Situação do bolão">
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {(Object.keys(SITUACAO_INFO) as Situacao[]).map(s => (
              <Chip key={s} on={situacao === s} onClick={() => setSituacao(s)}>{SITUACAO_INFO[s].label}</Chip>
            ))}
          </div>
          <p style={{ fontSize: "0.76rem", color: "var(--text-muted)", margin: "8px 0 0" }}>{SITUACAO_INFO[situacao].help}</p>
        </Field>
        <Field label="Nome do bolão">
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Ex.: Bolão da firma" style={{ ...inputStyle, width: "100%" }} />
        </Field>
        <Field label="Regra de pontuação">
          <div style={{ display: "flex", gap: 8 }}>
            <select value={ruleId ?? ""} onChange={e => setRuleId(Number(e.target.value))} style={{ ...inputStyle, flex: 1, cursor: "pointer" }}>
              {rules.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
            <button type="button" onClick={() => setRulesOpen(true)} style={ghost}>Gerenciar regras</button>
          </div>
        </Field>
        <Field label="Quais jogos">
          <div style={{ display: "flex", gap: 8, marginBottom: 0, flexWrap: "wrap" }}>
            <Chip on={scopeType === "all"} onClick={() => setScopeType("all")}>Todos os jogos</Chip>
            <Chip on={scopeType === "stage"} onClick={() => setScopeType("stage")}>Por fase</Chip>
            <Chip on={scopeType === "matches"} onClick={() => setScopeType("matches")}>Jogos específicos</Chip>
          </div>
          {scopeType === "stage" && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
              {stageList.map(s => (
                <Chip key={s} on={stages.includes(s)} onClick={() => setStages(p => p.includes(s) ? p.filter(x => x !== s) : [...p, s])}>{stageLabel(s)}</Chip>
              ))}
            </div>
          )}
          {scopeType === "matches" && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginBottom: 6 }}>{matchIds.length} jogo(s) selecionado(s)</div>
              <div style={{ maxHeight: 240, overflowY: "auto", ...card, padding: 10 }}>
                {STAGE_ORDER.map(s => ({ s, list: allMatches.filter(m => m.stage === s).sort((a, b) => a.match_number - b.match_number) })).filter(x => x.list.length).map(({ s, list }) => (
                  <div key={s} style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: "0.7rem", color: "var(--accent)", fontWeight: 700, textTransform: "uppercase", marginBottom: 4 }}>{stageLabel(s)}</div>
                    {list.map(m => (
                      <label key={m.match_id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.82rem", padding: "3px 0", cursor: "pointer" }}>
                        <input type="checkbox" checked={matchIds.includes(m.match_id)} onChange={() => setMatchIds(p => p.includes(m.match_id) ? p.filter(x => x !== m.match_id) : [...p, m.match_id])} />
                        <span>{FLAGS[m.home_team ?? ""] ?? "🏳️"} {m.home_team ?? "?"} × {m.away_team ?? "?"} {FLAGS[m.away_team ?? ""] ?? "🏳️"}</span>
                        {m.status === "finalizado" && m.home_score != null && <span style={{ marginLeft: "auto", fontSize: "0.72rem", color: "#22c55e", fontWeight: 700 }}>{m.home_score}–{m.away_score}</span>}
                      </label>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </Field>
        <Field label={`Participantes (${selected.length} selecionado${selected.length === 1 ? "" : "s"})`}>
          {/* 1) Selecionar quem já existe na plataforma */}
          <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: 6 }}>Selecione quem já está na plataforma:</div>
          {allUsers.length > 4 && (
            <input value={userSearch} onChange={e => setUserSearch(e.target.value)} placeholder="Buscar pessoa…"
              style={{ ...inputStyle, width: "100%", marginBottom: 8 }} />
          )}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", maxHeight: 170, overflowY: "auto" }}>
            {allUsers.length === 0 && <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Ninguém cadastrado ainda — crie abaixo.</span>}
            {allUsers
              .filter(u => !userSearch.trim() || u.name.toLowerCase().includes(userSearch.toLowerCase()) || u.username.toLowerCase().includes(userSearch.toLowerCase()))
              .map(u => (
                <Chip key={u.id} on={selected.some(x => x.id === u.id)} onClick={() => toggleUser(u)}>
                  {u.name}
                  {u.username !== u.name && <span style={{ opacity: 0.55, marginLeft: 5, fontSize: "0.72rem" }}>@{u.username}</span>}
                </Chip>
              ))}
          </div>

          {/* 2) Criar um participante novo (vira usuário sem login) */}
          <div style={{ borderTop: "1px solid var(--border)", marginTop: 12, paddingTop: 12 }}>
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: 6 }}>Ou crie um participante novo:</div>
            <div style={{ display: "flex", gap: 8 }}>
              <input value={newName} onChange={e => setNewName(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addParticipant(); } }}
                placeholder="Nome do novo participante" style={{ ...inputStyle, flex: 1 }} />
              <button type="button" onClick={addParticipant} disabled={busy} style={ghost}>+ Criar</button>
            </div>
          </div>
        </Field>
        {error && <p style={{ color: "#ef4444", fontSize: "0.82rem", margin: 0 }}>{error}</p>}
        {situacao === "ao_vivo" ? (
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button onClick={createAndGo} disabled={busy} style={{ ...btn, flex: 1, minWidth: 160, opacity: busy ? 0.7 : 1 }}>{busy ? "Criando…" : "Criar bolão"}</button>
            <button onClick={goToGrade} disabled={busy} style={{ ...ghost, alignSelf: "stretch" }}>Preencher palpites agora →</button>
          </div>
        ) : (
          <button onClick={goToGrade} disabled={busy} style={{ ...btn, width: "100%", opacity: busy ? 0.7 : 1 }}>
            {busy ? "Preparando…" : "Avançar para os palpites →"}
          </button>
        )}
      </Shell>
      {rulesOpen && <RulesModal criteria={criteria} modes={modes} isAdmin={!!user?.is_admin} onClose={() => setRulesOpen(false)} onChanged={() => { bolao.rules().then(rs => setRules(rs)); }} />}
      </>
    );
  }

  // ── Passo 2: grade jogos × participantes ────────────────────────────────────
  if (step === "grade" && pool) {
    const byStage = STAGE_ORDER.map(s => ({ s, list: matches.filter(m => m.stage === s).sort((a, b) => a.match_number - b.match_number) })).filter(x => x.list.length);
    return (
      <Shell title={pool.name} subtitle="Jogos já realizados pontuam na hora; os que faltam ficam pendentes até acontecerem. Linhas em branco são ignoradas." wide
        footer={
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
            {error && <span style={{ color: "#ef4444", fontSize: "0.82rem", alignSelf: "center", marginRight: "auto" }}>{error}</span>}
            <button onClick={() => setStep("config")} style={ghost}>← Voltar</button>
            <button onClick={saveRegistro} disabled={busy} style={{ ...btn, opacity: busy ? 0.7 : 1 }}>{busy ? "Salvando…" : "Salvar registro"}</button>
          </div>
        }>
        <div style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "collapse", fontSize: "0.82rem", minWidth: "100%" }}>
            <thead>
              <tr>
                <th style={{ ...thStyle, textAlign: "left", position: "sticky", left: 0, background: "var(--surface)", zIndex: 2 }}>Jogo</th>
                <th style={thStyle}>Resultado</th>
                {selected.map(u => <th key={u.id} style={{ ...thStyle, minWidth: 92 }}>{u.name}</th>)}
              </tr>
            </thead>
            <tbody>
              {byStage.map(({ s, list }) => (
                <RowGroup key={s} label={stageLabel(s)} cols={selected.length + 2}>
                  {list.map(m => (
                    <tr key={m.match_id} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td style={{ ...tdStyle, textAlign: "left", whiteSpace: "nowrap", position: "sticky", left: 0, background: "var(--surface)" }}>
                        <span style={{ marginRight: 6 }}>{FLAGS[m.home_team ?? ""] ?? "🏳️"}</span>{m.home_team ?? "?"}
                        <span style={{ color: "var(--text-muted)" }}> × </span>
                        {m.away_team ?? "?"}<span style={{ marginLeft: 6 }}>{FLAGS[m.away_team ?? ""] ?? "🏳️"}</span>
                      </td>
                      <td style={{ ...tdStyle, whiteSpace: "nowrap" }}>
                        {m.status === "finalizado" && m.home_score != null
                          ? <span style={{ color: "#22c55e", fontWeight: 700 }}>{m.home_score}–{m.away_score}</span>
                          : <span style={{ fontSize: "0.66rem", color: "var(--text-muted)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 5px" }}>A JOGAR</span>}
                      </td>
                      {selected.map(u => {
                        const c = grid[cellKey(m.match_id, u.id)] ?? { home: "", away: "" };
                        return (
                          <td key={u.id} style={tdStyle}>
                            <div style={{ display: "flex", gap: 3, justifyContent: "center", alignItems: "center" }}>
                              <input value={c.home} onChange={e => setCell(m.match_id, u.id, "home", e.target.value)} style={miniInput} inputMode="numeric" />
                              <span style={{ color: "var(--text-muted)" }}>×</span>
                              <input value={c.away} onChange={e => setCell(m.match_id, u.id, "away", e.target.value)} style={miniInput} inputMode="numeric" />
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </RowGroup>
              ))}
            </tbody>
          </table>
        </div>
      </Shell>
    );
  }

  // ── Passo 3: pronto + ranking ───────────────────────────────────────────────
  return (
    <Shell title="Bolão registrado ✓" subtitle={pool ? `“${pool.name}” salvo. Pontuação calculada pelos resultados reais.` : ""}>
      <RankTable rows={ranking} />
      <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
        <a href="/bolao" style={{ ...btn, textDecoration: "none", display: "inline-block" }}>Ver nos meus bolões</a>
        <button onClick={() => { setStep("config"); setName(""); setSelected([]); setGrid({}); setPool(null); setRanking([]); }} style={ghost}>Registrar outro</button>
      </div>
    </Shell>
  );
}

// ── UI helpers ────────────────────────────────────────────────────────────────
const thStyle: React.CSSProperties = { textAlign: "center", padding: "8px 10px", fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", borderBottom: "1px solid var(--border)", fontWeight: 700 };
const tdStyle: React.CSSProperties = { textAlign: "center", padding: "6px 10px" };
const miniInput: React.CSSProperties = { width: 32, textAlign: "center", background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 5, padding: "5px 3px", color: "var(--text)", fontSize: "0.85rem", fontWeight: 700, outline: "none" };

function Shell({ title, subtitle, children, footer, wide }: { title: string; subtitle?: string; children: React.ReactNode; footer?: React.ReactNode; wide?: boolean }) {
  return (
    <div style={{ maxWidth: wide ? 1100 : 560, margin: "0 auto", padding: "28px 16px", animation: "shellIn .28s ease both" }}>
      <style>{`@keyframes shellIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}`}</style>
      <h1 style={{ fontSize: "1.25rem", fontWeight: 800, marginBottom: 4 }}>{title}</h1>
      {subtitle && <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: 20 }}>{subtitle}</p>}
      <div style={{ ...card, padding: 20, display: "flex", flexDirection: "column", gap: 16, boxShadow: "0 10px 36px -18px rgba(0,0,0,0.5)" }}>{children}</div>
      {footer && <div style={{ marginTop: 16 }}>{footer}</div>}
    </div>
  );
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: 6 }}><label style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>{label}</label>{children}</div>;
}
function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" onClick={onClick} style={{ border: "1px solid " + (on ? "var(--accent)" : "var(--border)"), background: on ? "rgba(88,166,255,0.12)" : "var(--surface2)", color: on ? "var(--accent)" : "var(--text-muted)", borderRadius: 6, padding: "6px 12px", fontSize: "0.82rem", fontWeight: 600, cursor: "pointer" }}>{children}</button>;
}
function RowGroup({ label, cols, children }: { label: string; cols: number; children: React.ReactNode }) {
  return (
    <>
      <tr><td colSpan={cols} style={{ padding: "10px 10px 4px", fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--accent)", position: "sticky", left: 0 }}>{label}</td></tr>
      {children}
    </>
  );
}
function RankTable({ rows }: { rows: RankingRow[] }) {
  if (rows.length === 0) return <div style={{ padding: 20, color: "var(--text-muted)", textAlign: "center" }}>Nenhum ponto calculado (os jogos podem não estar finalizados).</div>;
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
        {["#", "Nome", "Pontos", "Palpites"].map(h => <th key={h} style={{ textAlign: h === "Nome" ? "left" : "center", padding: "8px 12px", fontSize: "0.74rem", color: "var(--text-muted)", textTransform: "uppercase" }}>{h}</th>)}
      </tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.user_id} style={{ borderBottom: "1px solid var(--border)", background: i === 0 ? "rgba(88,166,255,0.05)" : "transparent" }}>
            <td style={{ textAlign: "center", padding: 12, fontWeight: 700, color: i < 3 ? ["#f5c542", "#c0c0c0", "#cd7f32"][i] : "var(--text-muted)" }}>{i + 1}</td>
            <td style={{ padding: 12, fontWeight: i === 0 ? 700 : 400 }}>{r.name}</td>
            <td style={{ textAlign: "center", padding: 12, fontWeight: 700, color: "var(--accent)" }}>{r.total_points}</td>
            <td style={{ textAlign: "center", padding: 12, color: "var(--text-muted)", fontSize: "0.85rem" }}>{r.predictions}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
