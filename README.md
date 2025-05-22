# Tapify Logging Agent

This repo contains the configuration and setup script for deploying **Promtail** and **Node Exporter** on any Tapify machine to:

- Collect Docker logs and forward them to the central **Loki** instance at [`loki.tapify.ro`](https://loki.tapify.ro)
- Expose system metrics to **Prometheus** via a secure VPN connection
- Generate and activate WireGuard VPN configs to securely connect each machine to the metrics server

---

## 📦 What it does

### 🔧 Promtail
- Collects logs from all Docker containers on the machine
- Adds metadata labels like:
  - `project` (from `docker-compose.yml` service labels)
  - `host` (machine hostname)
  - `job=docker`
- Forwards logs securely to **Loki** for centralized analysis via **Grafana**

### 🔐 WireGuard VPN
- Stations connect to the metrics server over WireGuard using static IPs
- No need for DDNS, public IPs, or port forwarding
- Prometheus scrapes node-exporter metrics over the VPN
- VPN interface is automatically started and enabled when configuring the station

---

## 🛠 Setup Instructions

### 1. Clone this repo onto the target machine:

```bash
git clone git@github.com:Tapify-Romania/tapify-logging-agent.git
cd tapify-logging-agent
```

### 2. Run the setup script:

```bash
./setup.sh
```

This will:
- Prompt for VPN details (server public key and endpoint)
- Generate a `.env` file
- Pull and start the required Docker containers (Promtail + Node Exporter)

---

## 🔧 Add the Station to the VPN

Each station needs to be manually added to the VPN network:

1. Run the WireGuard client setup script:

    ```bash
    ./setup-wireguard-client.sh
    ```

2. When prompted, enter:
    - A **station ID** (e.g. `station01`)
    - A **static VPN IP** (e.g. `10.66.66.2`)

3. The script will:
    - Generate `wireguard/wg0-client.conf` and install it to `/etc/wireguard/wg0.conf`
    - Start and enable the WireGuard interface
    - Output `wireguard/peers.conf` — paste the `[Peer]` block into the metrics server's config

4. On the **metrics server**, open:

    ```bash
    sudo vim /etc/wireguard/wg0.conf
    ```

    Paste the peer block, then reload WireGuard:

    ```bash
    sudo systemctl restart wg-quick@wg0
    ```

---

## 🔄 Manually Start VPN (if needed)

If the VPN interface was not started automatically (e.g., you skipped the setup script), run:

```bash
./start-wireguard.sh
```

This will:
- Check if `/etc/wireguard/wg0.conf` exists
- Enable and start the `wg0` interface
- Print verification steps

---

## 🐳 Requirements

- Docker and Docker Compose must be installed
- Docker containers must use the `json-file` logging driver (default)
- WireGuard must be installed on both the station and the metrics server

Example `docker-compose.yml` service:

```yaml
services:
  api:
    image: your-api-image
    labels:
      - "project=api"
    logging:
      driver: "json-file"
      options:
        labels: "project"
```

---

## 📁 Files in this repo

```
tapify-logging-agent/
├── docker-compose.yml             # Starts Promtail and Node Exporter
├── promtail-config.yml            # Promtail configuration
├── setup.sh                       # Prompts for VPN info and runs Docker setup
├── setup-wireguard-client.sh      # Generates and installs client VPN config
├── start-wireguard.sh             # Manually start WireGuard VPN if needed
├── .env.example                   # Template for server public key and endpoint
├── .env                           # Local config generated from .env.example (ignored from Git)
├── wireguard/
│   ├── .gitkeep                   # Ensures folder is tracked
│   ├── wg0-client.conf            # Generated client config (ignored from Git)
│   ├── peers.conf                 # Peer block to paste into metrics server config
│   └── keys/                      # Private/public keys per station (ignored from Git)
```

---

## 📍 Notes

- VPN client configs and keys are stored in `wireguard/` but ignored by Git
- VPN setup is reproducible using `.env`
- Prometheus scrapes stations over VPN (e.g., `10.66.66.2:9100`)
- Loki endpoint is hardcoded to `https://loki.tapify.ro` — update it in `promtail-config.yml` if needed

---

## 📊 View Logs in Grafana

Visit: [https://metrics.tapify.ro](https://metrics.tapify.ro)

1. Go to **Explore**
2. Select Data Source: **Loki**
3. Filter logs by `project`, `host`, or `container`
