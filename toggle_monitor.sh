#!/usr/bin/env bash
# ==============================================================================
# NovoAuto - Alternador do Monitor Visual (TUI) em Janela Flutuante
# Mapeado para o atalho F9 ou Super+Z no Hyprland
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Localiza interpretador Python (usa o venv se existir, senão python3 do sistema)
if [ -d "$SCRIPT_DIR/.venv" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [ -d "$HOME/autojg_ver2/.venv" ]; then
    PYTHON_BIN="$HOME/autojg_ver2/.venv/bin/python"
else
    PYTHON_BIN="$(which python3)"
fi

# Verifica se o monitor já está rodando
MONITOR_PID=$(pgrep -f "python.*main.py monitor" | head -n 1)

if [ -n "$MONITOR_PID" ]; then
    kill -TERM "$MONITOR_PID" 2>/dev/null || kill -9 "$MONITOR_PID" 2>/dev/null
    notify-send -u normal -i dialog-information "⚡ NovoAuto" "Monitor TUI FECHADO." -t 2000
    echo "[NovoAuto] Monitor TUI fechado (PID: $MONITOR_PID)."
else
    notify-send -u normal -i dialog-information "⚡ NovoAuto" "Abrindo Monitor TUI em tempo real..." -t 2000
    kitty --class novoauto-monitor --title "NovoAuto Monitor" -e bash -c "cd '$SCRIPT_DIR' && '$PYTHON_BIN' main.py monitor" &
    echo "[NovoAuto] Monitor TUI iniciado."
fi
