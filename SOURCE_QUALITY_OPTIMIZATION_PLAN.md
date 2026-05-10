# Source Quality Optimization Plan

Last updated: 2026-05-10

Latest sample review: `SOURCE_SAMPLE_REVIEW_20260510.md`

## Goal

Use real collected data to tune source selection, category mapping, quality
scoring, and digest ranking.

The next step is not to add more sources blindly. The next step is to run the
selected source set once, inspect the raw inputs and each pipeline output, then
turn that review into concrete rules.

## Core Questions

This iteration should answer:

- Which selected sources actually return useful daily items?
- Which sources return too much low-quality or promotional content?
- Which categories are missing, overlapping, or too broad?
- Which signals should make a story rank higher?
- Which signals should make a story rank lower or be filtered out?
- Which articles should appear in Telegram versus only in the full archive?

## Selected V1 Inputs

### Media Sources

Use now:

- `CoinDesk`
- `The Block`
- `Blockworks`
- `Decrypt`
- `The Defiant`
- `Unchained`
- `Cointelegraph`
- `Foresight News`
- `Wu Blockchain`
- `Odaily Newsflash`
- `Odaily Articles`
- `Protos`
- `Chainalysis`
- `CryptoSlate`
- `Forkast`
- `Investing.com Crypto`

### Announcement Sources

Use now:

- `Binance`
- `OKX`
- `Bybit`

### Next Adapter Test Sources

Do not include in the main quality review until adapters are verified:

- `SEC`
- `CFTC`
- `Kraken`
- `Ethereum Foundation Blog`
- `TRM Labs`
- `Elliptic`

## Development Phases

### Phase 1: Full Source Sampling

Purpose: collect one clean 24h sample from every selected V1 source.

Tasks:

- Run the selected source set with current defaults.
- Export source-level counts before filtering.
- Export source-level samples for manual review.
- Preserve `input_type` / `source_class` for each item.
- Separate media items from announcement items in debug output.

Recommended debug outputs:

```text
exports/debug/latest/raw.json
exports/debug/latest/source_inventory.md
exports/debug/latest/source_samples.md
exports/debug/latest/source_counts.json
exports/debug/latest/announcement_samples.md
```

Manual review questions:

- Did every selected source return data?
- Are any sources unexpectedly empty?
- Are any sources over-producing low-value content?
- Are announcement sources mostly listings/product notices or mostly campaigns?
- Does Foresight/Odaily replace PANews well enough for Chinese coverage?

Success criteria:

- At least 80% of selected media sources return usable data.
- No single media source dominates more than 30-35% of raw candidates.
- Announcement items are distinguishable from media news.
- The raw candidate set is large enough for coverage but not chaotic.

### Phase 2: Input Type And Source Metadata

Purpose: make the pipeline understand what each input is.

Tasks:

- Add `input_type`:
  - `media_news`
  - `official_announcement`
  - `specialist_signal`
- Add `source_tier`:
  - `tier_1`
  - `tier_2`
  - `tier_3`
  - `fallback`
- Add `source_region`:
  - `global`
  - `us`
  - `europe`
  - `asia`
  - `china`
  - `korea`
- Add `source_focus`:
  - `broad_crypto`
  - `defi`
  - `institutional`
  - `regulatory`
  - `security`
  - `exchange`
  - `market`
  - `culture`

Manual review questions:

- Do source classes match how the article should be treated?
- Are first-party announcements kept separate from media reports?
- Are specialist/security sources eligible for priority boosts?

Success criteria:

- Every item has explicit source metadata.
- Debug exports can be grouped by source class and source tier.
- Ranking rules no longer rely only on raw source names.

### Phase 3: Category Taxonomy Review

Purpose: make categories match the way we actually read crypto news.

Current categories to evaluate:

- `Exchange Listings`
- `Deal Flow & Funding`
- `Infrastructure & Tech`
- `RWA & Institutional`
- `DeFi & New Primitives`
- `Regulatory & Policy`
- `Macro & Market`
- `Emerging Narratives`
- `General`

Proposed category refinements:

- Add `Security & Exploits`
- Add `Stablecoins & Payments`
- Add `Governance & Protocol Updates`
- Add `Market Structure`
- Reduce use of `General`

Manual review questions:

- Which articles landed in the wrong category?
- Which categories are too broad?
- Which important stories got buried under `General`?
- Are exchange campaigns being wrongly classified as listings?
- Are security incidents mixed into DeFi or Infrastructure?

Success criteria:

- `General` is less than 10% of classified output.
- Security incidents have their own category or strong priority override.
- Official listings are separate from exchange marketing campaigns.
- Stablecoin/payment stories stop being scattered across DeFi/RWA/Macro.

### Phase 4: Relevance And Quality Filter

Purpose: remove junk before classification and scoring.

High-quality indicators:

- Original reporting or direct official source.
- Multiple independent sources cover the same event.
- Clear affected party, amount, chain, token, protocol, or jurisdiction.
- Regulatory, security, funding, listing, protocol, or institutional impact.
- Concrete numbers: funding amount, exploit size, TVL, volume, revenue,
  liquidation, ETF flow, AUM, market share.
- Source is high-trust for the topic.

Low-quality indicators:

- Pure price prediction without new information.
- Sponsored/promotional tone.
- Exchange campaign, reward pool, trading competition, deposit event.
- Generic "what is crypto" education content.
- Rewritten version of a story already captured.
- Thin market update with no causal signal.
- Meme/social chatter without market or ecosystem impact.
- AI/tech story with no crypto relevance.

Filter actions:

- `keep`: eligible for classification and scoring.
- `demote`: keep in archive, unlikely to appear in Telegram.
- `drop`: remove from digest pipeline.
- `needs_cluster_context`: low alone, useful if part of a larger story.

