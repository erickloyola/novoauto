"""
NovoAuto - Configuração Central do Sistema
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Mapeamento de rede UDP, esquemas de entrada (WASD e ARROWS) baseados estritamente em comandoinput.jpeg
e carregamento de timings humanizados.
"""

from dataclasses import dataclass
from enum import Enum
import json
import logging
from pathlib import Path
from typing import Dict, Any

try:
    import evdev.ecodes as ecodes
except ImportError:
    # Mapeamento dummy caso evdev não esteja disponível em ambiente de desenvolvimento isolado
    class DummyEcodes:
        KEY_W = 17
        KEY_A = 30
        KEY_S = 31
        KEY_D = 32
        KEY_SPACE = 57
        KEY_LEFTSHIFT = 42
        KEY_RIGHTSHIFT = 54
        KEY_LEFTCTRL = 29
        KEY_UP = 103
        KEY_DOWN = 108
        KEY_LEFT = 105
        KEY_RIGHT = 106
        KEY_ESC = 1
    ecodes = DummyEcodes()

BASE_DIR = Path(__file__).resolve().parent

# ==============================================================================
# 1. Configurações de Rede e Telemetria UDP
# ==============================================================================
UDP_HOST = "127.0.0.1"
UDP_PORT = 5555
UDP_BUFFER_SIZE = 65536  # 64KB
UDP_LIVENESS_TIMEOUT_SEC = 1.5

# ==============================================================================
# 2. Esquemas de Entrada e Mapeamento de Teclas (comandoinput.jpeg)
# ==============================================================================
class GameAction(Enum):
    LIGHT_ATTACK = "LIGHT_ATTACK"       # Toque rápido (W ou Up)
    HEAVY_ATTACK = "HEAVY_ATTACK"       # Segurar e soltar (W ou Up)
    MEDIUM_ATTACK = "MEDIUM_ATTACK"     # Dash para frente / Golpe Médio (D ou Right)
    DODGE_BACK = "DODGE_BACK"           # Recuo / Destreza (A ou Left)
    BLOCK = "BLOCK"                     # Bloqueio / Guarda (S ou Down)
    PARRY = "PARRY"                     # Pulso de Bloqueio (S ou Down)
    SPECIAL_ATTACK = "SPECIAL_ATTACK"   # Especial SP1/SP2/SP3 (Espaço ou Ctrl)
    STRIKER_ASSIST = "STRIKER_ASSIST"   # Relíquia / Striker (Shift)

class InputScheme(Enum):
    WASD = "WASD"
    ARROWS = "ARROWS"

ACTION_KEYS: Dict[InputScheme, Dict[GameAction, int]] = {
    InputScheme.WASD: {
        GameAction.LIGHT_ATTACK: ecodes.KEY_W,
        GameAction.HEAVY_ATTACK: ecodes.KEY_W,
        GameAction.MEDIUM_ATTACK: ecodes.KEY_D,
        GameAction.DODGE_BACK: ecodes.KEY_A,
        GameAction.BLOCK: ecodes.KEY_S,
        GameAction.PARRY: ecodes.KEY_S,
        GameAction.SPECIAL_ATTACK: ecodes.KEY_SPACE,
        GameAction.STRIKER_ASSIST: ecodes.KEY_LEFTSHIFT,
    },
    InputScheme.ARROWS: {
        GameAction.LIGHT_ATTACK: ecodes.KEY_UP,
        GameAction.HEAVY_ATTACK: ecodes.KEY_UP,
        GameAction.MEDIUM_ATTACK: ecodes.KEY_RIGHT,
        GameAction.DODGE_BACK: ecodes.KEY_LEFT,
        GameAction.BLOCK: ecodes.KEY_DOWN,
        GameAction.PARRY: ecodes.KEY_DOWN,
        GameAction.SPECIAL_ATTACK: ecodes.KEY_LEFTCTRL,
        GameAction.STRIKER_ASSIST: ecodes.KEY_RIGHTSHIFT,
    }
}

