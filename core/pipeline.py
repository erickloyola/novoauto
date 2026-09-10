"""
NovoAuto - Loop Principal Reativo de Alta Frequência (Pipeline)
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Orquestra ingestão de UDP, computação cinemática e decisões da FSM com latência < 0.1ms.
"""

import logging
import os
import signal
import shutil
import subprocess
import sys
import time
from typing import Optional, Callable

try:
    import orjson as json_engine
    HAS_ORJSON = True
except ImportError:
    import json as json_engine
    HAS_ORJSON = False

from capture.memory_receiver import FastMemoryReceiver
from physics.kinematics import PhysicsEngine, KinematicSnapshot
from execution.virtual_device import VirtualDevice
from execution.combo_sequencer import ComboSequencer
from brain.combat_fsm import CombatBrain
from core.telemetry_schema import TelemetryPacket

logger = logging.getLogger("NovoAuto.Pipeline")

class NovoAutoPipeline:
    """
    Loop principal de combate de latência ultrabaixa.
    """
    def __init__(
        self,
        dry_run: bool = False,
        on_packet_callback: Optional[Callable[[TelemetryPacket, KinematicSnapshot, str, float], None]] = None,
    ):
        self.dry_run = dry_run
        self.on_packet_callback = on_packet_callback
        self.running = False

        # Componentes do Pipeline
        self.receiver = FastMemoryReceiver()
        self.physics = PhysicsEngine()
        self.device = VirtualDevice(dry_run=self.dry_run)
        self.combo = ComboSequencer(self.device)
        self.brain = CombatBrain(self.device, self.combo)

        # Métricas de Desempenho
        self.loop_count: int = 0
        self.last_cycle_us: float = 0.0
        self.avg_cycle_us: float = 0.0
        self._was_in_fight: bool = False

        self._setup_signals()

    def _ensure_game_focus(self) -> None:
        """Garante que a janela do jogo esteja em foco no ambiente Hyprland para receber os inputs do kernel."""
        if shutil.which("hyprctl"):
            try:
                subprocess.run(
                    ["hyprctl", "dispatch", "focuswindow", "class:(steam_app_3127280|champions|Champions)"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=0.1,
                )
            except Exception:
                pass

    def _setup_signals(self) -> None:
        def _sig_handler(sig, frame):
            logger.info(f"[Pipeline] Sinal {sig} recebido. Encerrando com segurança...")
            self.stop()
        try:
            signal.signal(signal.SIGINT, _sig_handler)
            signal.signal(signal.SIGTERM, _sig_handler)
        except Exception:
            pass

    def start(self) -> None:
        """Inicia o loop contínuo de percepção e combate."""
        self.running = True
        logger.info("[Pipeline] Pipeline NovoAuto INICIADO.")

        total_time_us = 0.0
        processed_packets = 0

        last_heartbeat = 0.0
        try:
            while self.running:
                t0 = time.perf_counter()

                # 1. Ingestão não-bloqueante (drena pacotes acumulados)
                packet = self.receiver.poll_latest_packet()

                if packet is not None:
                    if packet.in_fight and not self._was_in_fight:
                        self._ensure_game_focus()
                    self._was_in_fight = packet.in_fight

                    # 2. Computação Cinemática Vetorial (< 5 microssegundos)
                    snapshot = self.physics.update(
                        timestamp_ms=packet.timestamp_ms,
                        player_x=packet.player.pos.x,
                        player_y=packet.player.pos.y,
                        player_z=packet.player.pos.z,
                        opp_x=packet.opponent.pos.x,
                        opp_y=packet.opponent.pos.y,
                        opp_z=packet.opponent.pos.z,
                        is_opponent_blocking=packet.opponent.is_blocking,
                        raw_distance=packet.distance,
                    )

                    # 3. Decisão da FSM (< 10 microssegundos)
                    try:
                        self.brain.update(packet, snapshot)
                    except Exception as e:
                        logger.error(f"[Pipeline] Erro inesperado no Brain FSM: {e}", exc_info=True)

                    t1 = time.perf_counter()
                    dt_us = (t1 - t0) * 1_000_000.0
                    self.last_cycle_us = dt_us
                    total_time_us += dt_us
                    processed_packets += 1
                    self.avg_cycle_us = total_time_us / processed_packets

                    if self.on_packet_callback:
                        try:
                            self.on_packet_callback(packet, snapshot, self.brain.state, self.last_cycle_us)
                        except Exception as e:
                            logger.error(f"[Pipeline] Erro no callback de pacote: {e}")

                    self._publish_shm_state(packet, snapshot)

                else:
                    now_sec = time.perf_counter()
                    if (now_sec - last_heartbeat) >= 0.1:
                        last_heartbeat = now_sec
                        self._publish_shm_heartbeat()

                    # Se não há combate ativo ou sem pacote recente
                    if not self.receiver.is_connected() and self.brain.state != "PAUSA_SEGURA":
                        self.brain.trigger_safety_pause()
                    # Micro-pausa para evitar consumo desnecessário de CPU em neutro ocioso
                    time.sleep(0.0005)

                self.loop_count += 1

        except KeyboardInterrupt:
            logger.info("[Pipeline] Interrupção por teclado.")
        finally:
            self.stop()

    def _publish_shm_heartbeat(self) -> None:
        """Mantém /dev/shm ativo para o monitor TUI saber que o bot está ligado mesmo entre lutas."""
        try:
            state = {
                "timestamp": time.time(),
                "pid": os.getpid(),
                "in_fight": False,
                "distance": 0.0,
                "player": None,
                "opponent": None,
                "opp_state_id": 0,
                "opp_state_name": "Idle",
                "player_state_id": 0,
                "player_state_name": "Idle",
                "physics": None,
                "fsm_state": self.brain.state,
                "latency_us": self.last_cycle_us,
                "bot_active": not self.dry_run,
            }
            tmp_file = "/dev/shm/novoauto_state.tmp"
            target_file = "/dev/shm/novoauto_state.json"
            if HAS_ORJSON:
                raw_bytes = json_engine.dumps(state)
            else:
                raw_bytes = json_engine.dumps(state).encode("utf-8")
            with open(tmp_file, "wb") as f:
                f.write(raw_bytes)
            os.replace(tmp_file, target_file)
        except Exception:
            pass

    def _publish_shm_state(self, packet: TelemetryPacket, snapshot: KinematicSnapshot) -> None:
        """Publica estado consolidado em /dev/shm para sincronização atômica e sem colisões com o monitor TUI."""
        try:
            state = {
                "timestamp": time.time(),
                "pid": os.getpid(),
                "in_fight": packet.in_fight,
                "distance": packet.distance,
                "player": {
                    "pos": {"x": packet.player.pos.x, "y": packet.player.pos.y, "z": packet.player.pos.z},
                    "hp_pct": packet.player.hp_pct,
                    "mana": packet.player.mana,
                    "power_bars": packet.player.power_bars,
                    "is_blocking": packet.player.is_blocking,
                    "is_stunned": packet.player.is_stunned,
                    "striker_ready": packet.player.striker_ready,
                },
                "opponent": {
                    "pos": {"x": packet.opponent.pos.x, "y": packet.opponent.pos.y, "z": packet.opponent.pos.z},
                    "hp_pct": packet.opponent.hp_pct,
                    "mana": packet.opponent.mana,
                    "power_bars": packet.opponent.power_bars,
                    "is_blocking": packet.opponent.is_blocking,
                    "is_stunned": packet.opponent.is_stunned,
                },
                "opp_state_id": packet.opp_state_id,
                "opp_state_name": packet.opp_state_name,
                "player_state_id": packet.player_state_id,
                "player_state_name": packet.player_state_name,
                "physics": {
                    "dx": snapshot.dx,
                    "d3d": snapshot.d3d,
                    "v_player": snapshot.v_player,
                    "v_opp": snapshot.v_opp,
                    "v_rel": snapshot.v_rel,
                    "a_opp": snapshot.a_opp,
                    "action": snapshot.action.name,
                    "zone": snapshot.zone.name,
                    "t_impact_ms": snapshot.t_impact_ms,
                    "is_side_inverted": snapshot.is_side_inverted,
                } if snapshot else None,
                "fsm_state": self.brain.state,
                "latency_us": self.last_cycle_us,
                "bot_active": not self.dry_run,
            }
            tmp_file = "/dev/shm/novoauto_state.tmp"
            target_file = "/dev/shm/novoauto_state.json"
            if HAS_ORJSON:
                raw_bytes = json_engine.dumps(state)
            else:
                raw_bytes = json_engine.dumps(state).encode("utf-8")
            with open(tmp_file, "wb") as f:
                f.write(raw_bytes)
            os.replace(tmp_file, target_file)
        except Exception:
            pass

    def stop(self) -> None:
        """Parada segura do motor."""
        if not self.running:
            return
        self.running = False
        logger.info("[Pipeline] Encerrando componentes...")
        self.brain.trigger_safety_pause()
        self.device.emergency_stop()
        self.device.close()
        self.receiver.close()
        try:
            if os.path.exists("/dev/shm/novoauto_state.json"):
                os.remove("/dev/shm/novoauto_state.json")
        except Exception:
            pass
        logger.info("[Pipeline] Pipeline NovoAuto finalizado com sucesso.")
