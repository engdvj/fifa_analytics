"use client";

import React from "react";

// Barra de paginação padrão das abas (fixa no rodapé). Mostra botões numerados
// quando há poucas páginas; quando há muitas, cai para "pág. X / Y" compacto.
export default function FixedPager({
  page, pageCount, onPage, total, unit,
}: {
  page: number;          // 0-based
  pageCount: number;
  onPage: (p: number) => void;
  total: number;
  unit: string;          // "jogadores", "grupos", "seleções"
}) {
  if (pageCount <= 1) return null;
  const showNumbers = pageCount <= 9;
  return (
    <div className="v2-fixed-pager" style={{ position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 40, background: "#0d1117ee", borderTop: "1px solid #21262d", backdropFilter: "blur(6px)", padding: "9px 16px", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
      <PageBtn disabled={page === 0} onClick={() => onPage(page - 1)}>← Anterior</PageBtn>
      {showNumbers ? (
        Array.from({ length: pageCount }).map((_, i) => (
          <button
            key={i}
            onClick={() => onPage(i)}
            style={{ minWidth: 30, height: 30, padding: "0 6px", borderRadius: 6, fontSize: 12, cursor: "pointer", fontFamily: "inherit",
              background: i === page ? "#1f6feb" : "#161b22", color: i === page ? "#fff" : "#8b949e",
              border: `1px solid ${i === page ? "#1f6feb" : "#30363d"}` }}
          >{i + 1}</button>
        ))
      ) : (
        <span style={{ minWidth: 96, textAlign: "center", color: "#8b949e", fontSize: 12 }}>pág. {page + 1} / {pageCount}</span>
      )}
      <PageBtn disabled={page >= pageCount - 1} onClick={() => onPage(page + 1)}>Próxima →</PageBtn>
      <span className="v2-fixed-pager-count" style={{ marginLeft: 12, color: "#8b949e", fontSize: 12 }}>{total} {unit} · pág. {page + 1}/{pageCount}</span>
    </div>
  );
}

function PageBtn({ children, disabled, onClick }: { children: React.ReactNode; disabled: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 6, color: disabled ? "#484f58" : "#e6edf3", padding: "6px 12px", fontSize: 12, cursor: disabled ? "default" : "pointer", fontFamily: "inherit" }}>{children}</button>
  );
}
