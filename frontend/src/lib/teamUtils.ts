import { Match } from "@/lib/api";

export const CONFEDERATION: Record<string, string> = {
  "Alemanha": "UEFA", "Espanha": "UEFA", "França": "UEFA", "Inglaterra": "UEFA",
  "Portugal": "UEFA", "Países Baixos": "UEFA", "Bélgica": "UEFA", "Croácia": "UEFA",
  "Suíça": "UEFA", "Áustria": "UEFA", "Turquia": "UEFA", "Escócia": "UEFA",
  "Tchéquia": "UEFA", "Noruega": "UEFA", "Suécia": "UEFA", "Bósnia e Herzegovina": "UEFA",
  "Brasil": "CONMEBOL", "Argentina": "CONMEBOL", "Colômbia": "CONMEBOL",
  "Uruguai": "CONMEBOL", "Equador": "CONMEBOL", "Paraguai": "CONMEBOL",
  "Marrocos": "CAF", "Senegal": "CAF", "Egito": "CAF", "Costa do Marfim": "CAF",
  "Côte d'Ivoire": "CAF", "Gana": "CAF", "RD Congo": "CAF", "Tunísia": "CAF",
  "Argélia": "CAF", "Cabo Verde": "CAF", "África do Sul": "CAF",
  "Japão": "AFC", "Coreia do Sul": "AFC", "Austrália": "AFC", "Irã": "AFC",
  "Arábia Saudita": "AFC", "Catar": "AFC", "Iraque": "AFC", "Jordânia": "AFC",
  "Uzbequistão": "AFC",
  "Estados Unidos": "CONCACAF", "México": "CONCACAF", "Canadá": "CONCACAF",
  "Panamá": "CONCACAF", "Haiti": "CONCACAF", "Curaçao": "CONCACAF",
  "Nova Zelândia": "OFC",
};

export interface TeamSummary {
  name: string;
  code: string | null;
  group: string | null;
  games: Match[];
  played: number;
  wins: number;
  draws: number;
  losses: number;
  gf: number;
  ga: number;
  points: number;
  confederation: string;
}

export const FLAGS: Record<string, string> = {
  "África do Sul": "🇿🇦", "Alemanha": "🇩🇪", "Argélia": "🇩🇿",
  "Arábia Saudita": "🇸🇦", "Argentina": "🇦🇷", "Austrália": "🇦🇺",
  "Bélgica": "🇧🇪", "Bósnia e Herzegovina": "🇧🇦", "Brasil": "🇧🇷",
  "Cabo Verde": "🇨🇻", "Canadá": "🇨🇦", "Catar": "🇶🇦",
  "Colômbia": "🇨🇴", "Coreia do Sul": "🇰🇷", "Costa do Marfim": "🇨🇮",
  "Côte d'Ivoire": "🇨🇮", "Croácia": "🇭🇷", "Curaçao": "🇨🇼",
  "Egito": "🇪🇬", "Equador": "🇪🇨", "Escócia": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
  "Espanha": "🇪🇸", "Estados Unidos": "🇺🇸", "França": "🇫🇷",
  "Gana": "🇬🇭", "Haiti": "🇭🇹", "Inglaterra": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
  "Iraque": "🇮🇶", "Irã": "🇮🇷", "Japão": "🇯🇵",
  "Jordânia": "🇯🇴", "Marrocos": "🇲🇦", "México": "🇲🇽",
  "Noruega": "🇳🇴", "Nova Zelândia": "🇳🇿", "Panamá": "🇵🇦",
  "Paraguai": "🇵🇾", "Países Baixos": "🇳🇱", "Portugal": "🇵🇹",
  "RD Congo": "🇨🇩", "Senegal": "🇸🇳", "Suécia": "🇸🇪",
  "Suíça": "🇨🇭", "Tchéquia": "🇨🇿", "Tunísia": "🇹🇳",
  "Turquia": "🇹🇷", "Uruguai": "🇺🇾", "Uzbequistão": "🇺🇿", "Áustria": "🇦🇹",
};

