"""
NovoAuto - Emulador de Periférico no Kernel Linux (/dev/uinput via python-evdev)
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Emula teclado virtual diretamente no kernel do Linux com latência praticamente nula (< 0.5ms).
Possui fallback para modo simulado (dry-run), suporte à inversão de lados e travas de segurança.
"""

import logging
import time
from typing import Optional, Set

try:
    import evdev
    from evdev import ecodes
    HAS_EVDEV = True
except ImportError:
    HAS_EVDEV = False
    ecodes = None

from config import (
    TIMINGS,
    GameAction,
    InputScheme,
    ACTION_KEYS,
    INVERTED_ACTION_KEYS,
)
from execution.humanizer import sleep_jitter

logger = logging.getLogger("NovoAuto.VirtualDevice")

class VirtualDevice:
    """
    Controlador virtual de entradas para MCoC.
    """
    def __init__(
        self,
        scheme: InputScheme = InputScheme.WASD,
        device_name: str = "NovoAuto-MCoC-Virtual-Controller",
        dry_run: bool = False,
    ):
        self.scheme = scheme
        self.device_name = device_name
        self.dry_run = dry_run or not HAS_EVDEV
        self.uinput: Optional[Any] = None
        self.active_keys: Set[int] = set()
        self.is_emergency_stopped: bool = False
        self.is_side_inverted: bool = False

        if not self.dry_run:
            self._init_uinput()

    def _init_uinput(self) -> None:
        """Inicializa o periférico virtual no subsistema /dev/uinput."""
        try:
            cap = {
                ecodes.EV_KEY: [
                    ecodes.KEY_W,
                    ecodes.KEY_A,
                    ecodes.KEY_S,
                    ecodes.KEY_D,
                    ecodes.KEY_SPACE,
                    ecodes.KEY_LEFTSHIFT,
                    ecodes.KEY_RIGHTSHIFT,
                    ecodes.KEY_LEFTCTRL,
                    ecodes.KEY_UP,
                    ecodes.KEY_DOWN,
                    ecodes.KEY_LEFT,
                    ecodes.KEY_RIGHT,
                    ecodes.KEY_ESC,
                ]
            }
            self.uinput = evdev.UInput(cap, name=self.device_name, version=0x3)
            logger.info(f"[VirtualDevice] Periférico '{self.device_name}' registrado no kernel via /dev/uinput.")
        except Exception as e:
            logger.warning(f"[VirtualDevice] Acesso a /dev/uinput falhou ({e}). Ativando modo simulado DRY-RUN.")
            self.dry_run = True

    def set_side_inverted(self, inverted: bool) -> None:
        """Define se o jogador está invertido no ringue (lado direito)."""
        self.is_side_inverted = inverted

    def _get_key(self, action: GameAction) -> int:
        """Retorna o keycode correto considerando esquema e eventual inversão de lado."""
        table = INVERTED_ACTION_KEYS if self.is_side_inverted else ACTION_KEYS
        return table[self.scheme][action]

    def press_key(self, keycode: int) -> None:
        """Pressiona uma tecla no teclado virtual do kernel."""
        if self.is_emergency_stopped:
            return
        if self.dry_run or not self.uinput:
            logger.debug(f"[Input DRY-RUN] Key Down: {keycode}")
            self.active_keys.add(keycode)
            return

        self.uinput.write(ecodes.EV_KEY, keycode, 1)  # 1 = Down
        self.uinput.syn()
        self.active_keys.add(keycode)

    def release_key(self, keycode: int) -> None:
        """Solta uma tecla no teclado virtual do kernel."""
        if self.dry_run or not self.uinput:
            logger.debug(f"[Input DRY-RUN] Key Up: {keycode}")
            self.active_keys.discard(keycode)
            return

        self.uinput.write(ecodes.EV_KEY, keycode, 0)  # 0 = Up
        self.uinput.syn()
        self.active_keys.discard(keycode)

    # --------------------------------------------------------------------------
    # Ações Elementares de Combate
    # --------------------------------------------------------------------------
    def tap_light(self) -> None:
        """Executa Ataque Leve (Light - L)."""
        key = self._get_key(GameAction.LIGHT_ATTACK)
        self.press_key(key)
        sleep_jitter(TIMINGS.light_tap_ms, TIMINGS.light_tap_jitter_ms)
        self.release_key(key)

    def dash_medium(self) -> None:
        """Executa Ataque Médio / Dash Frente (Medium - M)."""
        key = self._get_key(GameAction.MEDIUM_ATTACK)
        self.press_key(key)
        sleep_jitter(TIMINGS.medium_dash_ms, TIMINGS.medium_dash_jitter_ms)
        self.release_key(key)

    def dash_back(self) -> None:
        """Executa Recuo / Destreza (Dash Back)."""
        key = self._get_key(GameAction.DODGE_BACK)
        self.press_key(key)
        sleep_jitter(TIMINGS.dexterity_dash_ms, TIMINGS.dexterity_dash_jitter_ms)
        self.release_key(key)

    def double_dash_back(self) -> None:
        """Executa Recuo Duplo rápido (Evasão de Ataque Pesado ou Especial)."""
        self.dash_back()
        sleep_jitter(60.0, 10.0)
        self.dash_back()

    def hold_heavy(self, duration_ms: float = TIMINGS.heavy_hold_ms) -> None:
        """Executa Ataque Pesado (Heavy - H): Segura e solta."""
        key = self._get_key(GameAction.HEAVY_ATTACK)
        self.press_key(key)
        sleep_jitter(duration_ms, TIMINGS.heavy_hold_jitter_ms)
        self.release_key(key)

    def engage_block(self) -> None:
        """Ergue a guarda / bloqueio contínuo."""
        key = self._get_key(GameAction.BLOCK)
        self.press_key(key)

    def release_block(self) -> None:
        """Abaixa a guarda / bloqueio."""
        key = self._get_key(GameAction.BLOCK)
        self.release_key(key)

    def parry_pulse(self, duration_ms: float = TIMINGS.parry_pulse_ms) -> None:
        """Executa pulso cirúrgico de Aparar (Parry)."""
        key = self._get_key(GameAction.PARRY)
        self.press_key(key)
        sleep_jitter(duration_ms, TIMINGS.parry_pulse_jitter_ms)
        self.release_key(key)

    def trigger_special(self) -> None:
        """Dispara Ataque Especial (SP1 / SP2 / SP3)."""
        key = self._get_key(GameAction.SPECIAL_ATTACK)
        self.press_key(key)
        sleep_jitter(65.0, 8.0)
        self.release_key(key)

    def trigger_striker(self) -> None:
        """Aciona a Relíquia / Striker para estender combo."""
        key = self._get_key(GameAction.STRIKER_ASSIST)
        self.press_key(key)
        sleep_jitter(60.0, 8.0)
        self.release_key(key)

    # --------------------------------------------------------------------------
    # Mecanismos de Segurança e Desarme
    # --------------------------------------------------------------------------
    def release_all(self) -> None:
        """Libera imediatamente todas as teclas pressionadas."""
        keys = list(self.active_keys)
        for k in keys:
            self.release_key(k)
        self.active_keys.clear()

    def emergency_stop(self) -> None:
        """Trava o dispositivo em segurança e solta qualquer tecla presa."""
        self.is_emergency_stopped = True
        self.release_all()
        logger.warning("[VirtualDevice] PARADA DE EMERGÊNCIA! Entradas bloqueadas e teclas soltas.")

    def reset_emergency_stop(self) -> None:
        """Desativa a trava de emergência."""
        if self.is_emergency_stopped:
            self.is_emergency_stopped = False
            logger.info("[VirtualDevice] Trava de emergência desativada. Operação normal.")

    def close(self) -> None:
        """Encerra e destrói o dispositivo virtual."""
        self.release_all()
        if self.uinput:
            try:
                self.uinput.close()
            except Exception:
                pass
            self.uinput = None
