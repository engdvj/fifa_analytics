#!/usr/bin/env bash
# Abre o watcher completo (sem systemd): janela flutuante + daemon.
#
# A janela é a "dona": quando você fecha a janela (✕), o daemon encerra junto.
# Instância única — abrir de novo enquanto já está aberto não cria uma segunda.
#
# Variáveis úteis:
#   FIFA_SKIP_UPDATE=1   não roda `fifa-analytics atualizar` (só usa dados locais)
#   FIFA_POLL_SECS=600   intervalo entre coletas das fontes
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source .venv/bin/activate

# já existe uma janela aberta? (lock de instância única) — então não abre outra.
if [ -f /tmp/fifa-copa.lock ] && \
   python - <<'PY'
import fcntl, sys
try:
    f = open("/tmp/fifa-copa.lock", "r+")
    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    sys.exit(1)   # conseguiu travar → NÃO há janela viva
except (OSError, BlockingIOError):
    sys.exit(0)   # travado por outra → já está aberta
PY
then
    echo "Copa 2026 Watcher já está aberto."
    exit 0
fi

# janela (sobe o socket server) em background
python watcher/fifa_progress.py --windows &
WIN_PID=$!

# daemon em background
sleep 1
python watcher/watch-fifa.py &
DAEMON_PID=$!

# encerra ambos ao sair / Ctrl+C
trap 'kill "$WIN_PID" "$DAEMON_PID" 2>/dev/null || true' EXIT INT TERM

# espera a JANELA: quando ela fechar (✕), o script sai e o trap mata o daemon
wait "$WIN_PID"
