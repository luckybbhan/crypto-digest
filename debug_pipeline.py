import argparse
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config import DEFAULT_SOURCE_METADATA, ENABLE_FORESIGHT_API, FEEDS, SOURCE_METADATA
from digest import (
    TZ_CST,
    apply_deduplication,
    apply_normalization,
    apply_relevance_filter,
    annotate_story_scores,
    article_story_similarity,
    article_rank_score,
    build_story_clusters,
    classify_articles,
    cluster_stories,
    collect_articles,
    filter_articles_by_hours,
    group_articles_by_topic,
    localize_articles_for_telegram,
    render_header,
    render_topic_section,
    score_articles,
    summarize_digest,
    summarize_topic,
    telegram_articles_for_topic,
)
from source_history import source_status as non_rss_source_status


BASE_DIR = Path(__file__).resolve().parent
EXPORT_ROOT = BASE_DIR / "exports" / "debug"


def _article_key(article: dict) -> str:
    return (article.get("link") or article.get("title") or "").strip().lower()


def _json_article(article: dict) -> dict:
    published = article["published"]
    return {
        "source": article["source"],
        "input_type": article.get("input_type"),
        "source_tier": article.get("source_tier"),
        "source_region": article.get("source_region"),
        "source_focus": article.get("source_focus"),
        "source_weight": article.get("source_weight"),
        "quality_action": article.get("quality_action"),
        "quality_reason": article.get("quality_reason"),
        "title": article["title"],
        "display_title": article.get("display_title"),
        "link": article["link"],
        "summary": article["summary"],
        "display_summary": article.get("display_summary"),
        "published_utc": published.astimezone(timezone.utc).isoformat(),
        "published_utc8": published.astimezone(TZ_CST).isoformat(),
        "topics": article.get("topics", []),
        "importance_score": article.get("importance_score", 0),
        "importance_score_components": article.get("importance_score_components", []),
        "story_id": article.get("story_id"),
        "cluster_size": article.get("cluster_size", 1),
        "story_source_count": article.get("story_source_count", 1),
        "story_sources": article.get("story_sources", [article["source"]]),
        "supporting_sources": article.get("supporting_sources", []),
        "story_summary": article.get("story_summary"),
        "story_score": article.get("story_score"),
        "story_score_components": article.get("story_score_components", []),
    }


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_articles(path: Path, articles: list[dict]) -> None:
    _write_json(path, [_json_article(article) for article in articles])


def _json_story(story: dict) -> dict:
    return {
        "story_id": story["story_id"],
        "canonical_title": story["canonical_title"],
        "story_score": story.get("story_score"),
        "story_score_components": story.get("story_score_components", []),
        "article_count": story["article_count"],
        "source_count": story["source_count"],
        "sources": story["sources"],
        "supporting_sources": story["supporting_sources"],
        "input_types": story["input_types"],
        "source_tiers": story["source_tiers"],
        "first_published_utc8": story["first_published"].astimezone(TZ_CST).isoformat(),
        "latest_published_utc8": story["latest_published"].astimezone(TZ_CST).isoformat(),
        "primary_article": _json_article(story["primary_article"]),
        "articles": [_json_article(article) for article in story["articles"]],
        "cluster_matches": story["cluster_matches"],
    }


def _write_stories(path: Path, stories: list[dict]) -> None:
    _write_json(path, [_json_story(story) for story in stories])


def _removed(before: list[dict], after: list[dict]) -> list[dict]:
    after_keys = {_article_key(article) for article in after}
    return [article for article in before if _article_key(article) not in after_keys]


def _source_metadata(source: str) -> dict:
    return DEFAULT_SOURCE_METADATA | SOURCE_METADATA.get(source, {})


def _expected_sources() -> list[str]:
    sources = [feed["name"] for feed in FEEDS]
    if ENABLE_FORESIGHT_API:
        sources.append("Foresight News")
    sources.extend(["Binance", "OKX", "Bybit"])
    return sorted(set(sources))


def _counts_by_field(articles: list[dict], field: str) -> dict[str, int]:
    return dict(Counter(str(article.get(field) or "unknown") for article in articles))


def build_source_counts(stages: dict[str, list[dict]]) -> dict:
    return {
        stage: {
            "total": len(articles),
            "by_source": dict(Counter(article["source"] for article in articles)),
            "by_input_type": _counts_by_field(articles, "input_type"),
            "by_source_tier": _counts_by_field(articles, "source_tier"),
            "by_source_region": _counts_by_field(articles, "source_region"),
            "by_source_focus": _counts_by_field(articles, "source_focus"),
            "by_quality_action": _counts_by_field(articles, "quality_action"),
            "by_quality_reason": _counts_by_field(articles, "quality_reason"),
        }
        for stage, articles in stages.items()
    }


