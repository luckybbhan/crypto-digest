#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== crypto-digest collector deploy =="
echo "repo: $ROOT_DIR"

mkdir -p logs data

ensure_env() {
  local key="$1"
  local value="$2"
  if [[ ! -f .env ]]; then
    touch .env
    chmod 600 .env
  fi
  if ! grep -q "^${key}=" .env; then
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

ensure_env "MINIFLUX_URL" "http://localhost:8080"
ensure_env "MINIFLUX_USERNAME" "admin"
ensure_env "MINIFLUX_PASSWORD" "change-me"
ensure_env "MINIFLUX_ADMIN_USERNAME" "admin"
ensure_env "MINIFLUX_ADMIN_PASSWORD" "change-me"
ensure_env "MINIFLUX_POSTGRES_PASSWORD" "miniflux_secret"
ensure_env "RSSHUB_URL" "http://rsshub:1200"
ensure_env "ENABLE_RSSHUB_FEEDS" "1"
ensure_env "ENABLE_REPLACEMENT_FEEDS" "1"
ensure_env "ENABLE_FORESIGHT_API" "1"
chmod 600 .env

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "== starting Miniflux/RSSHub =="
docker compose -f docker-compose.miniflux.yml up -d

echo "== waiting for Miniflux API =="
for i in {1..60}; do
  if python3 miniflux_client.py --check >/tmp/crypto-digest-miniflux-check.log 2>&1; then
    cat /tmp/crypto-digest-miniflux-check.log
    break
  fi
  if [[ "$i" == "60" ]]; then
    echo "Miniflux did not become ready in time. Last check:"
    cat /tmp/crypto-digest-miniflux-check.log || true
    exit 1
  fi
  sleep 5
done

echo "== ensuring RSS feeds =="
python3 miniflux_client.py --ensure-feeds

echo "== requesting RSS refresh =="
python3 miniflux_client.py --refresh

echo "== collecting non-RSS history once =="
python3 source_collector.py --hours 24

echo "== installing collector cron =="
collector_cmd="cd $ROOT_DIR && . .venv/bin/activate && python3 source_collector.py --hours 24 >> logs/source_collector.log 2>&1"
refresh_cmd="cd $ROOT_DIR && . .venv/bin/activate && python3 miniflux_client.py --refresh >> logs/miniflux_refresh.log 2>&1"
tmp_cron="$(mktemp)"
crontab -l 2>/dev/null | grep -v "crypto-digest/source_collector.py" | grep -v "crypto-digest/miniflux_client.py --refresh" > "$tmp_cron" || true
{
  cat "$tmp_cron"
  printf '*/10 * * * * %s\n' "$collector_cmd"
  printf '5 * * * * %s\n' "$refresh_cmd"
} | crontab -
rm -f "$tmp_cron"

echo "== current status =="
docker compose -f docker-compose.miniflux.yml ps
python3 miniflux_client.py --check || true
python3 source_history.py --hours 24 || true

echo "== done =="
echo "Collectors are running. Let them collect for 24h, then run:"
echo "  cd $ROOT_DIR && source .venv/bin/activate && python3 debug_pipeline.py --source miniflux --hours 24 --sample-per-source 10"
