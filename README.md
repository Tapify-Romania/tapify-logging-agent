# Tapify Logging Agent

This repo contains the configuration and setup script for deploying **Promtail** on any Tapify machine to collect Docker logs and forward them to the central **Loki** instance hosted at [`loki.tapify.ro`](https://loki.tapify.ro).  
It also includes a **Cloudflare Dynamic DNS updater** to make each machine reachable via a subdomain (even with dynamic IPs), enabling Prometheus scraping from a central location.

---

## 📦 What it does

### 🔧 Promtail
- Collects logs from all Docker containers on the machine
- Adds metadata labels like:
  - `project` (from `docker-compose.yml` service labels)
  - `host` (machine hostname)
  - `job=docker`
- Forwards logs securely to **Loki** for centralized analysis via **Grafana**

### 🌐 Cloudflare DDNS
- Automatically updates a specific subdomain (e.g., `station01.example.com`) via Cloudflare when the machine’s external IP changes
- Ensures the machine remains reachable for **Prometheus** even on dynamic IPs

---

## 🛠 Setup Instructions

1. **Clone this repo** onto the target machine:

    ```bash
    git clone git@github-station:Tapify-Romania/tapify-logging-agent.git
    cd tapify-logging-agent
    ```

2. **Run the setup script:**

    ```bash
    ./setup.sh
    ```

    This will:
    - Prompt you for Cloudflare credentials and generate `ddns/.env` from `ddns/.env.example`
    - Pull the required Docker images
    - Start Promtail, Node Exporter, and the Cloudflare DDNS updater

---

## 🐳 Requirements

- Docker and Docker Compose must be installed
- Docker containers must use the `json-file` logging driver (default)
- Your `docker-compose.yml` files should include `labels` like `project=api`, `project=dashboard`, etc.

Example:

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

## 🌐 Cloudflare DDNS Setup

The first time you run `setup.sh`, you’ll be prompted for the following environment variables (from `ddns/.env.example`):

```env
CF_API_TOKEN=your_cloudflare_api_token
CF_ZONE_ID=your_zone_id
CF_RECORD_ID=your_dns_record_id
CF_RECORD_NAME=station01.example.com
```

This `.env` file is used by the `ddns-updater` Docker container to:

- Check the public IP of the machine every 5 minutes
- Update the A record in Cloudflare if it changes

> 📌 You can retrieve `ZONE_ID` and `RECORD_ID` using the [Cloudflare API](https://developers.cloudflare.com/api/).

---

## 📁 Files in this repo

```
tapify-logging-agent/
├── promtail-config.yml       # Promtail configuration
├── docker-compose.yml        # Promtail + Node Exporter + DDNS updater
├── setup.sh                  # Full setup script
├── ddns/
│   ├── .env.example          # Template for DDNS credentials
│   ├── update-ddns.sh        # Cloudflare IP updater
│   ├── entrypoint.sh         # Runs update loop every 5 minutes
│   └── Dockerfile            # Lightweight Alpine-based updater container
├── README.md                 # You're here
```

---

## 📍 Notes

- Promtail and the DDNS container run with `restart: unless-stopped` so they persist across reboots
- Logs can be filtered in Grafana by `project`, `host`, or `container_name`
- Loki endpoint is hardcoded to `https://loki.tapify.ro` — update it in `promtail-config.yml` if needed

---

## 📊 View Logs in Grafana

Go to: [https://metrics.tapify.ro](https://metrics.tapify.ro)

Then:

1. Explore → Select Data Source: **Loki**
2. Filter by `project`, `host`, `container`, etc.
3. Visualize or alert as needed
