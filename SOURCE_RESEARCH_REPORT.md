# Crypto Digest Source Research Report

Last updated: 2026-05-10

## Purpose

This report records the candidate source universe for the crypto digest system
and proposes a source mix for stable daily operation.

The goal is not to maximize article count. The goal is to build a small,
high-signal editorial stack:

```text
crypto-native media
+ Chinese/Asia media
+ traditional financial media
+ first-party announcements
+ specialist/security signals
= story-level digest candidates
```

News sources and announcements are separate input classes. News sources provide
reported coverage and context. Announcements provide primary-source facts. They
should only merge at the story layer.

## Source Classes

### `media_news`

Reported coverage from crypto-native, Chinese/Asia, and traditional media.

Use for:

- Context and interpretation
- Cross-source confirmation
- Market, policy, institutional, and ecosystem impact
- Human-readable narrative

### `official_announcement`

Primary-source updates from exchanges, protocols, companies, foundations, and
regulators.

Use for:

- Listings and delistings
- Product and service changes
- Enforcement actions and policy updates
- Protocol upgrades and governance notices
- Official company or foundation announcements

### `specialist_signal`

Security, compliance, investigation, and on-chain risk sources.

Use for:

- Exploits and hacks
- Address attribution
- Illicit finance
- Sanctions and compliance
- Technical or protocol risk

## Recommended V1 Source Mix

This is the recommended default source mix for the next stable version.

## Access-Driven Selection

The final source choice should prefer sources that are both valuable and
operationally stable. A source can be high quality but still stay out of V1 if
access requires paywalled scraping, X/Twitter monitoring, fragile HTML parsing,
or an unofficial paid API.

### V1: Use Now

These sources are worth using now because they are already implemented or have
a simple RSS/API path.

#### Media

| Source | Input class | Access path | Decision |
|---|---|---|---|
| CoinDesk | `media_news` | RSS | Use now |
| The Block | `media_news` | RSS | Use now |
| Blockworks | `media_news` | RSS | Use now |
| Decrypt | `media_news` | RSS | Use now |
| The Defiant | `media_news` | RSS | Use now |
| Unchained | `media_news` | RSS | Use now |
| Cointelegraph | `media_news` | RSS | Use now, lower weight |
| Foresight News | `media_news` | Direct API adapter | Use now |
| Wu Blockchain | `media_news` | RSS/Substack feed | Use now |
| Odaily Newsflash | `media_news` | RSS | Use now, lower weight |
| Odaily Articles | `media_news` | RSS | Use now, lower weight |
| Protos | `specialist_signal` | RSS | Use now |
| Chainalysis | `specialist_signal` | RSS | Use now |
| CryptoSlate | `media_news` | RSS | Use now, low weight |
| Forkast | `media_news` | RSS | Use now, low weight |
| Investing.com Crypto | `media_news` | RSS | Use now, low weight |

#### Announcements

| Source | Input class | Access path | Decision |
|---|---|---|---|
| Binance | `official_announcement` | Existing API adapter | Use now |
| OKX | `official_announcement` | Existing HTML adapter | Use now |
| Bybit | `official_announcement` | Existing API adapter | Use now, keep fallback because 403 can happen |

### V1.5: Add Next

These sources are valuable and likely feasible, but they need adapter testing
before becoming daily production inputs.

| Source | Input class | Access path | Decision |
|---|---|---|---|
| SEC press releases | `official_announcement` | Official RSS/search page | Add next |
| CFTC press releases | `official_announcement` | Official RSS feeds | Add next |
| Kraken | `official_announcement` | Blog/RSS or announcement pages | Add next, but filter marketing posts |
| Ethereum Foundation Blog | `official_announcement` | Official blog/feed | Add next |
| TRM Labs | `specialist_signal` | Blog/feed to verify | Add next if feed is stable |
| Elliptic | `specialist_signal` | Blog/feed to verify | Add next if feed is stable |
| SlowMist | `specialist_signal` | RSSHub/direct route to verify | Add next only if route stabilizes |
| PeckShield | `specialist_signal` | Feed/API/X dependency to verify | Add next only if route is reliable |

