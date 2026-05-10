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
-> source_collector.py polls non-RSS sources into SQLite
-> digest.py reads last 24h RSS entries from Miniflux
-> digest.py reads last 24h non-RSS entries from SQLite
-> Telegram/Telegraph output
```

## Local Start

Start Miniflux and Postgres:

```bash
docker compose -f docker-compose.miniflux.yml up -d
```

This Compose file also starts a private RSSHub adapter on `127.0.0.1:1200`.
RSSHub is optional; it is only used when `ENABLE_RSSHUB_FEEDS=1`.

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

To import RSSHub-backed feeds into Miniflux, use Docker's internal service name:

```bash
ENABLE_RSSHUB_FEEDS=1 RSSHUB_URL=http://rsshub:1200 python3 miniflux_client.py --ensure-feeds
```

See `RSSHUB_SETUP.md` for source replacement tests.

Ask Miniflux to refresh all feeds:

```bash
python3 miniflux_client.py --refresh
```

Check feed count and last-24h entry count:

```bash
python3 miniflux_client.py --check
```

## Collect Non-RSS Sources

Miniflux only stores RSS feeds. `Foresight News`, `Binance`, `OKX`, and `Bybit`
are fetched through direct adapters, so they need a small local history store to
avoid missing items when those APIs only return the latest page.

Collect all non-RSS sources into SQLite:

```bash
python3 source_collector.py
```

Check local non-RSS history:

```bash
python3 source_history.py --hours 24
```

Useful collector modes:

```bash
python3 source_collector.py --foresight-only
python3 source_collector.py --exchange-only
python3 source_collector.py --json
```

The default DB path is:

```text
data/source_history.sqlite3
```

Override with `.env` if needed:

```bash
SOURCE_HISTORY_DB=data/source_history.sqlite3
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

Miniflux handles RSS polling internally. Cron should run the non-RSS collector
frequently and the digest once a day.

Example collector cron, every 10 minutes:

```cron
*/10 * * * * cd /path/to/crypto-digest && /path/to/.venv/bin/python source_collector.py >> logs/source_collector.log 2>&1
```

Example daily test run:

```cron
0 9 * * * cd /path/to/crypto-digest && /path/to/.venv/bin/python digest.py --source miniflux --telegraph
```

Keep Miniflux running continuously with Docker Compose or systemd.

## Notes

- Miniflux only replaces the RSS collection layer.
- `Foresight News`, `Binance`, `OKX`, and `Bybit` are stored by
  `source_collector.py` and read by `digest.py --source miniflux`.
- If Miniflux has just been installed, wait for one or more polling cycles before
  expecting complete 24h coverage.
- If `source_collector.py` has just been installed, wait for several collector
  runs before expecting complete non-RSS 24h coverage.
- The current Compose file uses a 30-minute polling scheduler and a 15-minute
  minimum interval for high-frequency feeds.
