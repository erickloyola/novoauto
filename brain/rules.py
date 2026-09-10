"""
NovoAuto - Regras Táticas e Matriz de Decisão MCoC Pro
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Mapeia as 7 regras determinísticas de combate de nível profissional:
1. Aparar Preditivo (Parry Cirúrgico de 120ms)
2. Defesa Ativa contra Especiais (Destreza + Guarda sustentada por 1.2s até Recovery)
3. Quebra-Guarda com Ataque Pesado (Heavy Shield Break)
4. Baiting e Gestão Preventiva de SP3 (Anti-SP3)
5. Guarda de Emergência por Dano (Emergency Guard 420ms)
6. Disciplina Pós-Combo (Cooldown Anti-Whiff 0.70s)
7. Iniciativa Ofensiva em Neutro (Guarda Aberta)
"""

from enum import Enum, auto
from config import (
    SPECIAL_DEFENSE_HOLD_SEC,
    EMERGENCY_GUARD_HOLD_SEC,
    POST_COMBO_COOLDOWN_SEC,
    DAMAGE_THRESHOLD_HP_PCT,
    SP3_DANGER_THRESHOLD,
)

class CombatRule(Enum):
    PREDICTIVE_PARRY = auto()
    SPECIAL_DEFENSE = auto()
    GUARD_BREAK = auto()
    ANTI_SP3_BAITING = auto()
    EMERGENCY_GUARD = auto()
    POST_COMBO_COOLDOWN = auto()
    NEUTRAL_OFFENSE = auto()
    SAFETY_PAUSE = auto()
