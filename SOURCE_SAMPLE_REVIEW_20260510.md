# Source Sample Review - 2026-05-10

Debug run:

```bash
python3 debug_pipeline.py --source live --hours 24 --sample-per-source 5
```

Export:

```text
exports/debug/20260510_011935
exports/debug/20260510_013225
exports/debug/latest
```

## Run Summary

Latest validated run:

```text
exports/debug/20260510_013225
```

| Stage | Count |
|---|---:|
| Raw | 428 |
| Media news | 353 |
| Official announcements | 55 |
| Specialist signals | 20 |
| After 24h | 98 |
| After relevance | 65 |
| After dedup | 65 |
| After cluster | 55 |
| Classified | 55 |

Post-run local clustering guard:

- A numeric-token guard was added after this run to avoid merging generic market
  stories only because they share terms like `Bitcoin` and `$80,000`.
- Replaying the final clustering logic on `after_dedup.json` produced 56 stories
  from 65 candidates, with 9 articles removed by clustering.

## Source Availability

### Working

- `CoinDesk`
- `Cointelegraph`
- `The Block`
- `Decrypt`
- `Blockworks`
- `The Defiant`
- `Unchained`
- `Forkast`
- `Investing.com`
- `Wu Blockchain`
- `Odaily Newsflash`
- `Odaily Articles`
- `Chainalysis`
- `Protos`
- `Foresight News`
- `Binance`
- `OKX`
- `Bybit`

### Problematic

- `CryptoSlate`: returned `403 Forbidden` on this run.

### Low Recent Yield In This 24h Window

- `Blockworks`: 50 raw items, 0 inside 24h.
- `Unchained`: 10 raw items, 0 inside 24h.
- `Forkast`: 10 raw items, 0 inside 24h.
- `Chainalysis`: 10 raw items, 0 inside 24h.
- `Protos`: 10 raw items, 0 inside 24h.
- `Binance`, `OKX`, `Bybit`: returned announcements, but none inside the 24h
  window for this run.

This does not mean the sources are bad. It means they are not daily-volume
sources every day. They should remain enabled but not be expected to contribute
daily.

## Source Mix After Clustering

| Source | Clustered count |
|---|---:|
| CoinDesk | 12 |
| Cointelegraph | 11 |
| Foresight News | 11 |
| The Block | 8 |
| Decrypt | 4 |
| Odaily Newsflash | 4 |
| Investing.com | 2 |
| Odaily Articles | 2 |
| The Defiant | 1 |

Observations:

- The final candidate set is dominated by `Cointelegraph`, `CoinDesk`, and
  `Foresight News`.
- `The Block` is contributing good institutional/regulatory coverage.
- `Odaily` adds useful Chinese speed but also brings unrelated macro and noisy
  market commentary.
- `Investing.com` contributes market items but should stay low weight.
- Security/specialist sources did not contribute in the 24h window, but the
  category still needs to exist because security stories are high-impact when
  they appear.

## Story Clustering Results

Implemented:

- Every cluster now has a `story_id`, primary article, supporting articles,
  source list, input type list, and source count.
- `ranked_stories.md` shows why a story ranked where it did.
- Same-story matching now uses title similarity plus normalized entities,
  amounts, and article context.

Good merges observed:

- `LayerZero / Kelp DAO exploit` merged from `The Block`, `CoinDesk`, and
  `The Defiant`.
- `Aave / North Korea / $71M ETH` merged from `CoinDesk` and `Cointelegraph`.
- `Kraken / Payward / OCC trust charter` merged from four sources.
- `TeraWulf / $427M loss / AI revenue` merged from two sources.

Guardrail added:

- Numeric tokens no longer count as important story terms by themselves. This
  prevents generic market items from merging only because they share the same
  asset and price level.
- Generic market words such as `above`, `holds`, `rebounds`, and `adoption`
  are ignored for same-story confidence, so two thin Bitcoin price stories do
  not merge without a stronger shared event/entity.

## Ranking Review

Issue found:

- `portfolio_company` scoring used substring matching. Short/generic portfolio
  names such as `Ola` and `CAP` could accidentally match unrelated words like
  `volatility`, `Latin Americans`, or `market cap`.

Status:

- Implemented stricter portfolio matching using configured portfolio topic
  terms, word boundaries, and generic-term exclusions.
- Added story-level `topic_weight` so security, regulation, funding, and real
  listing stories have explicit editorial priority.
- Main digest rendering now sorts by `story_score` when available and displays
  supporting source counts such as `The Block + 2 sources`.
- Topic takeaway input now receives story context instead of only isolated
  article titles.

Next review question:

- Decide whether broad security/crime stories should share the same weight as
  protocol exploits, bridge hacks, and direct user-fund incidents.

Decision:

- Implemented a split: `Security & Exploits` receives a small base weight, while
  protocol/user-fund incidents receive an additional `protocol_security_impact`
  score component.

## Category Issues Found

### 1. `Exchange Listings` Is Too Narrow And Currently Misfires

Observed issue:

- `CME is set to let traders bet on bitcoin volatility, not just price` was
  classified as `Exchange Listings`.

Desired behavior:

- This should be `Market Structure` or `Macro & Market`, not exchange listings.

Action:

- Add `Market Structure` category.
- Tighten `Exchange Listings` to only token listings, delistings, spot pairs,
  futures/perp contracts, and trading-pair launches.
- Exclude CME/volatility/options/ETF products unless the story is truly an
  exchange listing announcement.

