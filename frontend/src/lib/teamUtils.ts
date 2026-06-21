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
