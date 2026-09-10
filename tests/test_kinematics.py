"""
Testes Unitários: Motor de Cinemática e Análise Física (physics/kinematics.py)
"""

import pytest
from physics.kinematics import PhysicsEngine, PhysicalAction, CombatRangeZone

def test_first_frame_initialization():
    engine = PhysicsEngine()
    snap = engine.update(1000, player_x=-2.0, player_y=0.0, player_z=0.0, opp_x=1.0, opp_y=0.0, opp_z=0.0, override_now_sec=10.0)
    
    assert snap.dx == pytest.approx(3.0)
    assert snap.v_player == 0.0
    assert snap.v_opp == 0.0
    assert snap.v_rel == 0.0
    assert snap.action == PhysicalAction.NEUTRAL
    assert snap.zone == CombatRangeZone.BAITING_MID
    assert snap.is_side_inverted is False

def test_dash_forward_detection():
    engine = PhysicsEngine()
    t0 = 10.0
    engine.update(1000, -2.0, 0, 0, 1.5, 0, 0, override_now_sec=t0)
    
    # Oponente avança 0.15m em 16ms (velocidade ~ -9.3 m/s)
    t1 = t0 + 0.016
    snap = engine.update(1016, -2.0, 0, 0, 1.35, 0, 0, override_now_sec=t1)
    
    assert snap.v_opp < -2.2
    assert snap.action == PhysicalAction.DASH_FORWARD
    assert snap.v_rel < 0.0

def test_dash_back_detection():
    engine = PhysicsEngine()
    t0 = 10.0
    engine.update(1000, -2.0, 0, 0, 1.0, 0, 0, override_now_sec=t0)
    
    # Oponente recua rapidamente para a direita (0.1m em 16ms -> ~6.2 m/s)
    t1 = t0 + 0.016
    snap = engine.update(1016, -2.0, 0, 0, 1.10, 0, 0, override_now_sec=t1)
    
    assert snap.v_opp > 2.0
    assert snap.action == PhysicalAction.DASH_BACK

def test_side_inversion():
    engine = PhysicsEngine()
    # Jogador no lado direito (+1.5m), oponente no lado esquerdo (-1.0m)
    snap = engine.update(1000, player_x=1.5, player_y=0, player_z=0, opp_x=-1.0, opp_y=0, opp_z=0, override_now_sec=10.0)
    assert snap.is_side_inverted is True

    # Oponente avança em direção ao jogador (movendo para a direita, x aumentando)
    t1 = 10.016
    snap2 = engine.update(1016, player_x=1.5, player_y=0, player_z=0, opp_x=-0.85, opp_y=0, opp_z=0, override_now_sec=t1)
    assert snap2.is_side_inverted is True
    assert snap2.action == PhysicalAction.DASH_FORWARD

def test_zone_classification():
    engine = PhysicsEngine()
    
    s_close = engine.update(1000, 0.0, 0, 0, 1.2, 0, 0, override_now_sec=1.0)
    assert s_close.zone == CombatRangeZone.CLOSE_INFIGHT

    s_dash = engine.update(1016, 0.0, 0, 0, 2.2, 0, 0, override_now_sec=1.016)
    assert s_dash.zone == CombatRangeZone.DASH_PUNISH

    s_bait = engine.update(1032, 0.0, 0, 0, 3.5, 0, 0, override_now_sec=1.032)
    assert s_bait.zone == CombatRangeZone.BAITING_MID

    s_far = engine.update(1048, 0.0, 0, 0, 4.5, 0, 0, override_now_sec=1.048)
    assert s_far.zone == CombatRangeZone.FAR_RESET
