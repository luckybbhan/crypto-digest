# Crypto Digest Development Plan

This document captures the key system variables and iteration directions for
turning the digest from a news aggregation script into a stable, investment-grade
daily intelligence product.

## Product Goal

Build a daily crypto digest that is:

- Reliable enough to run unattended every day.
- Concise enough for a team to read quickly.
- Broad enough to cover major crypto market activity.
- Opinionated enough to prioritize what matters.
- Differentiated through portfolio, watchlist, and investment-context relevance.

## Core System Variables

### 1. Source Coverage

Current coverage is strongest in mainstream crypto media and basic exchange
announcements. Future coverage should add more first-party and data-driven
sources.

Current strengths:

- Mainstream English media: CoinDesk, Cointelegraph, The Block, Decrypt,
  Blockworks, The Defiant.
- Chinese/Asia coverage: Wu Blockchain, PANews.
- Exchange listings: Binance, OKX, Bybit.
- Supplementary media: CryptoSlate, Forkast, Investing.com.

Target additions:

- More exchanges: Coinbase, Kraken, Upbit, Bithumb, Bitget, KuCoin, Gate, MEXC.
- Official sources: project blogs, protocol governance forums, foundation blogs.
- Regulatory sources: SEC, CFTC, DOJ, Treasury, Federal Register, ESMA, FCA, SFC.
- Market/data sources: DefiLlama, Token Terminal, Artemis, Dune, Glassnode,
  Nansen.
- Security sources: PeckShield, SlowMist, CertiK, Cyvers, ZachXBT.
- Funding sources: RootData, Crypto Fundraising, Messari, Crunchbase.
- Narrative sources: curated X lists, Farcaster, Telegram channels, Discord
  announcements.

### 2. Deduplication And Story Clustering

Crypto news is highly repetitive. The digest should group multiple reports about
the same event and keep the most authoritative or information-rich version.

Important variables:

- Exact URL/title deduplication.
- Same-story clustering across outlets.
- Source priority by topic.
- Preservation of useful secondary links for major stories.
- Avoiding false merges for similar but distinct events.

Future improvement:

- Replace title-only Jaccard matching with embedding or LLM-assisted clustering.
- Keep one primary article plus optional supporting sources for top stories.

### 3. Topic Taxonomy

The taxonomy should reflect how an investment team reads crypto news, not just
generic media categories.

Current useful categories:

- Portfolio
- Exchange Listings
- Deal Flow & Funding
- Infrastructure & Tech
- RWA & Institutional
- DeFi & New Primitives
- Regulatory & Policy
- Macro & Market
- Emerging Narratives
- General

Potential refinements:

- Security Incidents
- Token And Protocol Metrics
- Market Structure
- Ecosystem And Governance
- Watchlist And Competitors
- Stablecoins And Payments

### 4. Relevance And Importance Scoring

The digest should not treat every article equally. Each item should receive a
priority score before rendering.

Possible scoring signals:

- Portfolio company mentioned.
- Watchlist company, competitor, or ecosystem mentioned.
- Top-tier source or first-party source.
- Major exchange listing or delisting.
- Funding amount, valuation, or investor quality.
- Regulatory severity or jurisdiction.
- TVL, volume, revenue, active users, price, liquidation, or open interest move.
- Security exploit size.
- Recency and story momentum across multiple sources.

Target output:

- Top stories first.
- Topic sections capped by quality threshold.
- Low-priority items moved to full digest only, or dropped.

### 5. Portfolio And Watchlist Context

This is the strongest differentiation opportunity. Generic crypto digests are
easy to replicate; portfolio-aware digests are not.

Priority capabilities:

- Direct portfolio company mentions.
- Competitor mentions.
- Ecosystem mentions.
- Relevant protocol/category news.
- Major partner, investor, chain, exchange, or regulatory updates.
- Negative risk signals such as hacks, depegs, lawsuits, delistings, or outages.

Future data model:

- Portfolio companies.
- Watchlist companies.
- Competitors.
- Ecosystems/chains.
- Categories.
- Key people and investors.
- Token tickers and aliases.

