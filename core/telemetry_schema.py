"""
NovoAuto - Esquema de Telemetria e Parser de Memória
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Fornece estruturas de dados de alta performance com slots de memória e parser dual
capaz de ingerir tanto o formato em produção do BlizzMod (chaves planas) quanto o formato expandido (aninhado).
"""

from dataclasses import dataclass
import time
from typing import Dict, Any, Optional

@dataclass(slots=True)
class Vector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

@dataclass(slots=True)
class CombatantState:
    pos: Vector3
    hp_pct: float = 100.0
    mana: float = 0.0
    power_bars: int = 0
    is_blocking: bool = False
    is_stunned: bool = False
    striker_ready: bool = False

@dataclass(slots=True)
class TelemetryPacket:
    timestamp_ms: int
    in_fight: bool
    distance: float
    player: CombatantState
    opponent: CombatantState
    opp_state_id: int = -1
    opp_state_name: str = ""
    player_state_id: int = -1
    player_state_name: str = ""
    receive_time: float = 0.0

def parse_telemetry_dict(raw: Dict[str, Any], recv_time: Optional[float] = None) -> TelemetryPacket:
    """
    Deserializa e normaliza dicionários brutos provenientes do socket UDP.
    Suporta formato plano (BlizzMod atual) e aninhado (DATAGRAMA_UDP.md).
    """
    if recv_time is None:
        recv_time = time.perf_counter()

    timestamp_ms = int(raw.get("timestamp_ms", int(recv_time * 1000.0)))
    in_fight = bool(raw.get("in_fight", False))
    distance = float(raw.get("distance", 0.0))

    # 1. Parsing do Jogador (Player)
    if "player" in raw and isinstance(raw["player"], dict):
        p_data = raw["player"]
        p_pos_data = p_data.get("pos", {})
        p_pos = Vector3(
            x=float(p_pos_data.get("x", 0.0)),
            y=float(p_pos_data.get("y", 0.0)),
            z=float(p_pos_data.get("z", 0.0))
        )
        p_hp = float(p_data.get("hp_pct", 100.0))
        p_mana = float(p_data.get("mana", 0.0))
        p_bars = int(p_data.get("power_bars", min(3, int(p_mana))))
        p_blocking = bool(p_data.get("is_blocking", False))
        p_stunned = bool(p_data.get("is_stunned", False))
        p_striker = bool(p_data.get("striker_ready", False))
    else:
        # Formato plano do BlizzMod
        p_pos_data = raw.get("player_pos", {})
        p_pos = Vector3(
            x=float(p_pos_data.get("x", -2.1)),
            y=float(p_pos_data.get("y", 0.0)),
            z=float(p_pos_data.get("z", 0.0))
        )
        p_hp = float(raw.get("player_hp_pct", 100.0))
        p_mana = float(raw.get("player_mana", 0.0))
        if p_mana > 3.0:
            p_mana = (p_mana / 100.0) * 3.0
        p_bars = min(3, max(0, int(p_mana)))
        p_blocking = bool(raw.get("is_player_blocking", False))
        p_stunned = bool(raw.get("is_player_stunned", False))
        p_striker = bool(raw.get("striker_ready", False))

    player_state = CombatantState(
        pos=p_pos,
        hp_pct=p_hp,
        mana=p_mana,
        power_bars=p_bars,
        is_blocking=p_blocking,
        is_stunned=p_stunned,
        striker_ready=p_striker,
    )

    # 2. Parsing do Oponente (Opponent)
    if "opponent" in raw and isinstance(raw["opponent"], dict):
        o_data = raw["opponent"]
        o_pos_data = o_data.get("pos", {})
        o_pos = Vector3(
            x=float(o_pos_data.get("x", 0.0)),
            y=float(o_pos_data.get("y", 0.0)),
            z=float(o_pos_data.get("z", 0.0))
        )
        o_hp = float(o_data.get("hp_pct", 100.0))
        o_mana = float(o_data.get("mana", 0.0))
        if o_mana > 3.0:
            o_mana = (o_mana / 100.0) * 3.0
        o_bars = int(o_data.get("power_bars", min(3, max(0, int(o_mana)))))
        o_blocking = bool(o_data.get("is_blocking", False))
        o_stunned = bool(o_data.get("is_stunned", False))
        o_striker = bool(o_data.get("striker_ready", False))
    else:
        # Formato plano do BlizzMod
        o_pos_data = raw.get("opponent_pos", {})
        o_pos = Vector3(
            x=float(o_pos_data.get("x", 0.75)),
            y=float(o_pos_data.get("y", 0.0)),
            z=float(o_pos_data.get("z", 0.0))
        )
        o_hp = float(raw.get("opponent_hp_pct", 100.0))
        o_mana = float(raw.get("opponent_mana", 0.0))
        if o_mana > 3.0:
            o_mana = (o_mana / 100.0) * 3.0
        o_bars = min(3, max(0, int(o_mana)))
        o_blocking = bool(raw.get("is_opponent_blocking", False))
        o_stunned = bool(raw.get("is_opponent_stunned", False))
        o_striker = False

    # 3. Animações e Máquinas de Estado Il2Cpp
    opp_st = raw.get("opponent_state", {})
    if isinstance(opp_st, dict):
        opp_state_id = int(opp_st.get("id", -1))
        opp_state_name = str(opp_st.get("name", ""))
    else:
        opp_state_id = int(raw.get("opponent_state_id", -1))
        opp_state_name = str(raw.get("opponent_state_name", ""))

    if opp_state_id == 1:
        o_blocking = True
    if opp_state_id == 8:
        o_stunned = True

    opponent_state = CombatantState(
        pos=o_pos,
        hp_pct=o_hp,
        mana=o_mana,
        power_bars=o_bars,
        is_blocking=o_blocking,
        is_stunned=o_stunned,
        striker_ready=o_striker,
    )

    pl_st = raw.get("player_state", {})
    if isinstance(pl_st, dict):
        player_state_id = int(pl_st.get("id", -1))
        player_state_name = str(pl_st.get("name", ""))
    else:
        player_state_id = int(raw.get("player_state_id", -1))
        player_state_name = str(raw.get("player_state_name", ""))

    return TelemetryPacket(
        timestamp_ms=timestamp_ms,
        in_fight=in_fight,
        distance=distance,
        player=player_state,
        opponent=opponent_state,
        opp_state_id=opp_state_id,
        opp_state_name=opp_state_name,
        player_state_id=player_state_id,
        player_state_name=player_state_name,
        receive_time=recv_time,
    )
