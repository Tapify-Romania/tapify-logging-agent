#!/bin/bash
set -e

# ────────────────────────────────────────────────────────────────
# 📦 Step 0: Ensure WireGuard is installed
# ────────────────────────────────────────────────────────────────

if ! command -v wg &> /dev/null; then
  echo "📦 WireGuard not found. Installing..."
  sudo apt update
  sudo apt install wireguard -y
else
  echo "✅ WireGuard is already installed."
fi

# ────────────────────────────────────────────────────────────────
# 🌍 Load variables from .env
# ────────────────────────────────────────────────────────────────

ENV_FILE="./.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ .env file not found at $ENV_FILE"
  echo "ℹ️  Run ./setup.sh first to generate it."
  exit 1
fi

# Export variables from .env
export $(grep -v '^#' "$ENV_FILE" | xargs)

# Validate required env vars
if [[ -z "$WG_SERVER_PUBLIC_KEY" || -z "$WG_SERVER_ENDPOINT" ]]; then
  echo "❌ Missing WG_SERVER_PUBLIC_KEY or WG_SERVER_ENDPOINT in .env"
  exit 1
fi

# Paths
KEYS_DIR="./wireguard/keys"
CONF_OUT="./wireguard/wg0-client.conf"
PEERS_OUT="./wireguard/peers.conf"
WG_SYSTEM_PATH="/etc/wireguard/wg0.conf"

mkdir -p "$KEYS_DIR"

# ────────────────────────────────────────────────────────────────
# 🔧 Step 1: Prompt for station ID and VPN IP
# ────────────────────────────────────────────────────────────────

read -p "Enter station ID (e.g., station01): " STATION_ID
read -p "Enter static VPN IP (e.g., 10.66.66.2): " CLIENT_IP

# ────────────────────────────────────────────────────────────────
# 🔐 Step 2: Generate WireGuard keypair
# ────────────────────────────────────────────────────────────────

PRIVATE_KEY=$(wg genkey)
PUBLIC_KEY=$(echo "$PRIVATE_KEY" | wg pubkey)

echo "$PRIVATE_KEY" > "$KEYS_DIR/${STATION_ID}.priv"
echo "$PUBLIC_KEY"  > "$KEYS_DIR/${STATION_ID}.pub"

# ────────────────────────────────────────────────────────────────
# 🧾 Step 3: Generate client config
# ────────────────────────────────────────────────────────────────

cat <<EOF > "$CONF_OUT"
[Interface]
PrivateKey = $PRIVATE_KEY
Address = $CLIENT_IP/32

[Peer]
PublicKey = $WG_SERVER_PUBLIC_KEY
Endpoint = $WG_SERVER_ENDPOINT
AllowedIPs = 10.66.66.1/32
PersistentKeepalive = 25
EOF

# ────────────────────────────────────────────────────────────────
# 📎 Step 4: Output peer block for server
# ────────────────────────────────────────────────────────────────

cat <<EOF > "$PEERS_OUT"
[Peer]
# $STATION_ID
PublicKey = $PUBLIC_KEY
AllowedIPs = $CLIENT_IP/32
EOF

# ────────────────────────────────────────────────────────────────
# ⚙️ Step 5: Deploy config and start VPN
# ────────────────────────────────────────────────────────────────

echo "📂 Copying $CONF_OUT → $WG_SYSTEM_PATH"
sudo cp "$CONF_OUT" "$WG_SYSTEM_PATH"

echo "🟢 Enabling and starting wg-quick@wg0"
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0

# ────────────────────────────────────────────────────────────────
# ✅ Done
# ────────────────────────────────────────────────────────────────

echo -e "\n✅ WireGuard client config saved to: $WG_SYSTEM_PATH"
echo -e "📎 Peer block for metrics server saved to: $PEERS_OUT\n"
cat "$PEERS_OUT"

echo -e "\n📋 Paste the above block into the metrics server's /etc/wireguard/wg0.conf and run:\n"
echo "    sudo systemctl restart wg-quick@wg0"

echo -e "\n🧪 To verify the VPN connection:"
echo "    ping 10.66.66.1"
echo "    sudo wg show"