### Watchlist: Valuable But Not V1

These sources are high value, but not good V1 candidates until we confirm a
reliable, legal, and low-maintenance access path.

| Source | Input class | Access issue | Decision |
|---|---|---|---|
| Bloomberg Crypto | `media_news` | Paywall/RSS uncertainty | Watchlist confirmation source |
| Reuters | `media_news` | Feed/API access to verify | Watchlist confirmation source |
| Financial Times | `media_news` | Paywall/access constraints | Watchlist confirmation source |
| Wall Street Journal | `media_news` | Paywall/access constraints | Watchlist confirmation source |
| Nikkei Asia | `media_news` | Feed/access to verify | Watchlist Asia confirmation source |
| Fortune Crypto | `media_news` | Access/feed to verify | Watchlist business source |
| CNBC Crypto | `media_news` | Page available, feed behavior to verify | Watchlist market-reaction source |
| Forbes Digital Assets | `media_news` | Contributor noise and access quality | Watchlist only |
| The Economist | `media_news` | Low frequency/paywall | Manual/thematic context |
| Coinbase listings | `official_announcement` | Coinbase says listing announcements moved to X handles | Do not add until X monitoring exists |
| Upbit | `official_announcement` | Korean notice page/API needs adapter | Add later after Korean notice parser |
| Bithumb | `official_announcement` | Korean notice page/API needs adapter | Add later after Korean notice parser |
| Gate | `official_announcement` | High marketing/campaign noise | Later, only with strict filters |
| HTX | `official_announcement` | High marketing/campaign noise | Later, only with strict filters |

### Do Not Add By Default

These are either noisy, unstable, duplicated, or not worth production complexity
for V1.

| Source | Reason |
|---|---|
| PANews | Too much high-frequency mixed content; keep as disabled fallback. |
| Crypto.news | Feed works, but quality/noise is not worth default inclusion. |
| CryptoBriefing | Overlaps with existing coverage and adds market noise. |
| BeInCrypto | Price/token-momentum noise risk is high. |
| DL News | Feed/status looked unreliable during testing. |
| Bankless | No suitable public article RSS found; better as podcast/newsletter context. |
| Messari | No suitable public RSS endpoint found during testing. |
| Bitcoin Magazine | Feed returned 403 during testing. |
| ChainCatcher | RSSHub route unstable from local testing. |
| TechFlow | RSSHub route unstable from local testing. |

### Practical V1 Choice

For the next implementation pass, choose:

```text
Media now:
  CoinDesk, The Block, Blockworks, Decrypt, The Defiant, Unchained,
  Cointelegraph, Foresight News, Wu Blockchain, Odaily Newsflash,
  Odaily Articles, Protos, Chainalysis, CryptoSlate, Forkast, Investing.com

Announcements now:
  Binance, OKX, Bybit

Next additions after adapter test:
  SEC, CFTC, Kraken, Ethereum Foundation, TRM Labs, Elliptic

Watchlist, not production yet:
  Bloomberg, Reuters, FT, WSJ, Nikkei Asia, Fortune, CNBC, Forbes,
  The Economist, Coinbase listings, Upbit, Bithumb
```

This gives the project enough breadth for daily coverage without depending on
fragile scraping or paid feeds.

### V1 Default Media Sources

