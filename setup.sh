#!/bin/bash
set -e

PROMTAIL_VERSION="2.9.4"
TEMPLATE_FILE=".env.example"
OUTPUT_FILE=".env"

# ────────────────────────────────────────────────────────────────
# 📄 Step 1: Generate .env from .env.example
# ────────────────────────────────────────────────────────────────

if [ -f "$OUTPUT_FILE" ]; then
  echo "⚠️  $OUTPUT_FILE already exists."
  echo -n "❓ Do you want to recreate it from $TEMPLATE_FILE? [y/N]: " > /dev/tty
  read recreate < /dev/tty
  if [[ "$recreate" =~ ^[Yy]$ ]]; then
    recreate_env_file=true
  else
    recreate_env_file=false
  fi
else
  recreate_env_file=true
fi

if $recreate_env_file; then
  echo "🛠 Creating $OUTPUT_FILE from $TEMPLATE_FILE..."

  > "$OUTPUT_FILE"

  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^#.*$ || -z "$line" ]]; then
      echo "$line" >> "$OUTPUT_FILE"
      continue
    fi

    key="${line%%=*}"
    default_val="${line#*=}"

    echo "🔧 Setting key: $key"
    echo -n "   → Enter value [default: $default_val]: " > /dev/tty
    read user_input < /dev/tty

    final_val="${user_input:-$default_val}"
    echo "$key=$final_val" >> "$OUTPUT_FILE"
  done < "$TEMPLATE_FILE"

  echo -e "\n✅ Final .env:"
  cat "$OUTPUT_FILE"
else
  echo "✅ Skipping .env creation."
fi

# ────────────────────────────────────────────────────────────────
# 🧪 Step 2: Export env vars for other scripts
# ────────────────────────────────────────────────────────────────

export $(grep -v '^#' "$OUTPUT_FILE" | xargs)

# Validate required env vars
if [[ -z "$NETBIRD_SETUP_KEY" ]]; then
  echo "❌ Missing NETBIRD_SETUP_KEY in .env"
  exit 1
fi

# ────────────────────────────────────────────────────────────────
# 🚀 Step 3: Install Promtail + Node Exporter
# ────────────────────────────────────────────────────────────────

echo -e "\n📦 Pulling Promtail Docker image..."
docker pull grafana/promtail:$PROMTAIL_VERSION

echo "🚀 Starting all containers with docker compose..."
docker compose up -d

echo "✅ All containers are up and running."

# ────────────────────────────────────────────────────────────────
# 🚀 Step 4: Install Netbird
# ────────────────────────────────────────────────────────────────

# Wait for apt lock to be released
while sudo fuser /var/lib/apt/lists/lock >/dev/null 2>&1; do
  echo "⏳ Waiting for apt lock to be released..."
  sleep 5
done

echo -e "\n📦 Installing Netbird..."
curl -fsSL https://pkgs.netbird.io/install.sh | bash

echo "🚀 Starting Netbird service..."
sudo systemctl enable netbird
sudo systemctl start netbird

echo "✅ Netbird installed and running."

# ────────────────────────────────────────────────────────────────
# 🔑 Step 5: Join Netbird Network
# ────────────────────────────────────────────────────────────────

sudo netbird up --setup-key "$NETBIRD_SETUP_KEY"

echo "✅ Machine joined to Netbird network."


