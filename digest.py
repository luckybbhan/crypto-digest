import hashlib
import re
import time
import logging
from collections import defaultdict
from datetime import datetime, timezone

import feedparser
import httpx

from config import FEEDS, TOPICS, TOPIC_EMOJI, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/digest.log"),
    ],
)
log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_feed(feed: dict) -> list[dict]:
    try:
        r = httpx.get(feed["url"], timeout=15, follow_redirects=True, headers=HEADERS)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"Failed to fetch {feed['name']}: {e}")
        return []

    parsed = feedparser.parse(r.text)
    articles = []
    for entry in parsed.entries:
        articles.append({
            "source":    feed["name"],
            "title":     entry.get("title", "").strip(),
            "link":      entry.get("link", ""),
            "summary":   _clean_summary(entry.get("summary", "")),
            "published": _parse_date(entry),
            "topics":    [],
        })
    return articles


def _clean_summary(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:200] + "…" if len(text) > 200 else text


def _parse_date(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Tag by topic
# ---------------------------------------------------------------------------

def tag_article(article: dict) -> list[str]:
    text = (article["title"] + " " + article["summary"]).lower()
    matched = [
        topic for topic, keywords in TOPICS.items()
        if any(kw in text for kw in keywords)
    ]
    return matched or ["General"]


# ---------------------------------------------------------------------------
# Deduplicate
# ---------------------------------------------------------------------------

def deduplicate(articles: list[dict]) -> list[dict]:
    seen_urls, seen_titles, unique = set(), set(), []
    for a in articles:
        url_key   = a["link"].rstrip("/").lower()
        title_key = hashlib.md5(
            re.sub(r"[^a-z0-9]", "", a["title"].lower()).encode()
        ).hexdigest()
        if url_key in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        unique.append(a)
    return unique


# ---------------------------------------------------------------------------
# Render Telegram messages
# ---------------------------------------------------------------------------

def _escape(text: str) -> str:
    """Escape special chars for Telegram MarkdownV2."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", text)


def render_header(now: datetime, total: int, sources: int) -> str:
    date_str = _escape(now.strftime("%b %d, %Y"))
    time_str = _escape(now.strftime("%H:%M UTC"))
    return (
        f"📰 *Crypto Daily Digest — {date_str}*\n"
        f"_{sources} sources · {total} articles · {time_str}_"
    )


def render_topic_section(topic: str, articles: list[dict]) -> list[str]:
    """
    Returns a list of message strings for this topic.
    Each string is ≤4096 chars (Telegram's limit).
    """
    emoji = TOPIC_EMOJI.get(topic, "📌")
    header = f"{emoji} *{_escape(topic)}*  \\({len(articles)} articles\\)\n"

    messages = []
    current = header

    for a in sorted(articles, key=lambda x: x["published"], reverse=True):
        pub = _escape(a["published"].strftime("%b %d, %H:%M UTC"))
        source = _escape(a["source"])
        title = _escape(a["title"])
        summary = _escape(a["summary"]) if a["summary"] else "_No summary_"
        link = a["link"]

        block = f"\n[{title}]({link})\n_{source} · {pub}_\n{summary}\n"

        if len(current) + len(block) > 4000:
            messages.append(current)
            current = f"{emoji} *{_escape(topic)}* \\(cont\\.\\)\n" + block
        else:
            current += block

    if current.strip():
        messages.append(current)

    return messages


# ---------------------------------------------------------------------------
# Post to Telegram
# ---------------------------------------------------------------------------

def post_telegram(text: str, retries: int = 3) -> bool:
    for attempt in range(retries):
        try:
            r = httpx.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id":    TELEGRAM_CHANNEL_ID,
                    "text":       text,
                    "parse_mode": "MarkdownV2",
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            if r.status_code == 429:
                retry_after = r.json().get("parameters", {}).get("retry_after", 10)
                log.warning(f"Rate limited — waiting {retry_after}s")
                time.sleep(retry_after)
                continue
            r.raise_for_status()
            return True
        except Exception as e:
            log.error(f"Telegram post failed (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                time.sleep(5)
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    now = datetime.now(timezone.utc)
    log.info(f"Starting digest — {now.strftime('%Y-%m-%d %H:%M UTC')}")

    # Fetch all feeds
    all_articles = []
    for feed in FEEDS:
        log.info(f"  Fetching {feed['name']}…")
        articles = fetch_feed(feed)
        log.info(f"    → {len(articles)} articles")
        all_articles.extend(articles)

    log.info(f"Total fetched: {len(all_articles)}")

    # Deduplicate
    all_articles = deduplicate(all_articles)
    log.info(f"After dedup: {len(all_articles)}")

    # Tag by topic
    by_topic = defaultdict(list)
    for a in all_articles:
        a["topics"] = tag_article(a)
        for t in a["topics"]:
            by_topic[t].append(a)

    # Post to Telegram
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN":
        log.warning("Telegram not configured — printing to stdout instead")
        print(render_header(now, len(all_articles), len(FEEDS)))
        for topic, articles in by_topic.items():
            for msg in render_topic_section(topic, articles):
                print("\n" + "─" * 60)
                print(msg)
        return

    # Send header
    header = render_header(now, len(all_articles), len(FEEDS))
    post_telegram(header)
    time.sleep(2)

    # Send one section per topic (ordered)
    topic_order = list(TOPICS.keys()) + ["General"]
    for topic in topic_order:
        if topic not in by_topic:
            continue
        for msg in render_topic_section(topic, by_topic[topic]):
            success = post_telegram(msg)
            if success:
                log.info(f"  Posted: {topic}")
            time.sleep(2)  # avoid Telegram rate limits

    log.info("Done.")


if __name__ == "__main__":
    main()
