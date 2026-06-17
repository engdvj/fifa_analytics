#!/usr/bin/env bash
# Instala os serviços systemd (modo usuário) do watcher da Copa 2026.
#   fifa-watcher   — daemon que coleta jogos novos e atualiza o ranking
#   fifa-progress  — janela flutuante que mostra a fila e o progresso
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"

for unit in fifa-watcher.service fifa-progress.service; do
    cp "$HERE/$unit" "$UNIT_DIR/$unit"
    echo "instalado: $UNIT_DIR/$unit"
done

systemctl --user daemon-reload
systemctl --user enable --now fifa-watcher.service
systemctl --user enable --now fifa-progress.service

echo ""
echo "Serviços ativos. Comandos úteis:"
echo "  systemctl --user status fifa-watcher fifa-progress"
echo "  journalctl --user -u fifa-watcher -f      # logs do daemon"
echo "  systemctl --user restart fifa-watcher     # forçar coleta agora"
echo "  systemctl --user stop fifa-watcher fifa-progress"
