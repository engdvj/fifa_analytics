"use client";

import { useState } from "react";
import useSWR from "swr";
import { bolao, ScoringRule } from "@/lib/api";

function RulesSection({ rules }: { rules: ScoringRule[] }) {
  return (
    <div>
      <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-muted)" }}>
        Modos de pontuação disponíveis
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {rules.map((r) => (
          <div
            key={r.id}
            style={{
              background: "var(--surface2)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "14px 16px",
            }}
          >
            <div className="font-semibold text-sm mb-1">{r.name}</div>
            <div style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>{r.description}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CreatePoolForm({ rules, onCreated }: { rules: ScoringRule[]; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [ruleId, setRuleId] = useState<number | null>(rules[0]?.id ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ruleId) return;
    setLoading(true);
    setError(null);
    try {
      const userRes = await fetch("http://localhost:8000/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, name: email.split("@")[0] }),
      });
      if (!userRes.ok) {
        const body = await userRes.json();
        throw new Error(body.detail ?? "Erro ao criar usuário");
      }
      const user = await userRes.json();
      await bolao.createPool({ name, owner_id: user.id, rule_id: ruleId });
      setName("");
      setEmail("");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10 }}
      className="p-5 space-y-3"
    >
      <h3 className="font-semibold text-sm mb-1">Criar bolão</h3>
      <input
        type="text"
        required
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Nome do bolão"
        style={{
          width: "100%",
          background: "var(--surface2)",
          border: "1px solid var(--border)",
          borderRadius: 6,
          padding: "8px 12px",
          color: "var(--text)",
          fontSize: "0.85rem",
          outline: "none",
        }}
      />
      <input
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Seu email"
        style={{
          width: "100%",
          background: "var(--surface2)",
          border: "1px solid var(--border)",
          borderRadius: 6,
          padding: "8px 12px",
          color: "var(--text)",
          fontSize: "0.85rem",
          outline: "none",
        }}
      />
      <select
        value={ruleId ?? ""}
        onChange={(e) => setRuleId(Number(e.target.value))}
        style={{
          width: "100%",
          background: "var(--surface2)",
          border: "1px solid var(--border)",
          borderRadius: 6,
          padding: "8px 12px",
          color: "var(--text)",
          fontSize: "0.85rem",
          outline: "none",
        }}
      >
        {rules.map((r) => (
          <option key={r.id} value={r.id}>
            {r.name}
          </option>
        ))}
      </select>
      {error && <p style={{ color: "var(--red)", fontSize: "0.8rem" }}>{error}</p>}
      <button
        type="submit"
        disabled={loading}
        style={{
          background: loading ? "var(--surface2)" : "var(--accent)",
          color: loading ? "var(--text-muted)" : "#0d1117",
          border: "none",
          borderRadius: 6,
          padding: "8px 20px",
          fontWeight: 700,
          fontSize: "0.85rem",
          cursor: loading ? "not-allowed" : "pointer",
        }}
      >
        {loading ? "Criando…" : "Criar bolão"}
      </button>
    </form>
  );
}

export default function BolaoPage() {
  const { data: rules, isLoading: loadingRules } = useSWR("rules", bolao.rules);
  const { data: pools, isLoading: loadingPools, mutate } = useSWR("pools", bolao.pools);

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold mb-1">Bolão Copa 2026</h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
          Crie um bolão, adicione amigos e compita pelos palpites mais certeiros.
        </p>
      </div>

      {loadingRules ? (
        <div className="h-20 animate-pulse rounded-lg" style={{ background: "var(--surface2)" }} />
      ) : (
        rules && (
          <>
            <RulesSection rules={rules} />
            <CreatePoolForm rules={rules} onCreated={() => mutate()} />
          </>
        )
      )}

      <div>
        <h2 className="text-base font-semibold mb-3">Bolões criados</h2>
        {loadingPools ? (
          <div className="space-y-2">
            {[1, 2].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded" style={{ background: "var(--surface2)" }} />
            ))}
          </div>
        ) : pools && pools.length > 0 ? (
          <div className="space-y-2">
            {pools.map((p) => (
              <div
                key={p.id}
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  padding: "12px 16px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span className="font-medium">{p.name}</span>
                <span style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>
                  #{p.id}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
            Nenhum bolão criado ainda.
          </p>
        )}
      </div>
    </div>
  );
}
