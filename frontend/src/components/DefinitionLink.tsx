"use client";

// Link inline que abre um modal explicativo de um conceito. Use em qualquer
// lugar onde um termo é citado:  <DefinitionLink id="xg">xG</DefinitionLink>
// A fonte de verdade é frontend/src/lib/definitions.ts.

import { useState } from "react";
import Modal from "@/components/ui/Modal";
import { getTerm, categoryOf, type Term } from "@/lib/definitions";
import { openGlossarioPopup } from "@/lib/glossario";

const kicker: React.CSSProperties = {
  fontSize: "0.74rem",
  fontWeight: 800,
  letterSpacing: 0.6,
  textTransform: "uppercase",
  color: "var(--text-muted)",
};

export function ConceptBody({
  term,
  onNavigate,
}: {
  term: Term;
  onNavigate?: (id: string) => void;
}) {
  const cat = categoryOf(term.category);
  const accent = cat?.accent ?? "var(--accent)";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {cat && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, color: accent, ...kicker }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: accent }} />
          {cat.label}
        </div>
      )}

      <p style={{ margin: 0, color: "var(--text)", fontSize: "1.05rem", lineHeight: 1.7 }}>{term.full}</p>

      {term.formula && (
        <Panel accent="var(--accent2)" label="Como é calculado" labelColor="var(--accent2)">
          <span style={{ fontSize: "0.98rem", color: "var(--accent2)", lineHeight: 1.6, fontWeight: 600 }}>
            {term.formula}
          </span>
        </Panel>
      )}

      {term.example && (
        <Panel accent={accent} label="Exemplo na prática" labelColor={accent} tint={accent}>
          <span style={{ fontSize: "1rem", color: "var(--text)", lineHeight: 1.65 }}>{term.example}</span>
        </Panel>
      )}

      {term.related && term.related.length > 0 && (
        <div style={{ marginTop: 2 }}>
          <div style={{ ...kicker, marginBottom: 9 }}>Veja também</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
            {term.related.map((rid) => {
              const r = getTerm(rid);
              if (!r) return null;
              return <RelatedChip key={rid} label={r.term} onClick={() => onNavigate?.(rid)} clickable={!!onNavigate} />;
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function Panel({
  accent,
  label,
  labelColor,
  tint,
  children,
}: {
  accent: string;
  label: string;
  labelColor?: string;
  tint?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: tint ? `color-mix(in srgb, ${tint} 8%, var(--surface))` : "var(--background)",
        border: "1px solid var(--border)",
        borderLeft: `4px solid ${accent}`,
        borderRadius: 9,
        padding: "13px 16px",
      }}
    >
      <div style={{ ...kicker, color: labelColor ?? "var(--text-muted)", marginBottom: 8 }}>{label}</div>
      {children}
    </div>
  );
}

function RelatedChip({ label, onClick, clickable }: { label: string; onClick: () => void; clickable: boolean }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        cursor: clickable ? "pointer" : "default",
        background: hover ? "rgba(88,166,255,0.1)" : "var(--surface2)",
        border: `1px solid ${hover ? "var(--accent)" : "var(--border)"}`,
        borderRadius: 6,
        padding: "4px 10px",
        fontSize: "0.78rem",
        color: "var(--accent)",
        fontWeight: 600,
        transition: "background 0.12s, border-color 0.12s",
      }}
    >
      {label}
    </button>
  );
}

// Modal compartilhado: navega entre termos relacionados e tem rodapé com link
// para o glossário (janela flutuante).
function ConceptModal({ id, open, onClose }: { id: string; open: boolean; onClose: () => void }) {
  const [activeId, setActiveId] = useState(id);
  const term = getTerm(open ? activeId : id) ?? getTerm(id);
  if (!term) return null;
  return (
    <Modal open={open} onClose={onClose} title={term.term} size="lg">
      <ConceptBody term={term} onNavigate={(rid) => setActiveId(rid)} />
      <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--border)", display: "flex", justifyContent: "flex-end" }}>
        <button
          onClick={openGlossarioPopup}
          style={{ background: "none", border: "none", color: "var(--accent)", fontWeight: 600, fontSize: "0.82rem", cursor: "pointer" }}
        >
          Ver no glossário ⧉
        </button>
      </div>
    </Modal>
  );
}

// Forma 1 — palavra/rótulo sublinhado (pontilhado) que abre o conceito.
export default function DefinitionLink({
  id,
  children,
  subtle = false,
}: {
  id: string;
  children?: React.ReactNode;
  subtle?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const base = getTerm(id);
  if (!base) return <>{children}</>;

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title={base.short}
        style={{
          display: "inline",
          background: "none",
          border: "none",
          padding: 0,
          margin: 0,
          font: "inherit",
          color: subtle ? "inherit" : "var(--accent)",
          borderBottom: "1px dotted var(--accent)",
          fontWeight: subtle ? "inherit" : 600,
          cursor: "pointer",
        }}
      >
        {children ?? base.term}
      </button>
      <ConceptModal id={id} open={open} onClose={() => setOpen(false)} />
    </>
  );
}

// Forma 2 — bolinha "?" ao lado de um rótulo, que abre o conceito.
export function DefinitionBubble({ id, size = 15 }: { id: string; size?: number }) {
  const [open, setOpen] = useState(false);
  const base = getTerm(id);
  if (!base) return null;

  return (
    <>
      <button
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
        title={`${base.term}: ${base.short}`}
        aria-label={`O que é ${base.term}?`}
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: size,
          height: size,
          marginLeft: 5,
          padding: 0,
          borderRadius: "50%",
          border: "1px solid var(--border)",
          background: "var(--surface2)",
          color: "var(--text-muted)",
          fontSize: size * 0.62,
          fontWeight: 700,
          lineHeight: 1,
          cursor: "pointer",
          verticalAlign: "middle",
        }}
      >
        ?
      </button>
      <ConceptModal id={id} open={open} onClose={() => setOpen(false)} />
    </>
  );
}