| Source | Class | Role | Default | Notes |
|---|---|---:|---:|---|
| CoinDesk | `media_news` | English authority / broad crypto | Yes | Strong mainline source for regulation, markets, institutions, and major events. Watch ownership caveat. |
| The Block | `media_news` | Data, funding, exchanges, institutions | Yes | Strong for factual business coverage. Use with awareness of historical FTX funding scandal. |
| Blockworks | `media_news` | Institutional, DeFi, research, markets | Yes | Good fit for high-signal investor/operator digest. |
| Decrypt | `media_news` | Culture, consumer crypto, AI/NFT/gaming | Yes | Useful breadth, but should be filtered for softer stories. |
| The Defiant | `media_news` | DeFi specialist | Yes | Important for protocol and DeFi-native stories. |
| Unchained | `media_news` | Deep context and interviews | Yes | Lower frequency, higher context value. Good for takeaway quality. |
| Cointelegraph | `media_news` | Fast broad coverage | Yes, lower weight | Keep for speed and breadth, but cap/score down because it can be noisy. |
| Foresight News | `media_news` | Chinese broad crypto media | Yes | Main Chinese broad source. Prefer over PANews for default stack. |
| Wu Blockchain | `media_news` | Asia, exchanges, policy | Yes | High value for Asia and exchange developments. |
| Odaily Newsflash | `media_news` | Chinese fast updates | Yes, lower weight | Useful for speed, but aggressive relevance filtering needed. |
| Odaily Articles | `media_news` | Chinese articles | Yes, lower weight | Useful supplement, but do not let it dominate. |
| Protos | `specialist_signal` | Investigation and anti-hype | Yes | Strong risk/scam/controversy source. |
| Chainalysis | `specialist_signal` | Compliance and illicit finance | Yes | Useful for security/compliance layer. |
| CryptoSlate | `media_news` | Secondary market/ecosystem coverage | Yes, low weight | Keep as backup breadth. |
| Forkast | `media_news` | Asia and policy supplement | Yes, low weight | Keep as secondary Asia view. |
| Investing.com Crypto | `media_news` | Market/business syndication | Yes, low weight | Useful occasionally, but PR/noise filtering is important. |

### V1 Default First-Party Announcements

| Source | Class | Role | Default | Notes |
|---|---|---:|---:|---|
| Binance | `official_announcement` | Exchange listings and product changes | Yes | Already implemented. Filter marketing/campaign posts. |
| OKX | `official_announcement` | Exchange listings and product changes | Yes | Already implemented. |
| Bybit | `official_announcement` | Exchange listings and product changes | Yes | Already implemented, but may require fallback due to API blocking. |
| Coinbase | `official_announcement` | Major US exchange listings/compliance | Next | High priority for next announcement expansion. |
| Kraken | `official_announcement` | Major US/EU exchange updates | Next | High priority for next announcement expansion. |
| Upbit | `official_announcement` | Korea listings and market structure | Next | High Asia relevance. |
| Bithumb | `official_announcement` | Korea listings and market structure | Next | High Asia relevance. |

### V1 Watchlist Traditional Media

Traditional media should be used as a high-trust confirmation layer, not as a
high-volume RSS firehose.

| Source | Class | Role | Default | Notes |
|---|---|---:|---:|---|
| Bloomberg Crypto | `media_news` | Wall Street, ETFs, listed companies, institutions | Watchlist / high priority | Very valuable, but access/paywall/RSS handling needs testing. |
| Reuters | `media_news` | Regulation, courts, enforcement, public companies | Watchlist / high priority | Excellent confirmation source. Need reliable feed/API path. |
| Financial Times | `media_news` | Banking, stablecoins, Europe, asset managers | Watchlist / high priority | High value, likely paywall/access constraints. |
| Wall Street Journal | `media_news` | US banks, stablecoins, regulation, TradFi adoption | Watchlist / high priority | High value, likely paywall/access constraints. |
| Nikkei Asia | `media_news` | Japan, Hong Kong, Singapore, Korea, Southeast Asia | Watchlist / medium-high | Strong Asia complement if feed access works. |
| Fortune Crypto | `media_news` | US crypto business, VC, policy, industry figures | Watchlist / medium | Good business lens, lower urgency than Bloomberg/Reuters/FT/WSJ. |
| CNBC Crypto | `media_news` | Market reaction, interviews, ETF/stock linkage | Watchlist / medium | Useful for market reaction, not primary fact source. |
| Forbes Digital Assets | `media_news` | Investing and company analysis | Watchlist / low-medium | Use carefully because contributor content can be noisy. |
| The Economist | `media_news` | Macro/regulatory long-form perspective | Watchlist / low frequency | Not a daily source, but valuable for thematic context. |

## Candidate Universe

### English Crypto-Native Media

