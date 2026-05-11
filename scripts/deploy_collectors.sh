#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== crypto-digest collector deploy =="
echo "repo: $ROOT_DIR"

mkdir -p logs data

if docker ps >/dev/null 2>&1; then
  DOCKER=(docker)
elif sudo -n docker ps >/dev/null 2>&1; then
  DOCKER=(sudo docker)
else
  echo "Docker is not accessible for this user."
  echo "Try: sudo usermod -aG docker $(whoami), then log out/in; or run this script with sudo-capable access."
  exit 1
fi

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
ensure_env "MINIFLUX_USER_AGENT" "Mozilla/5.0 (compatible; crypto-digest/1.0)"
chmod 600 .env

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "== starting Miniflux/RSSHub =="
"${DOCKER[@]}" compose -f docker-compose.miniflux.yml up -d

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
begin_marker="# crypto-digest collectors begin"
end_marker="# crypto-digest collectors end"
collector_cmd="cd $ROOT_DIR && . .venv/bin/activate && python3 source_collector.py --hours 24 >> logs/source_collector.log 2>&1"
refresh_cmd="cd $ROOT_DIR && . .venv/bin/activate && python3 miniflux_client.py --refresh >> logs/miniflux_refresh.log 2>&1"
snapshot_cmd="cd $ROOT_DIR && . .venv/bin/activate && python3 daily_source_snapshot.py --source miniflux --hours 24 >> logs/daily_source_snapshot.log 2>&1"
digest_cmd="cd $ROOT_DIR && . .venv/bin/activate && python3 digest.py --source miniflux >> logs/daily_digest.log 2>&1"
tmp_cron="$(mktemp)"
crontab -l 2>/dev/null | awk "
  /^${begin_marker}$/ {skip=1; next}
  /^${end_marker}$/ {skip=0; next}
  !skip {print}
" > "$tmp_cron" || true
{
  cat "$tmp_cron"
  printf '%s\n' "$begin_marker"
  printf '*/10 * * * * %s\n' "$collector_cmd"
  printf '5 * * * * %s\n' "$refresh_cmd"
  printf '50 0 * * * %s\n' "$refresh_cmd"
  printf '52 0 * * * %s\n' "$collector_cmd"
  printf '55 0 * * * %s\n' "$snapshot_cmd"
  printf '0 1 * * * %s\n' "$digest_cmd"
  printf '%s\n' "$end_marker"
} | crontab -
rm -f "$tmp_cron"

echo "== current status =="
"${DOCKER[@]}" compose -f docker-compose.miniflux.yml ps
python3 miniflux_client.py --check || true
python3 source_history.py --hours 24 || true

echo "== done =="
echo "Collectors are running. Let them collect for 24h, then run:"
echo "  cd $ROOT_DIR && source .venv/bin/activate && python3 debug_pipeline.py --source miniflux --hours 24 --sample-per-source 10"
echo "Daily source snapshots are written to:"
echo "  $ROOT_DIR/exports/source_snapshots/latest"
echo "Daily Telegram digest is scheduled at 09:00 Asia/Shanghai (01:00 UTC) to the test group."
