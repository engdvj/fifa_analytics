"use client";

import { useEffect, useRef } from "react";

const SIZE_MAP = {
  sm: 400,
  md: 560,
  lg: 720,
  xl: 960,
} as const;

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  size?: keyof typeof SIZE_MAP;
}

export default function Modal({ open, onClose, title, children, size = "md" }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{
        background: "rgba(0,0,0,0.72)", animation: "modalFade .16s ease", backdropFilter: "blur(2px)",
        // Reset de propriedades herdadas: o modal renderiza inline (sem portal),
        // então herda estilos do gatilho (ex.: bolinha "?" dentro de um <th>
        // uppercase/nowrap). Isso garante texto normal em qualquer contexto.
        textTransform: "none", whiteSpace: "normal", textAlign: "left", letterSpacing: "normal", fontStyle: "normal",
      }}
      onClick={onClose}
    >
      <style>{`@keyframes modalFade{from{opacity:0}to{opacity:1}}@keyframes modalPop{from{opacity:0;transform:translateY(12px) scale(.97)}to{opacity:1;transform:none}}`}</style>
      <div
        ref={dialogRef}
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          maxWidth: SIZE_MAP[size],
          width: "100%",
          maxHeight: "85vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 24px 64px -16px rgba(0,0,0,0.6)",
          animation: "modalPop .22s cubic-bezier(.2,.8,.25,1)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {(title != null) && (
          <div
            style={{ borderBottom: "1px solid var(--border)" }}
            className="flex items-center justify-between px-6 py-4 shrink-0"
          >
            <h2 className="text-base font-semibold" style={{ color: "var(--text)" }}>
              {title}
            </h2>
            <button
              onClick={onClose}
              style={{
                color: "var(--text-muted)",
                background: "none",
                border: "none",
                cursor: "pointer",
                fontSize: "1.1rem",
                lineHeight: 1,
                padding: "2px 6px",
              }}
              aria-label="Fechar"
            >
              ✕
            </button>
          </div>
        )}
        <div className="overflow-auto flex-1 p-6">{children}</div>
      </div>
    </div>
  );
}