### 6. Summary And Editorial Style

The digest should be factual, compact, and investment-oriented.

Current mode:

- Fact-only topic bullet summaries.

Target modes:

- Executive summary: 5-10 most important items.
- Topic summary: 3-5 bullets per active topic.
- Per-story summary: what happened, why it matters, who is affected.
- Portfolio relevance note when applicable.
- No hype, no predictions, no unsupported analysis.

### 7. Signal-To-Noise Controls

The system should avoid overwhelming readers. A digest with 150-200 raw articles
is useful as an archive but too noisy as a daily message.

Recommended controls:

- Telegram main message: top 10-20 items only.
- Portfolio and urgent alerts: always included.
- Topic section caps.
- Full Telegraph/web page for complete archive.
- Drop or hide low-relevance general news.
- Separate "full digest" from "executive brief".

### 8. Distribution Format

Telegram is good for fast consumption, but long-form content should live
elsewhere.

Recommended structure:

- Telegram main message: executive summary and full digest link.
- Telegram topic threads: brief topic summaries when running in production.
- Telegraph or web page: complete grouped digest.
- Logs: structured run stats and errors.
- Future: failure alert if a scheduled run fails.

### 9. Reliability And Operations

For daily unattended runs, the system needs production controls.

Needed capabilities:

- Environment-based secrets.
- Dry-run mode.
- Test group by default.
- Explicit production flag.
- Cron or server deployment.
- Structured logs.
- Retry/backoff for APIs.
- Source-level failure isolation.
- Run summary after completion.
- Optional alert on failure or unusually low article count.

## Iteration Roadmap

### Phase 1: Safe Testing And Deployment Baseline

- Keep test group as default.
- Keep `--prod` as the only production path.
- Keep `--dry-run` for safe previews.
- Move all secrets to `.env` or server environment variables.
- Add basic run documentation.
- Add server cron instructions.

Success criteria:

- A dry-run can complete with real sources.
- A test send can complete without touching production.
- Secrets are not committed.

### Phase 2: Output Quality And Noise Reduction

- Add importance scoring.
- Add top-story executive summary.
- Limit Telegram output to high-signal items.
- Keep full digest in Telegraph.
- Improve Markdown and HTML escaping.
- Add per-topic caps.

Success criteria:

- Main Telegram message is readable in under 2 minutes.
- Full digest remains available for deeper reading.
- Duplicate and low-value items are reduced.

### Phase 3: Better Coverage

- Add Coinbase, Kraken, Upbit, Bithumb, Bitget, KuCoin, Gate, and MEXC listings.
- Add security incident sources.
- Add DefiLlama and selected market/data sources.
- Add official regulatory feeds.
- Add funding databases or structured funding feeds.

Success criteria:

- Listings coverage includes major US and Asian exchanges.
- Security incidents appear faster than mainstream media.
- Major regulatory actions can be sourced directly.

### Phase 4: Portfolio Intelligence

- Move portfolio/watchlist data into a structured config file.
- Add aliases, tickers, ecosystems, competitors, and investors.
- Add portfolio relevance tagging.
- Add competitor and category alerts.
- Add dedicated portfolio summary section.

Success criteria:

- Portfolio-relevant items are never buried.
- Relevant competitor or ecosystem news is surfaced even without direct portfolio
  mentions.

### Phase 5: Investment-Grade Editorial Layer

- Add story-level "what happened / why it matters / affected parties".
- Add confidence and source quality labels.
- Add LLM-assisted clustering.
- Add trend/narrative tracking across days.
- Add weekly recap mode.

Success criteria:

- The digest reads like an analyst-curated brief, not a raw news feed.
- The system identifies recurring narratives and rising topics.

## Near-Term Priorities

1. Keep current code stable and test sending to the test group.
2. Add README run instructions.
3. Improve Telegram/Telegraph escaping.
4. Add executive summary and article caps.
5. Add Coinbase, Kraken, Upbit, and Bithumb listing sources.
6. Add portfolio/watchlist structured config.
