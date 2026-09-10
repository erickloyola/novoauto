"""
NovoAuto - Receptor Assíncrono UDP de Telemetria de Memória
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Lê datagramas UDP locais (127.0.0.1:5555) em modo não-bloqueante,
drenando buffers antigos para garantir latência < 0.1ms e zero Head-of-Line Blocking.
"""

import logging
import socket
import time
from typing import Optional

try:
    import orjson as json_engine
    HAS_ORJSON = True
except ImportError:
    import json as json_engine
    HAS_ORJSON = False

from config import UDP_HOST, UDP_PORT, UDP_BUFFER_SIZE, UDP_LIVENESS_TIMEOUT_SEC
from core.telemetry_schema import TelemetryPacket, parse_telemetry_dict

logger = logging.getLogger("NovoAuto.Receiver")

class FastMemoryReceiver:
    """
    Receptor UDP de alta velocidade para o NovoAuto.
    """
    def __init__(self, host: str = UDP_HOST, port: int = UDP_PORT):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.last_packet_time: float = 0.0
        self.last_packet: Optional[TelemetryPacket] = None
        self.packet_count: int = 0
        self._init_socket()

    def _init_socket(self) -> None:
        """Inicializa o socket UDP não-bloqueante."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Define buffer reduzido para minimizar acúmulo de pacotes obsoletos
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_BUFFER_SIZE)
            self.sock.bind((self.host, self.port))
            self.sock.setblocking(False)
            logger.info(f"[Receiver] Socket UDP aberto em {self.host}:{self.port} (orjson={HAS_ORJSON})")
        except Exception as e:
            logger.error(f"[Receiver] Falha ao abrir socket UDP em {self.host}:{self.port}: {e}")
            self.sock = None

    def poll_latest_packet(self) -> Optional[TelemetryPacket]:
        """
        Drena todos os pacotes pendentes no buffer e retorna APENAS o mais recente.
        Se nenhum pacote novo chegou, retorna None.
        """
        if not self.sock:
            return None

        latest_raw_bytes = None
        recv_time = time.perf_counter()

        while True:
            try:
                data, _ = self.sock.recvfrom(2048)
                latest_raw_bytes = data
                self.packet_count += 1
            except BlockingIOError:
                break
            except Exception as e:
                logger.debug(f"[Receiver] Exceção na leitura do socket: {e}")
                break

        if latest_raw_bytes is None:
            return None

        try:
            if HAS_ORJSON:
                raw_dict = json_engine.loads(latest_raw_bytes)
            else:
                raw_dict = json_engine.loads(latest_raw_bytes.decode("utf-8", errors="ignore"))

            packet = parse_telemetry_dict(raw_dict, recv_time=recv_time)
            self.last_packet = packet
            self.last_packet_time = recv_time
            return packet
        except Exception as e:
            logger.debug(f"[Receiver] Falha ao decodificar JSON do pacote: {e}")
            return None

    def is_connected(self) -> bool:
        """Retorna True se recebeu pacote válido nos últimos UDP_LIVENESS_TIMEOUT_SEC segundos."""
        if self.last_packet_time <= 0.0:
            return False
        return (time.perf_counter() - self.last_packet_time) <= UDP_LIVENESS_TIMEOUT_SEC

    def close(self) -> None:
        """Fecha o socket de rede de forma limpa."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
            logger.info("[Receiver] Socket UDP encerrado.")
