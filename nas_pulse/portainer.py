"""Portainer API client and Docker hygiene auditor."""

from __future__ import annotations

from typing import Any, Optional
import requests
import urllib3
from .config import Config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class PortainerHygieneResult:
    def __init__(
        self,
        active_stacks: int = 0,
        total_stacks: int = 0,
        dangling_volumes: int = 0,
        unused_networks: int = 0,
        is_clean: bool = True,
        summary: str = "",
    ):
        self.active_stacks = active_stacks
        self.total_stacks = total_stacks
        self.dangling_volumes = dangling_volumes
        self.unused_networks = unused_networks
        self.is_clean = is_clean
        self.summary = summary

class PortainerClient:
    """Interacts with Portainer API to inspect stacks and Docker hygiene."""

    def __init__(self, config: Config):
        self.config = config
        self.url = config.portainer_url.rstrip("/")
        self.token = config.portainer_token
        self.headers = {
            "X-API-Key": self.token,
            "Content-Type": "application/json",
        }
        self._env_id: Optional[int] = None

    def test_connection(self) -> dict[str, Any]:
        """Test reachability and authentication to Portainer."""
        if not self.config.has_portainer:
            return {"configured": False, "message": "Portainer is not configured"}

        try:
            res = requests.get(
                f"{self.url}/api/endpoints",
                headers=self.headers,
                verify=False,
                timeout=10,
            )
            if res.status_code == 200:
                endpoints = res.json()
                return {
                    "configured": True,
                    "connected": True,
                    "endpoints_count": len(endpoints),
                }
            return {
                "configured": True,
                "connected": False,
                "status_code": res.status_code,
                "error": res.text[:200],
            }
        except Exception as exc:
            return {
                "configured": True,
                "connected": False,
                "error": str(exc),
            }

    def get_env_id(self) -> int:
        """Resolve primary Docker endpoint ID in Portainer."""
        if self._env_id is not None:
            return self._env_id

        try:
            res = requests.get(
                f"{self.url}/api/endpoints",
                headers=self.headers,
                verify=False,
                timeout=10,
            )
            if res.status_code == 200:
                endpoints = res.json()
                if endpoints:
                    self._env_id = int(endpoints[0]["Id"])
                    return self._env_id
        except Exception:
            pass
        return 1

    def inspect_hygiene(self, fallback_containers: Optional[list[dict[str, Any]]] = None) -> Optional[PortainerHygieneResult]:
        """Audit stacks, volumes, and networks to identify hygiene issues."""
        if not self.config.has_portainer:
            return None

        try:
            # 1. Fetch stacks
            res_stacks = requests.get(
                f"{self.url}/api/stacks",
                headers=self.headers,
                verify=False,
                timeout=10,
            )
            stacks = res_stacks.json() if res_stacks.status_code == 200 else []
            total_stacks = len(stacks)
            active_stacks = sum(1 for s in stacks if isinstance(s, dict) and s.get("Status") == 1)

            # 2. Fetch Docker Engine resources
            env_id = self.get_env_id()
            res_conts = requests.get(
                f"{self.url}/api/endpoints/{env_id}/docker/containers/json?all=1",
                headers=self.headers,
                verify=False,
                timeout=10,
            )
            containers = res_conts.json() if res_conts.status_code == 200 else (fallback_containers or [])

            res_vols = requests.get(
                f"{self.url}/api/endpoints/{env_id}/docker/volumes",
                headers=self.headers,
                verify=False,
                timeout=10,
            )
            all_vols = res_vols.json().get("Volumes", []) if res_vols.status_code == 200 else []

            res_nets = requests.get(
                f"{self.url}/api/endpoints/{env_id}/docker/networks",
                headers=self.headers,
                verify=False,
                timeout=10,
            )
            all_nets = res_nets.json() if res_nets.status_code == 200 else []

            # 3. Compute active bindings
            active_vols: set[str] = set()
            active_nets: set[str] = set()

            for c in containers:
                for m in c.get("Mounts", []):
                    if isinstance(m, dict) and m.get("Type") == "volume" and m.get("Name"):
                        active_vols.add(m["Name"])

                net_settings = c.get("NetworkSettings", {})
                if isinstance(net_settings, dict):
                    nets = net_settings.get("Networks", {})
                    if isinstance(nets, dict):
                        for net_name in nets.keys():
                            active_nets.add(net_name)

            dangling_volumes = sum(
                1 for v in all_vols if isinstance(v, dict) and v.get("Name") and v["Name"] not in active_vols
            )
            unused_networks = sum(
                1
                for n in all_nets
                if isinstance(n, dict)
                and n.get("Name")
                and n["Name"] not in {"bridge", "host", "none"}
                and n["Name"] not in active_nets
            )

            is_clean = (dangling_volumes == 0 and unused_networks == 0)
            if is_clean:
                summary = "干净 (无闲置网络/卷)"
            else:
                summary = f"发现 {dangling_volumes}个悬空卷, {unused_networks}个闲置网络"

            return PortainerHygieneResult(
                active_stacks=active_stacks,
                total_stacks=total_stacks,
                dangling_volumes=dangling_volumes,
                unused_networks=unused_networks,
                is_clean=is_clean,
                summary=summary,
            )

        except Exception:
            return None
