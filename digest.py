import hashlib
import re
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import feedparser
import httpx

import json

from config import FEEDS, TOPICS, TOPIC_EMOJI, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, DEEPSEEK_API_KEY

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
# Tag by topic — DeepSeek LLM classification (batch), keyword fallback
# ---------------------------------------------------------------------------

TOPIC_NAMES = list(TOPICS.keys())
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

SYSTEM_PROMPT = f"""You are a crypto venture analyst. Classify each news article into exactly ONE topic from this list:
{chr(10).join(f"- {t}" for t in TOPIC_NAMES)}

Rules:
- Return ONLY a JSON array, one object per article, in the same order as input.
- Each object: {{"id": <number>, "topics": [<single topic name>]}}
- Pick the MOST relevant topic. If truly irrelevant to all, use "General".
- Do not explain anything, return only the JSON array."""


def classify_batch(articles: list[dict]) -> list[list[str]]:
    """Classify a batch of articles via DeepSeek. Returns list of topic lists."""
    items = "\n".join(
        f'{i+1}. Title: {a["title"]}\n   Summary: {a["summary"]}'
        for i, a in enumerate(articles)
    )
    try:
        r = httpx.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": items},
                ],
                "temperature": 0,
                "max_tokens": 1024,
            },
            timeout=30,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown code fences if present
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.MULTILINE).strip()
        results = json.loads(content)
        return [item["topics"] or ["General"] for item in sorted(results, key=lambda x: x["id"])]
    except Exception as e:
        log.warning(f"DeepSeek classification failed: {e} — falling back to keywords")
        return [_keyword_tag(a) for a in articles]


def _keyword_tag(article: dict) -> list[str]:
    text = (article["title"] + " " + article["summary"]).lower()
    matched = [t for t, kws in TOPICS.items() if any(kw in text for kw in kws)]
    return matched or ["General"]


def tag_all_articles(articles: list[dict], batch_size: int = 20) -> None:
    """Classify all articles in batches, assign topics in-place."""
    log.info(f"  Classifying {len(articles)} articles with DeepSeek…")
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        results = classify_batch(batch)
        for article, topics in zip(batch, results):
            article["topics"] = topics
        log.info(f"  Classified {min(i + batch_size, len(articles))}/{len(articles)}")


# ---------------------------------------------------------------------------
# Deduplicate — exact matches
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
# Cluster same-story articles across sources — keep best source
# ---------------------------------------------------------------------------

SOURCE_PRIORITY = ["The Block", "CoinDesk", "Cointelegraph", "Blockworks", "Decrypt", "Investing.com", "Reuters"]
STOPWORDS = {"the","a","an","in","on","at","to","for","of","and","or","is","as","by","with",
             "after","over","from","its","into","that","this","it","are","was","be","has","have"}

def _title_words(title: str) -> set:
    return set(re.sub(r"[^a-z0-9 ]", "", title.lower()).split()) - STOPWORDS

def _jaccard(s1: set, s2: set) -> float:
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)

def cluster_stories(articles: list[dict], threshold: float = 0.3) -> list[dict]:
    """
    Group articles about the same story, keep one per group.
    Within a group, prefer higher-priority sources.
    """
    kept = []
    for article in articles:
        words = _title_words(article["title"])
        matched = None
        for i, existing in enumerate(kept):
            if _jaccard(words, _title_words(existing["title"])) >= threshold:
                matched = i
                break
        if matched is None:
            kept.append(article)
        else:
            # Replace existing if current article is from a higher-priority source
            cur_pri = SOURCE_PRIORITY.index(article["source"]) if article["source"] in SOURCE_PRIORITY else 99
            ex_pri  = SOURCE_PRIORITY.index(kept[matched]["source"]) if kept[matched]["source"] in SOURCE_PRIORITY else 99
            if cur_pri < ex_pri:
                kept[matched] = article
    return kept


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

    # Filter to last 24 hours
    cutoff = now - timedelta(hours=24)
    all_articles = [a for a in all_articles if a["published"] >= cutoff]
    log.info(f"After 24h filter: {len(all_articles)}")

    # Deduplicate exact matches
    all_articles = deduplicate(all_articles)
    log.info(f"After dedup: {len(all_articles)}")

    # Cluster same-story articles across sources
    all_articles = cluster_stories(all_articles)
    log.info(f"After story clustering: {len(all_articles)}")

    # Tag by topic via DeepSeek
    tag_all_articles(all_articles)
    by_topic = defaultdict(list)
    for a in all_articles:
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
