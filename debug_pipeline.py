import argparse
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from digest import (
    TZ_CST,
    cluster_stories,
    deduplicate,
    fetch_exchange_articles,
    fetch_live_articles,
    tag_all_articles,
)
from miniflux_client import fetch_miniflux_articles


BASE_DIR = Path(__file__).resolve().parent
EXPORT_ROOT = BASE_DIR / "exports" / "debug"


def _article_key(article: dict) -> str:
    return (article.get("link") or article.get("title") or "").strip().lower()


def _json_article(article: dict) -> dict:
    published = article["published"]
    return {
        "source": article["source"],
        "title": article["title"],
        "link": article["link"],
        "summary": article["summary"],
        "published_utc": published.astimezone(timezone.utc).isoformat(),
        "published_utc8": published.astimezone(TZ_CST).isoformat(),
        "topics": article.get("topics", []),
    }


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_articles(path: Path, articles: list[dict]) -> None:
    _write_json(path, [_json_article(article) for article in articles])


def _removed(before: list[dict], after: list[dict]) -> list[dict]:
    after_keys = {_article_key(article) for article in after}
    return [article for article in before if _article_key(article) not in after_keys]


def _title_words(title: str) -> set[str]:
    from digest import _title_words as digest_title_words

    return digest_title_words(title)


def _jaccard(s1: set, s2: set) -> float:
    from digest import _jaccard as digest_jaccard

    return digest_jaccard(s1, s2)


def build_cluster_debug(articles: list[dict], threshold: float = 0.3) -> list[dict]:
    """Mirror cluster_stories and keep details about grouped articles."""
    clusters = []
    for article in articles:
        words = _title_words(article["title"])
        matched = None
        matched_score = 0.0
        for i, cluster in enumerate(clusters):
            score = _jaccard(words, _title_words(cluster["kept"]["title"]))
            if score >= threshold:
                matched = i
                matched_score = score
                break

        if matched is None:
            clusters.append({
                "kept": article,
                "members": [article],
                "scores": [],
            })
        else:
            cluster = clusters[matched]
            cluster["members"].append(article)
            cluster["scores"].append({
                "title": article["title"],
                "matched_kept_title": cluster["kept"]["title"],
                "score": round(matched_score, 3),
            })
            kept_after = cluster_stories([cluster["kept"], article], threshold=threshold)[0]
            cluster["kept"] = kept_after

    return [
        {
            "kept": _json_article(cluster["kept"]),
            "member_count": len(cluster["members"]),
            "members": [_json_article(article) for article in cluster["members"]],
            "scores": cluster["scores"],
        }
        for cluster in clusters
        if len(cluster["members"]) > 1
    ]


def write_topic_markdown(path: Path, by_topic: dict[str, list[dict]]) -> None:
    lines = ["# Classified Articles By Topic", ""]
    for topic in sorted(by_topic):
        articles = sorted(by_topic[topic], key=lambda a: a["published"], reverse=True)
        lines.extend([f"## {topic} ({len(articles)})", ""])
        for article in articles:
            pub = article["published"].astimezone(TZ_CST).strftime("%b %d, %H:%M UTC+8")
            lines.append(f"- [{article['title']}]({article['link']})")
            lines.append(f"  Source: {article['source']} · {pub}")
            if article["summary"]:
                lines.append(f"  Summary: {article['summary']}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export each digest pipeline stage for review.")
    parser.add_argument("--source", choices=["live", "miniflux"], default="miniflux")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--cluster-threshold", type=float, default=0.3)
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    stamp = now.astimezone(TZ_CST).strftime("%Y%m%d_%H%M%S")
    run_dir = EXPORT_ROOT / stamp
    latest_dir = EXPORT_ROOT / "latest"
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.source == "miniflux":
        rss_articles = fetch_miniflux_articles(hours=args.hours)
    else:
        rss_articles = fetch_live_articles()
    exchange_articles = fetch_exchange_articles()
    raw_articles = rss_articles + exchange_articles
    _write_articles(run_dir / "raw.json", raw_articles)

    cutoff = now - timedelta(hours=args.hours)
    after_24h = [article for article in raw_articles if article["published"] >= cutoff]
    _write_articles(run_dir / "after_24h.json", after_24h)

    after_dedup = deduplicate(after_24h)
    _write_articles(run_dir / "after_dedup.json", after_dedup)
    _write_articles(run_dir / "dedup_removed.json", _removed(after_24h, after_dedup))

    clusters = build_cluster_debug(after_dedup, threshold=args.cluster_threshold)
    _write_json(run_dir / "clusters.json", clusters)

    after_cluster = cluster_stories(after_dedup, threshold=args.cluster_threshold)
    _write_articles(run_dir / "after_cluster.json", after_cluster)
    _write_articles(run_dir / "cluster_removed.json", _removed(after_dedup, after_cluster))

    tag_all_articles(after_cluster)
    _write_articles(run_dir / "classified.json", after_cluster)

    by_topic = defaultdict(list)
    for article in after_cluster:
        for topic in article.get("topics", []):
            by_topic[topic].append(article)
    write_topic_markdown(run_dir / "by_topic.md", by_topic)

    summary = {
        "exported_at_utc": now.isoformat(),
        "source": args.source,
        "hours": args.hours,
        "cluster_threshold": args.cluster_threshold,
        "counts": {
            "rss": len(rss_articles),
            "exchange": len(exchange_articles),
            "raw": len(raw_articles),
            "after_24h": len(after_24h),
            "after_dedup": len(after_dedup),
            "dedup_removed": len(after_24h) - len(after_dedup),
            "after_cluster": len(after_cluster),
            "cluster_removed": len(after_dedup) - len(after_cluster),
            "classified": len(after_cluster),
        },
        "source_counts_after_cluster": dict(Counter(a["source"] for a in after_cluster)),
        "topic_counts": {topic: len(articles) for topic, articles in by_topic.items()},
    }
    _write_json(run_dir / "run_summary.json", summary)

    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)

    print(f"Debug export: {run_dir}")
    print(f"Latest: {latest_dir}")
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
