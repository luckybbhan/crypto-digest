import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import FEEDS
from digest import (
    fetch_binance,
    fetch_bybit,
    fetch_feed,
    fetch_okx,
)


BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "exports"
TZ_CST = timezone(timedelta(hours=8))


def _article_to_record(article: dict, now: datetime) -> dict:
    published = article["published"]
    age_hours = round((now - published).total_seconds() / 3600, 2)
    return {
        "source": article["source"],
        "title": article["title"],
        "link": article["link"],
        "summary": article["summary"],
        "published_utc": published.astimezone(timezone.utc).isoformat(),
        "published_utc8": published.astimezone(TZ_CST).isoformat(),
        "age_hours": age_hours,
    }


def _write_markdown(path: Path, records: list[dict], counts: Counter, now: datetime) -> None:
    lines = [
        "# Crypto Digest Source Export",
        "",
        f"- Exported: {now.astimezone(TZ_CST).strftime('%Y-%m-%d %H:%M UTC+8')}",
        f"- Total articles: {len(records)}",
        f"- Sources: {len(counts)}",
        "",
        "## Source Counts",
        "",
    ]
    for source, count in counts.most_common():
        lines.append(f"- {source}: {count}")

    lines.extend(["", "## Articles", ""])
    for source in sorted(counts):
        source_records = [r for r in records if r["source"] == source]
        lines.extend([f"### {source} ({len(source_records)})", ""])
        for i, record in enumerate(source_records, 1):
            published = datetime.fromisoformat(record["published_utc8"]).strftime("%b %d, %H:%M UTC+8")
            lines.append(f"{i}. [{record['title']}]({record['link']})")
            lines.append(f"   - Published: {published} ({record['age_hours']}h ago)")
            if record["summary"]:
                lines.append(f"   - Summary: {record['summary']}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export current news source articles for quality review.")
    parser.add_argument("--hours", type=int, default=24, help="Keep articles published within this many hours")
    parser.add_argument("--limit-per-source", type=int, default=30, help="Max articles to keep per source")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=args.hours)
    articles = []

    for feed in FEEDS:
        articles.extend(fetch_feed(feed))

    articles.extend(fetch_binance())
    articles.extend(fetch_okx())
    articles.extend(fetch_bybit())

    recent = [a for a in articles if a["published"] >= cutoff]
    recent.sort(key=lambda a: (a["source"], a["published"]), reverse=True)

    limited = []
    per_source = Counter()
    for article in recent:
        if per_source[article["source"]] >= args.limit_per_source:
            continue
        limited.append(article)
        per_source[article["source"]] += 1

    records = [_article_to_record(article, now) for article in limited]
    records.sort(key=lambda r: (r["source"], r["published_utc"]), reverse=True)
    counts = Counter(record["source"] for record in records)

    EXPORT_DIR.mkdir(exist_ok=True)
    stamp = now.astimezone(TZ_CST).strftime("%Y%m%d_%H%M")
    json_path = EXPORT_DIR / f"news_sources_{stamp}.json"
    md_path = EXPORT_DIR / f"news_sources_{stamp}.md"
    latest_json = EXPORT_DIR / "news_sources_latest.json"
    latest_md = EXPORT_DIR / "news_sources_latest.md"

    payload = {
        "exported_at_utc": now.isoformat(),
        "window_hours": args.hours,
        "limit_per_source": args.limit_per_source,
        "total_fetched": len(articles),
        "total_recent": len(recent),
        "total_exported": len(records),
        "counts_by_source": dict(counts),
        "articles": records,
    }
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    _write_markdown(md_path, records, counts, now)
    _write_markdown(latest_md, records, counts, now)

    print(f"Fetched: {len(articles)}")
    print(f"Recent: {len(recent)}")
    print(f"Exported: {len(records)}")
    print(f"Markdown: {md_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
