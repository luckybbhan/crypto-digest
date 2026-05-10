# RSSHub Adapter Setup

RSSHub is an optional adapter layer for sources that do not provide a stable
official RSS feed.

Target flow:

```text
RSSHub converts site routes to RSS
-> Miniflux polls and stores those RSS feeds
-> digest.py reads the Miniflux history
```

## Start RSSHub

RSSHub is included in `docker-compose.miniflux.yml`:

```bash
docker compose -f docker-compose.miniflux.yml up -d
```

It is bound to localhost only:

```text
http://127.0.0.1:1200
```

This keeps the adapter private to the server.

The Compose file defaults `RSSHUB_UA` to `ForesightNews/1.0` because Foresight
News API rejects ordinary browser user agents from RSSHub with Cloudflare 403.

## Feed Toggles

The default behavior is unchanged:

```bash
ENABLE_PANEWS=1
ENABLE_REPLACEMENT_FEEDS=0
ENABLE_RSSHUB_FEEDS=0
```

To test direct replacement feeds without RSSHub:

```bash
ENABLE_REPLACEMENT_FEEDS=1
```

This enables:

```text
Odaily Newsflash
Odaily Articles
Chainalysis
Protos
```

To test RSSHub feeds:

```bash
ENABLE_RSSHUB_FEEDS=1
```

This enables:

```text
ChainCatcher
TechFlow
SlowMist
```

## Foresight News

Foresight's RSSHub route currently returns Cloudflare 403 from the upstream API.
The project therefore includes a direct API adapter that uses Foresight's mobile
API user agent and decodes the compressed response.

Enable it with:

```bash
ENABLE_FORESIGHT_API=1
```

Because this is not an RSS feed, Miniflux does not store Foresight history yet.
When enabled, `digest.py` fetches Foresight directly during each run, including
when `--source miniflux` is used for the other RSS feeds.

## Important URL Detail

If `digest.py --source live` fetches from the host machine, use:

```bash
RSSHUB_URL=http://localhost:1200
```

If `miniflux_client.py --ensure-feeds` imports RSSHub routes into Miniflux
running inside Docker Compose, use:

```bash
RSSHUB_URL=http://rsshub:1200
```

The feed URL is stored inside Miniflux, and Miniflux fetches it from inside the
Docker network.

## Suggested Replacement Tests

Baseline:

```bash
ENABLE_PANEWS=1 ENABLE_REPLACEMENT_FEEDS=0 ENABLE_RSSHUB_FEEDS=0 \
python3 debug_pipeline.py --source live --hours 24
```

PANews off, direct replacements on:

```bash
ENABLE_PANEWS=0 ENABLE_REPLACEMENT_FEEDS=1 ENABLE_FORESIGHT_API=1 ENABLE_RSSHUB_FEEDS=0 \
python3 debug_pipeline.py --source live --hours 24
```

PANews off, direct replacements and RSSHub on:

```bash
ENABLE_PANEWS=0 ENABLE_REPLACEMENT_FEEDS=1 ENABLE_FORESIGHT_API=1 ENABLE_RSSHUB_FEEDS=1 \
RSSHUB_URL=http://localhost:1200 \
python3 debug_pipeline.py --source live --hours 24
```

For VPS Miniflux import:

```bash
ENABLE_PANEWS=0 ENABLE_REPLACEMENT_FEEDS=1 ENABLE_RSSHUB_FEEDS=1 \
RSSHUB_URL=http://rsshub:1200 \
python3 miniflux_client.py --ensure-feeds
```
