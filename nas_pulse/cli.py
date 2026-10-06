"""Unified Command Line Interface for NAS-Pulse."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional
from rich.console import Console

from . import __version__
from .config import Config
from .client import DSMClient, SynologyPrivilegeError, SynologyConnectionError
from .portainer import PortainerClient
from .formatter import PulseReport
from .wizard import run_wizard
from .doctor import run_doctor

def main(args: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nas-pulse",
        description="NAS-Pulse: Real-time clinical status diagnostic tool for Synology NAS & Docker hygiene.",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--env",
        metavar="PATH",
        help="Path to custom .env configuration file (defaults to local .env or ~/.config/nas-pulse/.env)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw structured JSON without terminal colors (ideal for AI agents or automation)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: pulse (default)
    subparsers.add_parser("pulse", help="Perform clinical diagnostic check on Synology NAS (default)")

    # Command: setup
    subparsers.add_parser("setup", help="Run interactive configuration wizard")

    # Command: doctor
    subparsers.add_parser("doctor", help="Run self-check doctor to verify environment & API permissions")

    parsed = parser.parse_args(args)
    console = Console()

    # Route: setup
    if parsed.command == "setup":
        saved = run_wizard(console=console)
        return 0 if saved else 1

    # Route: doctor
    if parsed.command == "doctor":
        ok = run_doctor(env_path=parsed.env, console=console)
        return 0 if ok else 1

    # Route: pulse (default action)
    config = Config(env_path=parsed.env)

    # If configuration is missing, guide the user to setup
    if not config.is_configured:
        if parsed.json:
            print(json.dumps({
                "error": "Configuration missing",
                "message": "Run `nas-pulse setup` to configure NAS connection.",
                "missing": config.validate(),
            }, indent=2, ensure_ascii=False))
            return 1

        console.print("\n[bold yellow]🩺 提示：未检测到有效的群晖 NAS 配置文件！[/bold yellow]")
        console.print("[dim]首次使用，请运行开箱配置向导来建立与 NAS 的通信。[/dim]\n")
        try:
            from rich.prompt import Confirm
            if Confirm.ask("是否现在启动配置向导 (nas-pulse setup)?", default=True):
                saved = run_wizard(console=console)
                if not saved:
                    return 1
                config = Config(env_path=str(saved))
            else:
                return 1
        except (KeyboardInterrupt, EOFError):
            return 1

    # Fetch data and generate report
    if not parsed.json:
        console.print("\n⏳ [cyan]大夫正在连通群晖脉门，感知物理体温与容器气血...[/cyan]")

    try:
        dsm = DSMClient(config)
        vitals = dsm.fetch_vitals()
    except SynologyPrivilegeError as err:
        if parsed.json:
            print(json.dumps({"error": "PrivilegeError", "message": str(err)}, indent=2))
            return 1
        console.print(f"\n[bold red]🚨 诊断中断：{err}[/bold red]")
        console.print("[yellow]提示：请参考 docs/DSM_USER_SETUP.md 为该用户分配 administrators 权限。[/yellow]\n")
        return 1
    except SynologyConnectionError as err:
        if parsed.json:
            print(json.dumps({"error": "ConnectionError", "message": str(err)}, indent=2))
            return 1
        console.print(f"\n[bold red]🚨 诊断中断：脉象全无！无法与 NAS WebAPI 取得通信，速去机房查看物理电源或交换机。[/bold red]")
        console.print(f"[dim]错误详情: {err}[/dim]\n")
        return 1
    except Exception as err:
        if parsed.json:
            print(json.dumps({"error": "UnexpectedError", "message": str(err)}, indent=2))
            return 1
        console.print(f"\n[bold red]🚨 未知故障: {err}[/bold red]\n")
        return 1

    # Optional Portainer hygiene check
    hygiene = None
    if config.has_portainer:
        portainer = PortainerClient(config)
        hygiene = portainer.inspect_hygiene(fallback_containers=vitals.get("containers"))

    report = PulseReport(vitals=vitals, hygiene=hygiene)

    if parsed.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        report.render(console=console)

    return 0

if __name__ == "__main__":
    sys.exit(main())