def write_source_inventory(path: Path, stages: dict[str, list[dict]]) -> None:
    stage_counts = {
        stage: Counter(article["source"] for article in articles)
        for stage, articles in stages.items()
    }
    sources = sorted(set(_expected_sources()) | {
        article["source"]
        for articles in stages.values()
        for article in articles
    })

    lines = [
        "# Source Inventory",
        "",
        "| Source | Type | Tier | Region | Focus | Raw | 24h | Relevant | Deduped | Clustered | Classified |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for source in sources:
        meta = _source_metadata(source)
        lines.append(
            "| "
            + " | ".join([
                source,
                meta["input_type"],
                meta["source_tier"],
                meta["source_region"],
                meta["source_focus"],
                str(stage_counts.get("raw", Counter()).get(source, 0)),
                str(stage_counts.get("after_24h", Counter()).get(source, 0)),
                str(stage_counts.get("after_relevance", Counter()).get(source, 0)),
                str(stage_counts.get("after_dedup", Counter()).get(source, 0)),
                str(stage_counts.get("after_cluster", Counter()).get(source, 0)),
                str(stage_counts.get("classified", Counter()).get(source, 0)),
            ])
            + " |"
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def write_source_samples(
    path: Path,
    title: str,
    articles: list[dict],
    sample_per_source: int = 5,
    input_type: Optional[str] = None,
) -> None:
    if input_type:
        articles = [article for article in articles if article.get("input_type") == input_type]

    by_source = defaultdict(list)
    for article in sorted(articles, key=lambda a: a["published"], reverse=True):
        if len(by_source[article["source"]]) < sample_per_source:
            by_source[article["source"]].append(article)

    lines = [f"# {title}", ""]
    for source in sorted(by_source):
        meta = _source_metadata(source)
        lines.extend([
            f"## {source} ({len(by_source[source])} samples)",
            "",
            f"- Type: `{meta['input_type']}`",
            f"- Tier: `{meta['source_tier']}`",
            f"- Region: `{meta['source_region']}`",
            f"- Focus: `{meta['source_focus']}`",
            "",
        ])
        for i, article in enumerate(by_source[source], 1):
            pub = article["published"].astimezone(TZ_CST).strftime("%b %d, %H:%M UTC+8")
            score = article.get("importance_score")
            score_text = f" · Score: {score}" if score is not None else ""
            lines.append(f"{i}. [{article['title']}]({article['link']})")
            lines.append(f"   Published: {pub}{score_text}")
            if article.get("summary"):
                lines.append(f"   Summary: {article['summary']}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 3)


def _source_action(row: dict) -> tuple[str, str]:
    raw = row["raw"]
    recent = row["after_24h"]
    relevant = row["after_relevance"]
    final = row["after_cluster"]
    input_type = row["input_type"]
    relevant_rate = row["raw_to_relevant_rate"]
    final_rate = row["relevant_to_final_rate"]

    if raw == 0:
        return "watch", "No raw items in this run; verify route or wait for a longer window."
    if recent == 0:
        return "watch", "Source returned items but none were inside the review window."
    if relevant == 0:
        return "demote", "Recent items were fully removed by relevance/quality filters."
    if final == 0:
        return "demote", "Relevant items did not survive final clustering."
    if input_type == "official_announcement" and final == 0:
        return "watch", "Announcements are bursty; keep collecting before judging."
    if raw >= 50 and relevant_rate < 0.1:
        return "demote", "High raw volume but low relevance conversion."
    if final_rate < 0.25 and relevant >= 4:
        return "watch", "Many relevant items collapsed or lost before final stories."
    return "keep", "Contributed usable final stories in this run."


def build_source_health(stages: dict[str, list[dict]], hours: int) -> list[dict]:
    stage_counts = {
        stage: Counter(article["source"] for article in articles)
        for stage, articles in stages.items()
    }
    drop_reasons_by_source = defaultdict(Counter)
    for article in stages.get("after_24h", []):
        if article.get("quality_action") == "drop":
            drop_reasons_by_source[article["source"]][article.get("quality_reason", "unknown")] += 1

    story_support_counts = Counter()
    for article in stages.get("after_cluster", []):
        for source in article.get("story_sources", [article["source"]]):
            story_support_counts[source] += 1

    try:
        history_status = non_rss_source_status(hours=hours)
    except Exception:
        history_status = {}

    rows = []
    sources = sorted(set(_expected_sources()) | {
        article["source"]
        for articles in stages.values()
        for article in articles
    })
    for source in sources:
        meta = _source_metadata(source)
        raw = stage_counts.get("raw", Counter()).get(source, 0)
        recent = stage_counts.get("after_24h", Counter()).get(source, 0)
        relevant = stage_counts.get("after_relevance", Counter()).get(source, 0)
        deduped = stage_counts.get("after_dedup", Counter()).get(source, 0)
        final = stage_counts.get("after_cluster", Counter()).get(source, 0)
        row = {
            "source": source,
            "input_type": meta["input_type"],
            "source_tier": meta["source_tier"],
            "source_region": meta["source_region"],
            "source_focus": meta["source_focus"],
            "source_weight": meta["source_weight"],
            "raw": raw,
            "after_24h": recent,
            "after_relevance": relevant,
            "after_dedup": deduped,
            "after_cluster": final,
            "supported_story_count": story_support_counts.get(source, final),
            "raw_to_24h_rate": _rate(recent, raw),
            "raw_to_relevant_rate": _rate(relevant, raw),
            "recent_to_relevant_rate": _rate(relevant, recent),
            "relevant_to_final_rate": _rate(final, relevant),
            "drop_reasons": dict(drop_reasons_by_source.get(source, Counter())),
            "history": history_status.get(source, {}),
        }
        action, reason = _source_action(row)
        row["suggested_action"] = action
        row["suggested_reason"] = reason
        rows.append(row)
    return rows


def write_source_health(path: Path, rows: list[dict]) -> None:
    lines = [
        "# Source Health",
        "",
        "| Source | Action | Type | Tier | Raw | 24h | Relevant | Final | Raw->Relevant | Relevant->Final | Last Seen | Reason |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        history = row.get("history") or {}
        last_seen = history.get("last_seen_utc") or ""
        lines.append(
            "| "
            + " | ".join([
                row["source"],
                row["suggested_action"],
                row["input_type"],
                row["source_tier"],
                str(row["raw"]),
                str(row["after_24h"]),
                str(row["after_relevance"]),
                str(row["after_cluster"]),
                f"{row['raw_to_relevant_rate']:.1%}",
                f"{row['relevant_to_final_rate']:.1%}",
                last_seen,
                row["suggested_reason"],
            ])
            + " |"
        )

    lines.extend(["", "## Drop Reasons", ""])
    for row in rows:
        if not row["drop_reasons"]:
            continue
        reasons = ", ".join(f"{reason}: {count}" for reason, count in sorted(row["drop_reasons"].items()))
        lines.append(f"- `{row['source']}`: {reasons}")

    path.write_text("\n".join(lines), encoding="utf-8")


def build_cluster_debug(articles: list[dict], threshold: float = 0.3) -> list[dict]:
    """Mirror cluster_stories and keep details about grouped articles."""
    clusters = []
    for article in articles:
        matched = None
        matched_score = 0.0
        for i, cluster in enumerate(clusters):
            score = article_story_similarity(article, cluster["kept"])
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
        articles = sorted(by_topic[topic], key=lambda a: (article_rank_score(a), a["published"]), reverse=True)
        lines.extend([f"## {topic} ({len(articles)})", ""])
        for article in articles:
            pub = article["published"].astimezone(TZ_CST).strftime("%b %d, %H:%M UTC+8")
            lines.append(f"- [{article['title']}]({article['link']})")
            lines.append(f"  Source: {article['source']} · {pub} · Score: {article_rank_score(article)}")
            if article["summary"]:
                lines.append(f"  Summary: {article['summary']}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_ranked_stories(path: Path, stories: list[dict]) -> None:
    lines = ["# Ranked Stories", ""]
    ranked = sorted(
        stories,
        key=lambda story: (
            story.get("story_score", story["primary_article"].get("importance_score", 0)),
            story["latest_published"],
        ),
        reverse=True,
    )
    for i, story in enumerate(ranked, 1):
        primary = story["primary_article"]
        pub = story["latest_published"].astimezone(TZ_CST).strftime("%b %d, %H:%M UTC+8")
        topics = ", ".join(primary.get("topics", [])) or "Unclassified"
        lines.append(f"## {i}. {story['canonical_title']}")
        lines.append("")
        lines.append(f"- Story score: `{story.get('story_score', primary.get('importance_score', 0))}`")
        lines.append(f"- Topic: `{topics}`")
        lines.append(f"- Primary: `{primary['source']}`")
        lines.append(f"- Sources: `{', '.join(story['sources'])}`")
        lines.append(f"- Articles: `{story['article_count']}` · Latest: `{pub}`")
        lines.append(f"- Link: {primary['link']}")
        lines.append("")

        components = story.get("story_score_components") or primary.get("importance_score_components", [])
        if components:
            lines.append("Score components:")
            for component in components:
                sign = "+" if component["value"] > 0 else ""
                lines.append(f"- `{sign}{component['value']}` {component['name']}: {component['reason']}")
            lines.append("")

        if story["article_count"] > 1:
            lines.append("Cluster members:")
            for article in sorted(story["articles"], key=lambda a: a["published"], reverse=True):
                lines.append(f"- `{article['source']}` [{article['title']}]({article['link']})")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_telegram_preview(path: Path, topic_order: list[str], by_topic: dict[str, list[dict]]) -> None:
    lines = ["# Telegram Preview", ""]
    for topic in topic_order:
        if topic not in by_topic:
            continue
        articles, omitted = telegram_articles_for_topic(topic, by_topic[topic])
        if not articles:
            continue
        lines.append(f"## {topic}")
        lines.append("")
        if omitted:
            lines.append(f"_Showing top {len(articles)} of {len(by_topic[topic])}; omitted {omitted} lower-ranked articles._")
            lines.append("")
        for message in render_topic_section(topic, articles, total_count=len(by_topic[topic])):
            lines.append("```text")
            lines.append(message)
            lines.append("```")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_telegram_full_preview(
    path: Path,
    header: str,
    executive_summary: str,
    topic_order: list[str],
    by_topic: dict[str, list[dict]],
) -> None:
    lines = ["# Telegram Full Preview", "", "## Header", "", "```text", header, "```", ""]
    if executive_summary:
        lines.extend(["## Executive Takeaways", "", "```text", executive_summary, "```", ""])
    for topic in topic_order:
        if topic not in by_topic:
            continue
        articles, omitted = telegram_articles_for_topic(topic, by_topic[topic])
        if not articles:
            continue
        lines.extend([f"## {topic}", ""])
        if omitted:
            lines.append(f"_Showing top {len(articles)} of {len(by_topic[topic])}; omitted {omitted} lower-ranked articles._")
            lines.append("")
        for message in render_topic_section(topic, articles, total_count=len(by_topic[topic])):
            lines.extend(["```text", message, "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_takeaway_preview(path: Path, executive_summary: str, topic_summaries: dict[str, str]) -> None:
    lines = ["# Takeaway Preview", ""]
    if executive_summary:
        lines.extend(["## Executive", "", executive_summary, ""])
    for topic, summary in topic_summaries.items():
        if not summary:
            continue
        lines.extend([f"## {topic}", "", summary, ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export each digest pipeline stage for review.")
    parser.add_argument("--source", choices=["live", "miniflux"], default="miniflux")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--cluster-threshold", type=float, default=0.3)
    parser.add_argument("--sample-per-source", type=int, default=5)
    parser.add_argument("--with-takeaways", action="store_true", help="Generate LLM takeaway previews")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    stamp = now.astimezone(TZ_CST).strftime("%Y%m%d_%H%M%S")
    run_dir = EXPORT_ROOT / stamp
    latest_dir = EXPORT_ROOT / "latest"
    run_dir.mkdir(parents=True, exist_ok=True)

    raw_articles = collect_articles(source=args.source, hours=args.hours)
    media_count = len([a for a in raw_articles if a.get("input_type") == "media_news"])
    announcement_count = len([a for a in raw_articles if a.get("input_type") == "official_announcement"])
    specialist_count = len([a for a in raw_articles if a.get("input_type") == "specialist_signal"])
    _write_articles(run_dir / "raw.json", raw_articles)

    after_normalize = apply_normalization(raw_articles)
    _write_articles(run_dir / "after_normalize.json", after_normalize)

    after_24h = filter_articles_by_hours(after_normalize, now, hours=args.hours)
    _write_articles(run_dir / "after_24h.json", after_24h)

    after_relevance = apply_relevance_filter(after_24h)
    _write_articles(run_dir / "after_relevance.json", after_relevance)
    _write_articles(run_dir / "relevance_removed.json", _removed(after_24h, after_relevance))

    after_dedup = apply_deduplication(after_relevance)
    _write_articles(run_dir / "after_dedup.json", after_dedup)
    _write_articles(run_dir / "dedup_removed.json", _removed(after_relevance, after_dedup))

    stories = build_story_clusters(after_dedup, threshold=args.cluster_threshold)
    clusters = build_cluster_debug(after_dedup, threshold=args.cluster_threshold)
    _write_json(run_dir / "clusters.json", clusters)

    after_cluster = [story["primary_article"] for story in stories]
    _write_articles(run_dir / "after_cluster.json", after_cluster)
    _write_articles(run_dir / "cluster_removed.json", _removed(after_dedup, after_cluster))

    classify_articles(after_cluster)
    score_articles(after_cluster)
    annotate_story_scores(stories)
    _write_articles(run_dir / "classified.json", after_cluster)
    _write_stories(run_dir / "stories.json", stories)

    by_topic = group_articles_by_topic(after_cluster)
    write_topic_markdown(run_dir / "by_topic.md", by_topic)
    write_ranked_stories(run_dir / "ranked_stories.md", stories)
    priority = ["Portfolio", "Exchange Listings"]
    rest = [topic for topic in by_topic if topic not in priority and topic != "General"]
    topic_order = priority + sorted(rest) + ["General"]
    telegram_visible_articles = []
    seen_telegram_articles = set()
    for topic, articles in by_topic.items():
        visible, _ = telegram_articles_for_topic(topic, articles)
        for article in visible:
            key = article.get("story_id") or article.get("link") or article.get("title")
            if key in seen_telegram_articles:
                continue
            seen_telegram_articles.add(key)
            telegram_visible_articles.append(article)
    localize_articles_for_telegram(telegram_visible_articles)
    write_telegram_preview(run_dir / "telegram_preview.md", topic_order, by_topic)
    if args.with_takeaways:
        executive_summary = summarize_digest(stories)
        topic_summaries = {
            topic: summarize_topic(topic, by_topic[topic])
            for topic in topic_order
            if topic in by_topic
        }
        (run_dir / "executive_takeaways.md").write_text(executive_summary, encoding="utf-8")
        write_takeaway_preview(run_dir / "topic_takeaways.md", executive_summary, topic_summaries)
        header = render_header(now, len(after_cluster), len(set(a["source"] for a in after_cluster)))
        write_telegram_full_preview(run_dir / "telegram_full_preview.md", header, executive_summary, topic_order, by_topic)

    stages = {
        "raw": raw_articles,
        "after_normalize": after_normalize,
        "after_24h": after_24h,
        "after_relevance": after_relevance,
        "after_dedup": after_dedup,
        "after_cluster": after_cluster,
        "classified": after_cluster,
    }
    source_counts = build_source_counts(stages)
    _write_json(run_dir / "source_counts.json", source_counts)
    write_source_inventory(run_dir / "source_inventory.md", stages)
    source_health = build_source_health(stages, hours=args.hours)
    _write_json(run_dir / "source_health.json", source_health)
    write_source_health(run_dir / "source_health.md", source_health)
    write_source_samples(
        run_dir / "source_samples.md",
        "Source Samples",
        raw_articles,
        sample_per_source=args.sample_per_source,
    )
    write_source_samples(
        run_dir / "announcement_samples.md",
        "Announcement Samples",
        raw_articles,
        sample_per_source=args.sample_per_source,
        input_type="official_announcement",
    )

    summary = {
        "exported_at_utc": now.isoformat(),
        "source": args.source,
        "hours": args.hours,
        "cluster_threshold": args.cluster_threshold,
        "sample_per_source": args.sample_per_source,
        "with_takeaways": args.with_takeaways,
        "counts": {
            "media_news": media_count,
            "official_announcement": announcement_count,
            "specialist_signal": specialist_count,
            "raw": len(raw_articles),
            "after_normalize": len(after_normalize),
            "after_24h": len(after_24h),
            "after_relevance": len(after_relevance),
            "relevance_removed": len(after_24h) - len(after_relevance),
            "after_dedup": len(after_dedup),
            "dedup_removed": len(after_relevance) - len(after_dedup),
            "after_cluster": len(after_cluster),
            "cluster_removed": len(after_dedup) - len(after_cluster),
            "classified": len(after_cluster),
        },
        "input_type_counts_after_cluster": dict(Counter(a.get("input_type", "unknown") for a in after_cluster)),
        "source_tier_counts_after_cluster": dict(Counter(a.get("source_tier", "unknown") for a in after_cluster)),
        "source_focus_counts_after_cluster": dict(Counter(a.get("source_focus", "unknown") for a in after_cluster)),
        "quality_action_counts_after_cluster": dict(Counter(a.get("quality_action", "unknown") for a in after_cluster)),
        "quality_reason_counts_after_cluster": dict(Counter(a.get("quality_reason", "unknown") for a in after_cluster)),
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