| Source | Status | Rationale |
|---|---|---|
| CoinDesk | Default core | Oldest/most recognized crypto-native source; strong broad coverage. |
| The Block | Default core | Strong data/business/institutional source. |
| Blockworks | Default core | Strong for institutional, DeFi, research, and podcasts. |
| Decrypt | Default core | Strong readable coverage across crypto culture, AI, NFT, gaming, and consumer topics. |
| The Defiant | Default core | Strong DeFi-native source. |
| Unchained | Default core | Deep interviews and context; high value for takeaways. |
| Cointelegraph | Default, lower weight | Broad and fast, but can be noisy or duplicative. |
| CryptoSlate | Default, low weight | Useful secondary coverage. |
| Forkast | Default, low weight | Useful Asia/policy supplement. |
| Investing.com Crypto | Default, low weight | Useful market/business supplement, but can include PR-like content. |
| Protos | Default specialist | Investigation, scams, controversy, and anti-hype coverage. |
| Chainalysis | Default specialist | Compliance, illicit finance, and risk reports. |
| Crypto.news | Not default | Feed works, but headline quality/noise makes it better as optional expansion. |
| CryptoBriefing | Not default | Feed works, but overlaps with market/noise coverage. |
| BeInCrypto | Not default | Feed works, but price/token-momentum noise risk is high. |
| DL News | Not default | Feed availability/status looked poor during testing. |
| Bankless | Not default | No suitable public article RSS found; better treated as podcast/newsletter context. |
| Messari | Not default | No suitable public RSS endpoint found during testing. |
| Bitcoin Magazine | Not default | Feed returned 403 during testing. |

### Chinese And Asia Media

| Source | Status | Rationale |
|---|---|---|
| Foresight News | Default core | Chinese broad crypto source; direct API adapter works and replaces PANews as main Chinese broad feed. |
| Wu Blockchain | Default core | Strong Asia/exchange/policy signal. |
| Odaily Newsflash | Default, low weight | Useful fast Chinese updates. Needs filtering. |
| Odaily Articles | Default, low weight | Useful Chinese article supplement. Needs filtering. |
| PANews | Disabled fallback | Too much high-frequency mixed/noisy content. Keep behind `ENABLE_PANEWS=1`. |
| ChainCatcher | Not default | RSSHub route had upstream gateway failures. Revisit later. |
| TechFlow | Not default | RSSHub route had route errors. Revisit later. |

### Traditional Financial And Business Media

| Source | Status | Rationale |
|---|---|---|
| Bloomberg Crypto | High-priority watchlist | Best for Wall Street, ETFs, public companies, miners, and institutional adoption. |
| Reuters | High-priority watchlist | Best for official confirmation, courts, enforcement, regulators, and public companies. |
| Financial Times | High-priority watchlist | Best for banks, stablecoins, asset managers, Europe, and systemic-risk framing. |
| Wall Street Journal | High-priority watchlist | Best for US banking system, stablecoins, institutional adoption, and regulatory risk. |
| Nikkei Asia | Medium-high watchlist | Best for Japan, Hong Kong, Singapore, Korea, and Southeast Asia. |
| Fortune Crypto | Medium watchlist | Good for US business, VC, industry figures, and policy. |
| CNBC Crypto | Medium watchlist | Good for market reaction, video/interview-driven coverage, and equity linkage. |
| Forbes Digital Assets | Low-medium watchlist | Useful investing lens, but contributor model needs filtering. |
| The Economist | Low-frequency watchlist | High quality for macro themes, but not daily operational coverage. |

### Exchange Announcement Sources

| Source | Status | Rationale |
|---|---|---|
| Binance | Implemented | Important for listings, delistings, futures, product changes, and restrictions. |
| OKX | Implemented | Important for listings, delistings, product changes, and global exchange updates. |
| Bybit | Implemented | Important but API can block from some environments. Needs fallback. |
| Coinbase | Next expansion | Major US exchange and regulatory signal. |
| Kraken | Next expansion | Major US/EU exchange and compliance signal. |
| Upbit | Next expansion | Strong Korea listing/market signal. |
| Bithumb | Next expansion | Strong Korea listing/market signal. |
| Gate | Later expansion | Useful but campaign/marketing noise likely high. |
| HTX | Later expansion | Useful but campaign/marketing noise likely high. |

