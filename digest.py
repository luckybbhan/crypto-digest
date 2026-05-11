import argparse
import base64
import hashlib
import json
import os
import re
import time
import logging
import unicodedata
import zlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

TZ_CST = timezone(timedelta(hours=8))
from html.parser import HTMLParser

import feedparser
import httpx

from config import (
    DEEPSEEK_API_KEY,
    DEFAULT_SOURCE_METADATA,
    ENABLE_FORESIGHT_API,
    FEEDS,
    FORESIGHT_API_LIMIT,
    SOURCE_METADATA,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID,
    TELEGRAM_DEFAULT_TOPIC_LIMIT,
    TELEGRAM_GROUP_ID,
    TELEGRAM_TOPIC_LIMITS,
    TELEGRAPH_TOKEN,
    TEST_GROUP_ID,
    TOPIC_EMOJI,
    TOPIC_TELEGRAM_ROUTE,
    TOPIC_THREAD_IDS,
    TOPICS,
)
from miniflux_client import fetch_miniflux_articles
from source_history import get_articles_for_hours as fetch_history_articles

# Portfolio company names for the system prompt context
PORTFOLIO_NAMES = [
    "Mavrick", "Cetus", "Ola", "Gravity", "Polyhedra", "Redbrick", "BBox", "Apriori",
    "Ethena", "Cyber Games Arena", "Solv", "Movement", "Sidekick", "Hologram AI",
    "Le Poker", "GAIB", "Tonark", "Sonic", "Sonex", "GTE", "Haedal", "Kaiju", "YB",
    "Gamer Boom", "CAP", "Perena", "Aspecta", "RateX", "Nunchi", "Noise", "Turtle",
    "EchoX", "Spout", "Stormbit",
]

GENERIC_PORTFOLIO_TERMS = {
    "cap",
    "gravity",
    "movement",
    "noise",
    "ola",
    "sonic",
    "yb",
}

TOPIC_SCORE_WEIGHTS = {
    "Security & Exploits": 1,
    "Regulatory & Policy": 2,
    "Deal Flow & Funding": 2,
    "Exchange Listings": 2,
    "RWA & Institutional": 1,
    "Stablecoins & Payments": 1,
    "Market Structure": 1,
    "Infrastructure & Tech": 1,
    "DeFi & New Primitives": 1,
    "Governance & Protocol Updates": 1,
    "Macro & Market": 0,
    "Emerging Narratives": 0,
    "Portfolio": 0,
    "General": -1,
}

SOURCE_TIER_SCORE_WEIGHTS = {
    "tier_1": 3,
    "tier_2": 1,
    "tier_3": -1,
    "fallback": -2,
}

TELEGRAM_SUPPLEMENTAL_SOURCES = {
    "Odaily Newsflash",
    "Odaily Articles",
    "PANews",
    "ChainCatcher",
    "TechFlow",
}
TELEGRAM_SUPPLEMENTAL_TOPIC_CAP = 0

TOPIC_DISPLAY_NAME = {
    "Portfolio": "投资组合",
    "Exchange Listings": "交易所上线",
    "Deal Flow & Funding": "融资与交易",
    "Infrastructure & Tech": "基础设施与技术",
    "Security & Exploits": "安全事件",
    "Stablecoins & Payments": "稳定币与支付",
    "Governance & Protocol Updates": "治理与协议更新",
    "Market Structure": "市场结构",
    "RWA & Institutional": "RWA 与机构",
    "DeFi & New Primitives": "DeFi 与新机制",
    "Regulatory & Policy": "监管与政策",
    "Macro & Market": "宏观与市场",
    "Emerging Narratives": "新叙事",
    "General": "综合",
}

PROTOCOL_SECURITY_PATTERNS = [
    r"\bhack(?:ed)?\b",
    r"\bexploit(?:ed)?\b",
    r"\bvulnerabilit(?:y|ies)\b",
    r"\bdrain(?:ed)?\b",
    r"\bstolen\b",
    r"\bprivate key\b",
    r"\bmultisig\b",
    r"\bbridge\b",
    r"\bprotocol\b",
    r"\bsmart contract\b",
    r"\blazarus\b",
    r"\bnorth korea\b",
    r"\blayerzero\b",
    r"\bkelp(?:dao)?\b",
    r"\baave\b",
    r"\bwasabi\b",
    r"\bsecurity incident\b",
    r"\b被盗\b",
    r"\b攻击\b",
    r"\b漏洞\b",
    r"\b黑客\b",
    r"\b私钥\b",
    r"\b安全事件\b",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "digest.log")),
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


def _decode_foresight_payload(data) -> list[dict]:
    payload = data.get("data")
    if isinstance(payload, dict):
        payload = payload.get("list")
    decoded = zlib.decompress(base64.b64decode(payload))
    parsed = json.loads(decoded)
    if isinstance(parsed, dict):
        return parsed.get("list", [])
    return parsed


