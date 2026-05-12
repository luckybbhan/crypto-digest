import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from config import TOPICS
from digest import (
    TZ_CST,
    annotate_story_scores,
    apply_deduplication,
    apply_relevance_filter,
    article_rank_score,
    build_story_clusters,
    classify_articles,
    group_articles_by_topic,
    localize_articles_for_telegram,
    render_header,
    render_topic_section,
    score_articles,
    telegram_articles_for_topic,
)


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SNAPSHOT = BASE_DIR / "exports" / "source_snapshots" / "latest" / "articles.json"
DEFAULT_OUTPUT_DIR = BASE_DIR / "exports" / "daily_reviews"


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _load_snapshot(path: Path) -> tuple[dict, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    articles = []
    for row in payload["articles"]:
        articles.append({
            "source": row["source"],
            "source_tier": row.get("source_tier") or "tier_3",
            "source_weight": float(row.get("source_weight") or 1.0),
            "quality_action": row.get("quality_action") or "keep",
            "quality_reason": row.get("quality_reason") or "relevant",
            "title": row["title"],
            "link": row.get("link") or "",
            "summary": row.get("summary") or "",
            "published": _parse_datetime(row["published_utc"]),
            "topics": [],
        })
    return payload, articles


def _article_key(article: dict) -> str:
    return article.get("story_id") or article.get("link") or article.get("title") or ""


def _topic_order() -> list[str]:
    priority = ["Portfolio", "Exchange Listings"]
    rest = [topic for topic in TOPICS.keys() if topic not in priority]
    return priority + rest + ["General"]


def _source_counts(articles: list[dict]) -> dict:
    return dict(Counter(article["source"] for article in articles).most_common())


def _raw_rows(articles: list[dict]) -> list[dict]:
    rows = []
    for index, article in enumerate(sorted(articles, key=lambda item: item["published"], reverse=True), 1):
        rows.append({
            "id": index,
            "source": article["source"],
            "source_tier": article.get("source_tier", ""),
            "quality_action": article.get("quality_action", ""),
            "quality_reason": article.get("quality_reason", ""),
            "published_utc8": article["published"].astimezone(TZ_CST).strftime("%Y-%m-%d %H:%M"),
            "title": article["title"],
            "link": article["link"],
            "summary": article.get("summary", ""),
            "manual_decision": "",
            "manual_note": "",
        })
    return rows


def _selected_rows(by_topic: dict[str, list[dict]]) -> tuple[list[dict], set[str], dict]:
    rows = []
    selected_keys = set()
    visible_topics = {}
    for topic in _topic_order():
        if topic not in by_topic:
            continue
        visible, omitted = telegram_articles_for_topic(topic, by_topic[topic])
        visible_topics[topic] = {"visible": len(visible), "total": len(by_topic[topic]), "omitted": omitted}
        for rank, article in enumerate(visible, 1):
            key = _article_key(article)
            selected_keys.add(key)
            rows.append({
                "topic": topic,
                "rank_in_topic": rank,
                "source": article["source"],
                "source_tier": article.get("source_tier", ""),
                "story_source_count": article.get("story_source_count", 1),
                "supporting_sources": ", ".join(article.get("supporting_sources", [])),
                "score": article_rank_score(article),
                "quality_reason": article.get("quality_reason", ""),
                "published_utc8": article["published"].astimezone(TZ_CST).strftime("%Y-%m-%d %H:%M"),
                "display_title": article.get("display_title") or article["title"],
                "original_title": article["title"],
                "link": article["link"],
                "summary": article.get("display_summary")
                if article.get("display_summary") is not None
                else article.get("story_summary") or article.get("summary", ""),
                "manual_decision": "",
                "manual_note": "",
            })
    return rows, selected_keys, visible_topics


def _omitted_rows(by_topic: dict[str, list[dict]], selected_keys: set[str]) -> list[dict]:
    rows = []
    for topic in _topic_order():
        if topic not in by_topic:
            continue
        sorted_articles = sorted(
            by_topic[topic],
            key=lambda item: (article_rank_score(item), item["published"]),
            reverse=True,
        )
        for article in sorted_articles:
            if _article_key(article) in selected_keys:
                continue
            rows.append({
                "topic": topic,
                "source": article["source"],
                "source_tier": article.get("source_tier", ""),
                "score": article_rank_score(article),
                "quality_action": article.get("quality_action", ""),
                "quality_reason": article.get("quality_reason", ""),
                "published_utc8": article["published"].astimezone(TZ_CST).strftime("%Y-%m-%d %H:%M"),
                "title": article["title"],
                "link": article["link"],
                "manual_decision": "",
                "manual_note": "",
            })
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _escape_cell(value) -> str:
    text = str(value or "").replace("\n", " ").strip()
    text = text.replace("|", "\\|")
    return text


def _write_markdown_table(path: Path, rows: list[dict], title: str, columns: list[str]) -> None:
    lines = [f"# {title}", ""]
    if not rows:
        lines.append("_No rows._")
        path.write_text("\n".join(lines), encoding="utf-8")
        return
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        lines.append("| " + " | ".join(_escape_cell(row.get(column)) for column in columns) + " |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_summary(path: Path, summary: dict) -> None:
    lines = [
        "# Daily Review Summary",
        "",
        f"- Snapshot: `{summary['snapshot']}`",
        f"- Exported at: `{summary['exported_at_utc']}`",
        f"- Raw articles: `{summary['counts']['raw']}`",
        f"- After relevance: `{summary['counts']['after_relevance']}`",
        f"- After dedup: `{summary['counts']['after_dedup']}`",
        f"- After cluster: `{summary['counts']['after_cluster']}`",
        f"- Telegram selected: `{summary['counts']['telegram_selected']}`",
        "",
        "## Raw Source Counts",
        "",
    ]
    for source, count in summary["source_counts_raw"].items():
        lines.append(f"- {source}: {count}")
    lines.extend(["", "## Final Selected Source Counts", ""])
    for source, count in summary["source_counts_selected"].items():
        lines.append(f"- {source}: {count}")
    lines.extend(["", "## Topic Counts", ""])
    for topic, data in summary["visible_topics"].items():
        lines.append(f"- {topic}: selected {data['visible']} / total {data['total']} / omitted {data['omitted']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_telegram_preview(path: Path, snapshot_payload: dict, clustered: list[dict], by_topic: dict[str, list[dict]]) -> None:
    exported_at = _parse_datetime(snapshot_payload["exported_at_utc"])
    source_count = len(set(article["source"] for article in clustered))
    lines = [render_header(exported_at, len(clustered), source_count), ""]
    for topic in _topic_order():
        if topic not in by_topic:
            continue
        visible, _ = telegram_articles_for_topic(topic, by_topic[topic])
        for message in render_topic_section(topic, visible, total_count=len(by_topic[topic])):
            lines.extend([message, ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def export_review(snapshot_path: Path, output_dir: Path) -> dict:
    snapshot_payload, raw_articles = _load_snapshot(snapshot_path)
    after_relevance = apply_relevance_filter(raw_articles)
    kept_after_relevance = {
        ((article.get("link") or "").strip(), (article.get("title") or "").strip())
        for article in after_relevance
    }
    after_dedup = apply_deduplication(after_relevance)
    stories = build_story_clusters(after_dedup)
    clustered = [story["primary_article"] for story in stories]
    classify_articles(clustered)
    score_articles(clustered)
    annotate_story_scores(stories)
    by_topic = group_articles_by_topic(clustered)

    telegram_visible = []
    seen = set()
    for topic, articles in by_topic.items():
        visible, _ = telegram_articles_for_topic(topic, articles)
        for article in visible:
            key = _article_key(article)
            if key in seen:
                continue
            seen.add(key)
            telegram_visible.append(article)
    localize_articles_for_telegram(telegram_visible)

    raw_rows = _raw_rows(raw_articles)
    selected_rows, selected_keys, visible_topics = _selected_rows(by_topic)
    omitted_rows = _omitted_rows(by_topic, selected_keys)
    removed_rows = [
        row for row in raw_rows
        if ((row["link"] or "").strip(), (row["title"] or "").strip()) not in kept_after_relevance
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "01_raw_sources.csv", raw_rows)
    _write_csv(output_dir / "02_final_selected.csv", selected_rows)
    _write_csv(output_dir / "03_omitted_after_processing.csv", omitted_rows)
    _write_csv(output_dir / "04_removed_by_relevance.csv", removed_rows)

    _write_markdown_table(
        output_dir / "01_raw_sources.md",
        raw_rows,
        "Raw Source Titles",
        ["id", "source", "quality_reason", "published_utc8", "title", "link", "manual_decision", "manual_note"],
    )
    _write_markdown_table(
        output_dir / "02_final_selected.md",
        selected_rows,
        "Final Telegram Selected Output",
        ["topic", "rank_in_topic", "source", "score", "published_utc8", "display_title", "link", "manual_decision", "manual_note"],
    )
    _write_markdown_table(
        output_dir / "03_omitted_after_processing.md",
        omitted_rows,
        "Processed But Not Sent To Telegram",
        ["topic", "source", "score", "quality_reason", "published_utc8", "title", "link", "manual_decision", "manual_note"],
    )
    _write_markdown_table(
        output_dir / "04_removed_by_relevance.md",
        removed_rows,
        "Removed By Relevance Filter",
        ["id", "source", "quality_reason", "published_utc8", "title", "link", "manual_decision", "manual_note"],
    )
    _write_telegram_preview(output_dir / "telegram_selected_preview.md", snapshot_payload, clustered, by_topic)

    summary = {
        "snapshot": str(snapshot_path),
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "raw": len(raw_articles),
            "after_relevance": len(after_relevance),
            "after_dedup": len(after_dedup),
            "after_cluster": len(clustered),
            "telegram_selected": len(selected_rows),
            "omitted_after_processing": len(omitted_rows),
            "removed_by_relevance": len(removed_rows),
        },
        "source_counts_raw": _source_counts(raw_articles),
        "source_counts_after_cluster": _source_counts(clustered),
        "source_counts_selected": dict(Counter(row["source"] for row in selected_rows).most_common()),
        "visible_topics": visible_topics,
        "output_dir": str(output_dir),
    }
    _write_summary(output_dir / "README.md", summary)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Export raw and final digest review tables for human calibration.")
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot).resolve()
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        run_name = snapshot_path.parent.name if snapshot_path.parent.name != "latest" else datetime.now(TZ_CST).strftime("%Y%m%d_%H%M")
        output_dir = DEFAULT_OUTPUT_DIR / run_name
    summary = export_review(snapshot_path, output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
