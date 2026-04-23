# Miniflux Collector Setup

Miniflux is the recommended collector layer for this project. It continuously
polls RSS feeds, stores article history, and lets `digest.py` generate the daily
brief from cached entries instead of relying on the current RSS window.

## Why Use Miniflux

RSS feeds often return only the latest 20-100 entries. If the digest runs once a
day, older entries may already have rolled out of the feed. Miniflux reduces this
risk by polling feeds throughout the day and storing every seen entry.

Target flow:

```text
Miniflux polls RSS feeds every 15-30 minutes
-> Miniflux stores and deduplicates entries
-> digest.py reads last 24h entries from Miniflux
-> digest.py still fetches exchange announcements directly
-> Telegram/Telegraph output
```

## Local Start

Start Miniflux and Postgres:

```bash
docker compose -f docker-compose.miniflux.yml up -d
```

Open Miniflux:

```text
http://localhost:8080
```

Default local credentials from `docker-compose.miniflux.yml`:

```text
username: admin
password: change-me
```

For production, override these with environment variables before first startup:

```bash
export MINIFLUX_ADMIN_USERNAME=admin
export MINIFLUX_ADMIN_PASSWORD='use-a-strong-password'
export MINIFLUX_POSTGRES_PASSWORD='use-a-strong-db-password'
docker compose -f docker-compose.miniflux.yml up -d
```

## Configure API Access

In the Miniflux UI:

1. Open `Settings`.
2. Open `API Keys`.
3. Create a new API key.
4. Add it to local `.env`:

```bash
MINIFLUX_URL=http://localhost:8080
MINIFLUX_API_TOKEN=your-api-token
```

Alternatively, use username/password in `.env`:

```bash
MINIFLUX_URL=http://localhost:8080
MINIFLUX_USERNAME=admin
MINIFLUX_PASSWORD=change-me
```

API token is preferred.

## Import Current Feeds

Create any missing RSS feeds from `config.py`:

```bash
python3 miniflux_client.py --ensure-feeds
```

Ask Miniflux to refresh all feeds:

```bash
python3 miniflux_client.py --refresh
```

Check feed count and last-24h entry count:

```bash
python3 miniflux_client.py --check
```

## Run Digest From Miniflux

Dry-run using Miniflux as the RSS source:

```bash
python3 digest.py --source miniflux --dry-run
```

Send to the test group:

```bash
python3 digest.py --source miniflux
```

Send to production:

```bash
python3 digest.py --source miniflux --prod
```

Publish Telegraph summary and send the link:

```bash
python3 digest.py --source miniflux --telegraph
```

## VPS Cron Shape

Miniflux handles RSS polling internally, so cron only needs to run the digest.

Example daily test run:

```cron
0 9 * * * cd /path/to/crypto-digest && /path/to/.venv/bin/python digest.py --source miniflux --telegraph
```

Keep Miniflux running continuously with Docker Compose or systemd.

## Notes

- Miniflux only replaces the RSS collection layer.
- Exchange announcement APIs are still fetched directly by `digest.py`.
- If Miniflux has just been installed, wait for one or more polling cycles before
  expecting complete 24h coverage.
- The current Compose file uses a 30-minute polling scheduler and a 15-minute
  minimum interval for high-frequency feeds.
