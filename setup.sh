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

# Ensure required dependencies are installed
if ! command -v unzip &> /dev/null; then
  echo "📦 Installing required dependency: unzip..."
  sudo apt-get update -y && sudo apt-get install -y unzip
fi

echo -e "\n📦 Installing Promtail..."
PROMTAIL_VERSION="2.9.4"
PROMTAIL_URL="https://github.com/grafana/loki/releases/download/v$PROMTAIL_VERSION/promtail-linux-amd64.zip"
PROMTAIL_BINARY="/usr/local/bin/promtail"

# Download and install Promtail
curl -sL "$PROMTAIL_URL" -o promtail.zip
unzip -o promtail.zip -d .
sudo mv promtail-linux-amd64 "$PROMTAIL_BINARY"
sudo chmod +x "$PROMTAIL_BINARY"
rm promtail.zip

# Use existing promtail-config.yml
PROMTAIL_CONFIG="$(dirname "$0")/promtail-config.yml"
if [ ! -f "$PROMTAIL_CONFIG" ]; then
  echo "❌ promtail-config.yml not found in the script directory. Please add it and re-run the script."
  exit 1
fi

# Ensure Promtail configuration directory exists
PROMTAIL_CONFIG_DIR="/etc/promtail"
PROMTAIL_CONFIG_FILE="$PROMTAIL_CONFIG_DIR/config.yaml"

if [ ! -d "$PROMTAIL_CONFIG_DIR" ]; then
  echo "📂 Creating Promtail configuration directory at $PROMTAIL_CONFIG_DIR..."
  sudo mkdir -p "$PROMTAIL_CONFIG_DIR"
fi

# Copy the Promtail configuration file if it doesn't already exist
if [ ! -f "$PROMTAIL_CONFIG_FILE" ]; then
  echo "📄 Copying Promtail configuration file to $PROMTAIL_CONFIG_FILE..."
  sudo cp "$(dirname "$0")/promtail-config.yml" "$PROMTAIL_CONFIG_FILE"
else
  echo "✅ Promtail configuration file already exists at $PROMTAIL_CONFIG_FILE. Skipping copy."
fi

# Create Promtail service
sudo tee /etc/systemd/system/promtail.service > /dev/null <<EOF
[Unit]
Description=Promtail Service
After=network.target

[Service]
ExecStart=/usr/local/bin/promtail --config.file=$PROMTAIL_CONFIG_FILE
Restart=always
User=nobody
Group=nogroup

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable the Promtail service
sudo systemctl daemon-reload
sudo systemctl enable promtail
sudo systemctl restart promtail
echo "✅ Promtail service configured and running."


echo -e "\n📦 Installing Node Exporter..."
NODE_EXPORTER_VERSION="1.6.1"
NODE_EXPORTER_URL="https://github.com/prometheus/node_exporter/releases/download/v$NODE_EXPORTER_VERSION/node_exporter-$NODE_EXPORTER_VERSION.linux-amd64.tar.gz"
NODE_EXPORTER_BINARY="/usr/local/bin/node_exporter"

# Download and install Node Exporter
curl -sL "$NODE_EXPORTER_URL" -o node_exporter.tar.gz
tar -xvf node_exporter.tar.gz --strip-components=1 -C . "node_exporter-$NODE_EXPORTER_VERSION.linux-amd64/node_exporter"
sudo mv node_exporter "$NODE_EXPORTER_BINARY"
sudo chmod +x "$NODE_EXPORTER_BINARY"
rm node_exporter.tar.gz

# Create Node Exporter service
sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<EOF
[Unit]
Description=Node Exporter
After=network.target

[Service]
ExecStart=$NODE_EXPORTER_BINARY
Restart=always
User=nobody
Group=nogroup

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable node_exporter
sudo systemctl start node_exporter
echo "✅ Node Exporter installed and running."

# ────────────────────────────────────────────────────────────────
# 🚀 Step 4: Install Netbird
# ────────────────────────────────────────────────────────────────

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


