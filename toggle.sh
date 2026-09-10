#!/usr/bin/env bash
# ==============================================================================
# NovoAuto - Script de Alternância Global (Toggle Ativar/Desativar)
# Mapeado para o atalho F10 ou Super+X no Hyprland
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/novoauto.log"
PID_FILE="$SCRIPT_DIR/.novoauto.pid"

# Localiza interpretador Python (usa o venv se existir, senão python3 do sistema)
if [ -d "$SCRIPT_DIR/.venv" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [ -d "$HOME/autojg_ver2/.venv" ]; then
    PYTHON_BIN="$HOME/autojg_ver2/.venv/bin/python"
else
    PYTHON_BIN="$(which python3)"
fi

# Verifica se o processo já está rodando
RUNNING_PID=$(pgrep -f "python.*main.py run" | head -n 1)

if [ -n "$RUNNING_PID" ]; then
    # Bot está rodando -> Desativar
    kill -SIGINT "$RUNNING_PID" 2>/dev/null || kill -9 "$RUNNING_PID" 2>/dev/null
    rm -f "$PID_FILE"
    notify-send -u normal -i dialog-warning "⚡ NovoAuto" "Automação DESATIVADA com segurança." -t 2500
    echo "[NovoAuto] Desativado (PID: $RUNNING_PID)."
else
    # Bot está parado -> Ativar
    cd "$SCRIPT_DIR" || exit 1
    PYTHONUNBUFFERED=1 setsid "$PYTHON_BIN" -u main.py run </dev/null >> "$LOG_FILE" 2>&1 &
    NEW_PID=$!
    echo "$NEW_PID" > "$PID_FILE"
    notify-send -u normal -i dialog-information "⚡ NovoAuto" "Automação ATIVADA (PID: $NEW_PID)!" -t 2500
    echo "[NovoAuto] Ativado em segundo plano (PID: $NEW_PID). Logs em $LOG_FILE."
fi
