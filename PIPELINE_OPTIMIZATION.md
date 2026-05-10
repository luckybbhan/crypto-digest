# Pipeline Optimization

This project now treats the digest workflow as a funnel. We optimize one stage
at a time and verify its output before moving to the next stage.

## Funnel

1. `Collect`
   - Gather media news, first-party announcements, and specialist/security signals.
   - Keep the input class explicit instead of treating every item as generic news.
   - Output: `raw.json`

2. `Normalize`
   - Clean titles, summaries, and links into a consistent shape.
   - Preserve input metadata such as `input_type`, `source_class`, and source role.
   - Output: `after_normalize.json`

3. `Time Filter`
   - Keep only articles inside the review window, usually 24 hours.
   - Output: `after_24h.json`

4. `Relevance Filter`
   - Remove obviously irrelevant, low-signal, or promotional content.
   - Output: `after_relevance.json`
   - Removed set: `relevance_removed.json`

5. `Dedup`
   - Remove exact duplicates by URL/title normalization.
   - Output: `after_dedup.json`
   - Removed set: `dedup_removed.json`

6. `Cluster`
   - Merge same-story coverage across media, announcement, and specialist inputs.
   - Keep source roles attached to the cluster instead of flattening everything.
   - Output: `after_cluster.json`
   - Debug details: `clusters.json`
   - Removed set: `cluster_removed.json`

7. `Classify`
   - Assign topic labels.
   - Output: `classified.json`
   - Human review: `by_topic.md`

8. `Score`
   - Rank articles inside each topic by importance.
   - Use different source weights for media reporting, first-party confirmation,
     specialist security signals, and low-trust/noisy feeds.
   - Included in `classified.json` and `by_topic.md` as `importance_score`.

9. `Takeaway`
   - Generate topic summaries only after the candidate set is trusted.

10. `Publish`
   - Render Telegram and Telegraph output.

## Review Workflow

When tuning a stage, review these files in order:

1. `run_summary.json`
2. The stage output file
3. The corresponding `*_removed.json` file
4. `by_topic.md` only after `Classify`

Do not tune downstream stages until the upstream stage looks correct.

## Current Iteration Order

1. `Relevance Filter`
2. `Dedup`
3. `Cluster`
4. `Classify`
5. `Score`
6. `Takeaway`

## Source Classes

The pipeline should not treat all inputs as news articles.

### `media_news`

Reported coverage from crypto-native and traditional media. This is the main
editorial layer for context, interpretation, and cross-source confirmation.

Examples:

- `CoinDesk`
- `The Block`
- `Blockworks`
- `Foresight News`
- `Bloomberg`
- `Reuters`

### `official_announcement`

Primary-source updates from exchanges, protocols, foundations, companies, and
regulators. These sources are authoritative for what the issuer announced, but
not necessarily neutral about impact.

Examples:

- Exchange listings and delistings
- Protocol upgrade posts
- Regulator enforcement actions
- Foundation roadmap updates
- Company product or service announcements

### `specialist_signal`

Specialist feeds for security, compliance, on-chain risk, investigations, or
technical incidents. These often arrive before broad media coverage and should
be used as early warning signals.

Examples:

- `Chainalysis`
- `TRM Labs`
- `Elliptic`
- `SlowMist`
- `PeckShield`
- `CertiK`
- `BlockSec`

## Story Merge Rule

The story layer is where different input classes come together:

```text
Official announcement: "Coinbase lists X"
Media news: "Coinbase expands listing strategy amid..."
Specialist signal: "Token X deployer linked to..."

=> one story cluster with separate source roles
```

This makes takeaways stronger because the model can distinguish the fact, the
context, and the risk signal instead of summarizing all three as equal news
items.
