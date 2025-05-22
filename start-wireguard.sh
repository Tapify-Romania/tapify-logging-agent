#!/bin/bash
set -e

WG_IFACE="wg0"
WG_CONF="/etc/wireguard/$WG_IFACE.conf"

if [ ! -f "$WG_CONF" ]; then
  echo "❌ WireGuard config not found at $WG_CONF"
  echo "ℹ️ Run ./setup-wireguard-client.sh first to generate and install it."
  exit 1
fi

echo "📡 Enabling and starting WireGuard tunnel: $WG_IFACE"

sudo systemctl enable wg-quick@$WG_IFACE
sudo systemctl start wg-quick@$WG_IFACE

echo "✅ WireGuard VPN started successfully."
echo
echo "🧪 To check status: sudo wg show"
echo "📶 To ping the metrics server: ping 10.66.66.1"