### Protocol And Foundation Announcement Sources

| Source | Status | Rationale |
|---|---|---|
| Ethereum Foundation | Next expansion | Core protocol roadmap, upgrades, grants, ecosystem coordination. |
| Solana | Next expansion | Major L1 updates and ecosystem releases. |
| Base | Next expansion | Major L2 and consumer/onchain app ecosystem. |
| Arbitrum | Later expansion | L2 governance, upgrades, ecosystem incentives. |
| Optimism | Later expansion | L2 governance, Superchain, upgrades. |
| Polygon | Later expansion | L2/zk/Ethereum scaling updates. |
| Aave | Next expansion | Major DeFi money market protocol. |
| Uniswap | Next expansion | Major DEX/protocol governance source. |
| Maker/Sky | Next expansion | Stablecoin/RWA/DeFi governance source. |
| Lido | Later expansion | Liquid staking and Ethereum staking risk source. |
| EigenLayer | Later expansion | Restaking and AVS risk source. |
| Chainlink | Later expansion | Oracle, CCIP, institutional/RWA infrastructure. |

### Regulator And Government Sources

| Source | Status | Rationale |
|---|---|---|
| SEC | Next expansion | US enforcement, ETFs, securities regulation, rulemaking. |
| CFTC | Next expansion | US commodities, derivatives, enforcement. |
| DOJ | Next expansion | Criminal enforcement and seizures. |
| Treasury / OFAC / FinCEN | Next expansion | Sanctions, AML, stablecoins, illicit finance. |
| Federal Reserve | Later expansion | Stablecoins, banks, payments, macro-financial risk. |
| FCA | Later expansion | UK crypto regulation and enforcement. |
| ESMA | Later expansion | EU/MiCA regulation. |
| HK SFC | Later expansion | Hong Kong licenses, ETFs, virtual asset policy. |
| MAS | Later expansion | Singapore licensing, stablecoins, payments. |
| Japan FSA | Later expansion | Japan crypto regulation and exchange oversight. |

### Security, Compliance, And Risk Sources

| Source | Status | Rationale |
|---|---|---|
| Chainalysis | Default specialist | Compliance and illicit finance reports. |
| Protos | Default specialist | Investigation and anti-hype reporting. |
| TRM Labs | Next expansion | Compliance, hacks, illicit finance. |
| Elliptic | Next expansion | Compliance, illicit finance, sanctions. |
| SlowMist | Next expansion | Exploit alerts and security incident tracking. |
| PeckShield | Next expansion | Fast hack/exploit alerts. |
| CertiK | Later expansion | Security incident reports, but needs noise filtering. |
| BlockSec | Later expansion | Technical exploit and attack analysis. |

## Recommended Weighting Model

Use source role weights, not just source names.

| Source role | Suggested weight | Notes |
|---|---:|---|
| High-trust traditional media confirmation | 1.25 | Bloomberg, Reuters, FT, WSJ when available. |
| High-trust crypto-native media | 1.15 | CoinDesk, The Block, Blockworks. |
| Specialist signal | 1.10 | Protos, Chainalysis, TRM, Elliptic, SlowMist, PeckShield. |
| First-party announcement | 1.05 | High factual trust for what was announced, but may be self-interested. |
| Context/depth media | 1.00 | Unchained, The Defiant, Decrypt, Foresight, Wu Blockchain. |
| Fast broad media | 0.90 | Cointelegraph, Odaily, CryptoSlate, Forkast. |
| Market/PR-prone media | 0.75 | Investing.com, Forbes contributor-style content, noisy optional feeds. |
| Disabled/noisy fallback | 0.50 | PANews and other high-volume fallback sources if enabled. |

## Recommended Caps

Caps should prevent one source class from dominating the digest.

