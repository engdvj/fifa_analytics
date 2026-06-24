// Central de Definições — fonte única de verdade dos conceitos de ANÁLISE da
// plataforma. Consumida pela página /definicoes e pelo componente
// <DefinitionLink> (modal explicativo acionável de qualquer lugar).
//
// Cada termo: id estável, categoria, definição curta (1 linha), explicação
// completa (leiga), exemplo real do torneio e relacionados. Quando o conceito é
// CALCULADO, traz também a fórmula em palavras.
// REGRAS: todo termo tem `example`; todo termo calculado tem `formula`.

export type CategoryId =
  | "selecao"
  | "avancadas"
  | "conceitos"
  | "estilos"
  | "jogadores";

export type Term = {
  id: string;
  term: string;
  category: CategoryId;
  short: string;
  full: string;
  formula?: string;
  example: string;
  related?: string[];
  aka?: string[]; // sinônimos/termos de busca
};

export type Category = {
  id: CategoryId;
  label: string;
  icon: string;
  blurb: string;
  accent: string;
};

export const CATEGORIES: Category[] = [
  { id: "selecao", label: "Métricas de Seleção", icon: "🏆", accent: "#58a6ff",
    blurb: "O score geral e seus 6 componentes — como avaliamos cada seleção de 0 a 100." },
  { id: "avancadas", label: "Estatísticas Avançadas", icon: "📊", accent: "#3fb950",
    blurb: "Os números da FIFA (xG, threat, controle…) que alimentam os scores." },
  { id: "conceitos", label: "Conceitos Estatísticos", icon: "🧮", accent: "#bc8cff",
    blurb: "Como os números viram nota: Elo, z-score, confiança por amostra, snapshots." },
  { id: "estilos", label: "Estilos de Jogo", icon: "🎨", accent: "#f0883e",
    blurb: "Os 6 arquétipos que descrevem COMO uma seleção joga (descritivo, não nota)." },
  { id: "jogadores", label: "Métricas de Jogador", icon: "👤", accent: "#39c5cf",
    blurb: "Como avaliamos jogadores via o Power Ranking oficial da FIFA." },
];

