#!/usr/bin/env bash
# Encerra TUDO do watcher de forma limpa e remove o estado em /tmp.
#
# Existe porque o problema recorrente é "fica um daemon antigo rodando" — o
# daemon carrega o código no launch (Python não relê o arquivo), então depois de
# alterar watch-fifa.py/fifa_progress.py é PRECISO matar o daemon velho, senão
# ele segue com o código bugado e o lock/socket órfãos travam o próximo start.
#
# Uso:  bash watcher/stop-window.sh
# Depois, para subir limpo:  bash watcher/run-window.sh
set -uo pipefail

echo "→ encerrando processos do watcher…"

# 1) sinaliza parada (run-window.sh observa o STOP_FILE) e dá um tempo
echo "1" > /tmp/fifa-copa.stop 2>/dev/null || true
sleep 1

# 2) SIGTERM por padrão de comando (encerramento limpo)
for pat in "watcher/run-window.sh" "watcher/fifa_progress.py" "watcher/watch-fifa.py"; do
  pkill -TERM -f "$pat" 2>/dev/null || true
done
sleep 2

# 3) quem sobrar leva SIGKILL (daemon travado não responde a TERM)
leftover=$(pgrep -f "watcher/(run-window.sh|fifa_progress.py|watch-fifa.py)" || true)
if [ -n "$leftover" ]; then
  echo "→ alguns processos não responderam — forçando SIGKILL: $leftover"
  for pat in "watcher/run-window.sh" "watcher/fifa_progress.py" "watcher/watch-fifa.py"; do
    pkill -KILL -f "$pat" 2>/dev/null || true
  done
  sleep 1
fi

# 4) remove estado/lock/socket órfãos (a outra causa de "buga sempre")
rm -f /tmp/fifa-copa.sock /tmp/fifa-copa.lock /tmp/fifa-copa.json \
      /tmp/fifa-copa.json.tmp /tmp/fifa-copa.stop \
      /tmp/fifa-copa-cmd.json /tmp/fifa-copa.cmd 2>/dev/null || true

# 5) confirma
if pgrep -f "watcher/(run-window.sh|fifa_progress.py|watch-fifa.py)" >/dev/null 2>&1; then
  echo "✗ ainda há processo do watcher vivo — verifique com: ps aux | grep watch-fifa"
  exit 1
fi
echo "✓ watcher encerrado e /tmp limpo. Suba de novo com: bash watcher/run-window.sh"
