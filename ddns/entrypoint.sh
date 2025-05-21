#!/bin/sh
echo "🚀 Starting DDNS updater loop..."
while true; do
  /app/update-ddns.sh
  sleep 300  # 5 minutes
done
