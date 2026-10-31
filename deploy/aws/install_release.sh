#!/bin/bash
# Called by SSM as root; never enable shell tracing or print runtime.json.
set -euo pipefail
umask 077
release=$1
domain=$2
runtime=$3
[[ "$release" =~ ^/opt/stream-chat/releases/[a-f0-9]{32}$ ]] || exit 2
[[ "$domain" =~ ^[a-z0-9][a-z0-9.-]+[a-z0-9]$ ]] || exit 2
[[ "$runtime" =~ ^/var/tmp/stream-chat-runtime\.[a-zA-Z0-9]+$ ]] || exit 2
test -f /var/lib/stream-chat-bootstrap.ready
exec 9>/var/lock/stream-chat-deploy.lock
flock -n 9 || { echo "Another release is being installed."; exit 1; }
cd "$release"
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r deploy/aws/requirements.txt
.venv/bin/python -B -m deploy.aws.run_server --config "$runtime" --check
chmod -R go+rX "$release"
cat > "$release/Caddyfile" <<EOF
$domain {
    reverse_proxy 127.0.0.1:8766
}
EOF
# Caddy access logging stays disabled: OAuth codes must not enter access logs.
caddy validate --config "$release/Caddyfile" --adapter caddyfile
previous=$(readlink -f /opt/stream-chat/current || true)
had_runtime=0
had_caddy=0
if test -f /etc/stream-chat/runtime.json; then
    cp -p /etc/stream-chat/runtime.json /etc/stream-chat/runtime.previous.json
    had_runtime=1
fi
if test -f /etc/caddy/Caddyfile; then
    cp -p /etc/caddy/Caddyfile /etc/caddy/Caddyfile.previous
    had_caddy=1
fi
rollback() {
    trap - ERR
    if test "$had_runtime" = 1; then cp -p /etc/stream-chat/runtime.previous.json /etc/stream-chat/runtime.json; fi
    if test "$had_caddy" = 1; then cp -p /etc/caddy/Caddyfile.previous /etc/caddy/Caddyfile; fi
    if test -n "$previous" && test -d "$previous"; then
        ln -sfn "$previous" /opt/stream-chat/current
        systemctl restart stream-chat || true
        systemctl restart caddy || true
    else
        systemctl stop stream-chat caddy || true
    fi
    echo "Release failed; restored the previous release where available. State files were preserved."
    exit 1
}
trap rollback ERR
install -m 640 -o root -g stream-chat "$runtime" /etc/stream-chat/runtime.json
install -m 644 deploy/aws/stream-chat.service /etc/systemd/system/stream-chat.service
install -m 644 "$release/Caddyfile" /etc/caddy/Caddyfile
ln -sfn "$release" /opt/stream-chat/current
systemctl daemon-reload
systemctl enable stream-chat caddy
systemctl restart stream-chat
healthy=0
for attempt in $(seq 1 30); do
    if curl --fail --silent http://127.0.0.1:8766/healthz >/dev/null; then healthy=1; break; fi
    sleep 1
done
test "$healthy" = 1
systemctl restart caddy
trap - ERR
echo "Backend healthy. HTTPS becomes available after the DNS A record points to this instance."
