"""Self-diagnostic tool to verify environment, network, and permissions (Bilingual EN/CN)."""

from __future__ import annotations

import sys
import time
from typing import Optional
from rich.console import Console
from rich.table import Table

from .config import Config
from .client import DSMClient, SynologyPrivilegeError, SynologyConnectionError
from .portainer import PortainerClient

def run_doctor(env_path: Optional[str] = None, console: Optional[Console] = None) -> bool:
    """Run comprehensive environment & connectivity checks, returning True if all core checks pass."""
    con = console or Console()
    con.print("\n[bold cyan]🩺 NAS-Pulse Doctor: 系统环境与网络探针健康诊断 / Diagnostics & Health Check[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("检查项 / Check Item", style="cyan", width=30)
    table.add_column("状态 / Status", width=14)
    table.add_column("详细信息 / 建议 (Details & Advice)", style="dim")

    all_passed = True

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        table.add_row("Python 版本 / Version", "[green]✔ PASS[/green]", f"Python {py_ver} (要求 / Requires >= 3.10)")
    else:
        table.add_row("Python 版本 / Version", "[red]✘ FAIL[/red]", f"当前为 Python {py_ver}，需要 >= 3.10")
        all_passed = False

    # 2. Config status
    config = Config(env_path)
    if config.loaded_path:
        table.add_row("配置文件 / Config File", "[green]✔ PASS[/green]", f"已加载 / Loaded: {config.loaded_path}")
    else:
        table.add_row("配置文件 / Config File", "[yellow]! WARN[/yellow]", "未找到 .env，读取环境变量 / No .env found, reading env vars")

    missing = config.validate()
    if not missing:
        table.add_row(
            "群晖凭证 / DSM Credentials",
            "[green]✔ PASS[/green]",
            f"目标 / Target: {config.nas_ip}:{config.nas_port} (User: {config.nas_user})",
        )
    else:
        table.add_row(
            "群晖凭证 / DSM Credentials",
            "[red]✘ FAIL[/red]",
            f"缺少配置 / Missing: {', '.join(missing)}。请先运行 `nas-pulse setup`",
        )
        all_passed = False

    # 3. Connectivity & Permissions (only if credentials present)
    if not missing:
        dsm = DSMClient(config)
        start_t = time.perf_counter()
        try:
            res = dsm.test_connection()
            latency = (time.perf_counter() - start_t) * 1000
            table.add_row(
                "DSM WebAPI 握手 / Handshake",
                "[green]✔ PASS[/green]",
                f"成功连接并测温 ({res.get('cpu_temp')}°C)，延迟 {latency:.1f}ms / RTT {latency:.1f}ms",
            )
        except SynologyPrivilegeError:
            table.add_row(
                "DSM WebAPI 权限 / Privilege",
                "[red]✘ FAIL[/red]",
                f"权限受限 (DSM Error 105)。用户 '{config.nas_user}' 需加入 administrators 组 (见 docs/DSM_USER_SETUP.md)",
            )
            all_passed = False
        except SynologyConnectionError as e:
            table.add_row(
                "DSM 连通性 / Connectivity",
                "[red]✘ FAIL[/red]",
                f"通信中断 / Disconnected: {e}。请检查 IP、端口与防火墙规则。",
            )
            all_passed = False

    # 4. Portainer check (optional)
    if config.has_portainer:
        portainer = PortainerClient(config)
        pt_res = portainer.test_connection()
        if pt_res.get("connected"):
            table.add_row(
                "Portainer API 探测 / Probe",
                "[green]✔ PASS[/green]",
                f"成功连通，已识别 {pt_res.get('endpoints_count')} 个 Docker 端点 / {pt_res.get('endpoints_count')} endpoint(s) found",
            )
        else:
            table.add_row(
                "Portainer API 探测 / Probe",
                "[yellow]! WARN[/yellow]",
                f"连接失败 / Error: {pt_res.get('error', 'Status code ' + str(pt_res.get('status_code')))}",
            )
    else:
        table.add_row(
            "Portainer API 探测 / Probe",
            "[dim]○ SKIP[/dim]",
            "未配置 Portainer (仅监测原生 DSM 容器与硬件) / Not configured (native mode)",
        )

    con.print(table)
    con.print()

    if all_passed:
        con.print("[bold green]🎉 全部核心指标检查合格！可直接执行 `nas-pulse` 进行全息体检。[/bold green]")
        con.print("[bold green]🎉 All core checks passed! You can run `nas-pulse` directly.[/bold green]\n")
    else:
        con.print("[bold yellow]⚠️ 存在未通过的检查项，请参考上表建议进行修正，或运行 `nas-pulse setup` 重新配置。[/bold yellow]")
        con.print("[bold yellow]⚠️ Some checks did not pass. Run `nas-pulse setup` to reconfigure.[/bold yellow]\n")

    return all_passed
