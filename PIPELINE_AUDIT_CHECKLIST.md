# Pipeline Audit Checklist

Use this checklist to keep iteration sequential. Do not skip ahead unless the
user explicitly changes the phase.

## 1. Source Continuity

Question: Are sources being collected continuously enough to avoid missing items?

Checks:

- RSS feeds are imported into Miniflux.
- Miniflux has fresh entries.
- Non-RSS collector stores Foresight and exchange announcements in SQLite.
- Collector cron is running frequently enough.

## 2. Source Health

Question: Which sources are useful after filtering and clustering?

Checks:

- Raw count.
- 24h count.
- Relevant count.
- Final clustered story count.
- Drop reasons.
- Last seen time.
- Suggested action: keep, demote, disable, watch.

## 3. Relevance Filter

Question: Are we dropping junk without losing important stories?

Checks:

- Review `relevance_removed.json`.
- Review kept low-score stories.
- Identify source-specific noise.
- Tune `keep`, `demote`, `drop` rules only from examples.

## 4. Deduplication

Question: Are exact duplicates removed safely?

Checks:

- URL duplicates.
- Title duplicates.
- Syndicated copies.
- False duplicate risk.

## 5. Story Clustering

Question: Are multiple reports about the same event grouped correctly?

Checks:

- Major stories merge across sources.
- Similar but distinct market stories do not merge.
- Chinese/English overlap is detected when possible.
- Primary source selection is reasonable.

## 6. Classification

Question: Do stories land in the right internal category?

Checks:

- `Security & Exploits`
- `Stablecoins & Payments`
- `Market Structure`
- `RWA & Institutional`
- `DeFi & New Primitives`
- `Regulatory & Policy`

## 7. Scoring

Question: Does the ranked story list match editorial judgment?

Checks:

- Top 20 ranked stories.
- Source weight impact.
- Topic weight impact.
- Multi-source confirmation.
- Protocol/security impact.
- Market-noise penalty.

## 8. Takeaways

Question: Does the summary explain the day clearly?

Checks:

- 5-8 executive bullets.
- Fact-first, no predictions.
- Includes affected entity, amount, jurisdiction, protocol, or token.
- Avoids headline repetition.

## 9. Telegram Output

Question: Is the final output readable in the existing Telegram topic structure?

Checks:

- Topic routing.
- Per-topic caps.
- Executive summary placement.
- Full archive link.
- Dry-run preview.
