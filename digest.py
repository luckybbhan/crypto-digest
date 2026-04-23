import argparse
import hashlib
import json
import os
import re
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TZ_CST = timezone(timedelta(hours=8))
from html.parser import HTMLParser

import feedparser
import httpx

from config import FEEDS, TOPICS, TOPIC_EMOJI, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, DEEPSEEK_API_KEY, TELEGRAM_GROUP_ID, TOPIC_THREAD_IDS, TEST_GROUP_ID, TELEGRAPH_TOKEN
from miniflux_client import fetch_miniflux_articles

# Portfolio company names for the system prompt context
PORTFOLIO_NAMES = [
    "Mavrick", "Cetus", "Ola", "Gravity", "Polyhedra", "Redbrick", "BBox", "Apriori",
    "Ethena", "Cyber Games Arena", "Solv", "Movement", "Sidekick", "Hologram AI",
    "Le Poker", "GAIB", "Tonark", "Sonic", "Sonex", "GTE", "Haedal", "Kaiju", "YB",
    "Gamer Boom", "CAP", "Perena", "Aspecta", "RateX", "Nunchi", "Noise", "Turtle",
    "EchoX", "Spout", "Stormbit",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(BASE_DIR, "logs", "digest.log")),
    ],
)
log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
BINANCE_API  = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
BINANCE_URL  = "https://www.binance.com/en/support/announcement/"
OKX_URL      = "https://www.okx.com/en-us/help/section/announcements-new-listings"
BYBIT_API    = "https://api.bybit.com/v5/announcements/index"


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_binance() -> list[dict]:
    """Fetch Binance new listing announcements via their internal API."""
    try:
        r = httpx.get(
            BINANCE_API,
            params={"type": 1, "pageNo": 1, "pageSize": 20, "catalogId": 48},
            headers=HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        articles_raw = r.json()["data"]["catalogs"][0]["articles"]
        articles = []
        for a in articles_raw:
            ts = a.get("releaseDate", 0) / 1000  # ms → seconds
            published = datetime.fromtimestamp(ts, tz=timezone.utc)
            articles.append({
                "source":    "Binance",
                "title":     a.get("title", "").strip(),
                "link":      f"{BINANCE_URL}{a.get('code', '')}",
                "summary":   "",
                "published": published,
                "topics":    [],
            })
        return articles
    except Exception as e:
        log.warning(f"Failed to fetch Binance: {e}")
        return []


def fetch_okx() -> list[dict]:
    """Fetch OKX global new listing announcements (en-us help center page)."""
    try:
        r = httpx.get(OKX_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
        # Extract embedded JSON from <script id="appState">
        start = r.text.find('id="appState">') + len('id="appState">')
        end = r.text.find("</script>", start)
        data = json.loads(r.text[start:end])
        article_list = data["appContext"]["initialProps"]["sectionData"]["articleList"]["list"]
        articles = []
        for a in article_list:
            ts = a.get("publishTime", 0) / 1000
            published = datetime.fromtimestamp(ts, tz=timezone.utc)
            slug = a.get("slug", "")
            articles.append({
                "source":    "OKX",
                "title":     a.get("title", "").strip(),
                "link":      f"https://www.okx.com/en-us/help/{slug}",
                "summary":   "",
                "published": published,
                "topics":    [],
            })
        return articles
    except Exception as e:
        log.warning(f"Failed to fetch OKX: {e}")
        return []


def fetch_bybit() -> list[dict]:
    """Fetch Bybit new listing announcements."""
    try:
        r = httpx.get(
            BYBIT_API,
            params={"locale": "en-US", "type": "new_crypto", "page": 1, "limit": 20},
            headers=HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        items = r.json()["result"]["list"]
        articles = []
        for a in items:
            ts = a.get("publishTime", 0) / 1000
            published = datetime.fromtimestamp(ts, tz=timezone.utc)
            articles.append({
                "source":    "Bybit",
                "title":     a.get("title", "").strip(),
                "link":      a.get("url", "https://announcements.bybit.com"),
                "summary":   a.get("description", ""),
                "published": published,
                "topics":    [],
            })
        return articles
    except Exception as e:
        log.warning(f"Failed to fetch Bybit: {e}")
        return []


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

Portfolio companies (ONLY classify as "Portfolio" if the article explicitly names one of these companies):
{", ".join(PORTFOLIO_NAMES)}

Rules:
- Return ONLY a JSON array, one object per article, in the same order as input.
- Each object: {{"id": <number>, "topics": [<single topic name>]}}
- Pick the MOST relevant topic.
- Use "Portfolio" ONLY if the article explicitly mentions one of the listed portfolio company names above. Do NOT use "Portfolio" for any other company.
- Use "Exchange Listings" for new token listing announcements on major exchanges.
- If truly irrelevant to all, use "General".
- Do not explain anything, return only the JSON array."""


def classify_batch(articles: list[dict]) -> list[list[str]]:
    """Classify a batch of articles via DeepSeek. Returns list of topic lists."""
    if not DEEPSEEK_API_KEY:
        log.warning("DEEPSEEK_API_KEY not configured — falling back to keyword classification")
        return [_keyword_tag(a) for a in articles]

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

SOURCE_PRIORITY = ["The Block", "CoinDesk", "Cointelegraph", "Blockworks", "The Defiant", "Decrypt", "Forkast", "CryptoSlate", "Wu Blockchain", "PANews", "Investing.com"]
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
# Summarise a topic's articles via DeepSeek
# ---------------------------------------------------------------------------

def summarize_topic(topic: str, articles: list[dict]) -> str:
    """Return a short bullet-point summary of the key takeaways for a topic."""
    if not DEEPSEEK_API_KEY:
        log.warning(f"DEEPSEEK_API_KEY not configured — skipping summary for {topic}")
        return ""

    items = "\n".join(
        f"- {a['title']}: {a['summary']}" for a in articles
    )
    prompt = (
        f"Summarise the {topic} news below in 3-5 bullet points.\n"
        f"Rules:\n"
        f"- State only facts — what happened, who did what, what amount\n"
        f"- No analysis, no opinion, no commentary\n"
        f"- Each bullet: one line, max 15 words\n"
        f"- Start each with a bold keyword e.g. *Monad:* or *Binance:*\n"
        f"- Use plain bullet character •\n\n"
        f"{items}"
    )
    try:
        r = httpx.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 400,
            },
            timeout=30,
        )
        r.raise_for_status()
        summary = r.json()["choices"][0]["message"]["content"].strip()
        bullets = "\n\n".join(line for line in summary.splitlines() if line.strip())
        return f"─────────────\n📝 *Key Takeaways*\n\n{bullets}"
    except Exception as e:
        log.warning(f"Summary failed for {topic}: {e}")
        return ""


# ---------------------------------------------------------------------------
# Render Telegram messages
# ---------------------------------------------------------------------------

def _escape(text: str) -> str:
    """Escape special chars for Telegram Markdown (legacy mode)."""
    return re.sub(r"([_*`\[])", r"\\\1", text)


def render_header(now: datetime, total: int, sources: int) -> str:
    now_cst = now.astimezone(TZ_CST)
    date_str = now_cst.strftime("%b %d, %Y")
    time_str = now_cst.strftime("%H:%M UTC+8")
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
    header = f"{emoji} *{_escape(topic)}*  ({len(articles)} articles)\n"

    messages = []
    current = header

    for a in sorted(articles, key=lambda x: x["published"], reverse=True):
        pub = a["published"].astimezone(TZ_CST).strftime("%b %d, %H:%M UTC+8")
        source = _escape(a["source"])
        title = _escape(a["title"])
        summary = _escape(a["summary"]) if a["summary"] else "_No summary_"
        link = a["link"]

        block = f"\n[{title}]({link})\n_{source} · {pub}_\n{summary}\n"

        if len(current) + len(block) > 4000:
            messages.append(current)
            current = f"{emoji} *{_escape(topic)}* (cont.)\n" + block
        else:
            current += block

    if current.strip():
        messages.append(current)

    return messages


# ---------------------------------------------------------------------------
# Post to Telegram
# ---------------------------------------------------------------------------

def post_telegram(
    text: str,
    thread_id: int = None,
    chat_id: str = None,
    retries: int = 3,
    dry_run: bool = False,
) -> bool:
    if dry_run:
        preview = text.replace("\n", " ")[:180]
        log.info(f"[dry-run] Telegram → chat {chat_id or TELEGRAM_GROUP_ID}, thread {thread_id or 'none'}: {preview}")
        return True

    if not TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN not configured — cannot post to Telegram")
        return False

    for attempt in range(retries):
        try:
            payload = {
                "chat_id":    chat_id or TELEGRAM_GROUP_ID,
                "text":       text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }
            if thread_id:
                payload["message_thread_id"] = thread_id
            r = httpx.post(
                f"{TELEGRAM_API}/sendMessage",
                json=payload,
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
# Telegraph
# ---------------------------------------------------------------------------

TELEGRAPH_API = "https://api.telegra.ph"

VOID_TAGS = {"br", "hr", "img"}


class _NodeBuilder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = []
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag}
        allowed_attrs = {k: v for k, v in attrs if k in ("href", "src")}
        if allowed_attrs:
            node["attrs"] = allowed_attrs
        if tag not in VOID_TAGS:
            node["children"] = []
            self.stack[-1].append(node)
            self.stack.append(node["children"])
        else:
            self.stack[-1].append(node)

    def handle_endtag(self, tag):
        if tag not in VOID_TAGS:
            self.stack.pop()

    def handle_data(self, data):
        if data:
            self.stack[-1].append(data)


def _html_to_nodes(html: str) -> list:
    builder = _NodeBuilder()
    builder.feed(html)
    return _clean_nodes(builder.root)


def _clean_nodes(nodes: list) -> list:
    result = []
    for node in nodes:
        if isinstance(node, str):
            if node.strip():
                result.append(node)
        elif isinstance(node, dict):
            cleaned = {"tag": node["tag"]}
            if node.get("attrs"):
                cleaned["attrs"] = node["attrs"]
            children = _clean_nodes(node.get("children", []))
            if children:
                cleaned["children"] = children
            result.append(cleaned)
    return result


def get_telegraph_token() -> str:
    if TELEGRAPH_TOKEN:
        return TELEGRAPH_TOKEN
    r = httpx.post(f"{TELEGRAPH_API}/createAccount", json={
        "short_name": "CryptoDigest",
        "author_name": "2Square Capital",
    }, timeout=15)
    token = r.json()["result"]["access_token"]
    log.info(f"Created Telegraph token: {token}")
    log.info("Save this to config.py as TELEGRAPH_TOKEN to reuse your account")
    return token


def _build_topic_html(topic: str, articles: list, summaries: dict) -> str:
    emoji = TOPIC_EMOJI.get(topic, "📌")
    html = f"<h3>{emoji} {topic} ({len(articles)})</h3>"
    for a in sorted(articles, key=lambda x: x["published"], reverse=True):
        pub = a["published"].astimezone(TZ_CST).strftime("%b %d, %H:%M UTC+8")
        summary = a["summary"] if a["summary"] else ""
        html += f'<p><a href="{a["link"]}"><strong>{a["title"]}</strong></a><br><em>{a["source"]} · {pub}</em>'
        if summary:
            html += f"<br>{summary}"
        html += "</p>"
    if topic in summaries:
        bullets = re.sub(r"^─+\n📝 \*Key Takeaways\*\n\n", "", summaries[topic]).strip()
        html += f"<blockquote>{bullets.replace(chr(10), '<br>')}</blockquote>"
    html += "<hr>"
    return html


def publish_telegraph_pages(by_topic: dict, topic_order: list, summaries: dict, now: datetime, token: str) -> list[str]:
    """Pack topics into Telegraph pages (under 64KB JSON), return list of URLs."""
    MAX_BYTES = 60_000  # measured on JSON-serialized nodes
    date_str = now.strftime("%b %d, %Y")
    time_str = now.astimezone(TZ_CST).strftime("%H:%M UTC+8")
    n_sources = len(set(a["source"] for t in by_topic.values() for a in t))
    n_articles = sum(len(v) for v in by_topic.values())
    header_nodes = _html_to_nodes(f"<p><em>{n_sources} sources · {n_articles} articles · {time_str}</em></p>")

    pages_nodes = []
    current_nodes = list(header_nodes)

    for topic in topic_order:
        if topic not in by_topic:
            continue
        chunk_nodes = _html_to_nodes(_build_topic_html(topic, by_topic[topic], summaries))
        candidate = current_nodes + chunk_nodes
        # Use ensure_ascii=True to match actual HTTP payload size
        if len(json.dumps(candidate).encode("utf-8")) > MAX_BYTES and len(current_nodes) > len(header_nodes):
            pages_nodes.append(current_nodes)
            current_nodes = list(header_nodes) + chunk_nodes
        else:
            current_nodes = candidate

    if len(current_nodes) > len(header_nodes):
        pages_nodes.append(current_nodes)

    total = len(pages_nodes)
    urls = []
    for i, nodes in enumerate(pages_nodes):
        title = f"Crypto Daily Digest — {date_str}" + (f" ({i+1}/{total})" if total > 1 else "")
        # Serialize with ensure_ascii=False to keep emoji compact, reducing actual payload size
        body = json.dumps({"access_token": token, "title": title, "content": nodes, "return_content": False}, ensure_ascii=False).encode("utf-8")
        r = httpx.post(f"{TELEGRAPH_API}/createPage", content=body, headers={"Content-Type": "application/json"}, timeout=30)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegraph error: {data.get('error')}")
        urls.append(data["result"]["url"])
        log.info(f"Telegraph page {i+1}/{total}: {urls[-1]}")

    return urls


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def fetch_live_articles() -> list[dict]:
    all_articles = []
    for feed in FEEDS:
        log.info(f"  Fetching {feed['name']}…")
        articles = fetch_feed(feed)
        log.info(f"    → {len(articles)} articles")
        all_articles.extend(articles)
    return all_articles


def fetch_exchange_articles() -> list[dict]:
    all_articles = []

    log.info("  Fetching Binance announcements…")
    binance = fetch_binance()
    log.info(f"    → {len(binance)} announcements")
    all_articles.extend(binance)

    log.info("  Fetching OKX announcements…")
    okx = fetch_okx()
    log.info(f"    → {len(okx)} announcements")
    all_articles.extend(okx)

    log.info("  Fetching Bybit announcements…")
    bybit = fetch_bybit()
    log.info(f"    → {len(bybit)} announcements")
    all_articles.extend(bybit)

    return all_articles


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", action="store_true", help="Send to production group")
    parser.add_argument("--telegraph", action="store_true", help="Publish to Telegraph and post link")
    parser.add_argument("--dry-run", action="store_true", help="Preview target/messages without posting")
    parser.add_argument(
        "--source",
        choices=["live", "miniflux"],
        default="live",
        help="Use live RSS fetches or Miniflux history for RSS articles",
    )
    args = parser.parse_args()

    target_group = TELEGRAM_GROUP_ID if args.prod else TEST_GROUP_ID
    log.info(f"Target: {'PROD' if args.prod else 'TEST'} group ({target_group})")

    now = datetime.now(timezone.utc)
    log.info(f"Starting digest — {now.astimezone(TZ_CST).strftime('%Y-%m-%d %H:%M UTC+8')}")

    all_articles = []
    if args.source == "miniflux":
        log.info("  Fetching RSS articles from Miniflux history…")
        rss_articles = fetch_miniflux_articles(hours=24)
        log.info(f"    → {len(rss_articles)} RSS articles")
        all_articles.extend(rss_articles)
    else:
        all_articles.extend(fetch_live_articles())

    all_articles.extend(fetch_exchange_articles())

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
    source_count = len(set(a["source"] for a in all_articles))

    # Tag by topic via DeepSeek
    tag_all_articles(all_articles)
    by_topic = defaultdict(list)
    for a in all_articles:
        for t in a["topics"]:
            by_topic[t].append(a)

    # Post to Telegram
    if not TELEGRAM_BOT_TOKEN and not args.dry_run:
        log.warning("Telegram not configured — printing to stdout instead")
        print(render_header(now, len(all_articles), source_count))
        for topic, articles in by_topic.items():
            for msg in render_topic_section(topic, articles):
                print("\n" + "─" * 60)
                print(msg)
        return

    priority = ["Portfolio", "Exchange Listings"]
    rest = [t for t in TOPICS.keys() if t not in priority]
    topic_order = priority + rest + ["General"]

    if args.telegraph:
        # Generate all summaries first, then publish one Telegraph page
        log.info("Generating summaries for Telegraph page…")
        summaries = {}
        for topic in topic_order:
            if topic not in by_topic:
                continue
            summaries[topic] = summarize_topic(topic, by_topic[topic])
            log.info(f"  Summary done: {topic}")

        if args.dry_run:
            urls = ["https://telegra.ph/dry-run-preview"]
            log.info("[dry-run] Skipping Telegraph publish")
        else:
            token = get_telegraph_token()
            urls = publish_telegraph_pages(by_topic, topic_order, summaries, now, token)

        header = render_header(now, len(all_articles), source_count)
        if len(urls) == 1:
            links = f"📖 [Read full digest]({urls[0]})"
        else:
            links = "\n".join(f"📖 [Part {i+1}]({u})" for i, u in enumerate(urls))
        post_telegram(f"{header}\n\n{links}", chat_id=target_group, dry_run=args.dry_run)
        log.info("Done.")
        return

    # Default: send raw messages to Telegram
    header = render_header(now, len(all_articles), source_count)
    post_telegram(header, chat_id=target_group, dry_run=args.dry_run)
    if not args.dry_run:
        time.sleep(2)

    for topic in topic_order:
        if topic not in by_topic:
            continue
        thread_id = TOPIC_THREAD_IDS.get(topic) if args.prod else None
        for msg in render_topic_section(topic, by_topic[topic]):
            success = post_telegram(msg, thread_id=thread_id, chat_id=target_group, dry_run=args.dry_run)
            if success:
                log.info(f"  Posted: {topic} → thread {thread_id or 'General'}")
            if not args.dry_run:
                time.sleep(2)
        summary = summarize_topic(topic, by_topic[topic])
        if summary:
            post_telegram(summary, thread_id=thread_id, chat_id=target_group, dry_run=args.dry_run)
            log.info(f"  Summary posted: {topic}")
            if not args.dry_run:
                time.sleep(2)

    log.info("Done.")


if __name__ == "__main__":
    main()
