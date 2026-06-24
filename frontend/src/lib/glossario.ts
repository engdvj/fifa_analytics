// Abre a Central de Definições numa janela flutuante (popup), para consultar
// os conceitos lado a lado com a página principal, em tempo real.
// Nome fixo da janela → cliques repetidos reaproveitam/focam a mesma janela.

export function openGlossarioPopup() {
  if (typeof window === "undefined") return;
  const w = window.open(
    "/definicoes?popup=1",
    "glossario-copa2026",
    "width=480,height=940,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes",
  );
  w?.focus();
}
