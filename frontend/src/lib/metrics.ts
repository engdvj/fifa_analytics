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
      ["gols", "Gols marcados"],
      ["gols_contra", "Gols sofridos"],
    ],
  },
  {
    group: "Ataque · por jogo",
    items: [
      ["gols_pj", "Gols"],
      ["xg_pj", "xG (esperados)"],
      ["chutes_pj", "Finalizações"],
      ["chutes_no_alvo_pj", "No alvo"],
      ["precisao_chutes", "Precisão de chute %"],
      ["threat_pj", "Ameaça (Threat)"],
      ["escanteios_pj", "Escanteios"],
      ["impedimentos_pj", "Impedimentos"],
    ],
  },
  {
    group: "Defesa · por jogo",
    items: [
      ["gols_contra_pj", "Gols sofridos"],
      ["chutes_sofridos_pj", "Chutes sofridos"],
      ["chutes_sofridos_no_alvo_pj", "No alvo sofridos"],
      ["defesas_goleiro_pj", "Defesas do goleiro"],
      ["save_pct_goleiro", "Save % goleiro"],
      ["turnovers_forcados_pj", "Turnovers forçados"],
      ["pressoes_defensivas_pj", "Pressões defensivas"],
    ],
  },
  {
    group: "Controle · por jogo",
    items: [
      ["posse", "Posse %"],
      ["pitch_control", "Controle de campo %"],
      ["final_third_control", "Controle terço final %"],
      ["passes_pj", "Passes"],
      ["precisao_passes", "Precisão de passes %"],
      ["progressoes_bola_pj", "Progressões"],
      ["linebreaks_pj", "Linebreaks"],
      ["dribles_certos_pj", "Dribles"],
    ],
  },
  {
    group: "Disciplina · por jogo",
    items: [
      ["faltas_cometidas_pj", "Faltas"],
      ["amarelos_pj", "Amarelos"],
      ["vermelhos_pj", "Vermelhos"],
    ],
  },
  // Totais acumulados (existem no snapshot; espelham as métricas de contagem por
  // jogo). Taxas (%, razões) e gols pró/contra já estão acima e não se repetem.
  {
    group: "Ataque · total",
    items: [
      ["xg", "xG (esperados)"],
      ["chutes", "Finalizações"],
      ["chutes_no_alvo", "No alvo"],
      ["chutes_dentro_area", "Finalizações na área"],
      ["threat", "Ameaça (Threat)"],
      ["entradas_terco_final", "Entradas no terço final"],
      ["escanteios", "Escanteios"],
      ["impedimentos", "Impedimentos"],
    ],
  },
  {
    group: "Defesa · total",
    items: [
      ["xg_sofrido", "xG sofrido"],
      ["chutes_sofridos", "Chutes sofridos"],
      ["chutes_sofridos_no_alvo", "No alvo sofridos"],
      ["defesas_goleiro", "Defesas do goleiro"],
      ["turnovers_forcados", "Turnovers forçados"],
      ["pressoes_defensivas", "Pressões defensivas"],
    ],
  },
  {
    group: "Controle · total",
    items: [
      ["passes", "Passes"],
      ["progressoes_bola", "Progressões"],
      ["linebreaks", "Linebreaks"],
      ["dribles_certos", "Dribles"],
      ["trocas_lado_certas", "Trocas de lado"],
    ],
  },
  {
    group: "Disciplina · total",
    items: [
      ["faltas_cometidas", "Faltas"],
      ["amarelos", "Amarelos"],
      ["vermelhos", "Vermelhos"],
    ],
  },
];
