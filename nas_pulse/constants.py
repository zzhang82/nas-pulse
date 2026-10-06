"""Global constants, thresholds, and markers for NAS-Pulse."""

DEFAULT_DSM_PORT = 5001
DEFAULT_DSM_VERSION = 7

# Markers for leftover/temporary containers (burn-in or helper scripts)
TEMP_CONTAINER_MARKERS = (
    "writer",
    "updater",
    "reorderer",
    "homepage-config",
    "homepage-css",
    "homepage-settings",
    "homepage-dashboard",
    "cpa-widget-file",
    "cpa-widget-update",
    "-pre-",
    "-swap-",
    "hostcli",
    "portainer-next",
    "temp-",
    "tmp-",
    "test-",
)

# Common homelab critical containers that should alert if stopped
DEFAULT_CRITICAL_CONTAINERS = [
    "homepage",
    "portainer",
    "syncthing",
    "uptime-kuma",
    "vaultwarden",
    "bitwarden",
    "bitwardenrs_1",
    "caddy",
    "caddy-proxy",
    "traefik",
    "nginx-proxy-manager",
    "jellyfin",
    "plex",
    "emby",
    "radarr",
    "sonarr",
    "prowlarr",
    "transmission",
    "qbittorrent",
]

def evaluate_cpu_temp(temp: int) -> tuple[str, str]:
    """Return clinical rating and style color for a given CPU temperature (°C)."""
    if temp <= 0:
        return "未知", "dim"
    elif temp < 42:
        return "冰凉", "green"
    elif temp < 58:
        return "正常", "green"
    elif temp < 72:
        return "微热", "yellow"
    else:
        return "烫手", "bold red"
