import argparse
import html
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from config import (
    FEEDS,
    MINIFLUX_API_TOKEN,
    MINIFLUX_PASSWORD,
    MINIFLUX_URL,
    MINIFLUX_USERNAME,
)


FEED_NAME_BY_URL = {feed["url"].rstrip("/"): feed["name"] for feed in FEEDS}


def _clean_summary(raw: str, max_chars: int = 200) -> str:
    text = re.sub(r"<[^>]+>", "", html.unescape(raw or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars] + "..." if len(text) > max_chars else text


def _parse_datetime(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class MinifluxClient:
    def __init__(
        self,
        base_url: str = MINIFLUX_URL,
        api_token: str = MINIFLUX_API_TOKEN,
        username: str = MINIFLUX_USERNAME,
        password: str = MINIFLUX_PASSWORD,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.username = username
        self.password = password

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        auth = None
        if self.api_token:
            headers["X-Auth-Token"] = self.api_token
        elif self.username and self.password:
            auth = (self.username, self.password)
        else:
            raise RuntimeError("Configure MINIFLUX_API_TOKEN or MINIFLUX_USERNAME/MINIFLUX_PASSWORD")

        response = httpx.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            auth=auth,
            timeout=30,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def get_feeds(self) -> list[dict]:
        return self._request("GET", "/v1/feeds").json()

    def create_feed(self, feed_url: str) -> int:
        data = self._request("POST", "/v1/feeds", json={"feed_url": feed_url}).json()
        return int(data["feed_id"])

    def ensure_feeds(self, feeds: list[dict] = FEEDS) -> dict[str, str]:
        existing = {feed["feed_url"] for feed in self.get_feeds()}
        results = {}
        for feed in feeds:
            url = feed["url"]
            if url in existing:
                results[url] = "exists"
                continue
            try:
                self.create_feed(url)
                results[url] = "created"
            except httpx.HTTPStatusError as exc:
                results[url] = f"failed: {exc.response.text}"
        return results

    def refresh_all_feeds(self) -> None:
        self._request("PUT", "/v1/feeds/refresh")

    def get_entries_since(self, since: datetime, limit: int = 1000) -> list[dict]:
        entries = []
        offset = 0
        since_ts = int(since.timestamp())
        while True:
            data = self._request(
                "GET",
                "/v1/entries",
                params={
                    "published_after": since_ts,
                    "order": "published_at",
                    "direction": "desc",
                    "limit": limit,
                    "offset": offset,
                },
            ).json()
            batch = data.get("entries", [])
            entries.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return entries


def entries_to_articles(entries: list[dict]) -> list[dict]:
    articles = []
    for entry in entries:
        feed = entry.get("feed") or {}
        feed_url = (feed.get("feed_url") or "").rstrip("/")
        source = FEED_NAME_BY_URL.get(feed_url, feed.get("title") or "Miniflux")
        published = _parse_datetime(entry.get("published_at", ""))
        articles.append({
            "source": source,
            "title": (entry.get("title") or "").strip(),
            "link": entry.get("url") or "",
            "summary": _clean_summary(entry.get("content", "")),
            "published": published,
            "topics": [],
        })
    return articles


def fetch_miniflux_articles(hours: int = 24) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    client = MinifluxClient()
    return entries_to_articles(client.get_entries_since(since))


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Miniflux feeds for crypto-digest.")
    parser.add_argument("--ensure-feeds", action="store_true", help="Create missing FEEDS in Miniflux")
    parser.add_argument("--refresh", action="store_true", help="Ask Miniflux to refresh all feeds")
    parser.add_argument("--check", action="store_true", help="Print feed and 24h entry counts")
    args = parser.parse_args()

    client = MinifluxClient()

    if args.ensure_feeds:
        results = client.ensure_feeds()
        for url, status in results.items():
            print(f"{status}: {url}")

    if args.refresh:
        client.refresh_all_feeds()
        print("Refresh requested.")

    if args.check:
        feeds = client.get_feeds()
        entries = client.get_entries_since(datetime.now(timezone.utc) - timedelta(hours=24))
        print(f"Feeds: {len(feeds)}")
        print(f"Entries in last 24h: {len(entries)}")


if __name__ == "__main__":
    main()