Manual review questions:

- What did the filter drop incorrectly?
- What did it keep that feels like garbage?
- Which sources need source-specific demotion?
- Which keywords are causing false positives?

Success criteria:

- Obvious marketing/promotional items are removed or demoted.
- False drops are rare for security/regulatory/funding stories.
- Raw candidates shrink into a reviewable candidate set.

### Phase 5: Story Clustering And Dedup Review

Purpose: merge repeated coverage into story-level units.

Status: implemented as first-class debug output. Continue tuning false
positive/false negative cases from real samples.

Tasks:

- Group same-event items across Chinese and English sources.
- Keep primary source plus supporting sources.
- Preserve announcement/media/specialist roles inside the cluster.
- Prevent false merges for similar but distinct events.

Cluster output should include:

```text
story_id
canonical_title
primary_source
supporting_sources
input_types_present
source_count
entities
topic
cluster_reason
```

Current debug outputs:

```text
exports/debug/latest/stories.json
exports/debug/latest/ranked_stories.md
```

Manual review questions:

- Did Chinese and English reports about the same event merge?
- Did two different exchange listings get incorrectly merged?
- Did a primary-source announcement attach to related media coverage?
- Are supporting sources useful or just duplicates?

Success criteria:

- Major repeated stories collapse into one story.
- Supporting sources improve confidence and context.
- False merges are low enough for human review.

### Phase 6: Importance Scoring

Purpose: decide what matters before writing takeaways.

Status: first explainable score components are implemented. The next iteration
should tune weights with manual review of `ranked_stories.md`.

Suggested scoring components:

```text
importance_score =
  source_weight
  + topic_weight
  + impact_weight
  + entity_weight
  + confirmation_weight
  + recency_weight
  + novelty_weight
  - noise_penalty
```

Source weights:

- `1.25`: high-trust traditional media confirmation.
- `1.15`: high-trust crypto-native media.
- `1.10`: specialist/security source.
- `1.05`: first-party announcement.
- `1.00`: context/depth media.
- `0.90`: fast broad media.
- `0.75`: market/PR-prone media.
- `0.50`: disabled/noisy fallback.

Topic weights:

- High: security exploit, regulation/enforcement, major funding, major listing,
  protocol incident, stablecoin risk, institutional adoption.
- Medium: infrastructure updates, governance, DeFi product launches, market
  structure.
- Low: generic market commentary, campaigns, education, soft culture.

Impact weights:

- Large exploit amount.
- Major jurisdiction.
- Top exchange or protocol.
- Major fundraise or investor.
- Significant TVL/revenue/volume/ETF flow change.
- Multi-source coverage.

Noise penalties:

- Campaign/reward-pool content.
- Price prediction without evidence.
- Sponsored or advertorial tone.
- Duplicated rewrite.
- Weak crypto relevance.

Manual review questions:

- Do top 10 stories feel like the actual top 10?
- Did a low-quality source outrank a high-quality story?
- Did a niche but important security/regulatory item get buried?
- Are Chinese/Asia stories underweighted?

Success criteria:

- Top-ranked stories are defensible to a human editor.
- Ranking is explainable with visible score components.
- Low-quality high-volume sources cannot dominate.

### Phase 7: Takeaway Quality Review

Purpose: make summaries useful instead of generic.

Takeaway requirements:

- Start from story clusters, not raw articles.
- Mention what happened.
- Mention why it matters.
- Mention affected protocol/company/token/jurisdiction.
- Avoid unsupported predictions.
- Use primary-source facts when available.
- Use media/specialist sources for context and risk.

Bad takeaway patterns:

- Restating headlines.
- Mixing unrelated stories into one bullet.
- Treating campaigns as meaningful news.
- Omitting numbers or affected parties.
- Saying "could impact the market" without explaining how.

Manual review questions:

- Can a reader understand the day in under two minutes?
- Are the top bullets actually important?
- Are takeaways factual and compact?
- Are Chinese and English inputs synthesized correctly?

Success criteria:

- Executive summary has 5-10 high-signal bullets.
- Topic takeaways are grounded in clustered stories.
- No obvious hallucinated causal claims.

## Review Workflow

For each test run, inspect files in this order:

1. `source_inventory.md`
2. `source_samples.md`
3. `raw.json`
4. `after_relevance.json`
5. `relevance_removed.json`
6. `clusters.json`
7. `stories.json`
8. `ranked_stories.md`
9. `after_cluster.json`
10. `classified.json`
11. `by_topic.md`
12. `run_summary.json`

## Next Concrete Build Tasks

1. Review `ranked_stories.md` manually and label false positives/false
   negatives in clustering.
2. Tune `story_score_components` weights so top 10 stories match editor
   judgment.
3. Split security weighting between protocol/user-fund incidents and broader
   crime/legal stories.
4. Add topic-level caps or demotions for low-signal market commentary.
5. Move takeaway generation from raw topic articles to ranked story clusters.
6. Add primary-source/official-announcement attachment when a media story covers
   the same first-party announcement.

Completed in the current iteration:

- Added local SQLite history for non-RSS sources (`Foresight News`, `Binance`,
  `OKX`, `Bybit`) via `source_collector.py`.
- `digest.py --source miniflux` now combines Miniflux RSS history with local
  non-RSS history.
- Added executive digest takeaways from ranked story clusters.
- Added Telegram topic routing from internal categories to the existing forum
  topics.
- Added Telegram per-topic caps so the main group receives top-ranked items,
  while Telegraph/debug exports keep the fuller archive.

## Decision Rule

Do not optimize the final summary until the candidate stories look right.

The correct order is:

```text
source quality -> relevance -> cluster -> classify -> score -> takeaway
```

If upstream data is noisy, the model will only produce polished noise.