Status:

- Implemented. Non-listing items classified as `Exchange Listings` are
  redirected to `Market Structure` or `Macro & Market`.

### 2. Security Stories Are Scattered

Observed examples:

- `LayerZero issues public apology for Kelp DAO exploit response...`
- `Why a 2017 Linux bug is now a major concern for the crypto industry`
- `Crypto wrench attacks on the rise...`
- `Wasabi Protocol` security incident from Foresight.

Current behavior:

- These are landing under `Infrastructure & Tech` or `DeFi & New Primitives`.

Desired behavior:

- Add `Security & Exploits`.
- Give security stories a priority override, especially when exploit amount,
  affected protocol, attacker attribution, or user funds are mentioned.

### 3. Stablecoin And Payments Stories Are Scattered

Observed examples:

- Meta stablecoin questions.
- Base x402 payments.
- Exodus AI-agent stablecoin.
- USDD transparency report.

Current behavior:

- These are split across `Regulatory & Policy`, `Infrastructure & Tech`, and
  `DeFi & New Primitives`.

Desired behavior:

- Add `Stablecoins & Payments`.
- Keep regulatory stablecoin bills in `Regulatory & Policy` only when the policy
  angle is dominant.

### 4. Roundups Still Leak Through

Observed example:

- `Here’s what happened in crypto today`

Desired behavior:

- Drop daily roundups unless the digest has no other coverage for a major story.

Action:

- Make roundup block patterns stronger than generic relevance rescue patterns.

Status:

- Implemented for daily/weekly roundup patterns and generic price-prediction
  roundups.

### 5. Opinion And Soft Commentary Need Demotion

Observed example:

- `How DeFi is changing the financial landscape for Latin Americans`

Desired behavior:

- Keep useful opinion pieces in archive only, not top Telegram output, unless
  explicitly tied to a major current event.

Action:

- Add `quality_action=demote` for opinion/context pieces instead of always
  passing them as normal articles.

## Source Quality Notes

### CoinDesk

Strong source. Some RSS entries have empty summaries, but titles and links are
good. Good candidate for primary source in clusters.

### Cointelegraph

Useful and fast, but volume and roundup/price commentary need stronger
demotion. Keep enabled with lower source weight and topic caps.

### The Block

High quality in this sample. Good for regulatory, institutional, and company
coverage. Should remain tier 1.

### Decrypt

Mixed quality. Crypto fraud/stablecoin/company items are useful, but non-crypto
AI/stock/UFO content was correctly removed. Keep with relevance filter.

### Foresight News

Very useful Chinese source. It contributed major RWA, Aave/Kelp, Base payments,
Wasabi security, and Chinese summaries. Keep as Chinese core.

### Odaily

Useful for speed, but noisy. It included macro, price prediction, AI stock, UFO,
NFT opinion, and market commentary. Keep as lower-weight China supplement.

### Investing.com

Useful occasionally, but mostly market/PR-adjacent. Keep low weight and demote
thin price/newswire items.

### Announcements

Binance, OKX, and Bybit all returned data, but none were inside this 24h window.
Bybit samples include stock/ETF-style perpetuals such as `QQQUSDT`, `EWJUSDT`,
and `MUUSDT`, so announcement filtering should distinguish crypto token
listings from TradFi-symbol contracts.

## Immediate Coding Recommendations

1. Add source metadata to every item.
   - Done in this iteration.

2. Add source-level debug exports.
   - Done in this iteration.

3. Add taxonomy categories:
   - `Security & Exploits`
   - `Stablecoins & Payments`
   - `Market Structure`
   - `Governance & Protocol Updates`

4. Add `quality_action` before classification:
   - `keep`
   - `demote`
   - `drop`
   - `needs_cluster_context`

5. Harden filters:
   - Drop daily roundups.
   - Demote opinions.
   - Drop unrelated macro/AI/stock stories unless crypto linkage is explicit.
   - Demote thin price prediction and TA pieces.
   - Demote campaign/reward/competition announcements.

6. Improve scoring:
   - Use `source_weight`.
   - Add security/regulatory/funding/major-announcement boosts.
   - Add multi-source confirmation boost.
   - Add noisy-source and opinion penalties.

7. Improve cluster output:
   - Preserve supporting sources in the story cluster.
   - Export `story_id`, `canonical_title`, `primary_source`,
     `supporting_sources`, and `input_types_present`.

## Implemented In This Iteration

- Added source metadata:
  - `input_type`
  - `source_tier`
  - `source_region`
  - `source_focus`
  - `source_weight`
- Added debug exports:
  - `source_inventory.md`
  - `source_samples.md`
  - `source_counts.json`
  - `announcement_samples.md`
- Added quality labels:
  - `quality_action`
  - `quality_reason`
- Added categories:
  - `Security & Exploits`
  - `Stablecoins & Payments`
  - `Governance & Protocol Updates`
  - `Market Structure`
- Added classification post-processing:
  - Real listings remain `Exchange Listings`.
  - Non-listing exchange/derivative market stories move out of
    `Exchange Listings`.
  - Security stories receive category override.
  - RWA stories take precedence over stablecoin keyword collisions.
- Added stronger hard-drop patterns for daily roundups, weekly roundups, and
  price-prediction roundups.

## Decision

The selected source mix is good enough for V1 sampling, but the pipeline needs
better scoring and story-cluster structure before takeaway optimization.

Next recommended implementation step:

```text
Make story clusters first-class objects and add explainable score components.
```
