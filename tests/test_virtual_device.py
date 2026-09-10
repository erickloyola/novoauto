"""
Testes Unitários: Dispositivo Virtual e Emulação de Periférico (execution/virtual_device.py)
"""

import pytest
from config import GameAction, InputScheme, ACTION_KEYS, INVERTED_ACTION_KEYS
from execution.virtual_device import VirtualDevice

def test_dry_run_press_and_release():
    dev = VirtualDevice(dry_run=True)
    key = ACTION_KEYS[InputScheme.WASD][GameAction.LIGHT_ATTACK]
    
    dev.press_key(key)
    assert key in dev.active_keys
    
    dev.release_key(key)
    assert key not in dev.active_keys

def test_emergency_stop():
    dev = VirtualDevice(dry_run=True)
    key = ACTION_KEYS[InputScheme.WASD][GameAction.BLOCK]
    
    dev.press_key(key)
    assert key in dev.active_keys
    
    dev.emergency_stop()
    assert dev.is_emergency_stopped is True
    assert len(dev.active_keys) == 0

    # Tentativa de pressionar tecla durante emergency stop deve ser ignorada
    dev.press_key(key)
    assert len(dev.active_keys) == 0

    # Desativa emergência
    dev.reset_emergency_stop()
    assert dev.is_emergency_stopped is False
    dev.press_key(key)
    assert key in dev.active_keys

def test_side_inversion_keycodes():
    dev = VirtualDevice(dry_run=True)
    
    # Lado normal: avanço é D
    dev.set_side_inverted(False)
    normal_fwd = dev._get_key(GameAction.MEDIUM_ATTACK)
    assert normal_fwd == ACTION_KEYS[InputScheme.WASD][GameAction.MEDIUM_ATTACK]

    # Lado invertido: avanço torna-se A
    dev.set_side_inverted(True)
    inverted_fwd = dev._get_key(GameAction.MEDIUM_ATTACK)
    assert inverted_fwd == INVERTED_ACTION_KEYS[InputScheme.WASD][GameAction.MEDIUM_ATTACK]
    assert normal_fwd != inverted_fwd
