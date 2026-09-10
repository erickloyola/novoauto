"""
NovoAuto - Dashboard de Monitoramento em Tempo Real no Terminal (TUI)
Marvel Contest of Champions (MCoC) - Zero-Vision Architecture

Exibe métricas de telemetria, derivadas de física, estado da FSM e latência de ciclo (< 0.1ms)
utilizando a biblioteca Rich Live no terminal sem sobrecarga gráfica.
"""

import time
from typing import Optional

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from core.telemetry_schema import TelemetryPacket, parse_telemetry_dict
from physics.kinematics import KinematicSnapshot, PhysicalAction, CombatRangeZone

class TerminalMonitor:
    """
    Monitor de combate em tempo real via terminal.
    """
    def __init__(self):
        self.console = Console() if HAS_RICH else None
        self.last_packet: Optional[TelemetryPacket] = None
        self.last_physics: Optional[KinematicSnapshot] = None
        self.last_state: str = "PAUSA_SEGURA"
        self.last_latency_us: float = 0.0
        self.bot_active: bool = False

    def update_data(
        self,
        packet: TelemetryPacket,
        physics: KinematicSnapshot,
        fsm_state: str,
        latency_us: float,
        bot_active: bool = False,
    ) -> None:
        self.last_packet = packet
        self.last_physics = physics
        self.last_state = fsm_state
        self.last_latency_us = latency_us
        self.bot_active = bot_active

    def update_from_dict(self, data: dict) -> None:
        try:
            self.last_packet = parse_telemetry_dict(data)
            phy_data = data.get("physics")
            if phy_data and isinstance(phy_data, dict):
                act_name = phy_data.get("action", "NEUTRAL")
                zone_name = phy_data.get("zone", "FAR_RESET")
                action_enum = getattr(PhysicalAction, act_name, PhysicalAction.NEUTRAL)
                zone_enum = getattr(CombatRangeZone, zone_name, CombatRangeZone.FAR_RESET)
                self.last_physics = KinematicSnapshot(
                    timestamp_ms=int(data.get("timestamp", 0) * 1000),
                    dx=float(phy_data.get("dx", 0.0)),
                    d3d=float(phy_data.get("d3d", 0.0)),
                    v_player=float(phy_data.get("v_player", 0.0)),
                    v_opp=float(phy_data.get("v_opp", 0.0)),
                    v_rel=float(phy_data.get("v_rel", 0.0)),
                    a_opp=float(phy_data.get("a_opp", 0.0)),
                    action=action_enum,
                    zone=zone_enum,
                    t_impact_ms=float(phy_data.get("t_impact_ms", 9999.0)),
                    is_side_inverted=bool(phy_data.get("is_side_inverted", False)),
                )
            self.last_state = str(data.get("fsm_state", "PAUSA_SEGURA"))
            self.last_latency_us = float(data.get("latency_us", 0.0))
            self.bot_active = bool(data.get("bot_active", False))
        except Exception:
            pass

    def generate_view(self) -> Table:
        if not HAS_RICH:
            return None

        # Tabela Principal
        badge = "[bold green][ROBÔ ATIVO][/bold green]" if self.bot_active else "[bold yellow][STANDBY / F10 DESATIVADO][/bold yellow]"
        table = Table(title=f"⚡ [bold yellow]NovoAuto - Zero-Vision Telemetry & Combat HUD[/bold yellow] {badge}", expand=True)
        table.add_column("Combatente", justify="center", style="bold cyan")
        table.add_column("Vida (HP)", justify="center")
        table.add_column("Poder (Mana)", justify="center")
        table.add_column("Posição (X, Y, Z)", justify="center")
        table.add_column("Estado Il2Cpp / Flags", justify="center")

        p = self.last_packet.player if self.last_packet else None
        o = self.last_packet.opponent if self.last_packet else None
        phy = self.last_physics

        # Linha do Jogador
        if p:
            hp_color = "green" if p.hp_pct > 50 else ("yellow" if p.hp_pct > 20 else "red")
            hp_str = f"[{hp_color}]{p.hp_pct:.1f}%[/{hp_color}]"
            mana_str = f"[cyan]{p.mana:.2f} ({p.power_bars}B)[/cyan]"
            pos_str = f"X:{p.pos.x:.2f} Y:{p.pos.y:.2f}"
            flags = []
            if p.is_blocking: flags.append("[blue]DEFENDENDO[/blue]")
            if p.is_stunned: flags.append("[red]ATORDOADO[/red]")
            if p.striker_ready: flags.append("[magenta]STRIKER PRONTO[/magenta]")
            st_str = " ".join(flags) if flags else "[dim]Normal[/dim]"
            table.add_row("🛡️ [bold green]PLAYER[/bold green]", hp_str, mana_str, pos_str, st_str)
        else:
            table.add_row("🛡️ PLAYER", "-", "-", "-", "-")

        # Linha do Oponente
        if o:
            hp_color = "green" if o.hp_pct > 50 else ("yellow" if o.hp_pct > 20 else "red")
            hp_str = f"[{hp_color}]{o.hp_pct:.1f}%[/{hp_color}]"
            mana_color = "red" if o.mana >= 2.8 else ("yellow" if o.mana >= 2.0 else "cyan")
            mana_str = f"[{mana_color}]{o.mana:.2f} ({o.power_bars}B)[/{mana_color}]"
            pos_str = f"X:{o.pos.x:.2f} Y:{o.pos.y:.2f}"
            flags = []
            if o.is_blocking: flags.append("[blue]BLOQUEANDO[/blue]")
            if o.is_stunned: flags.append("[red]ATORDOADO[/red]")
            opp_name = self.last_packet.opp_state_name if self.last_packet else ""
            if opp_name: flags.append(f"[yellow]{opp_name}[/yellow]")
            st_str = " ".join(flags) if flags else "[dim]Idle[/dim]"
            table.add_row("⚔️ [bold red]OPONENTE[/bold red]", hp_str, mana_str, pos_str, st_str)
        else:
            table.add_row("⚔️ OPONENTE", "-", "-", "-", "-")

        # Tabela Inferior de Física e Decisão
        status_table = Table(expand=True, box=None)
        status_table.add_column("Métrica Física", style="bold")
        status_table.add_column("Valor")
        status_table.add_column("Decisão FSM", style="bold")
        status_table.add_column("Status")

        if phy:
            dist_str = f"{phy.dx:.2f}m (3D: {phy.d3d:.2f}m)"
            vel_str = f"V_opp: {phy.v_opp:+.2f}m/s | V_rel: {phy.v_rel:+.2f}m/s"
            impact_str = f"{phy.t_impact_ms:.1f}ms" if phy.t_impact_ms < 9000 else "Sem Impacto"
            zone_str = f"{phy.zone.name} | Ação: {phy.action.name}"
        else:
            dist_str, vel_str, impact_str, zone_str = "-", "-", "-", "-"

        fsm_color = "green" if self.last_state == "JANELA_DE_PUNICAO" else ("yellow" if "DEFESA" in self.last_state else "cyan")
        fsm_str = f"[{fsm_color}]{self.last_state}[/{fsm_color}]"
        lat_str = f"[bold green]{self.last_latency_us:.1f} µs[/bold green]"

        status_table.add_row("Distância Ringue:", dist_str, "Estado FSM:", fsm_str)
        status_table.add_row("Velocidades:", vel_str, "Tempo de Impacto:", impact_str)
        status_table.add_row("Zonificação / Ação:", zone_str, "Latência Ciclo:", lat_str)

        # Envolve tudo em um painel
        layout = Table.grid(expand=True)
        layout.add_row(table)
        layout.add_row(Panel(status_table, title="[bold white]Telemetria Cinemática e FSM[/bold white]", border_style="cyan"))
        return layout
