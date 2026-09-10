"""
NovoAuto - Humanizador Biológico Estocástico
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Gera micro-variações temporais gaussianas (jitter biológico) para impedir padrões
matemáticos fixos detectáveis por mecanismos anti-cheat.
"""

import random
import time
from config import ENABLE_BIOLOGICAL_JITTER

def get_jittered_ms(base_ms: float, jitter_ms: float, min_ms: float = 0.0) -> float:
    """Calcula um intervalo em milissegundos. Se jitter desativado, retorna exatamente base_ms."""
    if not ENABLE_BIOLOGICAL_JITTER or jitter_ms <= 0.0:
        return max(min_ms, base_ms)
    val = random.gauss(base_ms, jitter_ms)
    return max(min_ms, val)

def sleep_jitter(base_ms: float, jitter_ms: float, min_ms: float = 0.0) -> None:
    """Pausa a execução aplicando jitter gaussiano se habilitado, ou o delay base fixo."""
    duration_ms = get_jittered_ms(base_ms, jitter_ms, min_ms=min_ms)
    if duration_ms > 0.0:
        time.sleep(duration_ms / 1000.0)

