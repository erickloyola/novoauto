"""
NovoAuto - Módulo de Cinemática e Análise Física Vetorial
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Calcula distâncias, derivadas de 1ª e 2ª ordem (velocidades lineares, velocidade relativa
de fechamento e aceleração) com suavização exponencial (EMA) e proteção contra inversão de lado.
Tempo de execução: < 5 microssegundos por ciclo.
"""

from dataclasses import dataclass
from enum import Enum, auto
import math
import time
from typing import Optional, Tuple

from config import (
    CONTACT_DISTANCE_METERS,
    PARRY_WINDOW_MIN_MS,
    PARRY_WINDOW_MAX_MS,
    EMA_ALPHA,
)

class PhysicalAction(Enum):
    NEUTRAL = auto()
    DASH_FORWARD = auto()
    DASH_BACK = auto()
    WALK_FORWARD = auto()
    WALK_BACK = auto()
    STATIC_BLOCK = auto()
    AIRBORNE = auto()

class CombatRangeZone(Enum):
    CLOSE_INFIGHT = auto()   # <= 1.6m
    DASH_PUNISH = auto()     # 1.6m - 2.8m
    BAITING_MID = auto()     # 2.8m - 4.0m
    FAR_RESET = auto()       # > 4.0m

@dataclass(slots=True)
class KinematicSnapshot:
    timestamp_ms: int
    dx: float                    # Distância longitudinal 1D (m)
    d3d: float                   # Distância euclidiana 3D (m)
    v_player: float              # Velocidade longitudinal do jogador (m/s)
    v_opp: float                 # Velocidade longitudinal do oponente (m/s)
    v_rel: float                 # Velocidade relativa de fechamento (m/s) (< 0 se aproximando)
    a_opp: float                 # Aceleração longitudinal do oponente (m/s²)
    action: PhysicalAction       # Ação física classificada
    zone: CombatRangeZone        # Zona espacial de combate
    t_impact_ms: float           # Tempo predito até impacto de hitboxes (ms)
    is_side_inverted: bool       # True se o jogador estiver no lado direito (X_player > X_opp)

