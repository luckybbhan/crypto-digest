# Crypto Daily Digest — Agent Skill

You are an autonomous agent. Execute all steps below to produce and publish today's crypto digest. Work directory: `/Users/ahao/projects/crypto-digest`.

---

## Step 1 — Read Config

Read `config.py` to get:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_GROUP_ID` (prod), `TEST_GROUP_ID` (test)
- `TOPIC_THREAD_IDS` (prod only)
- `TELEGRAPH_TOKEN`
- `FEEDS` (list of RSS sources with name + url)

The **target group** and **use_threads** flag are passed as arguments at the start of this prompt — read them carefully.

---

## Step 2 — Fetch Articles

### RSS Feeds
For each feed in `FEEDS`, use `WebFetch` to retrieve the RSS XML. Parse entries and extract:
- `title` (strip whitespace)
- `link`
- `summary` (strip HTML tags, max 200 chars)
- `published` (parse from `<pubDate>` or `<updated>`)
- `source` (feed name)

### Exchange Listing Announcements

**Binance** — run via Bash:
```bash
curl -s "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=1&pageSize=20&catalogId=48" -H "User-Agent: Mozilla/5.0"
```
Parse `.data.catalogs[0].articles[]`: title, `https://www.binance.com/en/support/announcement/{code}`, releaseDate (÷1000 for unix).

**OKX** — run via Bash:
```bash
curl -s "https://okx.zendesk.com/api/v2/help_center/en-us/sections/115000202672/articles.json?per_page=20" -H "User-Agent: Mozilla/5.0"
```
Parse `.articles[]`: title, html_url, created_at.

**Bybit** — run via Bash:
```bash
curl -s "https://api.bybit.com/v5/announcements/index?locale=en-US&type=new_crypto&page=1&limit=20" -H "User-Agent: Mozilla/5.0"
```
Parse `.result.list[]`: title, url, publishTime (÷1000).

If any source fails, skip it and continue. Never abort the whole run for one failed source.

---

## Step 3 — Filter, Deduplicate, Cluster

1. **24h filter**: Drop articles older than 24 hours from now (UTC).
2. **Exact dedup**: Drop if URL or MD5(normalised title) already seen.
3. **Story clustering**: Group articles about the same event (Jaccard similarity on title words ≥ 0.3, excluding stopwords: the/a/an/in/on/at/to/for/of/and/or/is/as/by/with/after/over/from/its). Keep only the highest-priority source per cluster.

Source priority (highest → lowest): The Block, CoinDesk, Cointelegraph, Blockworks, The Defiant, Decrypt, Forkast, CryptoSlate, Wu Blockchain, PANews, others.

---

## Step 4 — Classify by Topic

Assign each article to **exactly one** topic using your own editorial judgment:

| Topic | When to use |
|---|---|
| **Portfolio** | Article explicitly names one of our portfolio companies: Mavrick, Cetus, Ola, Gravity, Polyhedra, Redbrick, BBox, Apriori, Ethena, Cyber Games Arena, Solv, Movement, Sidekick, Hologram AI, Le Poker, GAIB, Tonark, Sonic, Sonex, GTE, Haedal, Kaiju, YB, Gamer Boom, CAP, Perena, Aspecta, RateX, Nunchi, Noise, Turtle, EchoX, Spout, Stormbit |
| **Exchange Listings** | New token listing on Binance, Coinbase, OKX, Bybit, Kraken, etc. |
| **Deal Flow & Funding** | Fundraising, VC rounds, valuations |
| **Infrastructure & Tech** | L1/L2, rollups, ZK, bridges, dev tools, chain launches |
| **RWA & Institutional** | Real-world assets, tokenization, ETFs, TradFi |
| **DeFi & New Primitives** | DeFi protocols, TVL, stablecoins, restaking, DEX |
| **Regulatory & Policy** | SEC, legislation, government, compliance, enforcement |
| **Macro & Market** | BTC/ETH price, Fed, macro indicators, market structure |
| **Emerging Narratives** | AI agents, consumer crypto, gaming, social, DePIN, memecoins |
| **General** | Doesn't fit any above |

Portfolio takes priority — only assign if a portfolio company name is explicitly mentioned.

---

## Step 5 — Summarise Each Topic

For each topic that has ≥1 article, write **3–5 bullet points** capturing key facts only.

Rules:
- Facts only — who, what happened, what amount
- No analysis, no opinion, no prediction
- Each bullet max 15 words
- Format: `• **Entity:** what happened`

---

## Step 6 — Build & Publish Telegraph Page

Construct the HTML, then publish via Bash.

**HTML layout** (Telegraph supports: `<h3>`, `<h4>`, `<p>`, `<a>`, `<strong>`, `<em>`, `<br>`, `<blockquote>`, `<ul>`, `<li>`, `<hr>`):

```
<p><em>{N} sources · {M} articles · {HH:MM} UTC</em></p>

[For each topic in order: Portfolio, Exchange Listings, Deal Flow & Funding,
RWA & Institutional, DeFi & New Primitives, Regulatory & Policy,
Macro & Market, Infrastructure & Tech, Emerging Narratives, General]

<h3>{emoji} {Topic Name} ({count})</h3>

[For each article, newest first:]
<p>
  <a href="{link}"><strong>{title}</strong></a><br>
  <em>{source} · {MMM DD, HH:MM} UTC</em><br>
  {summary}
</p>

[After articles:]
<blockquote>
  • <strong>Entity:</strong> fact<br>
  ...
</blockquote>
<hr>
```

Topic emojis: Portfolio 🗂️ · Exchange Listings 📋 · Deal Flow & Funding 💰 · Infrastructure & Tech ⚙️ · RWA & Institutional 🏦 · DeFi & New Primitives 🔁 · Regulatory & Policy ⚖️ · Macro & Market 📊 · Emerging Narratives 🚀 · General 📌

**If TELEGRAPH_TOKEN is empty**, first create an account:
```bash
curl -s -X POST "https://api.telegra.ph/createAccount" \
  -d "short_name=CryptoDigest&author_name=2Square+Capital"
```
Use the returned `access_token`. Print it so the user can save it to `config.py`.

**Publish the page:**
```bash
curl -s -X POST "https://api.telegra.ph/createPage" \
  -H "Content-Type: application/json" \
  -d '{"access_token":"TOKEN","title":"Crypto Daily Digest — MMM DD, YYYY","html_content":"...","return_content":false}'
```

Extract `result.url` from the response. If publish fails, log the error and fall back to Step 7 without a Telegraph link.

---

## Step 7 — Post to Telegram

**Main message** (always to target group, no thread):
```bash
curl -s -X POST "https://api.telegram.org/bot{TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "TARGET_GROUP_ID",
    "text": "📰 *Crypto Daily Digest — {Date}*\n_{N} sources · {M} articles · {HH:MM UTC}_\n\n📖 [Read full digest]({telegraph_url})",
    "parse_mode": "Markdown",
    "disable_web_page_preview": false
  }'
```

If no Telegraph URL (publish failed), post the top 3 articles from each topic instead.

**Prod mode with threads** (only when `use_threads=true`): For each topic in `TOPIC_THREAD_IDS`, also post a brief topic summary message to that thread:
```bash
# add "message_thread_id": THREAD_ID to the payload
```

---

## Step 8 — Done

Print final summary to stdout:
```
✅ Digest complete
   Articles: {M} ({N} sources)
   Topics: {topic list}
   Telegraph: {url}
   Target: {PROD/TEST}
```