| Bucket | Daily candidate cap before clustering | Reason |
|---|---:|---|
| English crypto-native core | 60 | Main coverage layer. |
| Chinese/Asia media | 35 | Important, but avoid single-region overload. |
| Traditional media | 15 | Confirmation layer, not firehose. |
| Exchange announcements | 30 | Many announcements are low-signal marketing/listing noise. |
| Protocol/foundation announcements | 25 | Important but should be clustered with media coverage. |
| Regulator/government announcements | 20 | High trust; usually lower volume. |
| Security/specialist signals | 25 | High importance, can be sparse but urgent. |

## Story-Layer Merge Policy

The digest should merge related inputs but keep source roles visible.

Example:

```text
Official announcement:
  Coinbase lists TOKEN

Media coverage:
  CoinDesk reports listing context and market impact

Specialist signal:
  PeckShield flags suspicious deployer activity

Story output:
  One story cluster with announcement, media context, and risk note attached
```

This is better than publishing three separate digest items or treating all
three as equal articles.

## Implementation Roadmap

### Phase 1: Stabilize media source mix

- Keep current default core media set.
- Keep PANews disabled by default.
- Keep RSSHub disabled by default until individual routes are stable.
- Add source role metadata to every collected item.

### Phase 2: Expand announcements as a separate pipeline

- Add `official_announcement` type.
- Add Coinbase and Kraken first.
- Add Upbit and Bithumb for Korea listing signal.
- Filter campaigns, reward pools, and generic marketing posts.

### Phase 3: Add specialist/security feeds

- Add TRM Labs and Elliptic if accessible.
- Add SlowMist, PeckShield, CertiK, and BlockSec with strict dedup and severity
  scoring.
- Make exploit/security stories eligible for priority override.

### Phase 4: Test traditional media access

- Test Bloomberg, Reuters, FT, WSJ, Nikkei Asia, Fortune, CNBC, Forbes, and The
  Economist access paths.
- Add only sources with reliable legal/technical access.
- Use these sources mainly as confirmation and scoring boosts.

## Final Recommended Pairing

For the next production iteration, use this pairing:

```text
Daily media backbone:
  CoinDesk, The Block, Blockworks, Decrypt, The Defiant, Unchained,
  Cointelegraph, Foresight News, Wu Blockchain, Odaily, Protos, Chainalysis

Low-weight breadth:
  CryptoSlate, Forkast, Investing.com

Disabled fallback:
  PANews, RSSHub-only unstable routes

Announcement backbone:
  Binance, OKX, Bybit

Next announcement expansion:
  Coinbase, Kraken, Upbit, Bithumb

Next specialist expansion:
  TRM Labs, Elliptic, SlowMist, PeckShield

Traditional confirmation watchlist:
  Bloomberg, Reuters, Financial Times, Wall Street Journal, Nikkei Asia,
  Fortune Crypto, CNBC Crypto, Forbes Digital Assets, The Economist
```

This mix should produce a digest that is broad enough to avoid missing major
events, but constrained enough to avoid becoming a noisy RSS dump.

## Reference Links

- CoinDesk: https://www.coindesk.com/
- CoinDesk Ethics: https://www.coindesk.com/ethics
- The Block: https://www.theblock.co/
- The Block Conflicts of Interest: https://www.theblock.co/conflicts-of-interest
- Blockworks: https://blockworks.co/
- Blockworks Trust and Ethics: https://blockworks.co/trust-ethics
- Decrypt: https://decrypt.co/
- The Defiant: https://thedefiant.io/
- Unchained: https://unchainedcrypto.com/
- Protos: https://protos.com/
- Chainalysis: https://www.chainalysis.com/
- Bloomberg Crypto: https://www.bloomberg.com/crypto
- Reuters: https://www.reuters.com/
- Financial Times: https://www.ft.com/
- Wall Street Journal: https://www.wsj.com/
- CNBC Crypto: https://www.cnbc.com/crypto/
- Fortune Crypto: https://fortune.com/section/crypto/
- Forbes Digital Assets: https://www.forbes.com/sites/digital-assets
- Foresight News: https://foresightnews.pro/
- Wu Blockchain: https://www.wublockchain.xyz/
- Odaily: https://www.odaily.news/
