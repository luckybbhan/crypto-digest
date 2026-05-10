# Current Iteration

Last updated: 2026-05-10

## Phase

Ready For Review / VPS Update

## Goal

Review the local optimization batch, then decide whether to push/deploy it to
the VPS.

This phase answers:

- Are the local changes acceptable?
- Should the branch be committed/pushed?
- Should the VPS pull the new version and run a test dry-run?

## Current Scope

Do not make more pipeline changes unless review finds a blocker.

Expected deliverables:

- Local review summary.
- Optional commit/push.
- VPS pull and dry-run, if approved.

## Latest Run

Command:

```bash
python3 debug_pipeline.py --source live --hours 24 --sample-per-source 5
```

Export:

```text
exports/debug/latest
```

Counts:

```text
raw 438 -> 24h 72 -> relevant 65 -> dedup 65 -> clustered 56
```

Source health decisions from this run:

- `keep`: CoinDesk, Cointelegraph, CryptoSlate, Decrypt, Foresight News, Investing.com, Odaily Articles, Odaily Newsflash, The Block
- `demote`: Wu Blockchain
- `watch`: Binance, Blockworks, Bybit, Chainalysis, Forkast, OKX, Protos, The Defiant, Unchained

Relevance filter changes in this run:

- Added missing crypto relevance terms for `btc`, `evm`, Chinese crypto-asset wording, smart contracts, protocols, security incidents, private keys, exploits, and stolen funds.
- Changed promotional filtering so strong-signal stories, such as stablecoin policy/news, are not dropped just because the title contains `rewards`.
- Recovered examples: Wasabi Protocol security incident updates, Trump Media BTC/CRO unrealized loss stories, and stablecoin rewards/Senate bill coverage.
- Added narrow relevance terms for `NFT`, `CLARITY Act`, and `prediction market`.
- Added Chinese hard-drop pattern for `星球早讯/午讯/晚讯` roundup posts.

Dedup changes in this run:

- Replaced ASCII-only title normalization with Unicode-aware title normalization.
- Exact dedup now preserves distinct Chinese titles and no longer treats all pure Chinese titles as the same empty key.
- Current final run removed `0` items at exact dedup; near-duplicates are handled by story clustering.

Current cluster merges:

- LayerZero/Kelp exploit response: CoinDesk + The Block.
- Arbitrum/Aave/North Korea ETH transfer: Cointelegraph + The Block.
- CLARITY Act markup: CoinDesk + CryptoSlate.
- Wasabi Protocol security incident update: Foresight News + Odaily Newsflash.

Classification changes in this run:

- Prediction-market stories now normalize to `Market Structure`, unless they are explicitly regulatory.
- RWA/Institutional now requires hard institutional signals such as tokenization, BlackRock, spot ETF flows, net inflows/outflows, or RWA terms.
- BTC price prediction and generic institutional-adoption market stories no longer stay in `RWA & Institutional`; they normalize to `Macro & Market`.

Scoring and clustering changes in this run:

- Price-prediction and short-term price-move stories are now demoted as `market_noise`.
- Generic `ETF` and `institutional` mentions no longer create high score by themselves.
- Hard RWA/institutional signals such as BlackRock, tokenization, RWA, and ETF inflows/outflows still receive high score.
- Cross-language clustering now uses narrow canonical story entities.
- Newly merged examples: BlackRock tokenized funds, Trump Media Q1 crypto losses, Strategy BTC-sale statement, and Aave/Arbitrum/North Korea ETH transfer.

Current top ranked stories:

- Arbitrum/Aave/North Korea ETH transfer.
- BlackRock tokenized fund offerings.
- LayerZero/Kelp exploit response.
- Spot Bitcoin ETF inflow streak.
- CLARITY Act markup.
- SEC innovation-pathway speech.

Takeaway changes in this run:

- Debug pipeline now supports `--with-takeaways`.
- Added `executive_takeaways.md` and `topic_takeaways.md` preview exports.
- Executive and topic summary prompts now require Simplified Chinese, source-grounded facts, and no invented dates/numbers/actions.
- Summary generation temperature is now `0`.
- Summary bullet markers are normalized to `•`.
- Story prompt input now includes clustered member reports, so supporting-source summaries can fill missing primary summaries.

Takeaway validation:

- Previous NFT-topic hallucinations disappeared.
- No `-` bullets remained after normalization.
- Executive preview is fact-first and no longer uses analytical phrasing such as `加速`.

Telegram output changes in this run:

- Added `telegram_full_preview.md` debug export matching default Telegram send order.
- Telegram output now hides `quality_action=demote` articles by default.
- Topics with no Telegram-visible articles are skipped.
- Cluster primary articles can inherit a usable `story_summary` from supporting reports.
- Removed `_No summary_` placeholders from Telegram article rendering.

Telegram validation:

```bash
python3 digest.py --source live --dry-run
```

Result:

- Dry-run completed successfully.
- Actual send path produced header, executive takeaways, and topic sections.
- Longest debug preview message was under 4000 chars.
- Live fetch had intermittent source timeouts, but the pipeline continued and completed.

Current topic counts:

- `Macro & Market`: 14
- `Market Structure`: 11
- `Regulatory & Policy`: 8
- `Security & Exploits`: 8
- `Stablecoins & Payments`: 5
- `Infrastructure & Tech`: 5
- `Emerging Narratives`: 4
- `RWA & Institutional`: 3
- `DeFi & New Primitives`: 3

Important limitation:

- This run used `--source live`, so RSS source freshness is judged only from the returned feed window. Non-RSS history freshness is available from SQLite, but RSS last-seen freshness from Miniflux is not yet included in `source_health`.

## Do Not Do In This Phase

- Do not change pipeline behavior unless a blocker is found.
- Do not refactor `digest.py`.
- Do not add new news sources unless the health report shows a clear gap.
- Do not change scoring weights.

## Next Step

Review the local outputs:

```text
exports/debug/latest/telegram_full_preview.md
exports/debug/latest/telegram_preview.md
exports/debug/latest/executive_takeaways.md
exports/debug/latest/topic_takeaways.md
```

If acceptable, commit/push locally, then update the VPS and run server dry-run.

## How To Resume

Before making changes, read:

```bash
cat CURRENT_ITERATION.md
```

Then continue only the current phase unless the user explicitly changes phase.
