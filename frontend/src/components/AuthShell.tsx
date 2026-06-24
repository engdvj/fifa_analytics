"use client";

import React from "react";

// Moldura visual compartilhada por login/registro — alinhada ao design system
// do app (acento azul), mantendo a marca Copa 2026 (troféu dourado + bandeiras).

const FLAGS = "🇧🇷🇦🇷🇫🇷🇩🇪🇪🇸🇵🇹🇳🇱🇬🇧🇲🇽🇺🇸🇯🇵🇲🇦";

export function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
      background: "radial-gradient(1100px 600px at 50% -10%, #0e2a4d 0%, transparent 60%), linear-gradient(165deg, #0a1320 0%, #0d1117 55%, #0a1626 100%)",
      position: "relative", overflow: "hidden",
    }}>
      <style>{`
        @keyframes authIn { from { opacity: 0; transform: translateY(14px) scale(.98); } to { opacity: 1; transform: none; } }
        .auth-card input { transition: border-color .15s, box-shadow .15s; }
        .auth-card input:focus { border-color: #58a6ff; box-shadow: 0 0 0 3px rgba(88,166,255,0.16); }
        .auth-card button[type=submit] { transition: transform .15s, box-shadow .15s, filter .15s; }
        .auth-card button[type=submit]:hover:not(:disabled) { transform: translateY(-2px); filter: brightness(1.06); box-shadow: 0 10px 26px rgba(88,166,255,0.4); }
      `}</style>

      {/* linhas de campo decorativas (azul sutil) */}
      <div aria-hidden style={{ position: "absolute", inset: 0, opacity: 0.05, pointerEvents: "none",
        backgroundImage: "repeating-linear-gradient(90deg, transparent 0 78px, #58a6ff 78px 80px)" }} />
      <div aria-hidden style={{ position: "absolute", left: "50%", top: "50%", width: 360, height: 360, transform: "translate(-50%,-50%)", border: "2px solid rgba(88,166,255,0.1)", borderRadius: "50%", pointerEvents: "none" }} />

      <div className="auth-card" style={{
        position: "relative", width: "100%", maxWidth: 410,
        background: "rgba(13,17,23,0.84)", backdropFilter: "blur(8px)",
        border: "1px solid rgba(88,166,255,0.22)", borderRadius: 18,
        boxShadow: "0 24px 70px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.02)",
        padding: "30px 30px 26px", animation: "authIn .35s cubic-bezier(.2,.8,.25,1) both",
      }}>
        {/* marca */}
        <div style={{ textAlign: "center", marginBottom: 18 }}>
          <div style={{ fontSize: 40, lineHeight: 1 }}>🏆</div>
          <div style={{ marginTop: 8, fontSize: 13, fontWeight: 800, letterSpacing: "0.22em", color: "#f5c542", textTransform: "uppercase" }}>Copa 2026</div>
          <div style={{ fontSize: 11, letterSpacing: "0.32em", color: "#58a6ff", textTransform: "uppercase", fontWeight: 700 }}>· Bolão ·</div>
        </div>

        <h1 style={{ margin: 0, fontSize: "1.4rem", fontWeight: 800, color: "#f0f6fc", textAlign: "center" }}>{title}</h1>
        <p style={{ margin: "6px 0 22px", fontSize: "0.86rem", color: "#8b949e", textAlign: "center", lineHeight: 1.4 }}>{subtitle}</p>

        {children}

        {/* faixa de bandeiras */}
        <div style={{ marginTop: 22, paddingTop: 16, borderTop: "1px solid rgba(255,255,255,0.06)", textAlign: "center", fontSize: 16, letterSpacing: 2, opacity: 0.85 }}>{FLAGS}</div>
      </div>
    </div>
  );
}

export const authInput: React.CSSProperties = {
  background: "rgba(22,27,34,0.9)", border: "1px solid #2b3340", borderRadius: 9,
  padding: "11px 13px", color: "#f0f6fc", fontSize: "0.95rem", outline: "none", width: "100%", boxSizing: "border-box",
};

export function authButton(loading: boolean): React.CSSProperties {
  return {
    marginTop: 4, border: "none", borderRadius: 9, padding: "12px",
    background: "linear-gradient(135deg, #4493e6 0%, #58a6ff 60%, #6cb4ff 100%)",
    color: "#06182e", fontWeight: 800, fontSize: "0.95rem",
    cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.7 : 1,
    boxShadow: "0 6px 18px rgba(88,166,255,0.3)",
  };
}

export function AuthError({ msg }: { msg: string | null }) {
  if (!msg) return null;
  return <p style={{ color: "#ff7b72", fontSize: "0.82rem", margin: "2px 0 0", textAlign: "center" }}>{msg}</p>;
}