export const TERMS: Term[] = [
  // ─────────────────────────── MÉTRICAS DE SELEÇÃO ───────────────────────────
  {
    id: "score_geral", term: "Score Geral", category: "selecao",
    short: "Nota de 0 a 100 que resume a força de uma seleção.",
    full: "É a nota principal de cada seleção, de 0 a 100. Combina seis componentes com pesos fixos: Resultado (30%), Ataque (20%), Defesa (20%), Eficiência (10%), Controle (10%) e Força Relativa (10%). Quanto maior, melhor o desempenho consolidado até aquele momento do torneio.",
    formula: "30% Resultado + 20% Ataque + 20% Defesa + 10% Eficiência + 10% Controle + 10% Força Relativa",
    example: "Alemanha ~74 lidera; o fundo da tabela fica em ~25. A nota de uma seleção só muda quando ELA joga — não quando as outras jogam.",
    related: ["score_resultado", "score_ataque", "score_defesa", "score_eficiencia", "score_controle", "score_forca_relativa", "referencia_fixa"],
    aka: ["ranking", "nota geral"],
  },
  {
    id: "score_resultado", term: "Resultado", category: "selecao",
    short: "Quanto a seleção venceu — ponderado pela força do adversário.",
    full: "Mede o que aconteceu no placar. É o maior peso do score geral (30%). Combina o aproveitamento ponderado pela força do adversário (70%) com o saldo de gols por jogo (30%). Vencer um time forte vale mais que vencer um fraco; golear vale mais que vencer apertado.",
    formula: "70% aproveitamento ponderado pelo adversário + 30% saldo de gols por jogo",
    example: "Um 2-0 e um 4-2 têm o MESMO resultado (venceram por +2). A diferença entre eles (ataque x defesa) aparece nas outras métricas, não aqui.",
    related: ["aproveitamento_ponderado", "saldo_gols", "score_geral"],
  },
  {
    id: "score_ataque", term: "Ataque", category: "selecao",
    short: "Quanto perigo a seleção cria — não só quantos gols faz.",
    full: "Mede a qualidade ofensiva (20% do geral). Combina xG por jogo (30%), gols por jogo (30%), chutes dentro da área (10%), chutes no alvo (10%), threat/ameaça (10%) e entradas no terço final (10%). Premia quem CRIA perigo de verdade (entra na área, penetra), não só quem chuta de longe.",
    formula: "30% xG + 30% gols + 10% chutes na área + 10% chutes no alvo + 10% threat + 10% entradas no terço final",
    example: "A Argentina venceu de 3-0 mas com pouca penetração (contra-ataque), então seu ataque 'real' é mediano — o 3-0 dela brilha mais no Resultado e na Eficiência.",
    related: ["xg", "threat", "chutes_dentro_area", "entradas_terco_final", "score_eficiencia"],
  },
  {
    id: "score_defesa", term: "Defesa", category: "selecao",
    short: "Quão pouco perigo a seleção permite — não só quantos gols sofre.",
    full: "Mede a solidez defensiva (20% do geral). Combina gols sofridos por jogo (30%), xG sofrido (30%), chutes sofridos no alvo (10%), defesas do goleiro / save% (15%) e turnovers forçados (15%). O xG sofrido é a chave: separa quem DEFENDEU de quem teve sorte / foi salvo pelo goleiro.",
    formula: "30% gols sofridos + 30% xG sofrido + 10% chutes sofridos no alvo + 15% save% + 15% turnovers forçados",
    example: "Cabo Verde fez 0-0 com a Espanha mas permitiu 2,26 de xG (foi bombardeada). O xG sofrido alto a derruba na Defesa, mesmo sem tomar gol — porque o gol zero foi do goleiro, não da defesa.",
    related: ["xg_sofrido", "save_pct", "turnovers_forcados", "clean_sheet"],
  },
  {
    id: "score_eficiencia", term: "Eficiência", category: "selecao",
    short: "Quão clínica a seleção é — converte as chances que cria?",
    full: "Mede o aproveitamento das oportunidades (10% do geral). Combina gols por xG (45%), conversão de chutes (30%), % de progressões certas (10%) e % de distribuição sob pressão (15%). É 'fazer mais com menos'. Tem um amortecedor: quem perde feio não é premiado por eficiência.",
    formula: "45% gols/xG + 30% conversão de chutes + 10% progressões certas + 15% distribuição sob pressão",
    example: "O Japão converteu 3,5× o xG dele — finalização clínica → lidera a Eficiência mesmo criando pouco.",
    related: ["gols_por_xg", "conversao_chutes", "score_geral"],
  },
  {
    id: "score_controle", term: "Controle", category: "selecao",
    short: "Quanto a seleção domina a bola e o território.",
    full: "Mede o domínio territorial (10% do geral). Combina controle no terço final (40%), posse (20%), precisão de passes (20%) e trocas de lado certas (20%). Prioriza o controle ONDE importa (perto do gol adversário) e a circulação (espalhar o jogo), não só ter a bola.",
    formula: "40% controle no terço final + 20% posse + 20% precisão de passes + 20% trocas de lado",
    example: "Controlar a bola é estilo, não garantia de vitória: um time de contra-ataque pontua baixo aqui, mas pode vencer mesmo assim.",
    related: ["final_third_control", "posse", "trocas_lado", "precisao_passes"],
  },
  {
    id: "score_forca_relativa", term: "Força Relativa", category: "selecao",
    short: "A força da seleção segundo o Elo — contra QUEM ela jogou.",
    full: "Mede a força relativa via Elo (10% do geral). É a única métrica recursiva: bater quem bateu os fortes te eleva (força de tabela). As outras métricas são absolutas (comparam ao campo); esta olha a trajetória 'contra quem, ao longo do tempo'.",
    formula: "Desvio do Elo em relação a 1500, normalizado para 0–100",
    example: "Times de baixa posse que VENCEM (ex.: contra-ataque) sobem aqui — o Elo agora valoriza o que você faz, não quanto tempo segura a bola.",
    related: ["elo", "performance_index"],
  },
  {
    id: "score_disciplina", term: "Disciplina", category: "selecao",
    short: "Faltas e cartões — quanto a seleção é disciplinada. (Não entra no geral.)",
    full: "Métrica DESCRITIVA, fora do score geral. Combina faltas cometidas (20%), cartões amarelos (30%) e vermelhos (50%) — menos é melhor. Cartões pesam mais que faltas (falta tática é jogo normal); o vermelho dói mais (deixa o time com 10).",
    formula: "20% faltas + 30% amarelos + 50% vermelhos (menos = nota maior)",
    example: "Uma seleção que comete muitas faltas e levou um vermelho cai aqui; um time limpo, que quase não falta, fica no topo da disciplina.",
    related: ["score_geral"],
  },

  // ─────────────────────────── ESTATÍSTICAS AVANÇADAS ───────────────────────────
  {
    id: "xg", term: "xG (Expected Goals)", category: "avancadas",
    short: "Gols esperados: a qualidade das chances que a seleção criou.",
    full: "xG = 'gols esperados'. Cada finalização recebe uma probabilidade de virar gol (com base em posição, ângulo, tipo de jogada). Somando, dá quantos gols um time 'deveria' ter feito pela qualidade das chances. Mede CRIAÇÃO de perigo, independente de a bola entrar ou não.",
    formula: "soma da probabilidade de gol de cada finalização do jogo",
    example: "xG 2,26 num jogo = o time criou chances que valeriam ~2 gols. Se fez 0, foi ineficiente ou azarado; se fez 4, foi clínico.",
    related: ["xg_sofrido", "threat", "gols_por_xg", "score_ataque"],
    aka: ["expected goals", "gols esperados"],
  },
  {
    id: "xg_sofrido", term: "xG Sofrido", category: "avancadas",
    short: "O xG do adversário contra você — quanto perigo você PERMITIU.",
    full: "É o xG de ataque do adversário no jogo, visto do seu lado: quanto perigo a sua defesa deixou o outro criar. É a melhor medida de 'defender de verdade', porque isola a estrutura defensiva do goleiro e da sorte.",
    formula: "xG de ataque do adversário no mesmo jogo",
    example: "Espanha 0,12 de xG sofrido por jogo (quase não deixa criar nada) = melhor defesa. Catar 3,52 (escancarada). O gol sofrido pode mentir; o xG sofrido não.",
    related: ["xg", "score_defesa", "save_pct"],
  },
  {
    id: "threat", term: "Threat (Ameaça)", category: "avancadas",
    short: "Medida holística de perigo ofensivo — o quão ameaçador o time foi.",
    full: "O 'threat' resume o perigo gerado por uma equipe a partir de onde e como ela teve a bola (sequências e qualidade de posse no terço final). É mais abrangente que só contar chutes — capta a ameaça mesmo antes da finalização. Vem pronto do FIFA Data Hub.",
    example: "Um time que vive martelando no campo de ataque, com sequências perigosas, tem threat alto — mesmo que ainda não tenha transformado isso em muitos chutes.",
    related: ["xg", "score_ataque", "final_third_control"],
    aka: ["ameaca", "perigo"],
  },
  {
    id: "pitch_control", term: "Controle de Campo (Pitch Control)", category: "avancadas",
    short: "Quanto do espaço do campo o time domina taticamente.",
    full: "Diferente de posse de bola: mede quanto do território a equipe controla taticamente (espaço dominado pelos jogadores), não só quem está com a bola no pé. Modelo do FIFA Data Hub.",
    example: "A Espanha empurra o adversário pra trás e ocupa o campo todo (controle alto); um time de retranca cede o campo e fica com controle baixo.",
    related: ["posse", "final_third_control", "score_controle"],
  },
  {
    id: "final_third_control", term: "Controle no Terço Final", category: "avancadas",
    short: "Domínio territorial no terço de ataque — onde o perigo mora.",
    full: "Controle de campo restrito ao terço final (perto do gol adversário). É o domínio que mais importa: controlar a bola no seu próprio campo não cria perigo; controlar perto do gol do adversário, sim. É o componente de maior peso no Controle.",
    example: "Dominar a bola no seu campo não vale nada aqui; dominar perto da área adversária (como Espanha 84 e Turquia 85) é o que conta.",
    related: ["pitch_control", "score_controle", "entradas_terco_final"],
  },
  {
    id: "posse", term: "Posse de Bola", category: "avancadas",
    short: "Percentual do tempo com a bola.",
    full: "A clássica posse de bola, em %. Importante: posse alta NÃO significa jogar melhor — os dados mostram que os times que mais pressionam e correm atrás da bola costumam ser os mais sufocados.",
    formula: "tempo com a bola ÷ tempo total de bola rolando",
    example: "Bélgica e Canadá têm baixa posse e defesas excelentes (dominam pela organização). Times fracos que apanham acabam com posse 'forçada' correndo atrás.",
    related: ["pitch_control", "score_controle"],
  },
  {
    id: "progressoes_bola", term: "Progressões de Bola", category: "avancadas",
    short: "Passes que levam a bola para frente, em direção ao gol.",
    full: "Conta os avanços bem-sucedidos da bola rumo ao gol adversário. Na Eficiência usamos a % de progressões CERTAS (acertou ÷ tentou), não a contagem bruta — premia avançar bem, não só avançar muito.",
    formula: "% certas = progressões certas ÷ progressões tentadas",
    example: "Um time que sai jogando e leva a bola até o ataque com passes faz muitas progressões; o time do 'chutão' faz poucas, mesmo que avance no campo.",
    related: ["score_eficiencia", "linebreaks"],
  },
  {
    id: "turnovers_forcados", term: "Turnovers Forçados", category: "avancadas",
    short: "Quantas vezes o time forçou o adversário a perder a bola.",
    full: "Recuperações de bola provocadas (desarmes, interceptações, pressão que rouba). É o RESULTADO útil de pressionar — entra na nota de Defesa como qualidade defensiva proativa.",
    example: "Uma seleção que rouba a bola ~45×/jogo pressionando força muitos turnovers; isso conta a favor dela na Defesa como recuperação proativa.",
    related: ["pressao_defensiva", "score_defesa"],
  },
  {
    id: "pressao_defensiva", term: "Pressão Defensiva", category: "avancadas",
    short: "Número de ações de pressão sobre quem está com a bola.",
    full: "Conta quantas vezes o time aperta o adversário com a bola. Cuidado: é métrica de ESTILO/intensidade, NÃO de qualidade. Quem pressiona muito costuma permitir MAIS perigo — porque pressiona justamente por estar sendo dominado e não ter a bola. Por isso NÃO entra na nota de Defesa.",
    example: "Arábia Saudita pressiona 365×/jogo mas sofre 2,35 de xG. Bélgica pressiona 121× e sofre 0,64 — não precisa correr atrás porque domina.",
    related: ["turnovers_forcados", "score_defesa"],
  },
  {
    id: "distribuicao_sob_pressao", term: "Distribuição Sob Pressão", category: "avancadas",
    short: "Acerto de passes quando o adversário está pressionando.",
    full: "% de passes certos enquanto sob pressão. Mede sangue-frio com a bola num momento difícil. Entra na Eficiência como 'uso eficiente da bola'.",
    formula: "passes certos sob pressão ÷ passes tentados sob pressão",
    example: "Sair jogando de trás com o adversário em cima, sem entregar a bola, é distribuição sob pressão alta — coragem técnica num momento difícil.",
    related: ["score_eficiencia", "precisao_passes"],
  },
  {
    id: "trocas_lado", term: "Trocas de Lado", category: "avancadas",
    short: "Inversões de jogo certas — espalhar a bola de um lado a outro.",
    full: "Passes longos que mudam o lado do ataque. Mede circulação/paciência e é POUCO correlacionado com posse, por isso é um eixo distinto no Controle: separa quem espalha o jogo de quem joga direto.",
    example: "Egito circula como ninguém (15 trocas/jogo); Canadá quase não troca de lado (2,5) — joga mais direto.",
    related: ["score_controle"],
  },
  {
    id: "linebreaks", term: "Linebreaks (Quebras de Linha)", category: "avancadas",
    short: "Passes que furam uma linha de marcação do adversário.",
    full: "Passes que ultrapassam com sucesso uma linha de pressão/marcação adversária, progredindo o jogo de forma perigosa.",
    example: "Um passe que corta a linha de quatro defensores e deixa o atacante de frente pro gol é um linebreak — vale mais que dez passes de lado.",
    related: ["progressoes_bola"],
  },
  {
    id: "chutes_dentro_area", term: "Chutes Dentro da Área", category: "avancadas",
    short: "Finalizações de posição perigosa (dentro da grande área).",
    full: "Chutes tomados de dentro da área — posições de maior probabilidade de gol. Entra no Ataque como 'volume de chance perigosa', complementando o xG: não só a qualidade, mas o volume de boas posições de finalização.",
    example: "Dez chutes de dentro da área valem muito mais que dez chutões de fora — são posições de gol de verdade.",
    related: ["score_ataque", "chutes_no_alvo", "xg"],
  },
  {
    id: "chutes_no_alvo", term: "Chutes no Alvo", category: "avancadas",
    short: "Finalizações na direção do gol.",
    full: "Chutes que vão no alvo (exigem defesa ou entram). Mede precisão/volume de finalização. Aparece no Ataque (seu lado) e na Defesa (chutes sofridos no alvo = chances no gol que você permitiu).",
    example: "Um time chuta 20× e acerta só 3 no alvo; outro chuta 8× e acerta 6 — o segundo finaliza com muito mais pontaria.",
    related: ["chutes_dentro_area", "save_pct"],
  },
  {
    id: "entradas_terco_final", term: "Entradas no Terço Final", category: "avancadas",
    short: "Quantas vezes o time leva a bola à zona perigosa de ataque.",
    full: "Recepções bem-sucedidas no terço final — chegar com consistência à zona de perigo. Mede penetração. Entra no Ataque.",
    formula: "soma das entradas pelos corredores central + esquerdo + direito",
    example: "Uma seleção que chega ao terço final 40×/jogo penetra bastante; um time de contra-ataque chega menos vezes, mas escolhe bem a hora.",
    related: ["score_ataque", "final_third_control"],
  },
  {
    id: "save_pct", term: "Save% (Defesas do Goleiro)", category: "avancadas",
    short: "Percentual de chutes no alvo que o goleiro defendeu.",
    full: "Isola a contribuição do GOLEIRO. Entra na Defesa (15%): um clean sheet com save% altíssimo foi mérito do goleiro, não necessariamente da defesa.",
    formula: "defesas ÷ chutes no alvo sofridos",
    example: "Cabo Verde fez 7 defesas e 100% de save% contra a Espanha — o gol zero foi um show do goleiro, não da linha defensiva.",
    related: ["score_defesa", "xg_sofrido", "clean_sheet"],
  },
  {
    id: "clean_sheet", term: "Clean Sheet (Jogo sem Sofrer Gol)", category: "avancadas",
    short: "Não tomar gol numa partida.",
    full: "Jogo em que a seleção não sofreu gols. É um bom sinal, mas pode 'mentir': um clean sheet pode vir de uma defesa sólida OU de sorte + goleiro. Por isso cruzamos com o xG sofrido para saber qual foi o caso.",
    example: "Espanha 0-0 Cabo Verde: clean sheet das duas, mas a Cabo Verde permitiu 2,26 de xG — o gol zero dela foi sorte + goleiro, não defesa sólida.",
    related: ["score_defesa", "xg_sofrido", "save_pct"],
  },
  {
    id: "saldo_gols", term: "Saldo de Gols", category: "avancadas",
    short: "Gols marcados menos gols sofridos.",
    full: "A diferença acumulada entre gols feitos e sofridos. Entra no Resultado (margem da vitória). Note: '+2' não diz se foi 2-0 ou 4-2 — essa diferença vive no Ataque e na Defesa.",
    formula: "gols marcados − gols sofridos",
    example: "Um 4-2 e um 2-0 têm o mesmo saldo (+2); o Resultado os trata igual, mas Ataque e Defesa contam a diferença entre eles.",
    related: ["score_resultado"],
  },
  {
    id: "conversao_chutes", term: "Conversão de Chutes", category: "avancadas",
    short: "Gols por chute — quão clínico no tiro.",
    full: "Mede aproveitamento de finalização. Entra na Eficiência junto com gols/xG.",
    formula: "gols ÷ chutes",
    example: "Fazer 3 gols em 8 chutes (alta conversão) é muito mais clínico que fazer 3 gols em 25 chutes.",
    related: ["score_eficiencia", "gols_por_xg"],
  },
  {
    id: "gols_por_xg", term: "Gols por xG", category: "avancadas",
    short: "Fez mais ou menos gols do que as chances sugeriam.",
    full: "Acima de 1 = finalizou acima do esperado (clínico ou sortudo); abaixo de 1 = desperdiçou. É o coração da Eficiência (45%).",
    formula: "gols ÷ xG",
    example: "Gols/xG 1,5 = marcou 50% acima do que o xG previa. Japão chegou a 3,5× — finalização absurdamente clínica.",
    related: ["xg", "score_eficiencia", "conversao_chutes"],
  },
  {
    id: "precisao_passes", term: "Precisão de Passes", category: "avancadas",
    short: "Percentual de passes certos.",
    full: "Acerto de passe da equipe. Mede a qualidade da circulação; entra no Controle (20%).",
    formula: "passes certos ÷ passes tentados",
    example: "405 passes certos em 472 tentados = 86% de precisão — circulação limpa.",
    related: ["score_controle", "distribuicao_sob_pressao"],
  },
  {
    id: "aproveitamento", term: "Aproveitamento (%)", category: "avancadas",
    short: "Percentual de pontos conquistados.",
    full: "Aproveitamento simples, sem ajuste de adversário. A versão usada no Resultado é o aproveitamento PONDERADO (que pesa pela força de quem você enfrentou).",
    formula: "pontos ÷ (jogos × 3)",
    example: "2 vitórias em 3 jogos = 6 de 9 pontos = 67% de aproveitamento.",
    related: ["aproveitamento_ponderado", "pontos"],
  },
  {
    id: "pontos", term: "Pontos", category: "avancadas",
    short: "Pontos da campanha: 3 por vitória, 1 por empate.",
    full: "Pontuação bruta acumulada no torneio, no critério clássico (vitória 3, empate 1, derrota 0).",
    formula: "3 × vitórias + 1 × empates",
    example: "2 vitórias e 1 empate = 7 pontos.",
    related: ["aproveitamento", "score_resultado"],
  },
  {
    id: "aproveitamento_ponderado", term: "Aproveitamento Ponderado", category: "avancadas",
    short: "Aproveitamento de pontos pesado pela força do adversário.",
    full: "O aproveitamento ajustado pelo Elo do adversário NO momento do jogo. Vencer um forte vale mais que vencer um fraco. É o principal componente do Resultado (70%).",
    formula: "cada resultado pesa por 1 + (Elo do adversário − 1500) / 400, entre 0,5× e 2×",
    example: "No 1º jogo todo adversário vale 1500 (ninguém jogou ainda), então todo vencedor empata em aproveitamento — só o saldo desempata.",
    related: ["score_resultado", "elo", "aproveitamento"],
  },
  {
    id: "escanteios", term: "Escanteios", category: "avancadas",
    short: "Escanteios conquistados a favor.",
    full: "Número de escanteios forçados — indício de pressão ofensiva e arma de bola parada.",
    example: "Um time que pressiona muito e cruza bastante tende a forçar mais escanteios.",
    related: ["estilo_bola_parada"],
  },
  {
    id: "impedimentos", term: "Impedimentos", category: "avancadas",
    short: "Vezes que o time foi flagrado em impedimento.",
    full: "Quantos impedimentos a equipe cometeu. Muitos podem indicar um ataque que arrisca a linha defensiva — ou desentrosamento na hora do passe.",
    example: "Um ataque que tenta muito as costas da defesa cai mais em impedimento.",
    related: ["score_ataque"],
  },
  {
    id: "sprints", term: "Sprints", category: "avancadas",
    short: "Número de corridas em velocidade máxima.",
    full: "Arrancadas em altíssima intensidade (perto da velocidade máxima do jogador). Indício do esforço físico e do estilo — pressão alta e contra-ataque exigem muitos sprints.",
    example: "Times de pressão alta e de contra-ataque costumam acumular muitos sprints por jogo.",
    related: ["pressao_defensiva", "estilo_contra_ataque"],
  },
  {
    id: "distancia_percorrida", term: "Distância Percorrida", category: "avancadas",
    short: "Distância total corrida pela equipe no jogo.",
    full: "Soma da distância percorrida por todos os jogadores. É volume físico — e correr mais NÃO significa jogar melhor (às vezes é correr atrás da bola).",
    example: "Um time dominado pode correr muito perseguindo a bola; um time que controla o jogo corre menos e com mais propósito.",
    related: ["posse", "sprints"],
  },

  // ─────────────────────────── CONCEITOS ESTATÍSTICOS ───────────────────────────
  {
    id: "elo", term: "Elo", category: "conceitos",
    short: "Rating de força que sobe/desce a cada jogo, conforme resultado e adversário.",
    full: "Sistema de rating (como no xadrez). Todo time começa em 1500. A cada jogo, você ganha/perde pontos conforme venceu, por quanto, e contra quem. Bater um favorito rende muito; perder pra um fraco custa caro. Alimenta a Força Relativa e o aproveitamento ponderado.",
    formula: "novo Elo = Elo + K × margem × (resultado real − resultado esperado), com K=40 e margem até 3×",
    example: "Um Elo de 1700 indica uma seleção bem acima da média; 1300, bem abaixo. Bater a Alemanha rende muito mais Elo que bater o Haiti.",
    related: ["score_forca_relativa", "performance_index", "aproveitamento_ponderado"],
  },
  {
    id: "performance_index", term: "Índice de Desempenho (Elo)", category: "conceitos",
    short: "Quão convincente foi a atuação — afina quanto o Elo se move.",
    full: "Dentro da faixa do resultado (vitória/empate/derrota), este índice decide o quão convincente foi a atuação, ajustando o movimento do Elo. É um blend de perigo e resultado, com a posse como coadjuvante.",
    formula: "gols×3 + xG×2 + chutes no alvo×0,5 + threat×0,05 + posse×0,05",
    example: "Vencer 1-0 sofrendo pressão move menos o Elo que vencer 1-0 dominando e criando muito — o índice de desempenho capta essa diferença.",
    related: ["elo", "score_forca_relativa"],
  },
  {
    id: "z_score", term: "Normalização (z-score → 0–100)", category: "conceitos",
    short: "Como um número cru vira nota de 0 a 100 comparando com o campo.",
    full: "Cada métrica bruta é convertida em nota 0–100 medindo quantos desvios-padrão ela está acima/abaixo da média do campo. A média vira ~50; 1 desvio-padrão = 25 pontos. Assim notas de métricas diferentes (gols, xG, posse…) ficam na mesma escala e somáveis.",
    formula: "nota = 50 + (valor − média) / desvio-padrão × 25, limitado a 0–100",
    example: "Um xG de 2,0 quando a média do torneio é 1,2 vira uma nota alta; um xG de 0,5 vira nota baixa — tudo na mesma régua 0–100.",
    related: ["referencia_fixa", "score_geral"],
    aka: ["zscore", "normalizacao", "escala"],
  },
  {
    id: "referencia_fixa", term: "Referência Fixa", category: "conceitos",
    short: "Por que a nota de uma seleção só muda quando ELA joga.",
    full: "A média e o desvio usados na normalização são calculados UMA vez sobre todos os jogos e reusados em cada snapshot. Resultado intencional: o score de uma seleção só muda quando ela própria entra em campo — nunca porque outra seleção jogou. Dá estabilidade à linha do tempo.",
    example: "Se a Argentina não jogou nesta rodada, a nota dela fica idêntica à do snapshot anterior — só muda quando ela voltar a campo.",
    related: ["z_score", "snapshot", "score_geral"],
  },
  {
    id: "confianca_amostra", term: "Confiança por Amostra", category: "conceitos",
    short: "Com poucos jogos, a nota é puxada para o meio (50) por cautela.",
    full: "Com poucos jogos, não dá pra confiar plenamente nos números. A confiança cresce: 1 jogo = 0,5, 2 jogos = 0,8, 3+ jogos = 1,0. Abaixo de 1, a nota é parcialmente puxada para 50 (neutro). Por isso, na 1ª rodada, times elite e fracos parecem mais próximos do que ficarão depois.",
    formula: "nota final = 50 × (1 − confiança) + nota × confiança",
    example: "No 1º jogo (confiança 0,5), uma atuação nota 80 aparece como ~65 — o sistema ainda não 'acredita' totalmente.",
    related: ["z_score", "nivel_evidencia"],
  },
  {
    id: "nivel_evidencia", term: "Nível de Evidência", category: "conceitos",
    short: "Rótulo da confiança: baixa, média ou alta.",
    full: "Tradução em palavras da confiança por amostra. Ajuda a ler quanto peso dar à nota naquele momento do torneio.",
    formula: "baixa (< 0,5) · média (0,5 a 0,75) · alta (≥ 0,75)",
    example: "Com 1 jogo, a evidência é 'baixa' — leia a nota com cautela; com 3+ jogos vira 'alta' e a nota é confiável.",
    related: ["confianca_amostra"],
  },
  {
    id: "snapshot", term: "Snapshot", category: "conceitos",
    short: "Uma 'foto' das notas após cada jogo finalizado do torneio.",
    full: "A cada jogo finalizado, recalculamos as notas de todas as seleções considerando tudo até ali — isso é um snapshot. A linha do tempo de snapshots permite ver a evolução (a 'corrida de barras' do dashboard) jogo a jogo.",
    example: "Snapshot 24 = como estavam as notas após o 24º jogo do torneio. Arrastar o slider do dashboard percorre os snapshots.",
    related: ["referencia_fixa", "score_geral"],
  },

  // ─────────────────────────── ESTILOS DE JOGO ───────────────────────────
  {
    id: "estilo_jogo", term: "Estilo de Jogo", category: "estilos",
    short: "Rótulo que descreve COMO a seleção joga (não é nota de qualidade).",
    full: "Classificação descritiva, derivada das 16 métricas de 'fase' da FIFA. Cada seleção recebe uma pontuação em 6 arquétipos e leva o rótulo do dominante. Não diz se é boa ou ruim — diz o jeito de jogar.",
    formula: "rótulo = o arquétipo com maior nota (z-score das fases vs. o campo)",
    example: "A Argentina recebe o rótulo 'Retranca' (defende fundo) e a Espanha 'Posse' — duas formas diferentes de jogar, sem dizer qual é melhor.",
    related: ["estilo_posse", "estilo_pressao_alta", "estilo_contra_ataque", "estilo_retranca", "estilo_jogo_direto", "estilo_bola_parada"],
  },
  {
    id: "estilo_posse", term: "Estilo: Posse", category: "estilos",
    short: "Domina a bola e constrói de trás, com paciência.",
    full: "Time que controla o jogo com a bola: muita construção (livre e sob pressão), progressão e presença no terço final.",
    formula: "construção livre + construção pressionada + progressão + terço final",
    example: "França, Espanha e México — seleções que mandam no jogo tendo a bola.",
    related: ["estilo_jogo", "posse", "score_controle"],
  },
  {
    id: "estilo_pressao_alta", term: "Estilo: Pressão Alta", category: "estilos",
    short: "Joga adiantado e pressiona a saída do adversário.",
    full: "Time agressivo sem a bola: pressão alta, bloco alto, contra-pressão e recuperação rápida. Quer roubar a bola perto do gol adversário.",
    formula: "pressão alta + bloco alto + contra-pressão + recuperação",
    example: "Alemanha, Estados Unidos e Suíça — sufocam a saída de bola do adversário lá na frente.",
    related: ["estilo_jogo", "pressao_defensiva"],
  },
  {
    id: "estilo_contra_ataque", term: "Estilo: Contra-ataque", category: "estilos",
    short: "Recua, rouba e ataca rápido na transição.",
    full: "Time que espera o adversário, recupera a bola e ataca veloz no espaço.",
    formula: "contra-ataque + transição ofensiva",
    example: "Suécia e Costa do Marfim — cedem a bola e explodem na velocidade quando recuperam.",
    related: ["estilo_jogo", "estilo_retranca"],
  },
  {
    id: "estilo_retranca", term: "Estilo: Retranca", category: "estilos",
    short: "Defende fundo, com linhas baixas, absorvendo a pressão.",
    full: "Time defensivo e compacto: bloco baixo, pressão baixa e foco na transição defensiva. Cede a bola e se fecha.",
    formula: "bloco baixo + pressão baixa + transição defensiva",
    example: "Argentina, Japão e Marrocos — se fecham atrás e apostam na solidez defensiva.",
    related: ["estilo_jogo", "estilo_contra_ataque", "score_defesa"],
  },
  {
    id: "estilo_jogo_direto", term: "Estilo: Jogo Direto", category: "estilos",
    short: "Abre mão da construção e busca a bola longa/vertical.",
    full: "Time que evita construir no chão e progride com bola longa, de forma vertical e direta.",
    formula: "bola longa",
    example: "Gana, Irã e Paraguai — pulam o meio-campo com lançamentos, jogo de primeira.",
    related: ["estilo_jogo"],
  },
  {
    id: "estilo_bola_parada", term: "Estilo: Bola Parada", category: "estilos",
    short: "Tem na bola parada (escanteios/faltas) uma arma central.",
    full: "Time que se destaca e se apoia fortemente em situações de bola parada — escanteios, faltas e pênaltis.",
    formula: "fase de bola parada (escanteios + faltas + pênaltis)",
    example: "Canadá e Austrália — perigosos nas jogadas ensaiadas de escanteio e falta.",
    related: ["estilo_jogo", "escanteios"],
  },

  // ─────────────────────────── MÉTRICAS DE JOGADOR ───────────────────────────
  {
    id: "player_score_geral", term: "Score Geral do Jogador", category: "jogadores",
    short: "Nota 0–100 do jogador, derivada do Power Ranking oficial da FIFA.",
    full: "Nota de jogador de 0 a 100. Mistura os três componentes do Power Ranking da FIFA com pesos por função (linha vs. goleiro).",
    formula: "linha: 40% ataque + 35% criatividade + 25% defesa · goleiro: 60% defesa + 25% criatividade + 15% ataque",
    example: "Um centroavante artilheiro tem a nota puxada pelo ataque; um zagueiro, pela defesa — cada posição brilha no que faz.",
    related: ["powerranking", "attacking_score", "defensive_score", "creativity_score"],
  },
  {
    id: "powerranking", term: "Power Ranking (FIFA)", category: "jogadores",
    short: "Avaliação oficial da FIFA por jogador, por jogo.",
    full: "Pontuação que a própria FIFA calcula para cada jogador, dividida em três componentes (ataque, defesa, criatividade). É a base do score geral de jogador na plataforma.",
    example: "É a nota que a própria FIFA dá a cada jogador na partida — a gente só a reescala para 0–100 e usa como score do jogador.",
    related: ["player_score_geral", "attacking_score", "defensive_score", "creativity_score"],
  },
  {
    id: "attacking_score", term: "Ataque (Jogador)", category: "jogadores",
    short: "Componente ofensivo do Power Ranking do jogador.",
    full: "Quanto o jogador contribui ofensivamente (finalização, presença, participação no ataque). Para goleiros, representa a qualidade na saída de bola.",
    example: "Um atacante que finaliza muito e participa das jogadas de gol tem attacking alto.",
    related: ["powerranking", "player_score_geral"],
  },
  {
    id: "defensive_score", term: "Defesa (Jogador)", category: "jogadores",
    short: "Componente defensivo do Power Ranking do jogador.",
    full: "Quanto o jogador contribui defensivamente (desarmes, interceptações, cobertura). Para goleiros, é a defesa do gol (peso maior).",
    example: "Um zagueiro que desarma e intercepta bastante tem defensive alto; para o goleiro, é o componente que mais pesa.",
    related: ["powerranking", "player_score_geral"],
  },
  {
    id: "creativity_score", term: "Criatividade (Jogador)", category: "jogadores",
    short: "Componente de criação do Power Ranking do jogador.",
    full: "Quanto o jogador cria para os companheiros (passes-chave, assistências, condução). Ausente para a maioria dos goleiros.",
    example: "Um meia que distribui passes-chave e dá assistências tem creativity alto, mesmo sem marcar gols.",
    related: ["powerranking", "player_score_geral"],
  },
  {
    id: "participacoes_gol", term: "Participações em Gol", category: "jogadores",
    short: "Gols + assistências do jogador.",
    full: "Envolvimento direto na produção ofensiva: soma de gols marcados e assistências.",
    formula: "gols + assistências",
    example: "2 gols + 3 assistências = 5 participações em gol no torneio.",
    related: ["player_score_geral", "attacking_score"],
  },
];

// Índice por id, para lookup rápido (modal e links).
export const TERMS_BY_ID: Record<string, Term> = Object.fromEntries(
  TERMS.map((t) => [t.id, t]),
);

export function getTerm(id: string): Term | undefined {
  return TERMS_BY_ID[id];
}

export function categoryOf(id: CategoryId): Category | undefined {
  return CATEGORIES.find((c) => c.id === id);
}
