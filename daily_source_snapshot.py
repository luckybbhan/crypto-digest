import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from digest import TZ_CST, apply_normalization, collect_articles, filter_articles_by_hours


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = BASE_DIR / "exports" / "source_snapshots"


def _article_row(article: dict) -> dict:
    published = article["published"].astimezone(timezone.utc)
    published_cst = article["published"].astimezone(TZ_CST)
    return {
        "source": article.get("source", ""),
        "source_tier": article.get("source_tier", ""),
        "source_weight": article.get("source_weight", ""),
        "quality_action": article.get("quality_action", ""),
        "quality_reason": article.get("quality_reason", ""),
        "published_utc": published.isoformat(),
        "published_utc8": published_cst.isoformat(),
        "title": article.get("title", ""),
        "link": article.get("link", ""),
        "summary": article.get("summary", ""),
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "source",
        "source_tier",
        "source_weight",
        "quality_action",
        "quality_reason",
        "published_utc",
        "published_utc8",
        "title",
        "link",
        "summary",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, rows: list[dict], counts: Counter) -> None:
    lines = ["# Daily Source Snapshot", ""]
    lines.append("## Source Counts")
    lines.append("")
    for source, count in counts.most_common():
        lines.append(f"- {source}: {count}")
    lines.append("")
    lines.append("## Articles")
    lines.append("")
    for row in rows:
        title = row["title"].replace("\n", " ").strip()
        published = row["published_utc8"][:16].replace("T", " ")
        quality = row["quality_reason"] or row["quality_action"] or "keep"
        lines.append(f"- [{row['source']}] {published} · {quality} · {title}")
        if row["link"]:
            lines.append(f"  {row['link']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _update_latest_link(run_dir: Path, latest_path: Path) -> None:
    if latest_path.exists() or latest_path.is_symlink():
        latest_path.unlink()
    latest_path.symlink_to(run_dir, target_is_directory=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export daily raw source titles for human review.")
    parser.add_argument("--source", choices=["live", "miniflux"], default="miniflux")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    run_name = now.astimezone(TZ_CST).strftime("%Y%m%d_%H%M")
    output_root = Path(args.output_dir)
    run_dir = output_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    articles = collect_articles(source=args.source, hours=args.hours)
    articles = apply_normalization(articles)
    articles = filter_articles_by_hours(articles, now, hours=args.hours)
    rows = [
        _article_row(article)
        for article in sorted(articles, key=lambda item: item["published"], reverse=True)
    ]
    counts = Counter(row["source"] for row in rows)
    payload = {
        "exported_at_utc": now.isoformat(),
        "source": args.source,
        "hours": args.hours,
        "total": len(rows),
        "source_counts": dict(counts.most_common()),
        "articles": rows,
    }

    _write_json(run_dir / "articles.json", payload)
    _write_csv(run_dir / "articles.csv", rows)
    _write_markdown(run_dir / "articles.md", rows, counts)
    _update_latest_link(run_dir, output_root / "latest")

    print(f"Snapshot: {run_dir}")
    print(f"Articles: {len(rows)}")
    for source, count in counts.most_common():
        print(f"{source}: {count}")


if __name__ == "__main__":
    main()
