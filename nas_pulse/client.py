"""Synology DSM WebAPI Client wrapper with error translation and diagnostics."""

from __future__ import annotations

import urllib3
from typing import Any, Optional
from synology_api import core_sys_info, docker_api
from .config import Config

# Suppress InsecureRequestWarning when cert_verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SynologyPrivilegeError(Exception):
    """Raised when the DSM user lacks administrator privileges for hardware APIs."""
    pass

class SynologyConnectionError(Exception):
    """Raised when communication with DSM fails or times out."""
    pass

class DSMClient:
    """Encapsulates Synology DSM WebAPI interactions."""

    def __init__(self, config: Config):
        self.config = config
        self._sys_info: Optional[core_sys_info.SysInfo] = None
        self._docker_api: Optional[docker_api.Docker] = None

    def connect(self) -> None:
        """Initialize connection to Synology DSM."""
        try:
            self._sys_info = core_sys_info.SysInfo(
                self.config.nas_ip,
                str(self.config.nas_port),
                self.config.nas_user,
                self.config.nas_password,
                secure=self.config.nas_secure,
                cert_verify=self.config.nas_cert_verify,
                dsm_version=self.config.nas_dsm_version,
            )
        except Exception as exc:
            msg = str(exc).strip() or f"{type(exc).__name__}: 认证失败或网络连接中断"
            if "105" in msg or "privilege" in msg.lower():
                raise SynologyPrivilegeError(
                    f"DSM Error 105: Account '{self.config.nas_user}' does not have sufficient privileges. "
                    "DSM 7 requires an administrator group member to read physical sensors and system health."
                ) from exc
            raise SynologyConnectionError(f"{msg}") from exc

    def test_connection(self) -> dict[str, Any]:
        """Test authentication and privilege level, returning brief status."""
        self.connect()
        assert self._sys_info is not None
        
        health = self._sys_info.get_system_health()
        if isinstance(health, dict) and health.get("error"):
            code = health["error"].get("code")
            if code == 105:
                raise SynologyPrivilegeError("DSM Error 105: Insufficient privilege.")
            raise SynologyConnectionError(f"DSM returned error code {code}")

        temp = self._sys_info.get_cpu_temp()
        return {
            "success": True,
            "cpu_temp": int(temp) if temp else 0,
            "status": "healthy",
        }

    def fetch_vitals(self) -> dict[str, Any]:
        """Fetch all hardware vitals and container resources."""
        if self._sys_info is None:
            self.connect()
        assert self._sys_info is not None

        # 1. System Info
        try:
            sys_health = self._sys_info.get_system_health() or {}
            cpu_util = self._sys_info.get_cpu_utilization() or {}
            mem_util = self._sys_info.get_memory_utilization() or {}
            cpu_temp = self._sys_info.get_cpu_temp() or 0
        except Exception as exc:
            if "105" in str(exc):
                raise SynologyPrivilegeError(
                    "DSM Error 105: Account lacks administrator permissions to read hardware sensors."
                ) from exc
            raise SynologyConnectionError(f"Failed to fetch system sensors: {exc}") from exc

        # 2. Volumes and Disks
        vol_data: list[dict[str, Any]] = []
        hdd_data: list[dict[str, Any]] = []
        try:
            raw_vol = self._sys_info.get_volume_info() or {}
            if isinstance(raw_vol, dict):
                data = raw_vol.get("data", {})
                vol_data = data.get("vol_info", []) or []
                hdd_data = data.get("hdd_info", []) or []
        except Exception:
            pass

        # 3. Docker API (via Synology DSM Container Manager)
        containers: list[dict[str, Any]] = []
        resources: list[dict[str, Any]] = []
        try:
            self._docker_api = docker_api.Docker(
                self.config.nas_ip,
                str(self.config.nas_port),
                self.config.nas_user,
                self.config.nas_password,
                secure=self.config.nas_secure,
                cert_verify=self.config.nas_cert_verify,
                dsm_version=self.config.nas_dsm_version,
            )
            raw_conts = self._docker_api.containers() or {}
            if isinstance(raw_conts, dict):
                containers = raw_conts.get("data", {}).get("containers", []) or []

            raw_res = self._docker_api.container_resources() or {}
            if isinstance(raw_res, dict):
                resources = raw_res.get("data", {}).get("resources", []) or []
        except Exception:
            # Container Manager may not be installed or enabled
            pass

        return {
            "sys_health": sys_health,
            "cpu_util": cpu_util,
            "mem_util": mem_util,
            "cpu_temp": int(cpu_temp) if cpu_temp else 0,
            "vol_info": vol_data,
            "hdd_info": hdd_data,
            "containers": containers,
            "resources": resources,
        }
