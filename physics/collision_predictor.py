"""
NovoAuto - Preditor Especializado de Colisão de Hitbox e Timing de Aparar (Parry)
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Modela a geometria de colisão dos lutadores e calcula o instante t_0 de impacto
com precisão sub-milimétrica para acionamento do Parry na janela de 120ms.
"""

from typing import Tuple
from config import CONTACT_DISTANCE_METERS, PARRY_WINDOW_MIN_MS, PARRY_WINDOW_MAX_MS
from physics.kinematics import KinematicSnapshot, PhysicalAction

class CollisionPredictor:
    """
    Preditor cinemático de colisão para combate no MCoC.
    """
    def __init__(
        self,
        contact_distance: float = CONTACT_DISTANCE_METERS,
        optimal_window_ms: Tuple[float, float] = (PARRY_WINDOW_MIN_MS, PARRY_WINDOW_MAX_MS),
    ):
        self.contact_distance = contact_distance
        self.window_min_ms = optimal_window_ms[0]
        self.window_max_ms = optimal_window_ms[1]

    def compute_impact_time_ms(self, current_dx: float, closing_speed: float) -> float:
        """
        Calcula o tempo restante até que as hitboxes colidam.
        closing_speed: velocidade escalar de aproximação em m/s (positiva).
        """
        if current_dx <= self.contact_distance:
            return 0.0
        if closing_speed <= 0.2:  # Velocidade muito baixa ou afastando-se
            return 9999.0
        time_sec = (current_dx - self.contact_distance) / closing_speed
        return time_sec * 1000.0

    def should_trigger_parry(self, snapshot: KinematicSnapshot) -> bool:
        """
        Avalia se a situação cinemática atual exige acionamento imediato do Aparar (Parry).
        """
        if snapshot.action != PhysicalAction.DASH_FORWARD:
            return False
        return self.window_min_ms <= snapshot.t_impact_ms <= self.window_max_ms