export function flag(team: string | null): string {
  return team ? (FLAGS[team] ?? "🏳️") : "🏳️";
}

// URL de imagem da bandeira (flagcdn). O Windows não tem fonte de emoji-bandeira
// nativa (🇩🇪 vira "DE"), então renderizamos por imagem. O ISO-2 é derivado do
// próprio emoji em FLAGS (regional indicators U+1F1E6..U+1F1FF = A..Z).
export function flagUrl(team: string | null, height = 20): string | null {
  if (!team) return null;
  // subdivisões (Inglaterra/Escócia usam bandeira com tag, não 2 indicadores)
  if (team === "Inglaterra") return `https://flagcdn.com/h${height}/gb-eng.png`;
  if (team === "Escócia") return `https://flagcdn.com/h${height}/gb-sct.png`;
  const emoji = FLAGS[team];
  if (!emoji) return null;
  const letters = [...emoji]
    .map((c) => c.codePointAt(0)!)
    .filter((cp) => cp >= 0x1f1e6 && cp <= 0x1f1ff)
    .map((cp) => String.fromCharCode(cp - 0x1f1e6 + 97));
  return letters.length === 2 ? `https://flagcdn.com/h${height}/${letters.join("")}.png` : null;
}

export interface KitColors {
  main: string;
  border: string;
  text: string;
}

export const KIT_COLORS: Record<string, KitColors> = {
  "Alemanha": { main: "#f8fafc", border: "#111827", text: "#111827" },
  "Argentina": { main: "#75aadb", border: "#f8fafc", text: "#111827" },
  "Austrália": { main: "#facc15", border: "#15803d", text: "#15803d" },
  "Bélgica": { main: "#dc2626", border: "#111827", text: "#f8fafc" },
  "Brasil": { main: "#f4d21f", border: "#078930", text: "#1d4ed8" },
  "Cabo Verde": { main: "#2563eb", border: "#f8fafc", text: "#f8fafc" },
  "Canadá": { main: "#dc2626", border: "#f8fafc", text: "#f8fafc" },
  "Colômbia": { main: "#facc15", border: "#2563eb", text: "#111827" },
  "Coreia do Sul": { main: "#f8fafc", border: "#dc2626", text: "#111827" },
  "Costa do Marfim": { main: "#f97316", border: "#15803d", text: "#f8fafc" },
  "Côte d'Ivoire": { main: "#f97316", border: "#15803d", text: "#f8fafc" },
  "Croácia": { main: "#f8fafc", border: "#dc2626", text: "#111827" },
  "Egito": { main: "#dc2626", border: "#f8fafc", text: "#f8fafc" },
  "Equador": { main: "#facc15", border: "#2563eb", text: "#111827" },
  "Escócia": { main: "#2563eb", border: "#f8fafc", text: "#f8fafc" },
  "Espanha": { main: "#dc2626", border: "#facc15", text: "#f8fafc" },
  "Estados Unidos": { main: "#f8fafc", border: "#1d4ed8", text: "#1f2a44" },
  "França": { main: "#1d4ed8", border: "#f8fafc", text: "#f8fafc" },
  "Gana": { main: "#facc15", border: "#111827", text: "#111827" },
  "Inglaterra": { main: "#f8fafc", border: "#dc2626", text: "#1f2a44" },
  "Irã": { main: "#f8fafc", border: "#15803d", text: "#111827" },
  "Iraque": { main: "#15803d", border: "#f8fafc", text: "#f8fafc" },
  "Japão": { main: "#2563eb", border: "#f8fafc", text: "#f8fafc" },
  "Jordânia": { main: "#dc2626", border: "#f8fafc", text: "#f8fafc" },
  "Marrocos": { main: "#dc2626", border: "#15803d", text: "#f8fafc" },
  "México": { main: "#15803d", border: "#f8fafc", text: "#f8fafc" },
  "Noruega": { main: "#dc2626", border: "#1d4ed8", text: "#f8fafc" },
  "Nova Zelândia": { main: "#111827", border: "#f8fafc", text: "#f8fafc" },
  "Países Baixos": { main: "#f97316", border: "#111827", text: "#111827" },
  "Panamá": { main: "#dc2626", border: "#f8fafc", text: "#f8fafc" },
  "Paraguai": { main: "#dc2626", border: "#f8fafc", text: "#f8fafc" },
  "Portugal": { main: "#7f1d1d", border: "#15803d", text: "#f8fafc" },
  "RD Congo": { main: "#dc2626", border: "#facc15", text: "#f8fafc" },
  "Senegal": { main: "#15803d", border: "#f8fafc", text: "#f8fafc" },
  "Suécia": { main: "#2563eb", border: "#facc15", text: "#facc15" },
  "Suíça": { main: "#dc2626", border: "#f8fafc", text: "#f8fafc" },
  "Turquia": { main: "#dc2626", border: "#f8fafc", text: "#f8fafc" },
  "Tchéquia": { main: "#dc2626", border: "#f8fafc", text: "#f8fafc" },
  "Tunísia": { main: "#dc2626", border: "#f8fafc", text: "#f8fafc" },
  "Uruguai": { main: "#60a5fa", border: "#111827", text: "#111827" },
  "Uzbequistão": { main: "#2563eb", border: "#f8fafc", text: "#f8fafc" },
  "Áustria": { main: "#dc2626", border: "#f8fafc", text: "#f8fafc" },
  "Curaçao": { main: "#1d4ed8", border: "#f8fafc", text: "#f8fafc" },
  "Haiti": { main: "#1d4ed8", border: "#dc2626", text: "#f8fafc" },
  "Bósnia e Herzegovina": { main: "#1d4ed8", border: "#facc15", text: "#facc15" },
};

