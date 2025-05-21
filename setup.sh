#!/bin/bash
set -e

PROMTAIL_VERSION="2.9.4"
DDNS_TEMPLATE="ddns/.env.example"
DDNS_ENV="ddns/.env"

# ────────────────────────────────────────────────────────────────
# 🌐 Step 1: Prompt and generate ddns/.env
# ────────────────────────────────────────────────────────────────

if [ -f "$DDNS_ENV" ]; then
  echo "⚠️  $DDNS_ENV already exists."
  echo -n "❓ Do you want to recreate it from $DDNS_TEMPLATE? [y/N]: " > /dev/tty
  read recreate < /dev/tty
  if [[ "$recreate" =~ ^[Yy]$ ]]; then
    recreate_ddns_env=true
  else
    recreate_ddns_env=false
  fi
else
  recreate_ddns_env=true
fi

if $recreate_ddns_env; then
  echo "🛠 Creating $DDNS_ENV from $DDNS_TEMPLATE..."

  > "$DDNS_ENV"

  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^#.*$ || -z "$line" ]]; then
      echo "$line" >> "$DDNS_ENV"
      continue
    fi

    key="${line%%=*}"
    default_val="${line#*=}"

    echo "🔧 Setting key: $key"
    echo -n "   → Enter value [default: $default_val]: " > /dev/tty
    read user_input < /dev/tty

    final_val="${user_input:-$default_val}"
    echo "$key=$final_val" >> "$DDNS_ENV"
  done < "$DDNS_TEMPLATE"

  echo -e "\n✅ Final ddns/.env:"
  cat "$DDNS_ENV"
else
  echo "✅ Skipping $DDNS_ENV creation."
fi

# ────────────────────────────────────────────────────────────────
# 🚀 Step 2: Pull Promtail image
# ────────────────────────────────────────────────────────────────

echo -e "\n📦 Pulling Promtail Docker image..."
docker pull grafana/promtail:$PROMTAIL_VERSION

# ────────────────────────────────────────────────────────────────
# 🐳 Step 3: Start Docker Compose
# ────────────────────────────────────────────────────────────────

echo "🚀 Starting all containers with docker compose..."
docker compose up -d

echo "✅ All containers are up and running."
