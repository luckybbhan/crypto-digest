import argparse
import json
from collections import Counter
from datetime import datetime, timezone

from config import ENABLE_FORESIGHT_API
from digest import fetch_exchange_articles, fetch_foresight_api
from source_history import get_articles_for_hours, prune_older_than, upsert_articles


def collect_non_rss_sources(include_foresight: bool = True, include_exchange: bool = True) -> list[dict]:
    articles = []
    if include_foresight and ENABLE_FORESIGHT_API:
        articles.extend(fetch_foresight_api())
    if include_exchange:
        articles.extend(fetch_exchange_articles())
    return articles


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect non-RSS sources into local SQLite history.")
    parser.add_argument("--foresight-only", action="store_true", help="Collect only Foresight News")
    parser.add_argument("--exchange-only", action="store_true", help="Collect only exchange announcements")
    parser.add_argument("--hours", type=int, default=24, help="Window for the post-collection status report")
    parser.add_argument("--prune-days", type=int, default=30, help="Delete history older than this many days")
    parser.add_argument("--json", action="store_true", help="Print machine-readable status")
    args = parser.parse_args()

    if args.foresight_only and args.exchange_only:
        parser.error("--foresight-only and --exchange-only cannot be used together")

    include_foresight = not args.exchange_only
    include_exchange = not args.foresight_only
    articles = collect_non_rss_sources(
        include_foresight=include_foresight,
        include_exchange=include_exchange,
    )
    result = upsert_articles(articles)
    deleted = prune_older_than(args.prune_days) if args.prune_days else 0
    recent = get_articles_for_hours(hours=args.hours)
    recent_counts = Counter(article["source"] for article in recent)
    status = {
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "fetched": len(articles),
        "inserted": result["inserted"],
        "updated": result["updated"],
        "pruned": deleted,
        "recent_hours": args.hours,
        "recent_total": len(recent),
        "recent_by_source": dict(sorted(recent_counts.items())),
    }

    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return

    print(f"Fetched: {status['fetched']}")
    print(f"Inserted: {status['inserted']}")
    print(f"Updated: {status['updated']}")
    print(f"Pruned: {status['pruned']}")
    print(f"History in last {args.hours}h: {status['recent_total']}")
    for source, count in status["recent_by_source"].items():
        print(f"{source}: {count}")


if __name__ == "__main__":
    main()
