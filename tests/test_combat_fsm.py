"""
Testes Unitários: Máquina de Estados Finita e Regras de Combate (brain/combat_fsm.py)
"""

import time
import pytest
from brain.combat_fsm import CombatBrain
from core.telemetry_schema import TelemetryPacket, CombatantState, Vector3
from physics.kinematics import KinematicSnapshot, PhysicalAction, CombatRangeZone
from execution.virtual_device import VirtualDevice
from execution.combo_sequencer import ComboSequencer

@pytest.fixture
def mock_brain():
    device = VirtualDevice(dry_run=True)
    combo = ComboSequencer(device)
    return CombatBrain(device, combo)

def make_packet(in_fight=True, dx=2.0, p_hp=100.0, p_mana=0.0, o_hp=100.0, o_mana=0.0, o_state=0, o_state_name="Idle", o_blocking=False, o_stunned=False, p_striker=False):
    return TelemetryPacket(
        timestamp_ms=int(time.perf_counter() * 1000),
        in_fight=in_fight,
        distance=dx,
        player=CombatantState(pos=Vector3(-1.5, 0, 0), hp_pct=p_hp, mana=p_mana, is_blocking=False, is_stunned=False, striker_ready=p_striker),
        opponent=CombatantState(pos=Vector3(0.5, 0, 0), hp_pct=o_hp, mana=o_mana, is_blocking=o_blocking, is_stunned=o_stunned),
        opp_state_id=o_state,
        opp_state_name=o_state_name,
        receive_time=time.perf_counter(),
    )

def make_physics(dx=2.0, action=PhysicalAction.NEUTRAL, t_impact_ms=9999.0, is_inverted=False):
    zone = CombatRangeZone.CLOSE_INFIGHT if dx <= 1.6 else (CombatRangeZone.DASH_PUNISH if dx <= 2.8 else CombatRangeZone.BAITING_MID)
    return KinematicSnapshot(
        timestamp_ms=int(time.perf_counter() * 1000),
        dx=dx,
        d3d=dx,
        v_player=0.0,
        v_opp=-3.0 if action == PhysicalAction.DASH_FORWARD else 0.0,
        v_rel=-3.0 if action == PhysicalAction.DASH_FORWARD else 0.0,
        a_opp=0.0,
        action=action,
        zone=zone,
        t_impact_ms=t_impact_ms,
        is_side_inverted=is_inverted,
    )

def test_fsm_initial_and_neutral(mock_brain):
    assert mock_brain.state == "PAUSA_SEGURA"
    
    p = make_packet(in_fight=True)
    s = make_physics()
    mock_brain.update(p, s)
    assert mock_brain.state == "NEUTRO"

def test_fsm_safety_pause_on_fight_end(mock_brain):
    p = make_packet(in_fight=True)
    s = make_physics()
    mock_brain.update(p, s)
    assert mock_brain.state == "NEUTRO"

    p_end = make_packet(in_fight=False)
    mock_brain.update(p_end, s)
    assert mock_brain.state == "PAUSA_SEGURA"

def test_predictive_parry_trigger(mock_brain):
    # Entra em neutro
    mock_brain.update(make_packet(), make_physics())
    
    # Oponente avança com timing ótimo de impacto (110ms)
    p_dash = make_packet(o_state=2, o_state_name="Run")
    s_dash = make_physics(dx=1.8, action=PhysicalAction.DASH_FORWARD, t_impact_ms=110.0)
    mock_brain.update(p_dash, s_dash)
    
    assert mock_brain.state == "DEFESA_PARRY"

def test_special_attack_defense(mock_brain):
    mock_brain.update(make_packet(o_mana=1.0), make_physics())
    
    # Oponente dispara especial (queda brusca de mana e state_id = 9)
    p_sp = make_packet(o_mana=0.1, o_state=9, o_state_name="FinalSpecialAttack")
    s = make_physics()
    mock_brain.update(p_sp, s)
    
    assert mock_brain.state == "DEFESA_ESPECIAL"
    assert mock_brain.is_holding_guard is True

def test_guard_break_on_blocking(mock_brain):
    mock_brain.update(make_packet(), make_physics())
    
    # Oponente bloqueando
    p_block = make_packet(o_blocking=True, o_state=1, o_state_name="Block")
    s_block = make_physics(dx=1.2)
    mock_brain.update(p_block, s_block)
    
    # Como o quebra-guarda executa e retorna a neutro com cooldown:
    assert mock_brain.state == "NEUTRO"
    assert mock_brain.last_combo_end_time > 0

def test_anti_sp3_baiting(mock_brain):
    mock_brain.update(make_packet(), make_physics())
    
    # Oponente com 2.85 de mana (risco iminente de SP3)
    p_sp3 = make_packet(o_mana=2.85)
    s_sp3 = make_physics(dx=3.2)
    mock_brain.update(p_sp3, s_sp3)
    
    assert mock_brain.state == "BAITING_SP"

def test_emergency_damage_guard(mock_brain):
    mock_brain.update(make_packet(p_hp=100.0), make_physics())
    
    # Queda de HP de 3%
    p_dmg = make_packet(p_hp=97.0)
    mock_brain.update(p_dmg, make_physics())
    
    assert mock_brain.is_holding_guard is True
