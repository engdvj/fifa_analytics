// Métricas oferecidas no seletor (chave no snapshot → rótulo). Scores primeiro,
// depois acumulados e algumas médias por jogo. score_geral é o default.
// Mantido em módulo neutro para evitar import circular entre os componentes
// do dashboard (RankingRaceScores ↔ TeamScoresCard ↔ SelecoesTab).
export const METRIC_OPTIONS: { group: string; items: [string, string][] }[] = [
  {
    group: "Scores",
    items: [
      ["score_geral", "Score Geral"],
      ["score_resultado", "Resultado"],
      ["score_ataque", "Ataque"],
      ["score_defesa", "Defesa"],
      ["score_eficiencia", "Eficiência"],
      ["score_controle", "Controle"],
      ["score_forca_relativa", "Força Relativa"],
      ["score_disciplina", "Disciplina"],
    ],
  },
  {
    group: "Campanha",
    items: [
      ["elo_rating", "Elo"],
      ["points", "Pontos"],
      ["aproveitamento", "Aproveitamento %"],
      ["saldo_gols", "Saldo de gols"],
      ["gols", "Gols"],
    ],
  },
  {
    group: "Por jogo",
    items: [
      ["gols_pj", "Gols / jogo"],
      ["xg_pj", "xG / jogo"],
      ["chutes_no_alvo_pj", "Chutes no alvo / jogo"],
      ["posse", "Posse"],
      ["pitch_control", "Controle de campo"],
    ],
  },
];
