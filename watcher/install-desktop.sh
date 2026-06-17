#!/usr/bin/env bash
# Registra o "Copa 2026 Watcher" no menu de aplicativos do Ubuntu/GNOME.
# Depois de rodar, procure por "Copa 2026" no menu e clique com o botão direito
# em "Adicionar aos favoritos" para fixar na barra de tarefas (dock).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/applications"
DESKTOP="$APP_DIR/fifa-watcher.desktop"

mkdir -p "$APP_DIR"
cp "$HERE/fifa-watcher.desktop" "$DESKTOP"
chmod +x "$DESKTOP"

# torna o launcher confiável (GNOME exige isso pra ícones em apps externos)
if command -v gio >/dev/null 2>&1; then
    gio set "$DESKTOP" metadata::trusted true 2>/dev/null || true
fi

# atualiza o cache do menu
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi

echo "✓ Atalho instalado: $DESKTOP"
echo ""
echo "Para fixar na barra de tarefas (dock):"
echo "  1. Abra o menu de aplicativos (tecla Super) e digite 'Copa 2026'"
echo "  2. Clique com o botão direito no ícone → 'Adicionar aos favoritos'"
echo ""
echo "Ou arraste o ícone do menu direto para a dock."
