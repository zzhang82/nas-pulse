"""Clinical output renderer and diagnostic summarizer using Rich (Bilingual EN/CN)."""

from __future__ import annotations

import json
from typing import Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .constants import evaluate_cpu_temp, TEMP_CONTAINER_MARKERS, DEFAULT_CRITICAL_CONTAINERS
from .portainer import PortainerHygieneResult

def looks_temporary_container(name: str) -> bool:
    """Check if a container name matches temporary, writer, or swap patterns."""
    lowered = (name or "").lower()
    return any(marker in lowered for marker in TEMP_CONTAINER_MARKERS)

class PulseReport:
    """Encapsulates parsed telemetry and provides rendering methods."""

    def __init__(
        self,
        vitals: dict[str, Any],
        hygiene: Optional[PortainerHygieneResult] = None,
        critical_containers: Optional[list[str]] = None,
    ):
        self.vitals = vitals
        self.hygiene = hygiene
        self.critical_targets = critical_containers or DEFAULT_CRITICAL_CONTAINERS

        # 1. CPU & Temp
        cpu_util = vitals.get("cpu_util", {})
        self.user_load = cpu_util.get("user_load", 0)
        self.system_load = cpu_util.get("system_load", 0)
        self.total_cpu_load = self.user_load + self.system_load
        self.cpu_temp = int(vitals.get("cpu_temp", 0))
        self.temp_rating, self.temp_style = evaluate_cpu_temp(self.cpu_temp)

        # 2. RAM
        mem_util = vitals.get("mem_util", {})
        total_real = mem_util.get("total_real", 0)
        self.real_usage = mem_util.get("real_usage", 0)
        cached = mem_util.get("cached", 0)

        self.total_gb = total_real / (1024 * 1024) if total_real else 0.0
        self.used_gb = (total_real * (self.real_usage / 100)) / (1024 * 1024) if total_real else 0.0
        self.cached_gb = cached / (1024 * 1024) if cached else 0.0

        # 3. Storage & Disks
        self.used_tb = 0.0
        self.free_tb = 0.0
        self.usage_pct = 0.0
        vol_info = vitals.get("vol_info", [])
        if vol_info and isinstance(vol_info, list):
            v = vol_info[0]
            total_size = int(v.get("total_size", 0))
            used_size = int(v.get("used_size", 0))
            if total_size > 0:
                self.used_tb = used_size / (1024**4)
                self.free_tb = (total_size - used_size) / (1024**4)
                self.usage_pct = (used_size / total_size) * 100

        hdd_info = vitals.get("hdd_info", [])
        self.disk_temps = [int(h.get("temp", 0)) for h in hdd_info if h.get("temp")]
        smart_healthy = sum(1 for h in hdd_info if h.get("smart_status") == "normal")
        total_hdds = len(hdd_info)
        if total_hdds == 0:
            self.disks_health = "未知 / Unknown"
            self.temp_range = "未知"
        elif smart_healthy == total_hdds:
            self.disks_health = f"{total_hdds}盘全绿 / All Healthy"
            self.temp_range = f"{min(self.disk_temps)}°C ~ {max(self.disk_temps)}°C" if self.disk_temps else "正常 / Normal"
        else:
            self.disks_health = f"{total_hdds - smart_healthy}盘异常 / Warning"
            self.temp_range = f"{min(self.disk_temps)}°C ~ {max(self.disk_temps)}°C" if self.disk_temps else "异常 / Alert"

        # 4. Uptime
        sys_health = vitals.get("sys_health", {})
        uptime_raw = sys_health.get("data", {}).get("uptime", "00:00:00")
        try:
            hours = int(str(uptime_raw).split(":")[0])
            self.uptime_days = hours // 24
        except Exception:
            self.uptime_days = 0

        # 5. Containers
        containers = vitals.get("containers", [])
        self.running_count = sum(1 for c in containers if c.get("status") == "running")
        self.stopped_count = sum(1 for c in containers if c.get("status") == "stopped")

        resources = vitals.get("resources", [])
        resource_map = {r.get("name"): r for r in resources if isinstance(r, dict) and r.get("name")}

        self.active_containers = []
        for c in containers:
            name = c.get("name")
            if c.get("status") == "running" and name in resource_map:
                res = resource_map[name]
                self.active_containers.append({
                    "name": name,
                    "cpu": float(res.get("cpu", 0.0)),
                    "memory": int(res.get("memory", 0)),
                    "mem_pct": float(res.get("memoryPercent", 0.0)),
                })
        self.active_containers.sort(key=lambda x: x["memory"], reverse=True)

        # Stopped alerts & temporary markers
        stopped_names = [c.get("name") for c in containers if c.get("status") == "stopped"]
        self.stopped_critical = [name for name in stopped_names if name in self.critical_targets]
        self.temporary_containers = [name for name in stopped_names if looks_temporary_container(name)]

    def generate_soul_diagnosis(self) -> str:
        """Formulate the signature clinical diagnosis in doctor tone."""
        if self.cpu_temp > 70:
            cpu_vibe = "体温烫手，注意散热排风"
        elif self.cpu_temp > 55:
            cpu_vibe = "体温微热"
        else:
            cpu_vibe = "体温冰凉无汗"

        if self.real_usage > 85:
            ram_vibe = "气血大亏，内存吃紧"
        elif self.real_usage > 65:
            ram_vibe = "气血运转平稳"
        else:
            ram_vibe = f"{self.total_gb:.0f}G气血极其充沛"

        if "全绿" in self.disks_health:
            disk_vibe = f"磁盘骨骼{self.disks_health}"
        else:
            disk_vibe = f"磁盘骨骼疑似有损({self.disks_health})"

        return f"“{cpu_vibe}（{self.cpu_temp}℃），{ram_vibe}，{disk_vibe}，脉象极平，处于巅峰。”"

    def to_dict(self) -> dict[str, Any]:
        """Convert report to serializable dictionary for JSON export."""
        return {
            "soul_diagnosis": self.generate_soul_diagnosis(),
            "vital_signs": {
                "cpu_temp_c": self.cpu_temp,
                "cpu_rating": self.temp_rating,
                "ram_usage_pct": self.real_usage,
                "ram_used_gb": round(self.used_gb, 2),
                "ram_total_gb": round(self.total_gb, 2),
                "ram_cached_gb": round(self.cached_gb, 2),
                "disks_health": self.disks_health,
                "disk_temp_range": self.temp_range,
                "volume_used_tb": round(self.used_tb, 2),
                "volume_free_tb": round(self.free_tb, 2),
                "volume_usage_pct": round(self.usage_pct, 1),
                "uptime_days": self.uptime_days,
            },
            "docker": {
                "running_count": self.running_count,
                "stopped_count": self.stopped_count,
                "stopped_critical": self.stopped_critical,
                "temporary_leftovers": self.temporary_containers,
                "top_active_containers": self.active_containers[:5],
            },
            "hygiene": {
                "active_stacks": self.hygiene.active_stacks if self.hygiene else None,
                "total_stacks": self.hygiene.total_stacks if self.hygiene else None,
                "dangling_volumes": self.hygiene.dangling_volumes if self.hygiene else None,
                "unused_networks": self.hygiene.unused_networks if self.hygiene else None,
                "summary": self.hygiene.summary if self.hygiene else "未配置 Portainer / Not Configured",
            },
        }

    def render(self, console: Optional[Console] = None) -> None:
        """Render beautiful terminal diagnostic card."""
        con = console or Console()

        # Part 1: Soul Diagnosis
        con.print()
        con.print(Panel("[bold magenta]🩺 NAS 脉搏诊断书 / Clinical Soul Diagnosis[/bold magenta]", expand=False))
        con.print(f"[bold cyan]{self.generate_soul_diagnosis()}[/bold cyan]\n")

        # Part 2: Vital Signs Table
        table = Table(title="📋 宿主机生命体征监测表 / Vital Signs Table", show_header=True, header_style="bold magenta")
        table.add_column("生命指征 / Vital Sign", style="cyan", width=25)
        table.add_column("实时测值 / Real-time Value", style="green", width=34)
        table.add_column("大夫断语 / Clinical Verdict", style="yellow")

        table.add_row(
            "体温 / CPU Temp",
            f"{self.cpu_temp} °C",
            f"[{self.temp_style}]{self.temp_rating}[/{self.temp_style}]",
        )
        table.add_row(
            "气血 / RAM Usage",
            f"{self.real_usage}% ({self.used_gb:.1f} GB / {self.total_gb:.1f} GB)",
            f"正常 / Normal (缓存 / Cache: {self.cached_gb:.1f} GB)",
        )
        table.add_row(
            "骨骼 / Disk Status",
            self.disks_health,
            f"健康无异响 (盘温 {self.temp_range})",
        )
        table.add_row(
            "腹心 / Volume Space",
            f"已用 {self.used_tb:.1f} TB / 剩余 {self.free_tb:.1f} TB",
            f"胃口良好 (使用率 {self.usage_pct:.1f}%)",
        )
        table.add_row(
            "心跳 / Uptime",
            f"已持续运行 {self.uptime_days} 天 / Days",
            "平稳跳动中 / Stable Rhythm",
        )

        if self.hygiene:
            table.add_row(
                "容器堆栈 / Stacks",
                f"{self.hygiene.active_stacks}个活跃 / 共{self.hygiene.total_stacks}个",
                "配置井然有序 / Well Organized",
            )
            hygiene_style = "green" if self.hygiene.is_clean else "red"
            hygiene_diag = "高枕无忧 / Clean" if self.hygiene.is_clean else "建议排查清理 / Attention Needed"
            table.add_row(
                "环境卫生 / Hygiene",
                f"[{hygiene_style}]{self.hygiene.summary}[/{hygiene_style}]",
                hygiene_diag,
            )

        con.print(table)
        con.print()

        # Part 3: Container Community Matrix
        con.print(Panel("[bold green]🐳 容器群落谱 / Container Community Matrix[/bold green]", expand=False))
        con.print(
            f"• 🟢 [bold green]正在运行 / Running[/bold green]: [bold]{self.running_count}[/bold] 个  |  "
            f"🔴 [bold red]已经停止 / Stopped[/bold red]: [bold]{self.stopped_count}[/bold] 个\n"
        )

        if self.active_containers:
            cont_table = Table(show_header=True, header_style="bold green")
            cont_table.add_column("活跃容器名称 / Container Name", style="cyan")
            cont_table.add_column("CPU %", style="yellow")
            cont_table.add_column("RAM 占用 / RAM Usage", style="yellow")
            cont_table.add_column("气血占比 / RAM %", style="magenta")

            for c in self.active_containers[:5]:
                mem_mb = c["memory"] / (1024 * 1024)
                cont_table.add_row(
                    c["name"],
                    f"{c['cpu']:.2f}%",
                    f"{mem_mb:.1f} MB",
                    f"{c['mem_pct']:.2f}%",
                )
            con.print(cont_table)

        # Highlight stopped critical containers
        if self.stopped_critical:
            con.print("\n[bold red]🚨 警示：关键服务已停止运行！ / Alert: Critical service(s) stopped![/bold red]")
            for name in self.stopped_critical:
                con.print(f"  - ❌ [bold red]{name}[/bold red] 处于停止状态，请确认是否为故意下线。")

        # Highlight temporary leftovers
        if self.temporary_containers:
            con.print("\n[bold yellow]🧹 卫生提示：发现疑似临时更新或辅助容器残留 / Hygiene notice: Temporary containers detected:[/bold yellow]")
            for name in self.temporary_containers[:6]:
                con.print(f"  - [yellow]{name}[/yellow]")
            if len(self.temporary_containers) > 6:
                con.print(f"  - ...以及另外 {len(self.temporary_containers) - 6} 个临时容器")

        # Memory hog note
        if self.active_containers:
            hog = self.active_containers[0]
            hog_mb = hog["memory"] / (1024 * 1024)
            con.print(
                f"\n[bold yellow]💡 气血提示 / RAM Insight：[/bold yellow] 容器 [bold cyan]{hog['name']}[/bold cyan] "
                f"是当前的内存大户，吞吐 [bold yellow]{hog_mb:.1f} MB[/bold yellow] "
                f"气血 (RAM 占比 {hog['mem_pct']:.2f}%)。\n"
            )