def fetch_foresight_api(limit: int = FORESIGHT_API_LIMIT) -> list[dict]:
    """Fetch Foresight News directly while its RSSHub route is blocked."""
    try:
        r = httpx.get(
            "https://api.foresightnews.pro/v2/feed",
            params={"size": limit},
            timeout=20,
            headers={"User-Agent": "ForesightNews/1.0", "Accept": "application/json"},
        )
        r.raise_for_status()
        raw_items = _decode_foresight_payload(r.json())
    except Exception as e:
        log.warning(f"Failed to fetch Foresight API: {e}")
        return []

    type_path = {"article": "article", "news": "news", "event": "timeline"}
    articles = []
    for raw in raw_items[:limit]:
        source_type = raw.get("source_type")
        item = raw.get(source_type) if source_type else raw
        if not isinstance(item, dict):
            continue

        item_type = source_type or ("news" if item.get("source_link") else "article")
        item_id = item.get("id")
        published = item.get("published_at") or item.get("last_update_at") or raw.get("published_at")
        if not item_id or not published:
            continue

        articles.append({
            "source": "Foresight News",
            "title": item.get("title", "").strip(),
            "link": f"https://foresightnews.pro/{type_path.get(item_type, 'article')}/detail/{item_id}",
            "summary": _clean_summary(item.get("brief") or item.get("content") or ""),
            "published": datetime.fromtimestamp(int(published), timezone.utc),
            "topics": [],
        })
    return [article for article in articles if article["title"]]


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
- Use "Exchange Listings" ONLY for actual token/spot/futures/perpetual listing, delisting, or trading-pair launch announcements from exchanges.
- Do NOT use "Exchange Listings" for campaigns, trading competitions, fee cuts, product launches, web/app launches, cards, copy trading, ETF filings, ETF flows, alpha pages, or generic exchange business news.
- Use "Portfolio" ONLY if the article explicitly mentions one of the listed portfolio company names above. Do NOT use "Portfolio" for any other company.
- If truly irrelevant to all, use "General".
- Do not explain anything, return only the JSON array."""

EXCHANGE_NAMES = {
    "binance", "binance us", "coinbase", "okx", "bybit", "kraken", "upbit", "bithumb",
    "gate", "gate.io", "htx", "huobi", "mexc", "bitget", "kucoin",
}

LISTING_ALLOW_PATTERNS = [
    r"\bwill list\b",
    r"\blists?\b",
    r"\bdelist(?:ing)?\b",
    r"\blaunch(?:es|ed)?\b.*\b(?:pair|contract)\b",
    r"\b(?:spot|futures|perpetual)\b.*\b(?:pair|contract)\b",
    r"\btrading pair\b",
    r"\bon the krw market\b",
    r"\b充值地址\b",
    r"\b上线\b",
    r"\b上線\b",
]

LISTING_BLOCK_PATTERNS = [
    r"\bcampaign\b",
    r"\bcompetition\b",
    r"\brewards?\b",
    r"\bfee(?:s)?\b",
    r"\bweb\b",
    r"\bapp\b",
    r"\bcard\b",
    r"\bcopy trading\b",
    r"\betf\b",
    r"\bflows?\b",
    r"\balpha page\b",
    r"\bpage\b",
    r"\btrading party\b",
    r"\b奖池\b",
    r"\b返还\b",
    r"\b活动\b",
    r"\b上线.*(?:页面|功能|活动)\b",
]

LOW_SIGNAL_PATTERNS = [
    r"\bhere'?s what happened in crypto today\b",
    r"\bdaily roundup\b",
    r"\blong & short\b",
    r"\bnewsletter\b",
    r"\bmorning minute\b",
    r"\bopinion\b",
    r"\bpress release\b",
    r"\bheadline consensus miami\b",
    r"\bconference\b",
    r"\bfestival\b",
]

HARD_DROP_PATTERNS = [
    r"\bhere'?s what happened in crypto today\b",
    r"\bwhat happened in crypto today\b",
    r"\bprice predictions?\b",
    r"\bdaily roundup\b",
    r"\bweekly roundup\b",
    r"\bweekly recap\b",
    r"\bweekly project updates\b",
    r"\bweb3 手抄报\b",
    r"\b本周不容错过\b",
    r"\b星球(?:早|午|晚)讯\b",
    r"\b比ufo更可疑\b",
    r"\bufo\b",
]

MARKET_NOISE_PATTERNS = [
    r"\bperformance update\b",
    r"\bbull score\b",
    r"\bweekly close\b",
    r"\bprice fails?\b",
    r"\bprice push\b",
    r"\bmetrics? favor\b",
    r"\bbreakout faces\b",
    r"\bprice targets?\b",
    r"\bpredicts?\b.*\b(?:btc|bitcoin|eth|ethereum)\b.*\b(?:hit|hitting|reach|reaching)\b",
    r"\b(?:btc|bitcoin|eth|ethereum)\b.*\b(?:hit|hitting|reach|reaching)\b.*\$",
    r"\bclimbs? near\b",
    r"\bsurges? past\b",
    r"\brally is stalling\b",
    r"\bslips from near\b",
    r"\brally to \$",
    r"\bprice rally\b",
    r"\btechnical analysis\b",
    r"\bprice prediction\b",
    r"\bwhales?, etf investors buy into volatility\b",
    r"\b日内下跌\b",
    r"\b日内上涨\b",
    r"\b跌破\d",
    r"\b突破\d",
    r"\b升破\b",
    r"\b短时突破\b",
]

STRONG_RELEVANCE_PATTERNS = [
    r"\betf\b.*\binflows?\b",
    r"\betf\b.*\boutflows?\b",
    r"\braises?\b", r"\braised\b", r"\bfunding\b", r"\bnew funds?\b",
    r"\bsec\b", r"\bcftc\b", r"\bdoj\b", r"\bfca\b", r"\bbis\b", r"\bmica\b",
    r"\barrests?\b", r"\bcharged\b", r"\bsues?\b", r"\blawsuit\b", r"\bwarns?\b",
    r"\bhack\b", r"\bhacked\b", r"\bexploit\b", r"\bfreeze[sd]?\b", r"\bseized?\b",
    r"\bstablecoin\b", r"\brwa\b", r"\btvl\b", r"\btokenized\b", r"\btreasury\b",
    r"\bdelist(?:ing)?\b", r"\bwill list\b", r"\blists?\b.*\btoken\b",
    r"\b查扣\b", r"\b逮捕\b", r"\b起诉\b", r"\b诉讼\b", r"\b警告\b",
    r"\b被盗\b", r"\b攻击\b", r"\b漏洞\b", r"\b冻结\b", r"\b增持比特币\b",
    r"\b融资\b", r"\b基金\b", r"\b市值\b", r"\b稳定币\b", r"\b代币化\b",
]

CRYPTO_RELEVANCE_PATTERNS = [
    r"\bbitcoin\b", r"\bbtc\b", r"\beth(?:ereum)?\b", r"\bevm\b", r"\bcrypto\b", r"\bblockchain\b", r"\btoken\b",
    r"\bcryptocurrenc(?:y|ies)\b", r"\bdefi\b", r"\bnfts?\b", r"\bstablecoin\b", r"\betf\b", r"\bexchanges?\b", r"\bonchain\b",
    r"\bweb3\b", r"\bl2\b", r"\brollup\b", r"\bsec\b", r"\bcftc\b", r"\bmi?ca\b",
    r"\bsolana\b", r"\barbitrum\b", r"\bbase\b", r"\bsui\b", r"\baptos\b", r"\brwa\b",
    r"\bclarity act\b", r"\bprediction markets?\b",
    r"加密资产", r"加密货币", r"虚拟资产", r"数字资产", r"链上", r"交易所", r"稳定币", r"比特币", r"以太坊",
    r"跨链桥", r"智能合约", r"去中心化", r"协议", r"安全事件", r"攻击者", r"私钥", r"被盗", r"漏洞",
    r"NFT", r"CLARITY法案", r"加密监管",
]

CRYPTO_ENTITY_PATTERNS = [
    r"\btether\b", r"\busdt\b", r"\busdc\b", r"\btron\b", r"\bcircle\b", r"\baave\b",
    r"\buniswap\b", r"\bmorpho\b", r"\bpolymarket\b", r"\bkalshi\b", r"\bftx\b",
    r"\bcoinbase\b", r"\bbinance\b", r"\bokx\b", r"\bbybit\b", r"\bkraken\b",
    r"\bupbit\b", r"\bbitget\b", r"\bkucoin\b", r"\bopensea\b", r"\bmetamask\b",
    r"\bhyperliquid\b", r"\bthorchain\b", r"\bspark(?:lend)?\b", r"\bkelp(?:dao)?\b",
    r"\brseth\b", r"\bxrp\b", r"\bmonad\b", r"\bberachain\b", r"\bworld liberty financial\b",
    r"\bdefillama\b", r"\blookonchain\b", r"\bsam bankman-fried\b", r"\bsbf\b",
    r"\b稳定币\b", r"\b泰达\b", r"\b波场\b", r"\b预测市场\b", r"\b永续合约\b",
    r"\b交易平台\b", r"\b现货etf\b", r"\b加密ETF\b",
]

CRYPTO_ENTITY_SUBSTRINGS = [
    "kelpdao",
    "defillama",
    "lookonchain",
    "sam bankman-fried",
    "polymarket",
    "tether",
    "usdt",
    "ftx",
    "coinbase",
    "aave",
    "circle",
    "uniswap",
    "跨链桥",
    "稳定币",
    "预测市场",
]

PRESS_RELEASE_PATTERNS = [
    r"/press-releases/",
    r"\bpress release\b",
    r"\bannounced today\b.*\bconference\b",
]

OPINION_PATTERNS = [
    r"/opinion/",
    r"\bopinion\b",
    r"\bcolumn\b",
]

PROMOTIONAL_PATTERNS = [
    r"\bcampaign\b",
    r"\bcompetition\b",
    r"\brewards?\b",
    r"\breward pool\b",
    r"\bdeposit bonus\b",
    r"\btrading contest\b",
    r"\btrading competition\b",
    r"\bwelcome bonus\b",
    r"\bairdrop guide\b",
    r"\bearn up to\b",
    r"\b奖池\b",
    r"\b交易大赛\b",
    r"\b空投教程\b",
    r"\b奖励\b",
    r"\b瓜分\b",
]

SOURCE_HARD_DROP_PATTERNS = [
    r"星球(?:早|午|晚)讯",
    r"24H热门币种与要闻",
    r"热门交互合集",
    r"TOP10 crypto news",
    r"weekly top10 crypto news",
    r"weekly project updates",
    r"未来(?:12个月|24小时).*重返历史高点",
    r"外星人存在",
    r"汉坦病毒",
    r"Polymarket.*访华",
    r"预测市场完成.*功能升级",
    r"Bitget.*IPO Prime.*OpenAI",
    r"BitMart.*BM发现",
    r"Strategy.*软件业务",
    r"NBA季后赛",
    r"中韩半导体ETF",
    r"沪深两市",
    r"沪指",
    r"KOSPI",
    r"日本国债收益率",
    r"海外投资者美股",
    r"印度总理.*黄金",
    r"WTI原油",
    r"沙特阿美",
    r"伊朗.*(?:回应|提案|战争|海峡|军方|领袖|官员)",
    r"美国能源部长",
    r"特朗普下令.*买美国货",
    r"黄仁勋",
    r"腾讯云",
    r"阿里千问",
    r"OpenAI放开员工售股",
    r"Sam Altman",
    r"陈茂波.*AI",
    r"AI现在仍未到",
    r"Cerebras",
    r"Scale AI",
    r"CoreWeave",
]

SOURCE_MARKET_NOISE_PATTERNS = [
    r"(?:ETH|SOL|BSC|BTC|[A-Z0-9]{2,12})链生态代币.*(?:市值突破|日内涨超)",
    r"Meme币.*(?:上涨|市值突破|日内涨超)",
    r"日内涨超\d+(?:倍|%)",
    r"BTC突破\d",
    r"BTC升破\d",
    r"比特币(?:突破|升破|市值突破)",
    r"加密市场普涨",
    r"恐慌贪婪指数",
    r"分析[：:].*(?:比特币|BTC|ETH).*(?:回调|下行|牛市|反弹|关键防线|算力|均线)",
    r"分析师[：:].*(?:BTC|比特币|ETH).*(?:增持|建仓|预测|下行|高点)",
    r"巨鲸.*(?:开设|做多|做空|清仓|平仓|浮盈|浮亏|充值|提取|转移|质押|兑换|存入)",
    r"聪明钱数据",
    r"新建钱包.*(?:提取|购入)",
    r"沉寂超\d+年地址被激活",
    r"Tracker信息.*(?:披露|增持)",
    r"地板价.*(?:翻倍|回暖)",
    r"(?:地址|团队|关联地址|BIT|TRUMP).*?(?:提取|转移|充值).*?(?:ETH|BTC|代币|LAB|PAXG)",
    r"某鲸鱼.*Tornado Cash",
    r"Aster上线.*热门港股",
    r"分析师.*(?:算力|链上结构|均线)",
]

SOURCE_ALLOW_PATTERNS = [
    r"CLARITY Act",
    r"GENIUS法案",
    r"SEC",
    r"CFTC",
    r"监管",
    r"牌照",
    r"许可证",
    r"法院",
    r"起诉",
    r"移送公安",
    r"查缉逃税",
    r"国税厅",
    r"现货ETF.*(?:净流入|净流出)",
    r"ETF.*(?:净流入|净流出)",
    r"代币化",
    r"国债.*上链",
    r"稳定币",
    r"加密支付",
    r"支付.*政府服务",
    r"跨境",
    r"融资",
    r"估值",
    r"Canton Network",
    r"TON",
    r"Telegram.*TON",
    r"桥接安全事件",
    r"安全事件",
    r"漏洞",
    r"攻击",
    r"被盗",
    r"补偿",
    r"赔付",
]

IMPORTANT_SIGNAL_PATTERNS = {
    "high": [
        r"\braises?\b", r"\braised\b", r"\bfunding\b", r"\bseed\b", r"\bseries [ab]\b",
        r"\betfs?\b.*\binflows?\b", r"\betfs?\b.*\boutflows?\b",
        r"\bspot (?:bitcoin|btc|ether|eth) etfs?\b.*\binflows?\b",
        r"\bsec\b", r"\bcftc\b", r"\bdoj\b", r"\bfca\b", r"\bmica\b",
        r"\bhack\b", r"\bexploit\b", r"\bfreeze[sd]?\b", r"\blawsuit\b", r"\bdelist(?:ing)?\b",
        r"\btokeni[sz](?:ed|ation)\b", r"\bblackrock\b", r"\brwa\b",
    ],
    "medium": [
        r"\blaunch(?:es|ed)?\b", r"\bmainnet\b", r"\btestnet\b", r"\bstaking\b",
        r"\bgovernance\b", r"\bliquidity\b", r"\btvl\b", r"\binflows?\b", r"\boutflows?\b",
        r"\bopen interest\b", r"\bliquidation\b", r"\bperpetual\b", r"\bstablecoin\b",
    ],
    "low": [
        r"\bwhale\b", r"\brally\b", r"\bprice\b", r"\bbull(?:ish)?\b", r"\bbear(?:ish)?\b",
        r"\btechnicals?\b", r"\bindicator\b", r"\baccumulation\b", r"\btrend\b",
    ],
}


def _combined_text(article: dict) -> str:
    return f"{article['title']} {article['summary']}".strip()


def is_low_signal_article(article: dict) -> bool:
    text = _combined_text(article).lower()
    return any(re.search(pattern, text) for pattern in LOW_SIGNAL_PATTERNS)


def is_market_noise_article(article: dict) -> bool:
    text = _combined_text(article).lower()
    return any(re.search(pattern, text) for pattern in MARKET_NOISE_PATTERNS)


def has_strong_relevance_signal(article: dict) -> bool:
    text = _combined_text(article).lower()
    return any(re.search(pattern, text) for pattern in STRONG_RELEVANCE_PATTERNS)


def is_press_release(article: dict) -> bool:
    text = _combined_text(article).lower()
    link = article["link"].lower()
    return any(re.search(pattern, text) for pattern in PRESS_RELEASE_PATTERNS) or any(re.search(pattern, link) for pattern in PRESS_RELEASE_PATTERNS)


def is_opinion_article(article: dict) -> bool:
    text = _combined_text(article).lower()
    link = article["link"].lower()
    return any(re.search(pattern, text) for pattern in OPINION_PATTERNS) or any(re.search(pattern, link) for pattern in OPINION_PATTERNS)


def is_hard_drop_article(article: dict) -> bool:
    text = _combined_text(article).lower()
    return any(re.search(pattern, text) for pattern in HARD_DROP_PATTERNS)


def is_promotional_article(article: dict) -> bool:
    text = _combined_text(article).lower()
    return any(re.search(pattern, text) for pattern in PROMOTIONAL_PATTERNS)


def has_source_allow_signal(article: dict) -> bool:
    text = _combined_text(article)
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in SOURCE_ALLOW_PATTERNS)


def source_quality_override(article: dict):
    """Apply stricter rules to high-volume sources with lots of market noise."""
    source = article.get("source", "")
    if source not in {"Odaily Newsflash", "Odaily Articles", "Wu Blockchain", "Foresight News"}:
        return None

    text = _combined_text(article)
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in SOURCE_HARD_DROP_PATTERNS):
        return "drop", "source_specific_noise"

    if has_source_allow_signal(article):
        return None

    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in SOURCE_MARKET_NOISE_PATTERNS):
        return "demote", "source_market_noise"

    if source == "Odaily Articles" and is_opinion_article(article):
        return "demote", "source_opinion"

    return None


def is_crypto_relevant(article: dict) -> bool:
    text = _combined_text(article).lower()
    return (
        any(re.search(pattern, text) for pattern in CRYPTO_RELEVANCE_PATTERNS)
        or any(re.search(pattern, text) for pattern in CRYPTO_ENTITY_PATTERNS)
        or any(token in text for token in CRYPTO_ENTITY_SUBSTRINGS)
    )


def has_portfolio_mention(article: dict) -> bool:
    text = _combined_text(article).lower()
    for keyword in TOPICS.get("Portfolio", []):
        term = keyword.lower().strip()
        if not term:
            continue
        if " " in term:
            if term in text:
                return True
            continue
        if term in GENERIC_PORTFOLIO_TERMS:
            continue
        if len(term) >= 4 and re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text):
            return True
    return False


def is_true_exchange_listing(article: dict) -> bool:
    text = _combined_text(article).lower()
    has_exchange = any(name in text for name in EXCHANGE_NAMES) or article["source"] in {"Binance", "OKX", "Bybit"}
    has_listing_signal = any(re.search(pattern, text) for pattern in LISTING_ALLOW_PATTERNS)
    has_block_signal = any(re.search(pattern, text) for pattern in LISTING_BLOCK_PATTERNS)
    return has_exchange and has_listing_signal and not has_block_signal


def _matches_topic_keywords(article: dict, topic: str) -> bool:
    text = _combined_text(article).lower()
    return any(keyword in text for keyword in TOPICS.get(topic, []))


def is_stablecoin_payment_story(article: dict) -> bool:
    text = _combined_text(article).lower()
    patterns = [
        r"\bstablecoin(?:s)?\b",
        r"\btether\b",
        r"\bcircle\b",
        r"\busde\b",
        r"\busdd\b",
        r"\bx402\b",
        r"\bpayments?\b",
        r"\bremittance\b",
        r"\bcross-border payment\b",
        r"\bmerchant\b",
        r"\b稳定币\b",
        r"\b支付\b",
        r"\b跨境支付\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def is_protocol_security_story(article: dict) -> bool:
    text = _combined_text(article).lower()
    return any(re.search(pattern, text) for pattern in PROTOCOL_SECURITY_PATTERNS)


def is_prediction_market_story(article: dict) -> bool:
    text = _combined_text(article).lower()
    patterns = [
        r"\bprediction markets?\b",
        r"\bpolymarket\b",
        r"\bkalshi\b",
        r"预测市场",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def is_rwa_institutional_story(article: dict) -> bool:
    text = _combined_text(article).lower()
    patterns = [
        r"\breal world assets?\b",
        r"\brwa\b",
        r"\btokeni[sz](?:ed|ation)\b",
        r"\bon-?chain treasury\b",
        r"\btokeni[sz]ed (?:bond|fund|treasur)",
        r"\bblackrock\b",
        r"\bfidelity\b",
        r"\bfranklin templeton\b",
        r"\bondo\b",
        r"\bcentrifuge\b",
        r"\bmaple\b",
        r"\bspot (?:bitcoin|btc|ether|eth) etfs?\b",
        r"\betf (?:inflows?|outflows?)\b",
        r"\bnet (?:inflows?|outflows?)\b",
        r"现实世界资产",
        r"代币化",
        r"货币市场基金",
        r"现货(?:比特币|以太坊|btc|eth)?etf",
        r"净流入",
        r"净流出",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def normalize_classification(article: dict, topics: list[str]) -> list[str]:
    topic = topics[0] if topics else "General"

    if is_true_exchange_listing(article):
        return ["Exchange Listings"]

    if topic == "Exchange Listings":
        if _matches_topic_keywords(article, "Market Structure"):
            return ["Market Structure"]
        return ["Macro & Market"]

    if _matches_topic_keywords(article, "Security & Exploits"):
        return ["Security & Exploits"]

    if topic != "Regulatory & Policy" and is_prediction_market_story(article):
        return ["Market Structure"]

    if is_rwa_institutional_story(article):
        return ["RWA & Institutional"]

    if topic != "Regulatory & Policy" and is_stablecoin_payment_story(article):
        return ["Stablecoins & Payments"]

    if topic == "RWA & Institutional":
        return ["Macro & Market"]

    if topic in {"General", "Macro & Market"} and _matches_topic_keywords(article, "Market Structure"):
        return ["Market Structure"]

    return [topic]


def classify_quality(article: dict) -> tuple[str, str]:
    source_override = source_quality_override(article)
    if source_override and source_override[0] == "drop":
        return source_override
    if not is_crypto_relevant(article) and not has_source_allow_signal(article):
        return "drop", "weak_crypto_relevance"
    if is_hard_drop_article(article):
        return "drop", "roundup_or_offtopic"
    if source_override:
        return source_override
    if is_promotional_article(article) and not is_true_exchange_listing(article) and not has_strong_relevance_signal(article):
        return "drop", "promotional"
    if is_press_release(article) and not has_strong_relevance_signal(article):
        return "drop", "low_signal_press_release"
    if is_low_signal_article(article) and not has_strong_relevance_signal(article):
        return "drop", "low_signal"
    if is_opinion_article(article):
        return "demote", "opinion"
    if is_market_noise_article(article) and not has_strong_relevance_signal(article):
        return "demote", "market_noise"
    return "keep", "relevant"


def normalize_articles(articles: list[dict]) -> list[dict]:
    """Normalize article fields before any filtering.

    Current fetchers already return a mostly uniform shape, so this stage is
    intentionally lightweight. Keeping it explicit makes the funnel easier to
    evolve later without coupling normalization to filtering.
    """
    normalized = []
    for article in articles:
        metadata = get_source_metadata(article.get("source", ""))
        normalized_article = {
            **article,
            "title": (article.get("title") or "").strip(),
            "summary": (article.get("summary") or "").strip(),
            "link": (article.get("link") or "").strip(),
            **metadata,
        }
        quality_action, quality_reason = classify_quality(normalized_article)
        normalized.append({
            **normalized_article,
            "quality_action": quality_action,
            "quality_reason": quality_reason,
        })
    return normalized


def get_source_metadata(source: str) -> dict:
    metadata = DEFAULT_SOURCE_METADATA | SOURCE_METADATA.get(source, {})
    return {
        "input_type": metadata["input_type"],
        "source_tier": metadata["source_tier"],
        "source_region": metadata["source_region"],
        "source_focus": metadata["source_focus"],
        "source_weight": metadata["source_weight"],
    }


def annotate_source_metadata(articles: list[dict]) -> list[dict]:
    annotated = []
    for article in articles:
        annotated_article = {**article, **get_source_metadata(article.get("source", ""))}
        quality_action, quality_reason = classify_quality(annotated_article)
        annotated.append({
            **annotated_article,
            "quality_action": quality_action,
            "quality_reason": quality_reason,
        })
    return annotated


def apply_low_signal_filter(articles: list[dict]) -> list[dict]:
    return [
        article
        for article in articles
        if has_strong_relevance_signal(article) or not is_low_signal_article(article)
    ]


def apply_market_noise_filter(articles: list[dict]) -> list[dict]:
    return [
        article
        for article in articles
        if has_strong_relevance_signal(article) or not is_market_noise_article(article)
    ]


def apply_press_release_filter(articles: list[dict]) -> list[dict]:
    return [
        article
        for article in articles
        if has_strong_relevance_signal(article) or not is_press_release(article)
    ]


def apply_crypto_relevance_filter(articles: list[dict]) -> list[dict]:
    return [article for article in articles if is_crypto_relevant(article)]


def prefilter_articles(articles: list[dict]) -> list[dict]:
    return [article for article in articles if article.get("quality_action") != "drop"]


def _score_component(name: str, value: int, reason: str) -> dict:
    return {"name": name, "value": value, "reason": reason}


def _normalize_summary_bullets(summary: str) -> str:
    lines = []
    for raw_line in (summary or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s+", "• ", line)
        if not line.startswith("•"):
            line = f"• {line}"
        lines.append(line)
    return "\n".join(lines)


def score_article_components(article: dict) -> list[dict]:
    text = _combined_text(article).lower()
    components = []

    if is_true_exchange_listing(article):
        components.append(_score_component("exchange_listing", 5, "Actual exchange listing/trading-pair signal"))
    if has_portfolio_mention(article):
        components.append(_score_component("portfolio_company", 6, "Mentions portfolio company"))

    high_matches = [pattern for pattern in IMPORTANT_SIGNAL_PATTERNS["high"] if re.search(pattern, text)]
    medium_matches = [pattern for pattern in IMPORTANT_SIGNAL_PATTERNS["medium"] if re.search(pattern, text)]
    low_matches = [pattern for pattern in IMPORTANT_SIGNAL_PATTERNS["low"] if re.search(pattern, text)]
    if high_matches:
        components.append(_score_component("high_signal_keywords", 3 * len(high_matches), f"{len(high_matches)} high-signal keyword matches"))
    if medium_matches:
        components.append(_score_component("medium_signal_keywords", len(medium_matches), f"{len(medium_matches)} medium-signal keyword matches"))
    if low_matches:
        components.append(_score_component("market_noise_keywords", -1 * len(low_matches), f"{len(low_matches)} price/noise keyword matches"))

    if article["source"] in {"The Block", "CoinDesk", "Cointelegraph"}:
        components.append(_score_component("legacy_source_bonus", 1, "Legacy priority source"))
    source_tier = article.get("source_tier", "tier_3")
    source_tier_adjustment = SOURCE_TIER_SCORE_WEIGHTS.get(source_tier, -1)
    if source_tier_adjustment:
        components.append(_score_component("source_tier", source_tier_adjustment, f"Configured source tier {source_tier}"))
    source_weight = float(article.get("source_weight", 1.0))
    source_weight_adjustment = round((source_weight - 1.0) * 4)
    if source_weight_adjustment:
        components.append(_score_component("source_weight", source_weight_adjustment, f"Configured source weight {source_weight:g}"))
    if article["source"] == "PANews":
        components.append(_score_component("panews_penalty", -1, "Fallback source penalty"))
    if article.get("quality_action") == "demote":
        components.append(_score_component("quality_demote", -3, article.get("quality_reason", "demoted by quality filter")))
    if is_opinion_article(article):
        components.append(_score_component("opinion_penalty", -3, "Opinion/editorial article"))

    return components


def score_article(article: dict) -> int:
    return sum(component["value"] for component in score_article_components(article))


def annotate_importance(articles: list[dict]) -> None:
    for article in articles:
        components = score_article_components(article)
        article["importance_score_components"] = components
        article["importance_score"] = sum(component["value"] for component in components)


def source_priority_rank(source: str) -> int:
    return SOURCE_PRIORITY.index(source) if source in SOURCE_PRIORITY else 99



def _article_story_key(article: dict) -> str:
    raw = (article.get("link") or article.get("title") or "").strip().lower()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


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
    if is_true_exchange_listing(article):
        return ["Exchange Listings"]

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
            article["topics"] = normalize_classification(article, topics)
        log.info(f"  Classified {min(i + batch_size, len(articles))}/{len(articles)}")


# ---------------------------------------------------------------------------
# Deduplicate — exact matches
# ---------------------------------------------------------------------------

def normalize_title_for_dedup(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title or "").casefold()
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


def deduplicate(articles: list[dict]) -> list[dict]:
    seen_urls, seen_titles, unique = set(), set(), []
    for a in articles:
        url_key   = a["link"].rstrip("/").lower()
        title_key = normalize_title_for_dedup(a["title"])
        duplicate_title = title_key and title_key in seen_titles
        if url_key in seen_urls or duplicate_title:
            continue
        seen_urls.add(url_key)
        if title_key:
            seen_titles.add(title_key)
        unique.append(a)
    return unique


# ---------------------------------------------------------------------------
# Cluster same-story articles across sources — keep best source
# ---------------------------------------------------------------------------

SOURCE_PRIORITY = [
    "The Block",
    "CoinDesk",
    "Cointelegraph",
    "Blockworks",
    "The Defiant",
    "Decrypt",
    "Unchained",
    "Chainalysis",
    "Protos",
    "Foresight News",
    "SlowMist",
    "ChainCatcher",
    "TechFlow",
    "Wu Blockchain",
    "Odaily Articles",
    "Odaily Newsflash",
    "Forkast",
    "CryptoSlate",
    "PANews",
    "Investing.com",
]
STOPWORDS = {"the","a","an","in","on","at","to","for","of","and","or","is","as","by","with",
             "after","over","from","its","into","that","this","it","are","was","be","has","have",
             "says","said","new","will","lets","set","major","linked","tied","amid"}
STORY_NOISE_WORDS = {
    "crypto", "bitcoin", "ethereum", "market", "markets", "price", "prices",
    "million", "billion", "today", "industry", "report", "reports", "news",
    "above", "adoption", "below", "holds", "rebounds", "rises", "surge",
    "surges",
}
STORY_ENTITY_PATTERNS = {
    "blackrock": [r"\bblackrock\b"],
    "tokenization": [r"\btokeni[sz](?:ed|ation)\b", r"代币化"],
    "fund": [r"\bfunds?\b", r"基金"],
    "clarity_act": [r"\bclarity act\b", r"CLARITY法案"],
    "wasabi": [r"\bwasabi\b"],
    "layerzero": [r"\blayerzero\b"],
    "kelpdao": [r"\bkelp ?dao\b", r"\bkelpdao\b"],
    "arbitrum": [r"\barbitrum\b"],
    "aave": [r"\baave\b"],
    "northkorea": [r"\bnorth korea\b", r"朝鲜"],
    "strategy": [r"\bstrategy\b", r"\bmicrostrategy\b"],
    "sell_btc": [r"\bsell(?:ing)?\b.*\b(?:btc|bitcoin)\b", r"出售比特币", r"出售 BTC"],
    "trump_media": [r"\btrump media\b", r"\btmtg\b", r"特朗普媒体"],
    "q1": [r"\bq1\b", r"第一季度"],
}


def _normalize_story_text(text: str) -> str:
    normalized = text.lower()
    normalized = re.sub(r"\$?(\d+(?:\.\d+)?)\s*(?:million|mn|m)\b", r"\1m", normalized)
    normalized = re.sub(r"\$?(\d+(?:\.\d+)?)\s*(?:billion|bn|b)\b", r"\1b", normalized)
    normalized = normalized.replace("kelp dao", "kelpdao")
    normalized = re.sub(r"\bkelp\b", "kelpdao", normalized)
    normalized = normalized.replace("north korea", "northkorea")
    normalized = normalized.replace("single-verifier", "singleverifier")
    return normalized

def _title_words(title: str) -> set:
    normalized = _normalize_story_text(title)
    return set(re.sub(r"[^a-z0-9. ]", "", normalized).split()) - STOPWORDS


def _story_words(article: dict) -> set:
    normalized = _normalize_story_text(_combined_text(article))
    return set(re.sub(r"[^a-z0-9. ]", "", normalized).split()) - STOPWORDS


def _important_story_terms(words: set) -> set:
    return {
        word
        for word in words
        if len(word) >= 4 and word not in STORY_NOISE_WORDS and not re.search(r"\d", word)
    }


def _numeric_terms(words: set) -> set:
    return {word for word in words if re.search(r"\d", word)}

def _story_entities(article: dict) -> set[str]:
    text = _combined_text(article).lower()
    entities = set()
    for entity, patterns in STORY_ENTITY_PATTERNS.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            entities.add(entity)
    return entities

def _jaccard(s1: set, s2: set) -> float:
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


def article_story_similarity(article: dict, existing: dict) -> float:
    """Estimate whether two articles describe the same concrete event."""
    title_words = _title_words(article["title"])
    existing_title_words = _title_words(existing["title"])
    title_score = _jaccard(title_words, existing_title_words)

    story_words = _story_words(article)
    existing_story_words = _story_words(existing)
    context_score = _jaccard(story_words, existing_story_words)

    shared_terms = _important_story_terms(title_words) & _important_story_terms(existing_title_words)
    shared_numbers = _numeric_terms(title_words) & _numeric_terms(existing_title_words)
    shared_entities = _story_entities(article) & _story_entities(existing)
    score = max(title_score, context_score)

    if len(shared_terms) < 2:
        score = min(score, 0.29)

    # Title wording often differs by publication. A shared entity/action/amount
    # set is a stronger same-story clue than raw Jaccard alone.
    if len(shared_terms) >= 3:
        score = max(score, 0.31)
    if len(shared_terms) >= 2 and shared_numbers:
        score = max(score, 0.34)
    if len(shared_entities) >= 3:
        score = max(score, 0.35)
    if {"blackrock", "tokenization"} <= shared_entities:
        score = max(score, 0.35)
    if {"strategy", "sell_btc"} <= shared_entities:
        score = max(score, 0.35)
    if {"trump_media", "q1"} <= shared_entities:
        score = max(score, 0.35)
    if {"trump_media"} <= shared_entities and shared_numbers:
        score = max(score, 0.34)

    return score


def choose_primary_article(members: list[dict]) -> dict:
    """Pick the representative article for a same-story cluster."""
    return sorted(
        members,
        key=lambda article: (
            source_priority_rank(article["source"]),
            -score_article(article),
            -article["published"].timestamp(),
        ),
    )[0]


def _story_id(members: list[dict]) -> str:
    raw = "|".join(sorted((article.get("link") or article.get("title") or "").strip().lower() for article in members))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _attach_story_fields(story: dict) -> dict:
    members = story["articles"]
    primary = story["primary_article"]
    sources = sorted({article["source"] for article in members})
    input_types = sorted({article.get("input_type", "unknown") for article in members})
    source_tiers = sorted({article.get("source_tier", "unknown") for article in members})
    story_id = _story_id(members)

    story.update({
        "story_id": story_id,
        "canonical_title": primary["title"],
        "article_count": len(members),
        "source_count": len(sources),
        "sources": sources,
        "supporting_sources": [source for source in sources if source != primary["source"]],
        "input_types": input_types,
        "source_tiers": source_tiers,
        "first_published": min(article["published"] for article in members),
        "latest_published": max(article["published"] for article in members),
    })
    story_summary = primary.get("summary") or next(
        (article.get("summary") for article in members if article.get("summary")),
        "",
    )
    primary.update({
        "story_id": story_id,
        "cluster_size": len(members),
        "story_source_count": len(sources),
        "story_sources": sources,
        "supporting_sources": story["supporting_sources"],
        "story_summary": story_summary,
    })
    return story


def build_story_clusters(articles: list[dict], threshold: float = 0.3) -> list[dict]:
    """Group same-story articles while preserving every member for review."""
    stories = []
    for article in articles:
        matched = None
        matched_score = 0.0
        for i, story in enumerate(stories):
            score = article_story_similarity(article, story["primary_article"])
            if score >= threshold:
                matched = i
                matched_score = score
                break

        if matched is None:
            stories.append({
                "primary_article": article,
                "articles": [article],
                "cluster_matches": [],
            })
            continue

        story = stories[matched]
        previous_primary = story["primary_article"]
        story["articles"].append(article)
        story["primary_article"] = choose_primary_article(story["articles"])
        story["cluster_matches"].append({
            "title": article["title"],
            "source": article["source"],
            "matched_primary_title": previous_primary["title"],
            "matched_primary_source": previous_primary["source"],
            "similarity": round(matched_score, 3),
        })

    return [_attach_story_fields(story) for story in stories]


def annotate_story_scores(stories: list[dict]) -> None:
    for story in stories:
        primary = story["primary_article"]
        components = [
            _score_component(
                "primary_article_score",
                int(primary.get("importance_score", score_article(primary))),
                "Importance score of representative article",
            )
        ]
        primary_topic = (primary.get("topics") or ["General"])[0]
        topic_weight = TOPIC_SCORE_WEIGHTS.get(primary_topic, 0)
        if topic_weight:
            components.append(_score_component("topic_weight", topic_weight, f"Editorial weight for {primary_topic}"))
        if primary_topic == "Security & Exploits" and is_protocol_security_story(primary):
            components.append(_score_component("protocol_security_impact", 2, "Protocol/user-fund security incident"))
        corroboration_bonus = min(max(story.get("source_count", 1) - 1, 0), 3)
        if corroboration_bonus:
            components.append(_score_component("source_corroboration", corroboration_bonus, f"{story['source_count']} sources cover this story"))
        if "official_announcement" in story.get("input_types", []) and is_true_exchange_listing(primary):
            components.append(_score_component("official_listing_signal", 1, "First-party exchange listing signal"))
        if "specialist_signal" in story.get("input_types", []):
            components.append(_score_component("specialist_signal", 1, "Specialist/security/regulatory source included"))

        story["story_score_components"] = components
        story["story_score"] = sum(component["value"] for component in components)
        primary["story_score"] = story["story_score"]
        primary["story_score_components"] = components


def cluster_stories(articles: list[dict], threshold: float = 0.3) -> list[dict]:
    """
    Group articles about the same story, keep one per group.
    Within a group, prefer higher-priority sources.
    """
    return [story["primary_article"] for story in build_story_clusters(articles, threshold=threshold)]


# ---------------------------------------------------------------------------
# Summarise a topic's articles via DeepSeek
# ---------------------------------------------------------------------------

def summarize_topic(topic: str, articles: list[dict]) -> str:
    """Return a short bullet-point summary of the key takeaways for a topic."""
    if not DEEPSEEK_API_KEY:
        log.warning(f"DEEPSEEK_API_KEY not configured — skipping summary for {topic}")
        return ""

    sorted_articles = sorted(articles, key=lambda a: (article_rank_score(a), a["published"]), reverse=True)
    items = "\n".join(
        f"- {a['title']} ({a['source']}; supporting sources: {', '.join(a.get('supporting_sources', [])) or 'none'}): {a.get('summary') or 'No summary; use title only'}"
        for a in sorted_articles[:12]
    )
    prompt = (
        f"用简体中文总结 {topic} 新闻，输出 3-5 条要点。\n"
        f"Rules:\n"
        f"- 只能使用下方 SOURCE DATA 中明确出现的信息。\n"
        f"- 禁止使用外部知识，禁止补充背景数据，禁止编造日期、金额、百分比或公司动作。\n"
        f"- 如果 SOURCE DATA 没有数字，就不要写数字。\n"
        f"- State only facts — what happened, who did what, what amount\n"
        f"- No analysis, no opinion, no commentary\n"
        f"- Each bullet: one line, concise Chinese\n"
        f"- Each bullet must describe exactly one event only\n"
        f"- Prefer including a key number when available\n"
        f"- Start each with a bold keyword e.g. **Monad:** or **Binance:**\n"
        f"- Do not repeat the headline verbatim\n"
        f"- Use neutral verbs; avoid analytical wording like 加速、利好、推动 unless present in SOURCE DATA\n"
        f"- Use plain bullet character •\n\n"
        f"SOURCE DATA:\n{items}"
    )
    try:
        r = httpx.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 400,
            },
            timeout=30,
        )
        r.raise_for_status()
        summary = r.json()["choices"][0]["message"]["content"].strip()
        bullets = _normalize_summary_bullets(summary)
        return f"─────────────\n📝 *Key Takeaways*\n\n{bullets}"
    except Exception as e:
        log.warning(f"Summary failed for {topic}: {e}")
        return ""


def ranked_stories(stories: list[dict], limit=None) -> list[dict]:
    ranked = sorted(
        stories,
        key=lambda story: (
            story.get("story_score", story["primary_article"].get("importance_score", 0)),
            story["latest_published"],
        ),
        reverse=True,
    )
    return ranked[:limit] if limit else ranked


def _story_prompt_line(story: dict, index: int) -> str:
    primary = story["primary_article"]
    topic = (primary.get("topics") or ["General"])[0]
    sources = ", ".join(story.get("sources", [primary["source"]]))
    summary = primary.get("summary") or ""
    member_lines = []
    for article in story.get("articles", [])[:4]:
        article_summary = article.get("summary") or ""
        member_lines.append(
            f"   - {article['source']}: {article['title']}"
            + (f" — {article_summary}" if article_summary else "")
        )
    related = "\n".join(member_lines)
    return (
        f"{index}. Topic: {topic}\n"
        f"   Score: {story.get('story_score', primary.get('importance_score', 0))}\n"
        f"   Title: {primary['title']}\n"
        f"   Sources: {sources}\n"
        f"   Summary: {summary}\n"
        f"   Reports:\n{related}"
    )


def summarize_digest(stories: list[dict], max_stories: int = 10) -> str:
    """Return an executive summary built from ranked story clusters."""
    top_stories = ranked_stories(stories, limit=max_stories)
    if not top_stories:
        return ""

    if not DEEPSEEK_API_KEY:
        bullets = []
        for story in top_stories[:8]:
            primary = story["primary_article"]
            keyword = primary["title"].split(":", 1)[0][:28]
            bullets.append(f"• **{keyword}:** {primary['title']}")
        return "─────────────\n🧭 *Executive Takeaways*\n\n" + "\n".join(bullets)

    items = "\n\n".join(_story_prompt_line(story, i) for i, story in enumerate(top_stories, 1))
    prompt = (
        "Write an executive crypto daily digest in concise Simplified Chinese from the ranked story clusters below.\n"
        "Rules:\n"
        "- Use only facts explicitly present in SOURCE DATA.\n"
        "- Do not use outside knowledge; never invent dates, numbers, percentages, partnerships, or company actions.\n"
        "- If a number/jurisdiction/protocol/token is not present in SOURCE DATA, omit it.\n"
        "- Output 5-8 bullets only.\n"
        "- Use plain bullet character •.\n"
        "- Each bullet must cover exactly one story cluster.\n"
        "- State what happened, who is affected, and the key number/jurisdiction/protocol/token when available.\n"
        "- Prefer security, regulation, institutional/RWA, listings, funding, and protocol events.\n"
        "- Do not include generic price commentary unless it has ETF flow, liquidation, or policy context.\n"
        "- No predictions, no investment advice, no vague phrases like 'could impact the market'.\n"
        "- Do not repeat the headline; synthesize the concrete fact from title and report details.\n"
        "- Use neutral verbs such as 提交、批准、完成、警告、发布; avoid 加速、利好、推动 unless present in SOURCE DATA.\n"
        "- Start each bullet with a bold keyword, e.g. **Aave:** or **SEC:**.\n"
        "- Keep each bullet under 34 Chinese characters when possible.\n\n"
        f"SOURCE DATA:\n{items}"
    )
    try:
        r = httpx.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 700,
            },
            timeout=30,
        )
        r.raise_for_status()
        summary = r.json()["choices"][0]["message"]["content"].strip()
        bullets = _normalize_summary_bullets(summary)
        return f"─────────────\n🧭 *Executive Takeaways*\n\n{bullets}"
    except Exception as e:
        log.warning(f"Executive summary failed: {e}")
        return ""


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _needs_chinese_localization(article: dict) -> bool:
    title = article.get("title") or ""
    summary = article.get("story_summary") or article.get("summary") or ""
    if not title.strip():
        return False
    if _contains_cjk(title) and (not summary or _contains_cjk(summary)):
        return False
    return True


def _localize_batch_for_telegram(articles: list[dict]) -> dict[int, dict]:
    if not DEEPSEEK_API_KEY or not articles:
        return {}

    items = []
    for idx, article in enumerate(articles, 1):
        summary = article.get("story_summary") or article.get("summary") or ""
        items.append(
            f"{idx}. Source: {article['source']}\n"
            f"Title: {article['title']}\n"
            f"Summary: {summary}"
        )
    prompt = (
        "把下面的加密新闻标题和摘要翻译/改写成适合 Telegram 阅读的简体中文。\n"
        "Rules:\n"
        "- 只翻译 SOURCE DATA 中已有信息，不补充背景，不编造数字、日期或动作。\n"
        "- title 用简洁中文，保留项目名、公司名、token ticker、法案名。\n"
        "- summary 用 1 句中文说明事实；如果原文没有摘要，可返回空字符串。\n"
        "- 不要使用 Markdown，不要加项目符号。\n"
        "- 输出严格 JSON 数组，每项格式: {\"id\": 1, \"title\": \"...\", \"summary\": \"...\"}\n\n"
        f"SOURCE DATA:\n{chr(10).join(items)}"
    )
    try:
        response = httpx.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 1800,
            },
            timeout=45,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.MULTILINE).strip()
        rows = json.loads(content)
        localized = {}
        for row in rows:
            try:
                item_id = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            title = (row.get("title") or "").strip()
            summary = (row.get("summary") or "").strip()
            if title:
                localized[item_id] = {"title": title, "summary": summary}
        return localized
    except Exception as e:
        log.warning(f"Telegram Chinese localization failed: {e}")
        return {}


def localize_articles_for_telegram(articles: list[dict], batch_size: int = 12) -> None:
    """Attach Chinese display fields used only by Telegram rendering."""
    targets = [article for article in articles if _needs_chinese_localization(article)]
    if not targets:
        return

    log.info(f"  Localizing {len(targets)} Telegram articles to Chinese…")
    for start in range(0, len(targets), batch_size):
        batch = targets[start:start + batch_size]
        translations = _localize_batch_for_telegram(batch)
        for idx, article in enumerate(batch, 1):
            translated = translations.get(idx)
            if not translated:
                continue
            article["display_title"] = translated["title"]
            article["display_summary"] = translated.get("summary", "")


# ---------------------------------------------------------------------------
# Render Telegram messages
# ---------------------------------------------------------------------------

def _escape(text: str) -> str:
    """Escape special chars for Telegram Markdown (legacy mode)."""
    return re.sub(r"([_*`\[])", r"\\\1", text)


def render_header(now: datetime, total: int, sources: int) -> str:
    now_cst = now.astimezone(TZ_CST)
    date_str = f"{now_cst.year}年{now_cst.month}月{now_cst.day}日"
    time_str = now_cst.strftime("%H:%M UTC+8")
    return (
        f"📰 *加密日报 — {date_str}*\n"
        f"_{sources} 个来源 · {total} 条新闻 · {time_str}_"
    )


def render_topic_section(topic: str, articles: list[dict], total_count=None) -> list[str]:
    """
    Returns a list of message strings for this topic.
    Each string is ≤4096 chars (Telegram's limit).
    """
    emoji = TOPIC_EMOJI.get(topic, "📌")
    topic_label = TOPIC_DISPLAY_NAME.get(topic, topic)
    count_text = f"{len(articles)} 条" if total_count is None or total_count == len(articles) else f"前 {len(articles)} / 共 {total_count} 条"
    header = f"{emoji} *{_escape(topic_label)}*  ({count_text})\n"

    messages = []
    current = header

    for a in sorted(articles, key=lambda x: (article_rank_score(x), x["published"]), reverse=True):
        pub = a["published"].astimezone(TZ_CST).strftime("%b %d, %H:%M UTC+8")
        source = _escape(a["source"])
        supporting = a.get("supporting_sources", [])
        source_line = source if not supporting else f"{source} + {len(supporting)} 个来源"
        title = _escape(a.get("display_title") or a["title"])
        display_summary = a.get("display_summary")
        if display_summary is None:
            display_summary = a.get("story_summary") or a.get("summary") or ""
        summary = f"{_escape(display_summary)}\n" if display_summary else ""
        link = a["link"]

        block = f"\n[{title}]({link})\n_{_escape(source_line)} · {pub}_\n{summary}"

        if len(current) + len(block) > 4000:
            messages.append(current)
            current = f"{emoji} *{_escape(topic_label)}*（续）\n" + block
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


def _summary_to_html(summary: str) -> str:
    body = re.sub(r"^─+\n(?:🧭|📝) \*[^*]+\*\n\n", "", summary or "").strip()
    return body.replace(chr(10), "<br>")


def _build_topic_html(topic: str, articles: list, summaries: dict) -> str:
    emoji = TOPIC_EMOJI.get(topic, "📌")
    html = f"<h3>{emoji} {topic} ({len(articles)})</h3>"
    for a in sorted(articles, key=lambda x: (article_rank_score(x), x["published"]), reverse=True):
        pub = a["published"].astimezone(TZ_CST).strftime("%b %d, %H:%M UTC+8")
        source_line = a["source"]
        if a.get("supporting_sources"):
            source_line += f" + {len(a['supporting_sources'])} sources"
        summary = a["summary"] if a["summary"] else ""
        html += f'<p><a href="{a["link"]}"><strong>{a["title"]}</strong></a><br><em>{source_line} · {pub}</em>'
        if summary:
            html += f"<br>{summary}"
        html += "</p>"
    if topic in summaries:
        html += f"<blockquote>{_summary_to_html(summaries[topic])}</blockquote>"
    html += "<hr>"
    return html


def publish_telegraph_pages(
    by_topic: dict,
    topic_order: list,
    summaries: dict,
    now: datetime,
    token: str,
    executive_summary: str = "",
) -> list[str]:
    """Pack topics into Telegraph pages (under 64KB JSON), return list of URLs."""
    MAX_BYTES = 60_000  # measured on JSON-serialized nodes
    date_str = now.strftime("%b %d, %Y")
    time_str = now.astimezone(TZ_CST).strftime("%H:%M UTC+8")
    n_sources = len(set(a["source"] for t in by_topic.values() for a in t))
    n_articles = sum(len(v) for v in by_topic.values())
    header_html = f"<p><em>{n_sources} sources · {n_articles} articles · {time_str}</em></p>"
    if executive_summary:
        header_html += f"<h3>🧭 Executive Takeaways</h3><blockquote>{_summary_to_html(executive_summary)}</blockquote><hr>"
    header_nodes = _html_to_nodes(header_html)

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


def collect_articles(source: str = "live", hours: int = 24) -> list[dict]:
    all_articles = []
    if source == "miniflux":
        log.info("  Fetching RSS articles from Miniflux history…")
        rss_articles = fetch_miniflux_articles(hours=hours)
        log.info(f"    → {len(rss_articles)} RSS articles")
        all_articles.extend(rss_articles)

        log.info("  Fetching non-RSS articles from local history…")
        history_articles = fetch_history_articles(
            hours=hours,
            sources=["Foresight News", "Binance", "OKX", "Bybit"],
        )
        log.info(f"    → {len(history_articles)} historical non-RSS articles")
        all_articles.extend(history_articles)
    else:
        all_articles.extend(fetch_live_articles())

    if source != "miniflux" and ENABLE_FORESIGHT_API:
        log.info("  Fetching Foresight News API…")
        foresight = fetch_foresight_api()
        log.info(f"    → {len(foresight)} articles")
        all_articles.extend(foresight)

    if source != "miniflux":
        all_articles.extend(fetch_exchange_articles())
    all_articles = annotate_source_metadata(all_articles)
    log.info(f"Total fetched: {len(all_articles)}")
    return all_articles


def apply_normalization(articles: list[dict]) -> list[dict]:
    normalized = normalize_articles(articles)
    log.info(f"After normalization: {len(normalized)}")
    return normalized


def filter_articles_by_hours(articles: list[dict], now: datetime, hours: int = 24) -> list[dict]:
    cutoff = now - timedelta(hours=hours)
    filtered = [article for article in articles if article["published"] >= cutoff]
    log.info(f"After {hours}h filter: {len(filtered)}")
    return filtered


def apply_relevance_filter(articles: list[dict]) -> list[dict]:
    filtered = prefilter_articles(articles)
    log.info(f"After relevance filter: {len(filtered)}")
    return filtered


def apply_deduplication(articles: list[dict]) -> list[dict]:
    filtered = deduplicate(articles)
    log.info(f"After dedup: {len(filtered)}")
    return filtered


def apply_story_clustering(articles: list[dict], threshold: float = 0.3) -> list[dict]:
    filtered = cluster_stories(articles, threshold=threshold)
    log.info(f"After story clustering: {len(filtered)}")
    return filtered


def classify_articles(articles: list[dict]) -> None:
    tag_all_articles(articles)


def score_articles(articles: list[dict]) -> None:
    annotate_importance(articles)


def article_rank_score(article: dict) -> int:
    return article.get("story_score", article.get("importance_score", 0))


def _is_telegram_supplemental_source(article: dict) -> bool:
    return article.get("source") in TELEGRAM_SUPPLEMENTAL_SOURCES


def _balance_telegram_sources(sorted_articles: list[dict], limit: int) -> list[dict]:
    """Keep supplemental feeds from crowding out primary sources in Telegram."""
    if limit <= 0:
        return sorted_articles
    candidates = sorted_articles[:]
    if not any(not _is_telegram_supplemental_source(article) for article in candidates):
        return candidates[:limit]

    selected = []
    supplemental_count = 0
    for article in candidates:
        if len(selected) >= limit:
            break
        if _is_telegram_supplemental_source(article):
            if supplemental_count >= TELEGRAM_SUPPLEMENTAL_TOPIC_CAP:
                continue
            supplemental_count += 1
        selected.append(article)

    return selected


def group_articles_by_topic(articles: list[dict]) -> dict[str, list[dict]]:
    by_topic = defaultdict(list)
    for article in articles:
        for topic in article["topics"]:
            by_topic[topic].append(article)
    return by_topic


def telegram_thread_for_topic(topic: str, prod: bool = False):
    if not prod:
        return None
    routed_topic = TOPIC_TELEGRAM_ROUTE.get(topic, topic)
    if routed_topic == "General":
        return None
    return TOPIC_THREAD_IDS.get(routed_topic)


def telegram_articles_for_topic(topic: str, articles: list[dict]):
    visible_articles = [article for article in articles if article.get("quality_action") != "demote"]
    sorted_articles = sorted(visible_articles, key=lambda a: (article_rank_score(a), a["published"]), reverse=True)
    limit = TELEGRAM_TOPIC_LIMITS.get(topic, TELEGRAM_DEFAULT_TOPIC_LIMIT)
    if limit <= 0:
        return sorted_articles, 0
    balanced_articles = _balance_telegram_sources(sorted_articles, limit)
    return balanced_articles, max(len(sorted_articles) - len(balanced_articles), 0)


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

    all_articles = collect_articles(source=args.source, hours=24)
    all_articles = apply_normalization(all_articles)
    all_articles = filter_articles_by_hours(all_articles, now, hours=24)
    all_articles = apply_relevance_filter(all_articles)
    all_articles = apply_deduplication(all_articles)
    stories = build_story_clusters(all_articles)
    all_articles = [story["primary_article"] for story in stories]
    log.info(f"After story clustering: {len(all_articles)}")
    source_count = len(set(a["source"] for a in all_articles))

    classify_articles(all_articles)
    score_articles(all_articles)
    annotate_story_scores(stories)
    by_topic = group_articles_by_topic(all_articles)
    executive_summary = summarize_digest(stories)
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

    # Post to Telegram
    if not TELEGRAM_BOT_TOKEN and not args.dry_run:
        log.warning("Telegram not configured — printing to stdout instead")
        print(render_header(now, len(all_articles), source_count))
        for topic, articles in by_topic.items():
            telegram_articles, omitted = telegram_articles_for_topic(topic, articles)
            for msg in render_topic_section(topic, telegram_articles, total_count=len(articles)):
                print("\n" + "─" * 60)
                print(msg)
            if omitted:
                print(f"\n_Omitted {omitted} lower-ranked {topic} articles from Telegram preview._")
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
            urls = publish_telegraph_pages(
                by_topic,
                topic_order,
                summaries,
                now,
                token,
                executive_summary=executive_summary,
            )

        header = render_header(now, len(all_articles), source_count)
        intro = f"{header}\n\n{executive_summary}" if executive_summary else header
        if len(urls) == 1:
            links = f"📖 [Read full digest]({urls[0]})"
        else:
            links = "\n".join(f"📖 [Part {i+1}]({u})" for i, u in enumerate(urls))
        post_telegram(f"{intro}\n\n{links}", chat_id=target_group, dry_run=args.dry_run)
        log.info("Done.")
        return

    # Default: send raw messages to Telegram
    header = render_header(now, len(all_articles), source_count)
    post_telegram(header, chat_id=target_group, dry_run=args.dry_run)
    if not args.dry_run:
        time.sleep(2)
    if executive_summary:
        post_telegram(executive_summary, chat_id=target_group, dry_run=args.dry_run)
        if not args.dry_run:
            time.sleep(2)

    for topic in topic_order:
        if topic not in by_topic:
            continue
        thread_id = telegram_thread_for_topic(topic, prod=args.prod)
        telegram_articles, omitted = telegram_articles_for_topic(topic, by_topic[topic])
        if not telegram_articles:
            log.info(f"  Skipped: {topic} has no Telegram-visible articles")
            continue
        if omitted:
            log.info(f"  Telegram cap: {topic} sending {len(telegram_articles)}/{len(by_topic[topic])}, omitted {omitted}")
        for msg in render_topic_section(topic, telegram_articles, total_count=len(by_topic[topic])):
            success = post_telegram(msg, thread_id=thread_id, chat_id=target_group, dry_run=args.dry_run)
            if success:
                log.info(f"  Posted: {topic} → thread {thread_id or 'General'}")
            if not args.dry_run:
                time.sleep(2)

    log.info("Done.")


if __name__ == "__main__":
    main()
