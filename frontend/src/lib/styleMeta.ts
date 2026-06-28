export const STYLE_COLOR: Record<string, string> = {
  "Pressão Alta": "#3fb950",
  Posse: "#58a6ff",
  Retranca: "#a371f7",
  "Jogo Direto": "#d29922",
  "Contra-ataque": "#f85149",
  "Bola Parada": "#f0883e",
  "Recorte misto": "#8b949e",
};

export const STYLE_LABEL: Record<string, string> = {
  "Pressão Alta": "Pressão/Recuperação",
  Posse: "Posse/Construção",
  Retranca: "Compacto/Reativo",
  "Jogo Direto": "Jogo Direto",
  "Contra-ataque": "Transição Rápida",
  "Bola Parada": "Bola Parada",
  "Recorte misto": "Recorte Misto",
};

export const STYLE_DESCRIPTION: Record<string, string> = {
  "Pressão Alta": "Tendência dominante em pressão alta, bloco alto, contrapressão e recuperação. Não significa pressionar alto o jogo inteiro.",
  Posse: "Tendência dominante em construção, progressão e presença no terço final. Indica controle com bola, não só posse por posse.",
  Retranca: "Tendência dominante em bloco baixo, pressão baixa e transição defensiva. É leitura de compactação e gestão de risco, não juízo de qualidade.",
  "Jogo Direto": "Tendência dominante em bola longa e ataque vertical para ganhar campo rápido.",
  "Contra-ataque": "Tendência dominante em contra-ataque e transição ofensiva. Acelera quando recupera a bola.",
  "Bola Parada": "Tendência dominante de criação ou perigo em escanteios, faltas e outras bolas paradas.",
  "Recorte misto": "Seleção de times com estilos diferentes; as métricas agregadas misturam mais de um arquétipo.",
};

export const STYLE_DEFINITION_ID: Record<string, string> = {
  "Pressão Alta": "estilo_pressao_alta",
  Posse: "estilo_posse",
  Retranca: "estilo_retranca",
  "Jogo Direto": "estilo_jogo_direto",
  "Contra-ataque": "estilo_contra_ataque",
  "Bola Parada": "estilo_bola_parada",
  "Recorte misto": "estilo_jogo",
};

export const STYLE_ORDER = [
  "Pressão Alta",
  "Posse",
  "Retranca",
  "Jogo Direto",
  "Contra-ataque",
  "Bola Parada",
] as const;

export function styleName(style?: string | null) {
  if (!style) return "Sem estilo definido";
  return STYLE_LABEL[style] ?? style;
}

export function styleDescription(style?: string | null) {
  if (!style) return "Sem estilo definido para este recorte.";
  return STYLE_DESCRIPTION[style] ?? "Rótulo gerado a partir da tendência dominante nas métricas de fase.";
}
