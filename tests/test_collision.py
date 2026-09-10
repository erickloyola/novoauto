"""
Testes Unitários: Preditor de Colisão de Hitbox e Parry (physics/collision_predictor.py)
"""

import pytest
from physics.collision_predictor import CollisionPredictor
from physics.kinematics import KinematicSnapshot, PhysicalAction, CombatRangeZone

def test_impact_time_calculation():
    predictor = CollisionPredictor(contact_distance=0.95)
    
    # Distância atual 1.95m, velocidade de aproximação 10.0 m/s
    # Distância até contato = 1.95 - 0.95 = 1.0m
    # Tempo até impacto = 1.0 / 10.0 = 0.10s = 100ms
    t_ms = predictor.compute_impact_time_ms(current_dx=1.95, closing_speed=10.0)
    assert t_ms == pytest.approx(100.0)

def test_impact_time_already_touching():
    predictor = CollisionPredictor(contact_distance=0.95)
    t_ms = predictor.compute_impact_time_ms(current_dx=0.80, closing_speed=5.0)
    assert t_ms == 0.0

def test_parry_optimal_timing_window():
    predictor = CollisionPredictor(optimal_window_ms=(90.0, 135.0))
    
    snap_optimal = KinematicSnapshot(
        timestamp_ms=1000, dx=1.8, d3d=1.8, v_player=0.0, v_opp=-4.0, v_rel=-4.0, a_opp=0.0,
        action=PhysicalAction.DASH_FORWARD, zone=CombatRangeZone.DASH_PUNISH,
        t_impact_ms=115.0, is_side_inverted=False,
    )
    assert predictor.should_trigger_parry(snap_optimal) is True

    snap_too_early = KinematicSnapshot(
        timestamp_ms=1000, dx=2.5, d3d=2.5, v_player=0.0, v_opp=-4.0, v_rel=-4.0, a_opp=0.0,
        action=PhysicalAction.DASH_FORWARD, zone=CombatRangeZone.DASH_PUNISH,
        t_impact_ms=180.0, is_side_inverted=False,
    )
    assert predictor.should_trigger_parry(snap_too_early) is False

    snap_too_late = KinematicSnapshot(
        timestamp_ms=1000, dx=1.1, d3d=1.1, v_player=0.0, v_opp=-4.0, v_rel=-4.0, a_opp=0.0,
        action=PhysicalAction.DASH_FORWARD, zone=CombatRangeZone.CLOSE_INFIGHT,
        t_impact_ms=40.0, is_side_inverted=False,
    )
    assert predictor.should_trigger_parry(snap_too_late) is False

def test_parry_rejects_non_dash():
    predictor = CollisionPredictor()
    snap_neutral = KinematicSnapshot(
        timestamp_ms=1000, dx=1.8, d3d=1.8, v_player=0.0, v_opp=0.0, v_rel=0.0, a_opp=0.0,
        action=PhysicalAction.NEUTRAL, zone=CombatRangeZone.DASH_PUNISH,
        t_impact_ms=115.0, is_side_inverted=False,
    )
    assert predictor.should_trigger_parry(snap_neutral) is False
