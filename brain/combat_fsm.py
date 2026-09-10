"""
NovoAuto - Cérebro Tático Determinístico (CombatBrain)
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Máquina de Estados Finita e Matriz de Decisão Reativa MCoC Pro.
Tempo de ciclo de decisão: < 10 microssegundos.
"""

import logging
import time
from typing import Optional
from transitions import Machine

from config import (
    TIMINGS,
    SPECIAL_DEFENSE_HOLD_SEC,
    EMERGENCY_GUARD_HOLD_SEC,
    POST_COMBO_COOLDOWN_SEC,
    DAMAGE_THRESHOLD_HP_PCT,
    SP3_DANGER_THRESHOLD,
)
from core.telemetry_schema import TelemetryPacket
from physics.kinematics import KinematicSnapshot, PhysicalAction, CombatRangeZone
from execution.virtual_device import VirtualDevice
from execution.combo_sequencer import ComboSequencer

logger = logging.getLogger("NovoAuto.CombatBrain")

class CombatBrain:
    """
    Controlador de decisão formal do NovoAuto.
    """
    STATES = [
        "PAUSA_SEGURA",
        "NEUTRO",
        "DEFESA_PARRY",
        "DEFESA_ESPECIAL",
        "ESQUIVA_PESADO",
        "QUEBRA_GUARDA",
        "BAITING_SP",
        "JANELA_DE_PUNICAO",
        "EXECUTANDO_COMBO",
    ]

    def __init__(self, virtual_device: VirtualDevice, combo_sequencer: ComboSequencer):
        self.device = virtual_device
        self.combo = combo_sequencer

        # Variáveis de Estado e Janelas Temporais
        self.last_player_hp: float = 100.0
        self.is_holding_guard: bool = False
        self.damage_taken_time: float = 0.0
        self.special_defense_until: float = 0.0
        self.last_combo_end_time: float = 0.0
        self.post_combo_cooldown_sec: float = POST_COMBO_COOLDOWN_SEC
        self.prev_opp_mana: float = 0.0

        # Últimos snapshots recebidos
        self.current_packet: Optional[TelemetryPacket] = None
        self.current_physics: Optional[KinematicSnapshot] = None

        # Máquina de Estados Finita via transitions
        self.machine = Machine(
            model=self,
            states=CombatBrain.STATES,
            initial="PAUSA_SEGURA",
            auto_transitions=False,
        )
        self._setup_transitions()

    def _setup_transitions(self) -> None:
        # Transições Defensivas (permite chamada a partir de qualquer estado para máxima resiliência)
        self.machine.add_transition("trigger_parry", "*", "DEFESA_PARRY", after="on_enter_parry")
        self.machine.add_transition("trigger_special_defense", "*", "DEFESA_ESPECIAL", after="on_enter_special_defense")
        self.machine.add_transition("trigger_heavy_evade", "*", "ESQUIVA_PESADO", after="on_enter_heavy_evade")
        self.machine.add_transition("trigger_guard_break", "*", "QUEBRA_GUARDA", after="on_enter_guard_break")
        self.machine.add_transition("trigger_baiting", "*", "BAITING_SP", after="on_enter_baiting")

        # Transições Ofensivas
        self.machine.add_transition("trigger_punish", "*", "JANELA_DE_PUNICAO", after="on_enter_punish")
        self.machine.add_transition("trigger_combo_start", "*", "EXECUTANDO_COMBO", after="on_enter_combo")

        # Retornos de Estado e Segurança (permite retorno ao neutro a partir de qualquer estado, inclusive NEUTRO)
        self.machine.add_transition("return_neutral", "*", "NEUTRO", after="on_enter_neutral")
        self.machine.add_transition("trigger_safety_pause", "*", "PAUSA_SEGURA", after="on_enter_safety_pause")

    def update(self, packet: TelemetryPacket, physics: KinematicSnapshot) -> None:
        """
        Ciclo principal de avaliação de regras táticas (< 10 microssegundos).
        """
        self.current_packet = packet
        self.current_physics = physics
        now = time.perf_counter()

        # Atualiza a orientação de lado no dispositivo virtual
        self.device.set_side_inverted(physics.is_side_inverted)

        # ----------------------------------------------------------------------
        # Regra 0: Validação de Combate Ativo com Debounce
        # ----------------------------------------------------------------------
        is_combat_active = packet.in_fight and (packet.player.hp_pct > 0.05) and (packet.opponent.hp_pct > 0.05)

        if not is_combat_active:
            if self.state != "PAUSA_SEGURA":
                self.trigger_safety_pause()
            return
        elif self.state == "PAUSA_SEGURA":
            self.last_player_hp = packet.player.hp_pct
            self.prev_opp_mana = packet.opponent.mana
            self.device.reset_emergency_stop()
            if self.state != "NEUTRO":
                self.return_neutral()
            return

        # Durante a execução física de combo, isola o fluxo de decisões
        if self.state == "EXECUTANDO_COMBO":
            return

        # ----------------------------------------------------------------------
        # Regra 5: Guarda de Emergência por Queda Súbita de HP (Dano Real)
        # ----------------------------------------------------------------------
        hp_drop = self.last_player_hp - packet.player.hp_pct
        if hp_drop >= DAMAGE_THRESHOLD_HP_PCT:
            self.last_player_hp = packet.player.hp_pct
            self.damage_taken_time = now
            self.is_holding_guard = True
            self.device.engage_block()
            logger.warning(f"[Dano] Queda de HP de {hp_drop:.1f}%! Erguendo BLOQUEIO DE EMERGÊNCIA!")
            return

        if self.is_holding_guard and self.special_defense_until == 0.0 and self.damage_taken_time > 0:
            if (now - self.damage_taken_time) < EMERGENCY_GUARD_HOLD_SEC:
                return  # Sustenta bloqueio para absorver combo adversário
            else:
                self.device.release_block()
                self.device.dash_back()
                self.is_holding_guard = False
                self.damage_taken_time = 0.0
                if self.state != "NEUTRO":
                    self.return_neutral()
                return

        self.last_player_hp = packet.player.hp_pct

        # ----------------------------------------------------------------------
        # Regra 6: Disciplina Pós-Combo (Cooldown Anti-Whiff / Wake-Up Protection)
        # ----------------------------------------------------------------------
        if (now - self.last_combo_end_time) < self.post_combo_cooldown_sec and self.state == "NEUTRO":
            # Reage apenas se o oponente acordar disparando Especial ou Dash
            if packet.opp_state_id == 9 or (self.prev_opp_mana >= 1.0 and (self.prev_opp_mana - packet.opponent.mana) >= 0.8):
                self._handle_special_trigger()
            elif physics.action == PhysicalAction.DASH_FORWARD or packet.opp_state_id == 2:
                self.device.parry_pulse(TIMINGS.parry_pulse_ms)
            self.prev_opp_mana = packet.opponent.mana
            return

        # ----------------------------------------------------------------------
        # Regra 2: Alerta e Reação a Ataque Especial Inimigo (SP1 / SP2)
        # ----------------------------------------------------------------------
        is_special_firing = (
            packet.opp_state_id == 9 or
            (self.prev_opp_mana >= 1.0 and (self.prev_opp_mana - packet.opponent.mana) >= 0.8)
        )
        self.prev_opp_mana = packet.opponent.mana

        if is_special_firing:
            self._handle_special_trigger()
            return

        # Sustentação Defensiva durante Especial Inimigo
        if self.is_holding_guard and self.special_defense_until > 0:
            if packet.opp_state_id in (6, 8, 10) or packet.opponent.is_stunned:
                # Fim do especial confirmado em recuperação!
                self.device.release_block()
                self.is_holding_guard = False
                self.special_defense_until = 0.0
                self.trigger_punish()
                return
            elif now < self.special_defense_until:
                return  # Continua absorvendo projéteis
            else:
                self.device.release_block()
                self.is_holding_guard = False
                self.special_defense_until = 0.0
                self.return_neutral()
                return

        # ----------------------------------------------------------------------
        # Regra 1: Oponente Atordoado (Stun de Parry ou Relíquia) -> Punição
        # ----------------------------------------------------------------------
        if packet.opponent.is_stunned or packet.opp_state_id == 8:
            if self.state in ["NEUTRO", "DEFESA_PARRY", "BAITING_SP"]:
                self.trigger_punish()
                return

        # ----------------------------------------------------------------------
        # Regra 3: Oponente Carregando Golpe Pesado -> Esquiva Dupla
        # ----------------------------------------------------------------------
        if packet.opp_state_id == 5:
            if self.state in ["NEUTRO", "BAITING_SP"]:
                self.trigger_heavy_evade()
                return

        # ----------------------------------------------------------------------
        # Regra 1: Oponente Avançando em Dash Forward ou Atacando -> Aparar Preditivo (Parry)
        # ----------------------------------------------------------------------
        is_dash_approaching = (
            (physics.action == PhysicalAction.DASH_FORWARD and 80.0 <= physics.t_impact_ms <= 140.0) or
            (packet.opp_state_id == 2 and physics.dx <= 2.8) or
            (packet.opp_state_id == 4 and physics.dx <= 1.8)
        )
        if is_dash_approaching:
            if self.state in ["NEUTRO", "BAITING_SP"]:
                self.trigger_parry()
                return

        # ----------------------------------------------------------------------
        # Regra 3: Oponente Bloqueando -> Ataque Pesado (Quebra-Guarda)
        # ----------------------------------------------------------------------
        if packet.opponent.is_blocking or packet.opp_state_id == 1:
            if self.state in ["NEUTRO", "JANELA_DE_PUNICAO"]:
                self.trigger_guard_break()
                return

        # ----------------------------------------------------------------------
        # Regra 4: Risco de SP3 (Oponente com 2.8+ Barras) -> Baiting Preventivo
        # ----------------------------------------------------------------------
        if packet.opponent.mana >= SP3_DANGER_THRESHOLD:
            if self.state == "NEUTRO":
                self.trigger_baiting()
                return
        elif self.state == "BAITING_SP":
            self.return_neutral()

        # ----------------------------------------------------------------------
        # Regra 7: Oponente em Guarda Aberta ou Neutro -> Iniciativa Ofensiva
        # ----------------------------------------------------------------------
        if not packet.opponent.is_blocking:
            if physics.zone in (CombatRangeZone.CLOSE_INFIGHT, CombatRangeZone.DASH_PUNISH, CombatRangeZone.BAITING_MID):
                if self.state == "NEUTRO":
                    self.trigger_punish()
                    return
            elif physics.zone == CombatRangeZone.FAR_RESET:
                if self.state == "NEUTRO" and (now - self.last_combo_end_time > 0.15):
                    logger.info("[CombatBrain] Oponente recuado em FAR_RESET! Avançando para reconectar distância de combate...")
                    self.device.dash_medium()
                    self.last_combo_end_time = now
                    return

    # --------------------------------------------------------------------------
    # Callbacks de Transição de Estado
    # --------------------------------------------------------------------------
    def on_enter_parry(self) -> None:
        logger.info(f"[CombatBrain] Executando APARAR PREDITIVO (Parry {TIMINGS.parry_pulse_ms:.0f}ms)...")
        self.device.parry_pulse(TIMINGS.parry_pulse_ms)

    def on_enter_special_defense(self) -> None:
        logger.info("[CombatBrain] Especial detectado! Executando DESTREZA e Bloqueio Sustentado por 1.0s...")
        self.device.double_dash_back()
        self.device.engage_block()
        self.is_holding_guard = True
        self.special_defense_until = time.perf_counter() + SPECIAL_DEFENSE_HOLD_SEC

    def on_enter_heavy_evade(self) -> None:
        logger.info("[CombatBrain] Oponente armando Pesado! Executando ESQUIVA DUPLA...")
        self.device.double_dash_back()
        time.sleep(0.08)
        self.trigger_punish()

    def on_enter_guard_break(self) -> None:
        logger.info("[CombatBrain] Oponente bloqueando! Executando QUEBRA-GUARDA...")
        if self.current_physics and self.current_physics.dx > 1.6:
            self.device.dash_medium()
            time.sleep(0.02)
        self.device.hold_heavy()
        time.sleep(0.04)
        self.device.dash_back()
        self.last_combo_end_time = time.perf_counter()
        self.return_neutral()

    def on_enter_baiting(self) -> None:
        logger.info("[CombatBrain] Risco iminente de SP3! Iniciando BAITING...")
        self.device.engage_block()
        time.sleep(0.03)
        self.device.release_block()
        self.device.dash_back()

    def on_enter_punish(self) -> None:
        logger.info("[CombatBrain] Janela de punição confirmada! Disparando Combo Sequencer...")
        self.trigger_combo_start()
        cancel_into_sp = False
        extend_with_striker = False
        is_close = False

        if self.current_packet:
            cancel_into_sp = self.current_packet.player.mana >= 1.0
            extend_with_striker = self.current_packet.player.striker_ready
        if self.current_physics:
            is_close = self.current_physics.dx <= 1.6

        self.combo.execute_standard_5hit(
            cancel_into_sp=cancel_into_sp,
            extend_with_striker=extend_with_striker,
            stop_check=lambda: self.device.is_emergency_stopped,
            is_close_range=is_close,
        )
        self.last_combo_end_time = time.perf_counter()
        self.return_neutral()

    def on_enter_combo(self) -> None:
        pass

    def on_enter_safety_pause(self) -> None:
        logger.warning("[CombatBrain] Combate inativo. Parada de emergência e liberação de teclas.")
        self.is_holding_guard = False
        self.special_defense_until = 0.0
        self.damage_taken_time = 0.0
        self.device.emergency_stop()

    def on_enter_neutral(self) -> None:
        pass

    def _handle_special_trigger(self) -> None:
        if self.state != "DEFESA_ESPECIAL":
            try:
                self.trigger_special_defense()
            except Exception:
                pass
