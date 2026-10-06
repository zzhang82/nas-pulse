# Synology DSM 7+ & Docker Battle-Tested Engineering Handbook / 群晖 DSM 7+ 与 Docker 实战避坑指南

[English](#english) • [中文说明](#中文说明)

---

## English

This handbook documents hard-earned, production-tested gotchas, architectural limitations, and operational optimizations discovered while running Docker and Synology DSM 7+ in a high-density 24/7 homelab.

### 🔑 1. DSM 7+ WebAPI Nuances & Permissions

#### Privilege Tiering (`Error 105`)
- **System-level APIs**: Endpoints like `core_sys_info.SysInfo` (CPU temperatures, system health, network utilization) strictly enforce that the calling user must belong to the **`administrators`** group.
- Calling these endpoints with a non-admin account returns:
  ```json
  {"error": {"code": 105}, "success": false}
  ```
  *(Error 105: Insufficient privilege)*
- **Security Solution**: Create a dedicated operator account (e.g. `nas_doctor`), put it in the `administrators` group, but explicitly check **"No Access"** on all sensitive shared folders (`homes`, `docker`, `backups`) and user apps.

#### FileStation Asynchronous Deletion Traps
- Deleting large non-empty folders (such as databases or node_modules) via the `FileStation` WebAPI is synchronous on the wire but triggers an HTTP timeout (default 120s).
- **Gotcha**: The timeout is purely on the HTTP client side; DSM's background kernel process will continue deleting the tree asynchronously. Do not spam retry requests—wait 30–60s for the background thread to finish.

#### Docker Root Mount Block (`/:/host`)
- DSM 7 kernel explicitly blocks mounting the host root directory `/:/host` into Docker containers for security.
- Containers attempting to mount `/:/host` fail immediately with `context canceled` or `permission denied`.
- **Solution**: Mount exact required directories (e.g. `/var/packages/` or `/volume1/@appdata/`) instead of `/`.

### 🛜 2. Zero-Port-Forward Wildcard SSL via Tailscale

To obtain 100% browser-trusted Let's Encrypt wildcard SSL certificates for internal NAS services without opening any router ports:

1. **Prerequisite**: In [Tailscale Admin Console](https://login.tailscale.com/) → **Settings** → **DNS**, enable **HTTPS Certificates**.
2. **Daemon Socket**: On DSM 7, the native Tailscale daemon socket lives at:
   📂 `/volume1/@appdata/Tailscale/tailscaled.sock`
3. **One-Command Extraction**:
   Run a temporary `tailscale/tailscale:stable` container mounted to the socket:
   ```bash
   docker run --rm \
     -v /volume1/@appdata/Tailscale/tailscaled.sock:/var/run/tailscale/tailscaled.sock \
     -v /volume1/docker/certs:/certs \
     --net=host \
     tailscale/tailscale:stable \
     tailscale cert --cert-file=/certs/cert.pem --key-file=/certs/privkey.pem your-machine.tail-scale.ts.net
   ```
   Valid certificates are written in under 5 seconds!

### 🐳 3. Portainer REST API Nuances

#### Container Path Suffix Requirement
- In Portainer, querying containers under a Docker Engine endpoint requires the **`/json`** suffix:
  - Correct: `GET /api/endpoints/{id}/docker/containers/json?all=1`
  - Wrong: `GET /api/endpoints/{id}/docker/containers` (returns `404 page not found`).

#### Deployment & Restart Timeouts
- When creating large stacks (`/api/stacks/create/standalone/string`), set the client HTTP timeout to at least **180s**.
- Portainer API calls for container `restart` or image `prune` frequently time out on the client side while succeeding on the NAS. Always poll container status before issuing duplicate restart commands.

### 🚀 4. System Kernel & Docker Engine Tuning

#### RAM Swappiness Tuning (`vm.swappiness = 10`)
- By default, Synology DSM sets `vm.swappiness = 60`. If your NAS has upgraded RAM (e.g. 16GB–32GB), this aggressively pushes idle Docker container memory into slow HDD swap partitions, causing random IOPS latency when containers awaken.
- **Tuning**: In DSM **Control Panel** → **Task Scheduler** → **Triggered Task (Boot-up)** as `root`:
  ```bash
  sysctl -w vm.swappiness=10
  ```

#### Docker Console Log Rotation
- Synology Container Manager does not rotate container stdout/stderr logs by default. High-throughput reverse proxies (Caddy, Traefik, Nginx) can balloon logs to tens of gigabytes.
- **Global Limit**: Add to `/etc/docker/daemon.json`:
  ```json
  {
    "log-driver": "json-file",
    "log-opts": {
      "max-size": "10m",
      "max-file": "3"
    }
  }
  ```
- Apply changes safely:
  ```bash
  sudo synosystemctl restart pkg-ContainerManager-dockerd
  ```

---

## 中文说明

本指南记录了在群晖 DSM 7+ 环境下，结合 Docker、Portainer 与自托管服务长期运行过程中总结出来的底层避坑经验与优化技巧。

### 🔑 1. Synology DSM 7+ 物理路径与权限限制

#### WebAPI 权限分层 (`Error 105`)
- **系统级 WebAPI**：`core_sys_info.SysInfo` (如 `sys_status` 和 `network_status`) 必须使用 **DSM 拥有 Administrator 权限** 的账号登录，否则群晖直接返回 `Error 105 - Insufficient privilege`。
- **安全解决方案**：创建一个专用的运维账号（如 `nas_doctor`），加入 `administrators` 组，但在共享文件夹权限中显式对所有私有目录选择“禁止访问”。

#### 文件系统删除超时
- 通过 `FileStation` API 删除非空文件夹（例如带有大量历史数据库的目录）属于耗时操作。
- 在 WebAPI 侧极易触发 **2 分钟（120秒）读取超时**。但**群晖底层会在后台继续异步完成文件夹的完整删除**，客户端切勿频繁重试，等待后台清理完毕即可。

#### Docker 根目录挂载保护
- 群晖 DSM 7 基于内核安全保护，**严格禁止在 Docker 容器中挂载宿主机根目录 `/:/host`**。
- 强行挂载将导致容器启动直接因权限被拒报错（`context canceled` 或 `permission denied`）。
- **解决办法**：必须采用**精确子目录挂载**。例如，只需挂载 `/var/packages/` 或 `/volume1/@appdata/`。

### 🛜 2. Tailscale SSL 证书自动化提取原理

要想在没有公网 IP、不暴露任何路由器端口的情况下，为局域网内的群晖容器申请 100% 被手机和电脑信任的免费 Let's Encrypt SSL 证书：

1. **核心前提**：必须在 [Tailscale Admin Console](https://login.tailscale.com/) 的 **Settings** → **DNS** 中，显式开启 **HTTPS Certificates**。
2. **物理套接字位置**：在群晖 DSM 7 上，宿主机 native 运行的 Tailscale 守护进程套接字路径为：
   📂 `/volume1/@appdata/Tailscale/tailscaled.sock`
3. **容器化一键申请**：
   在终端或 Portainer 中启动一个临时的 `tailscale/tailscale:stable` 容器：
   ```bash
   docker run --rm \
     -v /volume1/@appdata/Tailscale/tailscaled.sock:/var/run/tailscale/tailscaled.sock \
     -v /volume1/docker/certs:/certs \
     --net=host \
     tailscale/tailscale:stable \
     tailscale cert --cert-file=/certs/cert.pem --key-file=/certs/privkey.pem your-machine.tail-scale.ts.net
   ```

### 🐳 3. Portainer REST API 避坑技巧

#### Docker 代理路径补全
- Portainer 的 Docker Engine 代理路径在 `/api/endpoints/{id}/docker/`。
- 查询容器列表的完整路径必须带有 **`/json`** 后缀：
  👉 `GET /api/endpoints/{id}/docker/containers/json?all=1`
- 若请求 `/api/endpoints/{id}/docker/containers`，API 会直接返回 `404 page not found`。

#### 重启与删除超时不是失败证据
- 在部分群晖设备上，Portainer 对容器 `restart`、`delete` 以及 `images/prune` 偶发客户端 180s 超时。
- 超时后必须二次通过 API 确认容器当前状态，避免重复暴力重试。

### 🚀 4. 群晖 OS 底层优化：大内存 Swappiness 与容器日志防爆

#### 1️⃣ RAM 虚拟机交换倾斜度（vm.swappiness）优化
- 群晖默认的 `vm.swappiness = 60` 会极度积极地将闲置容器的堆内存换入到慢速 HDD 机械硬盘（swap 分区）中，导致微服务被意外唤醒时发生明显的卡顿和磁盘 random IOPS 暴增。
- 将 `swappiness` 优化为 `10`，迫使 Linux 内核优先驻留物理内存，显著降低 HDD 损耗和微服务唤醒延迟。
- **持久化方案**：在 **DSM 控制面板 -> 任务计划 -> 新建 -> 触发的任务 -> 用户定义的脚本**，配置 `root` 权限并在 `开机时 (Boot-up)` 执行：
  ```bash
  sysctl -w vm.swappiness=10
  ```

#### 2️⃣ Docker 引擎 stdout/stderr 日志防爆与自动轮转配置
- Synology Container Manager 默认不限制容器运行时日志的大小。高频反代服务标准输出日志会悄悄膨胀到数 GB。
- **全局限额方案**：通过 SSH 写入群晖 Docker 全局引擎配置文件 `/etc/docker/daemon.json`：
  ```json
  {
    "log-driver": "json-file",
    "log-opts": {
      "max-size": "10m",
      "max-file": "3"
    }
  }
  ```
- **配置生效命令**：
  ```bash
  sudo synosystemctl restart pkg-ContainerManager-dockerd
  ```
