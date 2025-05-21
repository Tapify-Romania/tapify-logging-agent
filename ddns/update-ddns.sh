#!/bin/bash
set -e

# Load variables from .env
ENV_PATH="/app/.env"
if [ -f "$ENV_PATH" ]; then
  export $(grep -v '^#' "$ENV_PATH" | xargs)
else
  echo "❌ .env file not found at $ENV_PATH"
  exit 1
fi

ZONE_ID="$CF_ZONE_ID"
RECORD_ID="$CF_RECORD_ID"
API_TOKEN="$CF_API_TOKEN"
RECORD_NAME="$CF_RECORD_NAME"

CURRENT_IP=$(curl -s https://api.ipify.org)
DNS_IP=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" | jq -r .result.content)

if [ "$CURRENT_IP" != "$DNS_IP" ]; then
  echo "🌀 Updating $RECORD_NAME to $CURRENT_IP"
  curl -s -X PUT "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" \
    --data "{\"type\":\"A\",\"name\":\"$RECORD_NAME\",\"content\":\"$CURRENT_IP\",\"ttl\":120,\"proxied\":false}"
else
  echo "✅ IP unchanged ($CURRENT_IP), no update needed."
fi
