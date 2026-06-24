"use client";

// Central de Definições — glossário navegável de todos os conceitos de análise.
// Dois modos: página cheia (sidebar de categorias) e popup (?popup=1, janela
// flutuante compacta para consultar lado a lado). Segue o design system.

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Modal from "@/components/ui/Modal";
import { ConceptBody } from "@/components/DefinitionLink";
import { openGlossarioPopup } from "@/lib/glossario";
import { CATEGORIES, TERMS, getTerm, type CategoryId, type Term } from "@/lib/definitions";

function norm(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

function matches(t: Term, q: string): boolean {
  if (!q) return true;
  const hay = norm([t.term, t.short, t.full, ...(t.aka ?? [])].join(" "));
  return norm(q).split(/\s+/).every((w) => hay.includes(w));
}

const kicker: React.CSSProperties = {
  fontSize: "0.68rem",
  fontWeight: 800,
  letterSpacing: 0.6,
  textTransform: "uppercase",
  color: "var(--accent2)",
};

export default function DefinicoesPage() {
  return (
    <Suspense fallback={null}>
      <Glossario />
    </Suspense>
  );
}

function Glossario() {
  const sp = useSearchParams();
  const popup = sp.get("popup") === "1";
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<CategoryId | "all">("all");
  const [openId, setOpenId] = useState<string | null>(null);

  const filtered = useMemo(
    () => TERMS.filter((t) => (cat === "all" || t.category === cat) && matches(t, q)),
    [q, cat],
  );
  const sections = useMemo(
    () =>
      CATEGORIES.map((c) => ({ cat: c, terms: filtered.filter((t) => t.category === c.id) }))
        .filter((s) => s.terms.length > 0),
    [filtered],
  );
  const openTerm = openId ? getTerm(openId) : undefined;

  const search = (
    <input
      value={q}
      onChange={(e) => setQ(e.target.value)}
      placeholder="Buscar conceito…"
      style={{
        width: "100%",
        background: "var(--surface2)",
        border: "1px solid var(--border)",
        borderRadius: 7,
        padding: "9px 11px",
        color: "var(--text)",
        fontSize: "0.85rem",
        outline: "none",
        boxSizing: "border-box",
      }}
    />
  );

  const empty = sections.length === 0 && (
    <div style={{ color: "var(--text-muted)", padding: "40px 0", textAlign: "center", fontSize: "0.9rem" }}>
      Nenhum conceito encontrado para “{q}”.
    </div>
  );

  const sectionsJsx = sections.map(({ cat: c, terms }) => (
    <section key={c.id} style={{ marginBottom: 28 }}>
      <div style={{ ...kicker, color: c.accent }}>{c.label}</div>
      <p style={{ margin: "5px 0 12px", fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.5 }}>{c.blurb}</p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(252px, 1fr))", gap: 12 }}>
        {terms.map((t) => (
          <TermTile key={t.id} term={t} dot={c.accent} onOpen={() => setOpenId(t.id)} />
        ))}
      </div>
    </section>
  ));

  // ───────────────────────── POPUP (janela flutuante lateral) ─────────────────────────
  if (popup) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--background)" }}>
        <div style={{ position: "sticky", top: 0, zIndex: 5, background: "var(--background)", padding: "12px 14px 11px", borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 9 }}>
            <strong style={{ fontSize: "0.95rem", color: "var(--text)" }}>Central de Definições</strong>
            <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{TERMS.length} conceitos</span>
          </div>
          {search}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 9 }}>
            <Pill active={cat === "all"} accent="var(--accent)" onClick={() => setCat("all")}>Todos</Pill>
            {CATEGORIES.map((c) => (
              <Pill key={c.id} active={cat === c.id} accent={c.accent} onClick={() => setCat(c.id)}>
                {c.label}
              </Pill>
            ))}
          </div>
        </div>
        <div style={{ padding: "14px 14px 48px" }}>
          {empty}
          {sectionsJsx}
        </div>
        {openTerm && (
          <Modal open onClose={() => setOpenId(null)} title={openTerm.term} size="sm">
            <ConceptBody term={openTerm} onNavigate={(rid) => setOpenId(rid)} />
          </Modal>
        )}
      </div>
    );
  }

  // ───────────────────────── PÁGINA CHEIA ─────────────────────────
  return (
    <div style={{ minHeight: "100vh", background: "var(--background)" }}>
      <div style={{ padding: "24px 30px 64px" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <div>
            <div style={kicker}>Glossário</div>
            <h1 style={{ margin: "6px 0 0", fontSize: "1.5rem", fontWeight: 800, color: "var(--text)", letterSpacing: -0.3 }}>
              Central de Definições
            </h1>
            <p style={{ margin: "8px 0 0", color: "var(--text-muted)", fontSize: "0.9rem", maxWidth: 680, lineHeight: 1.55 }}>
              Tudo que usamos para analisar a Copa, explicado de forma simples — com a fórmula em
              palavras e um exemplo real do torneio. Clique em qualquer conceito para abrir.
            </p>
          </div>
          <button
            onClick={openGlossarioPopup}
            title="Abrir numa janela flutuante para consultar ao lado da página"
            style={{
              display: "inline-flex", alignItems: "center", gap: 7,
              background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 7,
              padding: "8px 13px", fontSize: "0.82rem", fontWeight: 600, color: "var(--text)",
              cursor: "pointer", whiteSpace: "nowrap",
            }}
          >
            ⧉ Abrir em janela
          </button>
        </div>

        <div style={{ display: "flex", gap: 24, alignItems: "flex-start", marginTop: 22 }}>
          <aside style={{ width: 210, flexShrink: 0, position: "sticky", top: 14, alignSelf: "flex-start" }}>
            <div style={{ marginBottom: 10 }}>{search}</div>
            <NavItem label="Todos" count={TERMS.length} active={cat === "all"} onClick={() => setCat("all")} />
            {CATEGORIES.map((c) => (
              <NavItem
                key={c.id}
                label={c.label}
                count={TERMS.filter((t) => t.category === c.id).length}
                dot={c.accent}
                active={cat === c.id}
                onClick={() => setCat(c.id)}
              />
            ))}
          </aside>
          <main style={{ flex: 1, minWidth: 0 }}>
            {empty}
            {sectionsJsx}
          </main>
        </div>
      </div>

      {openTerm && (
        <Modal open onClose={() => setOpenId(null)} title={openTerm.term} size="lg">
          <ConceptBody term={openTerm} onNavigate={(rid) => setOpenId(rid)} />
        </Modal>
      )}
    </div>
  );
}

function Pill({ active, accent, onClick, children }: { active: boolean; accent: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      style={{
        cursor: "pointer",
        borderRadius: 999,
        padding: "5px 11px",
        fontSize: "0.76rem",
        fontWeight: 600,
        whiteSpace: "nowrap",
        color: active ? "#0d1117" : "var(--text-muted)",
        background: active ? accent : "var(--surface)",
        border: `1px solid ${active ? accent : "var(--border)"}`,
        transition: "color 0.12s, background 0.12s, border-color 0.12s",
      }}
    >
      {children}
    </button>
  );
}

function NavItem({ label, count, active, onClick, dot }: { label: string; count: number; active: boolean; onClick: () => void; dot?: string }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 8,
        textAlign: "left",
        padding: "7px 9px",
        marginBottom: 3,
        borderRadius: 6,
        border: `1px solid ${active ? "var(--accent)" : "transparent"}`,
        background: active ? "rgba(88,166,255,0.1)" : "transparent",
        color: active ? "var(--accent2)" : "var(--text-muted)",
        fontSize: "0.82rem",
        fontWeight: active ? 700 : 500,
        cursor: "pointer",
        transition: "background 0.12s, color 0.12s, border-color 0.12s",
      }}
    >
      {dot ? (
        <span style={{ width: 7, height: 7, borderRadius: 2, background: dot, flexShrink: 0 }} />
      ) : (
        <span style={{ width: 7, flexShrink: 0 }} />
      )}
      <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>
      <span style={{ fontSize: "0.72rem", opacity: 0.7 }}>{count}</span>
    </button>
  );
}

function TermTile({ term, dot, onOpen }: { term: Term; dot: string; onOpen: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onOpen}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        textAlign: "left",
        cursor: "pointer",
        background: "var(--surface)",
        border: `1px solid ${hover ? "var(--accent)" : "var(--border)"}`,
        borderRadius: 9,
        padding: "13px 15px",
        minHeight: 92,
        transition: "border-color 0.12s, background 0.12s",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 7, height: 7, borderRadius: 2, background: dot, flexShrink: 0 }} />
        <span style={{ fontWeight: 700, color: "var(--text)", fontSize: "0.92rem" }}>{term.term}</span>
      </span>
      <span style={{ color: "var(--text-muted)", fontSize: "0.82rem", lineHeight: 1.5 }}>{term.short}</span>
    </button>
  );
}