class PhysicsEngine:
    """
    Motor de cinemática vetorial do NovoAuto.
    """
    def __init__(
        self,
        contact_distance: float = CONTACT_DISTANCE_METERS,
        parry_window_ms: Tuple[float, float] = (PARRY_WINDOW_MIN_MS, PARRY_WINDOW_MAX_MS),
        alpha: float = EMA_ALPHA,
    ):
        self.contact_dist = contact_distance
        self.parry_window_min = parry_window_ms[0]
        self.parry_window_max = parry_window_ms[1]
        self.alpha = alpha

        self.prev_p_x: Optional[float] = None
        self.prev_o_x: Optional[float] = None
        self.prev_o_y: Optional[float] = None
        self.prev_time_sec: float = 0.0
        self.prev_v_opp: float = 0.0

        # Filtro EMA
        self.smoothed_v_opp: float = 0.0
        self.smoothed_v_rel: float = 0.0

    def reset(self) -> None:
        """Reinicia o histórico temporal entre lutas."""
        self.prev_p_x = None
        self.prev_o_x = None
        self.prev_o_y = None
        self.prev_time_sec = 0.0
        self.prev_v_opp = 0.0
        self.smoothed_v_opp = 0.0
        self.smoothed_v_rel = 0.0

    def update(
        self,
        timestamp_ms: int,
        player_x: float,
        player_y: float,
        player_z: float,
        opp_x: float,
        opp_y: float,
        opp_z: float,
        is_opponent_blocking: bool = False,
        override_now_sec: Optional[float] = None,
        raw_distance: Optional[float] = None,
    ) -> KinematicSnapshot:
        now_sec = override_now_sec if override_now_sec is not None else time.perf_counter()
        is_side_inverted = player_x > opp_x

        # 1. Distâncias Métricas (Usa a distância do motor se disponível, com fallback para coordenadas)
        if raw_distance is not None and raw_distance > 0.05:
            dx = raw_distance
            d3d = raw_distance
        else:
            dx = abs(opp_x - player_x)
            d3d = math.sqrt(
                (opp_x - player_x) ** 2 +
                (opp_y - player_y) ** 2 +
                (opp_z - player_z) ** 2
            )

        # 2. Inicialização no primeiro frame
        if self.prev_p_x is None or self.prev_o_x is None or self.prev_time_sec <= 0.0:
            self._save_state(player_x, opp_x, opp_y, now_sec, 0.0)
            return KinematicSnapshot(
                timestamp_ms=timestamp_ms,
                dx=dx,
                d3d=d3d,
                v_player=0.0,
                v_opp=0.0,
                v_rel=0.0,
                a_opp=0.0,
                action=PhysicalAction.NEUTRAL,
                zone=self._classify_zone(dx),
                t_impact_ms=9999.0,
                is_side_inverted=is_side_inverted,
            )

        # 3. Intervalo de tempo (Delta t)
        dt = now_sec - self.prev_time_sec
        if dt <= 0.0005:  # Previne divisão por micro-jitter
            dt = 0.0005

        # 4. Derivadas de 1ª Ordem
        raw_v_player = (player_x - self.prev_p_x) / dt
        raw_v_opp = (opp_x - self.prev_o_x) / dt
        raw_v_rel = (dx - abs(self.prev_o_x - self.prev_p_x)) / dt

        # Filtro de Suavização Exponencial (EMA)
        v_opp = self.alpha * raw_v_opp + (1.0 - self.alpha) * self.smoothed_v_opp
        self.smoothed_v_opp = v_opp

        v_rel = self.alpha * raw_v_rel + (1.0 - self.alpha) * self.smoothed_v_rel
        self.smoothed_v_rel = v_rel

        # 5. Derivada de 2ª Ordem (Aceleração do Oponente)
        a_opp = (v_opp - self.prev_v_opp) / dt

        # 6. Classificação da Ação Física
        # Sentido de avanço: se o oponente está na direita (normal), avanço = X decresce (v_opp negativo)
        # Se os lutadores trocaram de lado, avanço = X cresce (v_opp positivo)
        opp_forward_vel = v_opp if not is_side_inverted else -v_opp
        action = PhysicalAction.NEUTRAL

        if opp_y > 0.35:
            action = PhysicalAction.AIRBORNE
        elif opp_forward_vel <= -2.2 or (a_opp < -8.0 and opp_forward_vel < -1.2):
            action = PhysicalAction.DASH_FORWARD
        elif opp_forward_vel >= 2.0:
            action = PhysicalAction.DASH_BACK
        elif is_opponent_blocking and abs(v_opp) < 0.2:
            action = PhysicalAction.STATIC_BLOCK
        elif -1.5 <= opp_forward_vel < -0.3:
            action = PhysicalAction.WALK_FORWARD
        elif 0.3 < opp_forward_vel <= 1.5:
            action = PhysicalAction.WALK_BACK

        # 7. Predição Temporal de Impacto de Hitbox
        closing_speed = -v_rel  # Positivo quando encurtando distância
        if closing_speed > 0.4 and dx > self.contact_dist:
            t_impact_sec = (dx - self.contact_dist) / closing_speed
            t_impact_ms = t_impact_sec * 1000.0
        elif dx <= self.contact_dist:
            t_impact_ms = 0.0
        else:
            t_impact_ms = 9999.0

        # 8. Zonificação Espacial
        zone = self._classify_zone(dx)

        self._save_state(player_x, opp_x, opp_y, now_sec, v_opp)

        return KinematicSnapshot(
            timestamp_ms=timestamp_ms,
            dx=dx,
            d3d=d3d,
            v_player=raw_v_player,
            v_opp=v_opp,
            v_rel=v_rel,
            a_opp=a_opp,
            action=action,
            zone=zone,
            t_impact_ms=t_impact_ms,
            is_side_inverted=is_side_inverted,
        )

    def is_parry_timing_optimal(self, snapshot: KinematicSnapshot) -> bool:
        """
        Retorna True se o oponente está avançando agressivamente e o impacto
        ocorrerá dentro da janela ótima de Aparar (90ms a 135ms).
        """
        if snapshot.action != PhysicalAction.DASH_FORWARD:
            return False
        return self.parry_window_min <= snapshot.t_impact_ms <= self.parry_window_max

    def _classify_zone(self, dx: float) -> CombatRangeZone:
        if dx <= 1.60:
            return CombatRangeZone.CLOSE_INFIGHT
        elif dx <= 2.80:
            return CombatRangeZone.DASH_PUNISH
        elif dx <= 4.00:
            return CombatRangeZone.BAITING_MID
        else:
            return CombatRangeZone.FAR_RESET

    def _save_state(self, p_x: float, o_x: float, o_y: float, t_sec: float, v_opp: float) -> None:
        self.prev_p_x = p_x
        self.prev_o_x = o_x
        self.prev_o_y = o_y
        self.prev_time_sec = t_sec
        self.prev_v_opp = v_opp
