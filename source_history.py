import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config import SOURCE_HISTORY_DB


BASE_DIR = Path(__file__).resolve().parent


def history_db_path(path: Optional[str] = None) -> Path:
    raw_path = Path(path or SOURCE_HISTORY_DB)
    if raw_path.is_absolute():
        return raw_path
    return BASE_DIR / raw_path


def connect(path: Optional[str] = None) -> sqlite3.Connection:
    db_path = history_db_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_articles (
            item_key TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            summary TEXT NOT NULL,
            published_utc TEXT NOT NULL,
            first_seen_utc TEXT NOT NULL,
            last_seen_utc TEXT NOT NULL,
            raw_json TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source_articles_published ON source_articles(published_utc)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source_articles_source ON source_articles(source)")
    conn.commit()


def _published_utc(article: dict) -> datetime:
    published = article.get("published")
    if isinstance(published, datetime):
        return published.astimezone(timezone.utc)
    if isinstance(published, str):
        return datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _item_key(article: dict) -> str:
    source = (article.get("source") or "").strip().lower()
    identity = (article.get("link") or article.get("title") or "").strip().lower()
    normalized = f"{source}|{identity}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _article_payload(article: dict) -> dict:
    payload = dict(article)
    published = _published_utc(article)
    payload["published"] = published.isoformat()
    return payload


def upsert_articles(articles: list[dict], path: Optional[str] = None) -> dict:
    conn = connect(path)
    init_db(conn)
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    updated = 0

    for article in articles:
        key = _item_key(article)
        published = _published_utc(article).isoformat()
        payload = _article_payload(article)
        existing = conn.execute("SELECT item_key FROM source_articles WHERE item_key = ?", (key,)).fetchone()
        if existing:
            updated += 1
            conn.execute(
                """
                UPDATE source_articles
                SET title = ?, link = ?, summary = ?, published_utc = ?, last_seen_utc = ?, raw_json = ?
                WHERE item_key = ?
                """,
                (
                    (article.get("title") or "").strip(),
                    (article.get("link") or "").strip(),
                    (article.get("summary") or "").strip(),
                    published,
                    now,
                    json.dumps(payload, ensure_ascii=False),
                    key,
                ),
            )
        else:
            inserted += 1
            conn.execute(
                """
                INSERT INTO source_articles (
                    item_key, source, title, link, summary, published_utc,
                    first_seen_utc, last_seen_utc, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    (article.get("source") or "").strip(),
                    (article.get("title") or "").strip(),
                    (article.get("link") or "").strip(),
                    (article.get("summary") or "").strip(),
                    published,
                    now,
                    now,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    conn.commit()
    return {"inserted": inserted, "updated": updated, "total": len(articles)}


def rows_to_articles(rows: list[sqlite3.Row]) -> list[dict]:
    articles = []
    for row in rows:
        articles.append({
            "source": row["source"],
            "title": row["title"],
            "link": row["link"],
            "summary": row["summary"],
            "published": datetime.fromisoformat(row["published_utc"]).astimezone(timezone.utc),
            "topics": [],
        })
    return articles


def get_articles_since(since: datetime, sources: Optional[list[str]] = None, path: Optional[str] = None) -> list[dict]:
    conn = connect(path)
    init_db(conn)
    since_utc = since.astimezone(timezone.utc).isoformat()
    params: list = [since_utc]
    source_clause = ""
    if sources:
        placeholders = ", ".join("?" for _ in sources)
        source_clause = f" AND source IN ({placeholders})"
        params.extend(sources)

    rows = conn.execute(
        f"""
        SELECT source, title, link, summary, published_utc
        FROM source_articles
        WHERE published_utc >= ?{source_clause}
        ORDER BY published_utc DESC
        """,
        params,
    ).fetchall()
    return rows_to_articles(rows)


def get_articles_for_hours(hours: int = 24, sources: Optional[list[str]] = None, path: Optional[str] = None) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    return get_articles_since(since, sources=sources, path=path)


def prune_older_than(days: int, path: Optional[str] = None) -> int:
    conn = connect(path)
    init_db(conn)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cursor = conn.execute("DELETE FROM source_articles WHERE published_utc < ?", (cutoff.isoformat(),))
    conn.commit()
    return int(cursor.rowcount)


def source_counts(hours: int = 24, path: Optional[str] = None) -> dict[str, int]:
    articles = get_articles_for_hours(hours=hours, path=path)
    return dict(Counter(article["source"] for article in articles))


def source_status(hours: int = 24, path: Optional[str] = None) -> dict[str, dict]:
    conn = connect(path)
    init_db(conn)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = conn.execute(
        """
        SELECT
            source,
            COUNT(*) AS total_seen,
            SUM(CASE WHEN published_utc >= ? THEN 1 ELSE 0 END) AS recent_count,
            MAX(published_utc) AS latest_published_utc,
            MAX(last_seen_utc) AS last_seen_utc
        FROM source_articles
        GROUP BY source
        ORDER BY source
        """,
        (cutoff.isoformat(),),
    ).fetchall()
    return {
        row["source"]: {
            "total_seen": int(row["total_seen"] or 0),
            "recent_count": int(row["recent_count"] or 0),
            "latest_published_utc": row["latest_published_utc"],
            "last_seen_utc": row["last_seen_utc"],
        }
        for row in rows
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect local non-RSS source history.")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--prune-days", type=int)
    parser.add_argument("--db", default=None)
    args = parser.parse_args()

    if args.prune_days is not None:
        deleted = prune_older_than(args.prune_days, path=args.db)
        print(f"Pruned {deleted} rows older than {args.prune_days} days.")

    counts = source_counts(hours=args.hours, path=args.db)
    status = source_status(hours=args.hours, path=args.db)
    total = sum(counts.values())
    print(f"DB: {history_db_path(args.db)}")
    print(f"Articles in last {args.hours}h: {total}")
    for source, count in sorted(counts.items()):
        last_seen = status.get(source, {}).get("last_seen_utc") or "unknown"
        print(f"{source}: {count} recent, last_seen={last_seen}")


if __name__ == "__main__":
    main()