export function getKit(team: string | null): KitColors {
  return (team && KIT_COLORS[team]) ? KIT_COLORS[team] : { main: "#374151", border: "#6b7280", text: "#f8fafc" };
}

export function deriveTeams(matches: Match[]): TeamSummary[] {
  const map = new Map<string, TeamSummary>();

  for (const m of matches) {
    const entries = [
      { name: m.home_team, code: m.home_team_code },
      { name: m.away_team, code: m.away_team_code },
    ] as const;

    for (const { name, code } of entries) {
      if (!name) continue;
      if (!map.has(name)) {
        map.set(name, {
          name,
          code: code ?? null,
          group: m.group,
          games: [],
          played: 0,
          wins: 0,
          draws: 0,
          losses: 0,
          gf: 0,
          ga: 0,
          points: 0,
          confederation: CONFEDERATION[name] ?? "—",
        });
      }
      map.get(name)!.games.push(m);
    }
  }

  for (const t of map.values()) {
    for (const m of t.games) {
      if (m.status !== "finalizado") continue;
      const isHome = m.home_team === t.name;
      const gf = isHome ? (m.home_score ?? 0) : (m.away_score ?? 0);
      const ga = isHome ? (m.away_score ?? 0) : (m.home_score ?? 0);
      t.played++;
      t.gf += gf;
      t.ga += ga;
      if (gf > ga) { t.wins++; t.points += 3; }
      else if (gf === ga) { t.draws++; t.points++; }
      else { t.losses++; }
    }
  }

  return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
}

// Paleta de cores de seleção (compartilhada entre Seleções e Ranking Race).
// A cor é atribuída pela ORDEM em que a seleção foi escolhida.
export const SELECTION_COLORS = [
  "#58a6ff", "#f0883e", "#3fb950", "#f5c542", "#a78bfa", "#ec4899",
  "#22d3ee", "#fb7185", "#34d399", "#facc15", "#818cf8", "#fb923c",
  "#2dd4bf", "#e879f9", "#4ade80", "#60a5fa",
];

export function selectionColor(team: string, selectedTeams: string[]): string | null {
  const i = selectedTeams.indexOf(team);
  return i >= 0 ? SELECTION_COLORS[i % SELECTION_COLORS.length] : null;
}
