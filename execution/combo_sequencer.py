"""
NovoAuto - Sequenciador e Cancelamento de Combos
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Executa a cadeia universal de 5 acertos (M-L-L-L-M) com respeito estrito aos frames de recuperação,
cancelamento instantâneo em Ataque Especial (SP1/SP2) e extensão via Relíquia/Striker.
"""

import logging
import time
from typing import Callable, Optional

from config import TIMINGS
from execution.humanizer import sleep_jitter
from execution.virtual_device import VirtualDevice

logger = logging.getLogger("NovoAuto.Combo")

class ComboSequencer:
    """
    Controlador de encadeamento rítmico de ataques.
    """
    def __init__(self, virtual_device: VirtualDevice):
        self.device = virtual_device
        self.is_running = False

    def _wait_between_hits(self) -> None:
        """Pausa rítmica humanizada entre os acertos da cadeia."""
        sleep_jitter(TIMINGS.combo_hit_interval_ms, TIMINGS.combo_hit_interval_jitter_ms)

    def execute_standard_5hit(
        self,
        cancel_into_sp: bool = False,
        extend_with_striker: bool = False,
        stop_check: Optional[Callable[[], bool]] = None,
        is_close_range: bool = False,
    ) -> bool:
        """
        Executa a sequência de 5 acertos universal: M -> L -> L -> L -> M.
        Opcionalmente estende com Striker ou cancela no 5º golpe com Ataque Especial.
        """
        self.is_running = True
        logger.info(f"[Combo] Iniciando M-L-L-L-M (close_range={is_close_range}, sp={cancel_into_sp}, striker={extend_with_striker})...")

        try:
            # 1. Primeiro Hit: Médio (Dash-in de aproximação ou Médio à queima-roupa)
            if stop_check and stop_check():
                return False
            self.device.dash_medium()
            if is_close_range:
                sleep_jitter(110.0, 10.0)
            else:
                sleep_jitter(TIMINGS.dash_in_recovery_ms, TIMINGS.dash_in_recovery_jitter_ms)

            # 2. Segundo Hit: Leve
            if stop_check and stop_check():
                return False
            self.device.tap_light()
            self._wait_between_hits()

            # 3. Terceiro Hit: Leve
            if stop_check and stop_check():
                return False
            self.device.tap_light()
            self._wait_between_hits()

            # 4. Quarto Hit: Leve
            if stop_check and stop_check():
                return False
            self.device.tap_light()
            self._wait_between_hits()

            # 5. Quinto Hit: Médio Finalizador
            if stop_check and stop_check():
                return False
            self.device.dash_medium()

            # Conclusões com Striker ou Especial
            if extend_with_striker:
                time.sleep(0.045)
                logger.info("[Combo] Acionando STRIKER para extensão de combo!")
                self.device.trigger_striker()
                time.sleep(0.30)
                if cancel_into_sp:
                    logger.info("[Combo] Cancelando recuperação pós-striker em ATAQUE ESPECIAL!")
                    self.device.trigger_special()
                    time.sleep(0.25)
                else:
                    self.device.dash_back()
            elif cancel_into_sp:
                time.sleep(0.045)  # Janela de cancelamento do 5º hit
                logger.info("[Combo] Cancelando recuperação em ATAQUE ESPECIAL!")
                self.device.trigger_special()
                time.sleep(0.25)
            else:
                # Recuo defensivo padrão pós-combo para reset seguro de neutro
                time.sleep(0.16)
                self.device.dash_back()

            logger.info("[Combo] Sequência 5x concluída com sucesso.")
            return True

        finally:
            self.is_running = False

    def execute_heavy_finisher_variation(self, stop_check: Optional[Callable[[], bool]] = None) -> bool:
        """
        Executa a variação M -> L -> L -> L -> H (Pesado no final).
        """
        self.is_running = True
        logger.info("[Combo] Iniciando sequência M-L-L-L-H...")

        try:
            if stop_check and stop_check(): return False
            self.device.dash_medium()
            self._wait_between_hits()

            if stop_check and stop_check(): return False
            self.device.tap_light()
            self._wait_between_hits()

            if stop_check and stop_check(): return False
            self.device.tap_light()
            self._wait_between_hits()

            if stop_check and stop_check(): return False
            self.device.tap_light()
            self._wait_between_hits()

            if stop_check and stop_check(): return False
            self.device.hold_heavy()

            time.sleep(0.15)
            self.device.dash_back()
            return True

        finally:
            self.is_running = False
