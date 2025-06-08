# Tapify Logging Agent

This repo contains the configuration and setup script for deploying **Promtail** and **Node Exporter** on any Tapify machine to:

- Collect Docker logs and forward them to the central **Loki** instance at [`loki.tapify.ro`](https://loki.tapify.ro)
- Expose system metrics to **Prometheus** via a secure VPN connection
- Setups **Netbird** VPN and adds the machine to the **Netbird** dashboard for easy management

---

## 📦 What it does

### 🔧 Promtail
- Collects logs from all Docker containers on the machine
- Adds metadata labels like:
  - `project` (from `docker-compose.yml` service labels)
  - `host` (machine hostname)
  - `job=docker`
- Forwards logs securely to **Loki** for centralized analysis via **Grafana**

### 🔐 Netbird VPN
- Stations connect to the metrics server over Netbird VPN using static IPs
- No need for DDNS, public IPs, or port forwarding
- Prometheus scrapes node-exporter metrics over the VPN
- VPN interface is automatically started and enabled when configuring the station. You will need a Netbird setup key so that the machine is added to the Netbird dashboard.

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
- Prompt for Netbird Setup key which can be created from the [Netbird dashboard](https://app.netbird.io)
- Generate a `.env` file
- Pull and start the required Docker containers (Promtail + Node Exporter)
- Install and start Netbird and set it to run on boot

---

## 🔄 Manually Start Netbird (if needed)

If the VPN interface was not started automatically (e.g., you skipped the setup script), run:

```bash
netbird up

# to restart it use
netbird restart
```

---

## 📁 Files in this repo

```
tapify-logging-agent/
├── docker-compose.yml             # Starts Promtail and Node Exporter
├── promtail-config.yml            # Promtail configuration
├── setup.sh                       # Prompts for Netbird info and runs Docker setup
├── .env.example                   # Template for server public key and endpoint
├── .env                           # Local config generated from .env.example (ignored from Git)
```

---

## 📍 Notes

- Prometheus scrapes stations over VPN (e.g., `10.66.66.2:9100`)
- Loki endpoint is hardcoded to `https://loki.tapify.ro` — update it in `promtail-config.yml` if needed

---

## 📊 View Logs in Grafana

Visit: [https://metrics.tapify.ro](https://metrics.tapify.ro)

1. Go to **Explore**
2. Select Data Source: **Loki**
3. Filter logs by `project`, `host`, or `container`
