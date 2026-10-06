"""Interactive terminal setup wizard for NAS-Pulse (Bilingual EN/CN)."""

from __future__ import annotations

import getpass
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from .config import Config, DEFAULT_USER_CONFIG
from .client import DSMClient, SynologyPrivilegeError, SynologyConnectionError
from .portainer import PortainerClient

def prompt_clean(prompt_text: str, default: Optional[str] = None) -> str:
    """Prompt helper using Rich Prompt."""
    if default:
        return Prompt.ask(prompt_text, default=default).strip()
    return Prompt.ask(prompt_text).strip()

def run_wizard(console: Optional[Console] = None) -> Optional[Path]:
    """Execute interactive onboarding wizard, returns path of saved config if completed."""
    con = console or Console()

    welcome_text = (
        "[bold cyan]欢迎使用 NAS-Pulse (服务器诊脉仪) 首次配置向导！[/bold cyan]\n"
        "[bold cyan]Welcome to NAS-Pulse Interactive Setup Wizard![/bold cyan]\n\n"
        "只需 1 分钟，大夫即可为你打通群晖宿主机与 Docker 容器群落的脉搏。\n"
        "Connect physical sensors and Docker telemetry of your Synology NAS in 1 minute.\n"
        "[dim]注：所有凭证仅保存在你本地的 .env 文件中，绝不上传任何外部网络。[/dim]\n"
        "[dim]Note: All credentials stay strictly in your local .env and are never uploaded.[/dim]"
    )
    con.print(Panel(welcome_text, title="🩺 NAS-Pulse Setup Wizard (EN/CN)", expand=False))

    # --- Step 1: Synology DSM Connection ---
    con.print("\n[bold magenta]─── [1/2] 群晖 DSM 基础连接设置 / Synology DSM Connection ───[/bold magenta]")

    nas_ip = prompt_clean("? 请输入群晖 NAS 局域网 IP / Enter Synology NAS LAN IP or Hostname (e.g. 192.168.1.100)")
    while not nas_ip:
        nas_ip = prompt_clean("! IP 不能为空 / IP cannot be empty")

    nas_port_str = prompt_clean("? 请输入 DSM 管理端口 / Enter DSM Port", default="5001")
    try:
        nas_port = int(nas_port_str)
    except ValueError:
        nas_port = 5001

    nas_secure = Confirm.ask("? 是否使用 HTTPS 加密传输? / Use HTTPS connection?", default=True)
    nas_cert_verify = Confirm.ask("? 是否严格校验 SSL 证书? (自签名证书选 n) / Verify SSL certificate?", default=False)

    nas_user = prompt_clean("? 请输入 DSM 用户名 (建议专用运维账号) / Enter DSM Username (e.g. nas_doctor)")
    while not nas_user:
        nas_user = prompt_clean("! 用户名不能为空 / Username cannot be empty")

    # Mask password entry
    nas_password = ""
    while not nas_password:
        nas_password = getpass.getpass("? 请输入 DSM 密码 / Enter DSM Password (hidden): ")
        if not nas_password:
            con.print("[red]! 密码不能为空 / Password cannot be empty.[/red]")

    # Live verification of DSM credentials
    con.print("\n⏳ [cyan]正在尝试与群晖 WebAPI 建立连接并探测生命体征... / Probing DSM WebAPI...[/cyan]")
    test_cfg = Config()
    test_cfg.nas_ip = nas_ip
    test_cfg.nas_port = nas_port
    test_cfg.nas_user = nas_user
    test_cfg.nas_password = nas_password
    test_cfg.nas_secure = nas_secure
    test_cfg.nas_cert_verify = nas_cert_verify
    test_cfg.nas_dsm_version = 7

    dsm_client = DSMClient(test_cfg)
    try:
        res = dsm_client.test_connection()
        con.print(f"✔ [bold green]WebAPI 连通测试通过！成功感知 CPU 传感器 ({res.get('cpu_temp')}°C)。[/bold green]")
        con.print(f"✔ [bold green]Connection successful! CPU sensor probed at {res.get('cpu_temp')}°C.[/bold green]")
    except SynologyPrivilegeError:
        con.print("\n[bold red]⚠️ 权限受阻 / Insufficient Privilege (DSM Error 105)！[/bold red]")
        con.print(
            "[yellow]说明：群晖 DSM 7 WebAPI 读取硬件温度、内存与 SMART 状态需要 administrators 组权限。\n"
            f"建议：在群晖控制面板中将账号 '{nas_user}' 设为 administrators 组（详见 docs/DSM_USER_SETUP.md）。\n"
            "Note: Reading hardware sensors requires 'administrators' group membership in DSM 7.[/yellow]\n"
        )
        if not Confirm.ask("是否仍然先保存该配置？ / Save configuration anyway?", default=True):
            con.print("[yellow]已取消配置流程 / Setup aborted.[/yellow]")
            return None
    except SynologyConnectionError as err:
        con.print(f"\n[bold red]❌ 连接失败 / Connection failed：{err}[/bold red]")
        con.print("[yellow]提示：请检查 NAS 局域网 IP、端口以及防火墙配置。\nHint: Check NAS IP, port, and firewall rules.[/yellow]\n")
        if not Confirm.ask("是否仍然先保存该配置？ / Save configuration anyway?", default=True):
            con.print("[yellow]已取消配置流程 / Setup aborted.[/yellow]")
            return None

    # --- Step 2: Portainer Settings (Optional) ---
    con.print("\n[bold magenta]─── [2/2] Portainer 容器环境 (可选) / Portainer Integration (Optional) ───[/bold magenta]")
    enable_portainer = Confirm.ask("? 是否配置了 Portainer 协助监控 Docker 堆栈与悬空网络/卷? / Enable Portainer monitoring?", default=False)
    portainer_url = ""
    portainer_token = ""

    if enable_portainer:
        portainer_url = prompt_clean(
            "? 请输入 Portainer 访问地址 / Enter Portainer URL", default=f"http://{nas_ip}:9000"
        )
        portainer_token = prompt_clean("? 请输入 Portainer Access Token (API Key)")

        test_cfg.portainer_url = portainer_url
        test_cfg.portainer_token = portainer_token
        pt_client = PortainerClient(test_cfg)
        con.print("⏳ [cyan]正在测试 Portainer API 连通性... / Testing Portainer API...[/cyan]")
        pt_res = pt_client.test_connection()
        if pt_res.get("connected"):
            con.print("✔ [bold green]Portainer 连通测试通过！ / Portainer connected successfully![/bold green]")
        else:
            con.print(f"[yellow]! 提示：Portainer 测试未完全通过 ({pt_res.get('error')})，但配置仍将保留。[/yellow]")
            con.print(f"[yellow]! Warning: Portainer probe had issues ({pt_res.get('error')}), but settings are retained.[/yellow]")

    # --- Step 3: Save Destination ---
    con.print("\n[bold magenta]─── [3/3] 配置文件保存位置 / Config Save Destination ───[/bold magenta]")
    use_local = Confirm.ask("? 是否保存在当前项目目录下的 .env 文件中? / Save to local .env in current directory?", default=True)
    if use_local:
        target_path = Path(".env").resolve()
    else:
        target_path = DEFAULT_USER_CONFIG

    Config.save(
        dest_path=target_path,
        nas_ip=nas_ip,
        nas_port=nas_port,
        nas_user=nas_user,
        nas_password=nas_password,
        nas_secure=nas_secure,
        nas_cert_verify=nas_cert_verify,
        nas_dsm_version=7,
        portainer_url=portainer_url,
        portainer_token=portainer_token,
    )

    con.print(f"\n🎉 [bold green]配置已成功加密保存至 / Saved securely to: {target_path} (mode 0600)[/bold green]")
    con.print("[cyan]现在你可以随时运行 / You can now run:[/cyan]")
    con.print("  [bold white]nas-pulse[/bold white]         # 立即把脉出具体检单 / Perform clinical pulse check")
    con.print("  [bold white]nas-pulse doctor[/bold white]  # 运行全链路健康自检 / Run environment self-check\n")

    return target_path
