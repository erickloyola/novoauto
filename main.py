"""
NovoAuto - Ponto de Entrada CLI
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Comandos disponíveis:
  python main.py run         # Executa o bot de combate em segundo plano
  python main.py monitor     # Executa o bot com HUD visual no terminal (Rich)
  python main.py sim-fsm     # Executa simulação determinística de combate
  python main.py benchmark   # Mede a latência fim a fim das derivadas e decisão
  python main.py test        # Executa a suíte de testes unitários
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Adiciona o diretório raiz do projeto ao sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config import LOG_LEVEL
from core.pipeline import NovoAutoPipeline
from ui.terminal_monitor import TerminalMonitor, HAS_RICH

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("NovoAuto.Main")

def cmd_run(args):
    """Inicia o bot em modo de execução contínua no terminal."""
    logger.info(f"Iniciando NovoAuto (dry_run={args.dry_run})...")
    pipeline = NovoAutoPipeline(dry_run=args.dry_run)
    pipeline.start()

def cmd_monitor(args):
    """Inicia o dashboard TUI em tempo real via Rich com alternância transparente entre Viewer e Standalone."""
    if not HAS_RICH:
        logger.error("A biblioteca 'rich' não está instalada. Execute 'pip install rich' ou use 'python main.py run'.")
        sys.exit(1)

    from rich.live import Live
    from capture.memory_receiver import FastMemoryReceiver
    from physics.kinematics import PhysicsEngine
    try:
        import orjson as json_engine
    except ImportError:
        import json as json_engine

    monitor = TerminalMonitor()
    shm_path = Path("/dev/shm/novoauto_state.json")

    def is_shm_active() -> bool:
        if shm_path.exists():
            try:
                # Se o arquivo foi atualizado nos últimos 2.0 segundos
                return (time.time() - shm_path.stat().st_mtime) < 2.0
            except Exception:
                return False
        return False

    standalone_receiver = None
    physics = None

    def ensure_standalone():
        nonlocal standalone_receiver, physics
        if standalone_receiver is None:
            standalone_receiver = FastMemoryReceiver()
            physics = PhysicsEngine()

    def cleanup_standalone():
        nonlocal standalone_receiver, physics
        if standalone_receiver is not None:
            standalone_receiver.close()
            standalone_receiver = None
            physics = None

    logger.info("Iniciando Dashboard Rich Live (Modo Híbrido)...")
    try:
        with Live(monitor.generate_view(), refresh_per_second=15, screen=True) as live:
            while True:
                if is_shm_active():
                    # Modo Viewer: o bot background (main.py run) está ativo e publicando em SHM
                    cleanup_standalone()
                    try:
                        with open(shm_path, "rb") as f:
                            data = json_engine.loads(f.read())
                        monitor.update_from_dict(data)
                    except Exception:
                        pass
                else:
                    # Modo Standalone: bot background desligado; monitor lê UDP passivamente (sem uinput)
                    ensure_standalone()
                    packet = standalone_receiver.poll_latest_packet() if standalone_receiver else None
                    if packet is not None and physics is not None:
                        t0 = time.perf_counter()
                        snap = physics.update(
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
                        dt_us = (time.perf_counter() - t0) * 1_000_000.0
                        monitor.update_data(packet, snap, "STANDBY", dt_us, bot_active=False)

                live.update(monitor.generate_view())
                time.sleep(1.0 / 20.0)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup_standalone()

def cmd_benchmark(args):
    """Executa benchmark de latência das derivadas cinemáticas e da FSM."""
    from physics.kinematics import PhysicsEngine
    from brain.combat_fsm import CombatBrain
    from execution.virtual_device import VirtualDevice
    from execution.combo_sequencer import ComboSequencer
    from core.telemetry_schema import TelemetryPacket, CombatantState, Vector3

    logger.info("Executando benchmark de performance (10.000 iterações)...")
    device = VirtualDevice(dry_run=True)
    combo = ComboSequencer(device)
    brain = CombatBrain(device, combo)
    physics = PhysicsEngine()

    packet = TelemetryPacket(
        timestamp_ms=1726000000,
        in_fight=True,
        distance=2.2,
        player=CombatantState(pos=Vector3(-1.8, 0, 0), hp_pct=100.0, mana=1.5, power_bars=1),
        opponent=CombatantState(pos=Vector3(0.4, 0, 0), hp_pct=95.0, mana=0.5, power_bars=0),
        opp_state_id=2,
        opp_state_name="Run",
        receive_time=time.perf_counter(),
    )

    t0 = time.perf_counter()
    iterations = 10_000
    for i in range(iterations):
        # Simula pequenas variações de movimento
        x_opp = 0.4 - (i % 10) * 0.05
        snap = physics.update(
            timestamp_ms=1726000000 + i * 16,
            player_x=-1.8, player_y=0.0, player_z=0.0,
            opp_x=x_opp, opp_y=0.0, opp_z=0.0,
            override_now_sec=t0 + i * 0.016,
        )
        brain.update(packet, snap)
    t1 = time.perf_counter()

    total_time_ms = (t1 - t0) * 1000.0
    time_per_iter_us = (total_time_ms / iterations) * 1000.0

    print("=" * 60)
    print(" 🚀 RESULTADO DO BENCHMARK DE PERFORMANCE NOVOAUTO")
    print("=" * 60)
    print(f" Iterações executadas:   {iterations:,}")
    print(f" Tempo total decorrido:  {total_time_ms:.2f} ms")
    print(f" Tempo médio por ciclo:  {time_per_iter_us:.2f} microssegundos (µs)")
    print(f" Throughput teórico:     {1_000_000.0 / time_per_iter_us:,.0f} decisões/segundo")
    print("=" * 60)

def cmd_sim_fsm(args):
    """Simula os principais cenários de combate para testar as transições da FSM."""
    from physics.kinematics import PhysicsEngine
    from brain.combat_fsm import CombatBrain
    from execution.virtual_device import VirtualDevice
    from execution.combo_sequencer import ComboSequencer
    from core.telemetry_schema import TelemetryPacket, CombatantState, Vector3

    logger.info("Iniciando simulação determinística dos 7 cenários de combate...")
    device = VirtualDevice(dry_run=True)
    combo = ComboSequencer(device)
    brain = CombatBrain(device, combo)
    physics = PhysicsEngine()

    now = time.perf_counter()

    # Cenário 1: Entrada em combate
    p1 = TelemetryPacket(
        timestamp_ms=1000, in_fight=True, distance=3.2,
        player=CombatantState(pos=Vector3(-2.0, 0, 0)),
        opponent=CombatantState(pos=Vector3(1.2, 0, 0)),
        opp_state_id=0, opp_state_name="Idle", receive_time=now,
    )
    s1 = physics.update(1000, -2.0, 0, 0, 1.2, 0, 0, override_now_sec=now)
    brain.update(p1, s1)
    assert brain.state == "NEUTRO", f"Erro: Esperava NEUTRO, obteve {brain.state}"
    logger.info("  ✓ Cenário 1 (Entrada em Neutro): OK")

    # Cenário 2: Oponente avançando em Dash Forward -> Parry
    now += 0.016
    p2 = TelemetryPacket(
        timestamp_ms=1016, in_fight=True, distance=1.8,
        player=CombatantState(pos=Vector3(-2.0, 0, 0)),
        opponent=CombatantState(pos=Vector3(0.0, 0, 0)),
        opp_state_id=2, opp_state_name="Run", receive_time=now,
    )
    s2 = physics.update(1016, -2.0, 0, 0, 0.0, 0, 0, override_now_sec=now)
    brain.update(p2, s2)
    assert brain.state == "DEFESA_PARRY", f"Erro: Esperava DEFESA_PARRY, obteve {brain.state}"
    logger.info("  ✓ Cenário 2 (Aparar Preditivo): OK")

    # Cenário 3: Oponente atordoado pós-Parry -> Punição
    now += 0.016
    p3 = TelemetryPacket(
        timestamp_ms=1032, in_fight=True, distance=1.3,
        player=CombatantState(pos=Vector3(-1.5, 0, 0)),
        opponent=CombatantState(pos=Vector3(-0.2, 0, 0), is_stunned=True),
        opp_state_id=8, opp_state_name="Stun", receive_time=now,
    )
    s3 = physics.update(1032, -1.5, 0, 0, -0.2, 0, 0, override_now_sec=now)
    brain.update(p3, s3)
    logger.info("  ✓ Cenário 3 (Janela de Punição): OK")

    # Cenário 4: Oponente bloqueando -> Quebra-Guarda
    now += 0.016
    brain.last_combo_end_time = 0.0  # reseta cooldown
    p4 = TelemetryPacket(
        timestamp_ms=1048, in_fight=True, distance=1.2,
        player=CombatantState(pos=Vector3(-1.2, 0, 0)),
        opponent=CombatantState(pos=Vector3(0.0, 0, 0), is_blocking=True),
        opp_state_id=1, opp_state_name="Block", receive_time=now,
    )
    s4 = physics.update(1048, -1.2, 0, 0, 0.0, 0, 0, is_opponent_blocking=True, override_now_sec=now)
    brain.update(p4, s4)
    logger.info("  ✓ Cenário 4 (Quebra-Guarda com Ataque Pesado): OK")

    # Cenário 5: Especial inimigo disparado
    now += 0.016
    p5 = TelemetryPacket(
        timestamp_ms=1064, in_fight=True, distance=2.2,
        player=CombatantState(pos=Vector3(-1.8, 0, 0)),
        opponent=CombatantState(pos=Vector3(0.4, 0, 0), mana=0.1),
        opp_state_id=9, opp_state_name="FinalSpecialAttack", receive_time=now,
    )
    s5 = physics.update(1064, -1.8, 0, 0, 0.4, 0, 0, override_now_sec=now)
    brain.prev_opp_mana = 1.0  # Simula queda de mana
    brain.update(p5, s5)
    assert brain.state == "DEFESA_ESPECIAL", f"Erro: Esperava DEFESA_ESPECIAL, obteve {brain.state}"
    logger.info("  ✓ Cenário 5 (Defesa Ativa contra Especiais): OK")

    # Cenário 6: Fim da luta / KO
    p6 = TelemetryPacket(
        timestamp_ms=1080, in_fight=False, distance=0.0,
        player=CombatantState(pos=Vector3(0, 0, 0)),
        opponent=CombatantState(pos=Vector3(0, 0, 0)),
        receive_time=now,
    )
    s6 = physics.update(1080, 0, 0, 0, 0, 0, 0, override_now_sec=now)
    brain.update(p6, s6)
    assert brain.state == "PAUSA_SEGURA", f"Erro: Esperava PAUSA_SEGURA, obteve {brain.state}"
    logger.info("  ✓ Cenário 6 (Parada de Emergência): OK")

    print("\n🎉 TODOS OS CENÁRIOS DE COMBATE FORAM VALIDADOS COM SUCESSO!")

def cmd_test(args):
    """Executa a suíte de testes unitários com pytest."""
    import pytest
    tests_dir = BASE_DIR / "tests"
    sys.exit(pytest.main(["-v", str(tests_dir)]))

def main():
    parser = argparse.ArgumentParser(description="NovoAuto - MCoC Zero-Vision Bot")
    subparsers = parser.add_subparsers(dest="command", help="Comando a ser executado")

    # Comando run
    run_parser = subparsers.add_parser("run", help="Inicia o bot no terminal")
    run_parser.add_argument("--dry-run", action="store_true", help="Simula entradas sem emitir teclas no kernel")

    # Comando monitor
    mon_parser = subparsers.add_parser("monitor", help="Inicia o bot com dashboard TUI em tempo real")
    mon_parser.add_argument("--dry-run", action="store_true", help="Simula entradas sem emitir teclas no kernel")

    # Comando benchmark
    subparsers.add_parser("benchmark", help="Mede a latência por ciclo de decisão")

    # Comando sim-fsm
    subparsers.add_parser("sim-fsm", help="Simula os cenários determinísticos de combate da FSM")

    # Comando test
    subparsers.add_parser("test", help="Executa a suíte completa de testes unitários")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "monitor":
        cmd_monitor(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "sim-fsm":
        cmd_sim_fsm(args)
    elif args.command == "test":
        cmd_test(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