# Inversão de direção quando o jogador estiver no lado direito do ringue (X_player > X_opp)
INVERTED_ACTION_KEYS: Dict[InputScheme, Dict[GameAction, int]] = {
    InputScheme.WASD: {
        GameAction.LIGHT_ATTACK: ecodes.KEY_W,
        GameAction.HEAVY_ATTACK: ecodes.KEY_W,
        GameAction.MEDIUM_ATTACK: ecodes.KEY_A,   # Avanço vira 'A' (Esquerda)
        GameAction.DODGE_BACK: ecodes.KEY_D,       # Recuo vira 'D' (Direita)
        GameAction.BLOCK: ecodes.KEY_S,
        GameAction.PARRY: ecodes.KEY_S,
        GameAction.SPECIAL_ATTACK: ecodes.KEY_SPACE,
        GameAction.STRIKER_ASSIST: ecodes.KEY_LEFTSHIFT,
    },
    InputScheme.ARROWS: {
        GameAction.LIGHT_ATTACK: ecodes.KEY_UP,
        GameAction.HEAVY_ATTACK: ecodes.KEY_UP,
        GameAction.MEDIUM_ATTACK: ecodes.KEY_LEFT, # Avanço vira Seta Esquerda
        GameAction.DODGE_BACK: ecodes.KEY_RIGHT,   # Recuo vira Seta Direita
        GameAction.BLOCK: ecodes.KEY_DOWN,
        GameAction.PARRY: ecodes.KEY_DOWN,
        GameAction.SPECIAL_ATTACK: ecodes.KEY_LEFTCTRL,
        GameAction.STRIKER_ASSIST: ecodes.KEY_RIGHTSHIFT,
    }
}

# ==============================================================================
# 3. Parâmetros de Tempo e Jitter Biológico
# ==============================================================================
# Flag global de jitter biológico (True = humanizado com variações estocásticas, False = modo teste de resposta instantânea)
ENABLE_BIOLOGICAL_JITTER: bool = False

@dataclass
class TimingsConfig:
    reaction_base_ms: float = 0.0
    reaction_jitter_ms: float = 0.0
    light_tap_ms: float = 30.0
    light_tap_jitter_ms: float = 0.0
    medium_dash_ms: float = 50.0
    medium_dash_jitter_ms: float = 0.0
    heavy_hold_ms: float = 420.0
    heavy_hold_jitter_ms: float = 0.0
    parry_pulse_ms: float = 85.0
    parry_pulse_jitter_ms: float = 0.0
    dexterity_dash_ms: float = 45.0
    dexterity_dash_jitter_ms: float = 0.0
    dash_in_recovery_ms: float = 130.0
    dash_in_recovery_jitter_ms: float = 0.0
    combo_hit_interval_ms: float = 110.0
    combo_hit_interval_jitter_ms: float = 0.0
    bait_spacing_interval_ms: float = 120.0
    bait_spacing_jitter_ms: float = 0.0
    heavy_recovery_punish_delay_ms: float = 80.0

    @classmethod
    def load_from_file(cls, path: Path) -> "TimingsConfig":
        if not path.exists():
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: float(v) for k, v in data.items() if hasattr(cls, k)})
        except Exception:
            return cls()

TIMINGS = TimingsConfig.load_from_file(BASE_DIR / "timings.json")

# ==============================================================================
# 4. Parâmetros de Física e Combate
# ==============================================================================
CONTACT_DISTANCE_METERS = 0.95
PARRY_WINDOW_MIN_MS = 80.0
PARRY_WINDOW_MAX_MS = 140.0
EMA_ALPHA = 0.75

SPECIAL_DEFENSE_HOLD_SEC = 1.00
EMERGENCY_GUARD_HOLD_SEC = 0.25
POST_COMBO_COOLDOWN_SEC = 0.20
DAMAGE_THRESHOLD_HP_PCT = 1.8
SP3_DANGER_THRESHOLD = 2.80

LOG_LEVEL = logging.INFO
