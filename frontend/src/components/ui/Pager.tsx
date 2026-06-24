"use client";

// Paginação reutilizável. Mostra "X–Y de N" + Anterior/Próxima.
export default function Pager({ page, total, perPage, onPage }: {
  page: number; total: number; perPage: number; onPage: (p: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / perPage));
  if (pages <= 1) return null;
  const from = (page - 1) * perPage + 1;
  const to = Math.min(page * perPage, total);
  const btn = (disabled: boolean): React.CSSProperties => ({
    background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 6,
    padding: "5px 12px", fontSize: "0.8rem", fontWeight: 600,
    color: disabled ? "var(--text-muted)" : "var(--text)",
    cursor: disabled ? "default" : "pointer", opacity: disabled ? 0.45 : 1,
    transition: "background .15s, border-color .15s",
  });
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 4px 2px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
      <span style={{ marginRight: "auto" }}>{from}–{to} de {total}</span>
      <button disabled={page <= 1} onClick={() => onPage(page - 1)} style={btn(page <= 1)}>← Anterior</button>
      <span style={{ minWidth: 84, textAlign: "center" }}>Página {page} / {pages}</span>
      <button disabled={page >= pages} onClick={() => onPage(page + 1)} style={btn(page >= pages)}>Próxima →</button>
    </div>
  );
}
