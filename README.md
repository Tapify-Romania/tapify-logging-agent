# Tapify Logging Agent

This repo contains the configuration and setup script for deploying **Promtail** on any Tapify machine to collect Docker logs and forward them to the central **Loki** instance hosted at [`loki.tapify.ro`](https://loki.tapify.ro).

---

## 📦 What it does

- Collects logs from all Docker containers on the machine
- Adds metadata labels like:
  - `project` (from `docker-compose.yml` service labels)
  - `host` (machine hostname)
  - `job=docker`
- Forwards logs securely to **Loki** for centralized analysis via **Grafana**

---

## 🛠 Setup Instructions

1. **Clone this repo** onto the target machine:

    ```bash
    git clone git@github-station:Tapify-Romania/tapify-logging-agent.git
    cd tapify-logging-agent
    ```

2. **Run the setup script:**

    ```bash
    ./setup-promtail.sh
    ```

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

## 📁 Files in this repo

```
tapify-logging-agent/
├── promtail-config.yml      # Promtail configuration
├── docker-compose.yml       # Starts Promtail as a container
├── setup-promtail.sh        # Installs + starts Promtail
├── README.md                # You're here
```

---

## 📍 Notes

- Promtail runs with `restart: unless-stopped` so it stays up after reboot
- Logs can be filtered in Grafana by `project`, `host`, or `container_name`
- Loki endpoint is hardcoded to `https://loki.tapify.ro` — update if needed

---

## 📊 View Logs in Grafana

Go to: [https://metrics.tapify.ro](https://metrics.tapify.ro)

Then:

1. Explore → Select Data Source: **Loki**
2. Filter by `project`, `host`, `container`, etc.
3. Visualize or alert as needed
