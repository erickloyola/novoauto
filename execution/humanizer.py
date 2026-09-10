"""
NovoAuto - Humanizador Biológico Estocástico
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Gera micro-variações temporais gaussianas (jitter biológico) para impedir padrões
matemáticos fixos detectáveis por mecanismos anti-cheat.
"""

import random
import time

def get_jittered_ms(base_ms: float, jitter_ms: float, min_ms: float = 5.0) -> float:
    """Calcula um intervalo em milissegundos com distribuição gaussiana."""
    val = random.gauss(base_ms, jitter_ms)
    return max(min_ms, val)

def sleep_jitter(base_ms: float, jitter_ms: float, min_ms: float = 5.0) -> None:
    """Pausa a execução aplicando jitter gaussiano seguro."""
    delay_sec = get_jittered_ms(base_ms, jitter_ms, min_ms=min_ms) / 1000.0
    time.sleep(delay_sec)
