#!/bin/bash
set -e

echo "📦 Installing Promtail..."

docker pull grafana/promtail:2.9.4

echo "🔧 Launching Promtail container..."

docker compose up -d

echo "✅ Promtail is now running and shipping logs to Loki."
