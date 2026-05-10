# News Sources

For the full candidate-source investigation and recommended source pairing, see
`SOURCE_RESEARCH_REPORT.md`.

This project uses a curated source set rather than a single high-volume
aggregator. The current default is optimized for lower noise and better
coverage of regulation, security, institutional adoption, and protocol updates.

Important distinction: `news sources` and `first-party announcement sources`
are separate input classes. News sources provide reported coverage and context.
Announcements provide primary-source facts from exchanges, protocols,
regulators, companies, and foundations. They should be collected, scored, and
deduplicated differently, then merged at the story layer.

## Default Source Set

These are media/news sources, not official announcements.

### English Core

- `CoinDesk`
- `Cointelegraph`
- `The Block`
- `Decrypt`
- `Blockworks`
- `The Defiant`
- `Unchained`

These sources provide the main English news backbone.

### English Secondary

- `Forkast`
- `CryptoSlate`
- `Investing.com`

These remain enabled, but downstream filters and scoring should prevent them
from dominating the digest.

## English Sources Not Added By Default

- `Crypto.news`: feed works, but headline quality is noisy enough to keep out of
  the default set for now.
- `CryptoBriefing`: feed works, but overlaps with market/noise coverage.
- `BeInCrypto`: feed works, but tends to add price and token-momentum noise.
- `DL News`: RSS page exists, but the tested feed returned no entries and the
  site currently indicates it is closing.
- `Bankless`: no suitable public article RSS was found; available RSS references
  are mostly private/podcast feeds.
- `Messari`: no suitable public RSS endpoint was found in testing.
- `Bitcoin Magazine`: feed returned 403 in testing.

### Chinese And Asia Coverage

- `Wu Blockchain`
- `Odaily Newsflash`
- `Odaily Articles`
- `Foresight News`

`Foresight News` is fetched through a direct API adapter because its RSSHub route
currently receives upstream Cloudflare 403 responses. The adapter uses the
Foresight mobile API user agent and decodes the compressed response.

### Compliance And Investigation

- `Chainalysis`
- `Protos`

These sources add security, compliance, investigation, and market structure
coverage that PANews-style fast feeds do not cover cleanly.

## Disabled By Default

### PANews

PANews is disabled by default:

```bash
ENABLE_PANEWS=0
```

Reason: it contributes too much high-frequency mixed content. In the latest
baseline run, PANews accounted for `40/113` clustered articles. Replacing it
with Odaily, Foresight, Chainalysis, and Protos produced a smaller and cleaner
candidate set:

```text
PANews enabled:
after_cluster = 113

PANews disabled + replacement feeds + Foresight API:
after_cluster = 69
```

PANews remains available as a fallback:

```bash
ENABLE_PANEWS=1
```

### RSSHub Feeds

RSSHub remains disabled by default:

```bash
ENABLE_RSSHUB_FEEDS=0
```

Reason: the currently tested routes are unstable from the local environment.

- `ChainCatcher`: upstream gateway failures
- `TechFlow`: route error
- `SlowMist`: timeout
- `Foresight`: replaced by direct API adapter

RSSHub remains useful as an adapter layer for future sources, but it should not
be part of production input until individual routes are proven stable.

## First-Party Announcement Sources

Announcements are not "news sources" in the editorial sense. They are primary
inputs that help confirm facts, catch important updates before media coverage,
and improve takeaway accuracy.

### Exchange Announcements

Current:

- `Binance`
- `OKX`
- `Bybit`

Recommended expansion:

- `Coinbase`
- `Kraken`
- `Upbit`
- `Bithumb`
- `Gate`
- `HTX`

Exchange announcements should be used mainly for listings, delistings,
trading-pair launches, product updates, fee changes, compliance restrictions,
regional service changes, and security incidents. Campaigns, reward pools, and
marketing posts should be filtered aggressively.

### Protocol And Foundation Updates

Recommended future sources:

- `Ethereum Foundation`
- `Solana`
- `Base`
- `Arbitrum`
- `Optimism`
- `Polygon`
- `Aave`
- `Uniswap`
- `Maker/Sky`
- `Lido`
- `EigenLayer`
- `Chainlink`

These sources should carry high factual trust for their own releases, but they
are not neutral analysis. The digest should treat them as primary facts and use
media coverage for context, controversy, and impact.

### Regulators And Government Sources

Recommended future sources:

- `SEC`
- `CFTC`
- `DOJ`
- `Treasury / OFAC / FinCEN`
- `Federal Reserve`
- `FCA`
- `ESMA`
- `HK SFC`
- `MAS`
- `Japan FSA`

These should receive high trust for enforcement actions, rulemaking,
consultations, licenses, sanctions, and official policy changes.

### Security And Risk Feeds

Recommended future sources:

- `Chainalysis`
- `TRM Labs`
- `Elliptic`
- `SlowMist`
- `PeckShield`
- `CertiK`
- `BlockSec`

Security feeds should be treated as first-party or specialist signals depending
on the source. They are especially useful for exploit detection, address
attribution, sanctions, bridge incidents, and exchange compromise reports.

## Source Architecture

The intended source mix is:

```text
Media news sources
  -> reported coverage, context, interpretation

First-party announcement sources
  -> official facts, launches, enforcement, protocol updates

Specialist/security sources
  -> exploits, attribution, illicit finance, technical risk

Story layer
  -> merge related inputs into one event with sources attached
```

This avoids treating an exchange listing announcement, a Bloomberg story, and a
CoinDesk analysis as the same kind of input. They may describe the same story,
but they have different roles.

## Default Toggles

```bash
ENABLE_PANEWS=0
ENABLE_REPLACEMENT_FEEDS=1
ENABLE_FORESIGHT_API=1
ENABLE_RSSHUB_FEEDS=0
```

## Latest Source Test

Command shape:

```bash
ENABLE_PANEWS=0 ENABLE_REPLACEMENT_FEEDS=1 ENABLE_FORESIGHT_API=1 ENABLE_RSSHUB_FEEDS=0 \
python3 debug_pipeline.py --source live --hours 24
```

Latest result:

```text
raw: 418
after_24h: 100
after_relevance: 73
after_dedup: 73
after_cluster: 69
classified: 69
```

Clustered source distribution:

```text
CoinDesk: 13
Cointelegraph: 16
The Block: 8
Decrypt: 6
The Defiant: 2
Investing.com: 4
Wu Blockchain: 1
Odaily Newsflash: 4
Odaily Articles: 2
Protos: 1
Foresight News: 12
```

## Next Optimization Stage

With the source set stabilized, the next stage is `Dedup / Cluster`.

Main goals:

- Merge Chinese and English coverage of the same story.
- Prefer original or higher-priority sources when multiple versions exist.
- Reduce repeated Aave/Kelp/LayerZero-style same-event coverage.
- Keep enough source diversity for context without turning one event into many
  digest items.
