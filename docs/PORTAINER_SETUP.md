# How to Configure Portainer Access Token for NAS-Pulse / Portainer 访问令牌配置指南

[English](#english) • [中文说明](#中文说明)

---

## English

NAS-Pulse optionally integrates with Portainer to inspect Docker stack statuses, detect dangling anonymous volumes, and find unused Docker bridge networks.

### 🔒 Security Best Practice: Use Access Tokens (API Keys)

Never use your Portainer master username and password. Portainer provides scoped **Access Tokens** that can be revoked at any time.

### 🛠️ Step-by-Step Token Creation

1. Open **Portainer** in your browser (e.g. `http://<your-nas-ip>:9000`).
2. Log in as an administrator or operational user.
3. In the top right corner, click on your **User Profile Icon** → select **My Account**.
4. Scroll down to the **Access tokens** section.
5. Click **+ Add access token**.
6. Enter a description: `nas-pulse-auditor`.
7. Click **Create access token**.
8. **Copy the token immediately** (Portainer only displays it once!).

### ⚡ Integrating with NAS-Pulse

During `nas-pulse setup`:
1. When asked `? 是否配置了 Portainer 协助监控 Docker 堆栈与悬空网络/卷?`, choose `y`.
2. Enter your Portainer address (e.g. `http://192.168.1.100:9000`).
3. Paste the Access Token.

Or manually configure your `.env`:
```bash
PORTAINER_URL=http://192.168.1.100:9000
PORTAINER_TOKEN=ptr_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Run `nas-pulse doctor` to verify:
```text
Portainer API 探测: ✔ PASS (成功连通，已识别 1 个 Docker 端点)
```

---

## 中文说明

NAS-Pulse 支持可选接入 Portainer，以提供对 Docker 容器堆栈（Stacks）、无主悬空匿名卷（Dangling Volumes）以及闲置孤儿桥接网络（Unused Networks）的环境卫生监测。

### 🔒 安全最佳实践：使用访问令牌 (Access Token)

切勿在监控工具中配置 Portainer 的主登录密码。Portainer 提供了原生可随时吊销的 **Access Token (API Key)** 机制。

### 🛠️ 创建访问令牌步骤

1. 在浏览器中打开你的 **Portainer**（例如 `http://<your-nas-ip>:9000`）。
2. 使用管理员或运维账号登录。
3. 点击右上角 **用户头像** → 选择 **My Account (我的账户)**。
4. 页面向下滑动至 **Access tokens (访问令牌)** 区域。
5. 点击 **+ Add access token (添加访问令牌)**。
6. 填写描述名称：`nas-pulse-auditor`。
7. 点击 **Create access token**。
8. **立即复制生成的 Token 字符串**（该令牌仅展示一次！）。

### ⚡ 接入 NAS-Pulse

在运行 `nas-pulse setup` 时：
1. 当提示 `? 是否配置了 Portainer 协助监控 Docker 堆栈与悬空网络/卷?` 时选择 `y`。
2. 输入你的 Portainer 地址（例如 `http://192.168.1.100:9000`）。
3. 粘贴刚才复制的 Access Token。

或直接编辑 `.env` 文件：
```bash
PORTAINER_URL=http://192.168.1.100:9000
PORTAINER_TOKEN=ptr_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

运行 `nas-pulse doctor` 即可验证连通性：
```text
Portainer API 探测 / Probe: ✔ PASS (成功连通，已识别 1 个 Docker 端点)
```
