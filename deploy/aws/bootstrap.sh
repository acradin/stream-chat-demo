#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y --no-install-recommends python3-venv python3-pip awscli curl ca-certificates gnupg debian-keyring debian-archive-keyring
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key -o /tmp/caddy-key.asc
gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg /tmp/caddy-key.asc
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt -o /etc/apt/sources.list.d/caddy-stable.list
chmod 644 /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
apt-get update -q
apt-get install -y --no-install-recommends caddy
systemctl stop caddy
id stream-chat >/dev/null 2>&1 || useradd --system --home /var/lib/stream-chat --shell /usr/sbin/nologin stream-chat
install -d -m 700 -o stream-chat -g stream-chat /var/lib/stream-chat
install -d -m 750 -o root -g stream-chat /etc/stream-chat
install -d -m 755 /opt/stream-chat/releases
touch /var/lib/stream-chat-bootstrap.ready
