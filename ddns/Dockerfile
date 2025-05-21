FROM alpine:latest

RUN apk add --no-cache curl jq bash

WORKDIR /app

COPY update-ddns.sh .
COPY entrypoint.sh .
COPY .env .env

RUN chmod +x update-ddns.sh entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
