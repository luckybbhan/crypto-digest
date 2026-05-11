import os
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    """Small .env loader so the server can run without extra dependencies."""
    env_path = Path(__file__).resolve().parent / path
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "-1003723061243")

# Group with topics
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID", "-1003510224043")

# Test group (no topics/threads)
TEST_GROUP_ID = os.getenv("TEST_GROUP_ID", "-5270638639")

# Telegraph
TELEGRAPH_TOKEN = os.getenv("TELEGRAPH_TOKEN", "")
TOPIC_THREAD_IDS = {
    "Portfolio":             4,
    "Exchange Listings":     6,
    "Deal Flow & Funding":   7,
    "RWA & Institutional":   8,
    "DeFi & New Primitives": 9,
    "Regulatory & Policy":   10,
    "Macro & Market":        11,
    # General → General thread (no thread_id)
}

# Internal taxonomy can be more granular than the Telegram forum topics.
# This map keeps the analysis categories intact while routing posts to the
# existing forum structure.
TOPIC_TELEGRAM_ROUTE = {
    "Portfolio": "Portfolio",
    "Exchange Listings": "Exchange Listings",
    "Deal Flow & Funding": "Deal Flow & Funding",
    "RWA & Institutional": "RWA & Institutional",
    "DeFi & New Primitives": "DeFi & New Primitives",
    "Regulatory & Policy": "Regulatory & Policy",
    "Macro & Market": "Macro & Market",
    "Security & Exploits": "DeFi & New Primitives",
    "Stablecoins & Payments": "RWA & Institutional",
    "Governance & Protocol Updates": "DeFi & New Primitives",
    "Market Structure": "Macro & Market",
    "Infrastructure & Tech": "DeFi & New Primitives",
    "Emerging Narratives": "General",
    "General": "General",
}

TELEGRAM_DEFAULT_TOPIC_LIMIT = int(os.getenv("TELEGRAM_DEFAULT_TOPIC_LIMIT", "10"))
TELEGRAM_TOPIC_LIMITS = {
    "Portfolio": int(os.getenv("TELEGRAM_LIMIT_PORTFOLIO", "20")),
    "Exchange Listings": int(os.getenv("TELEGRAM_LIMIT_EXCHANGE_LISTINGS", "20")),
    "Deal Flow & Funding": int(os.getenv("TELEGRAM_LIMIT_DEAL_FLOW", "12")),
    "RWA & Institutional": int(os.getenv("TELEGRAM_LIMIT_RWA", "12")),
    "Stablecoins & Payments": int(os.getenv("TELEGRAM_LIMIT_STABLECOINS", "10")),
    "DeFi & New Primitives": int(os.getenv("TELEGRAM_LIMIT_DEFI", "12")),
    "Security & Exploits": int(os.getenv("TELEGRAM_LIMIT_SECURITY", "10")),
    "Governance & Protocol Updates": int(os.getenv("TELEGRAM_LIMIT_GOVERNANCE", "8")),
    "Infrastructure & Tech": int(os.getenv("TELEGRAM_LIMIT_INFRA", "8")),
    "Regulatory & Policy": int(os.getenv("TELEGRAM_LIMIT_REGULATORY", "12")),
    "Macro & Market": int(os.getenv("TELEGRAM_LIMIT_MACRO", "10")),
    "Market Structure": int(os.getenv("TELEGRAM_LIMIT_MARKET_STRUCTURE", "10")),
    "Emerging Narratives": int(os.getenv("TELEGRAM_LIMIT_NARRATIVES", "8")),
    "General": int(os.getenv("TELEGRAM_LIMIT_GENERAL", "6")),
}

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# Miniflux collector
MINIFLUX_URL = os.getenv("MINIFLUX_URL", "http://localhost:8080")
MINIFLUX_API_TOKEN = os.getenv("MINIFLUX_API_TOKEN", "")
MINIFLUX_USERNAME = os.getenv("MINIFLUX_USERNAME", "")
MINIFLUX_PASSWORD = os.getenv("MINIFLUX_PASSWORD", "")


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


# RSSHub adapter. When these URLs are imported into Miniflux running in the same
# Docker Compose network, use RSSHUB_URL=http://rsshub:1200.
RSSHUB_URL = os.getenv("RSSHUB_URL", "http://localhost:1200").rstrip("/")
ENABLE_PANEWS = _env_flag("ENABLE_PANEWS", "0")
ENABLE_REPLACEMENT_FEEDS = _env_flag("ENABLE_REPLACEMENT_FEEDS", "1")
ENABLE_RSSHUB_FEEDS = _env_flag("ENABLE_RSSHUB_FEEDS", "0")
ENABLE_FORESIGHT_API = _env_flag("ENABLE_FORESIGHT_API", "1")
FORESIGHT_API_LIMIT = int(os.getenv("FORESIGHT_API_LIMIT", "50"))
SOURCE_HISTORY_DB = os.getenv("SOURCE_HISTORY_DB", "data/source_history.sqlite3")

CORE_FEEDS = [
    # English — Tier 1
    {"name": "CoinDesk",      "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss"},
    {"name": "The Block",     "url": "https://www.theblock.co/rss.xml"},
    {"name": "Decrypt",       "url": "https://decrypt.co/feed"},
    {"name": "Blockworks",    "url": "https://blockworks.co/feed"},
    {"name": "The Defiant",   "url": "https://thedefiant.io/feed"},
    {"name": "Unchained",     "url": "https://unchainedcrypto.com/feed/"},
    # English — Tier 2
    {"name": "Forkast",       "url": "https://forkast.news/feed/"},
    {"name": "CryptoSlate",   "url": "https://cryptoslate.com/feed/"},
    {"name": "Investing.com", "url": "https://www.investing.com/rss/news_301.rss"},
    # Chinese
    {"name": "Wu Blockchain", "url": "https://wublock.substack.com/feed"},
]

PANEWS_FEED = {"name": "PANews", "url": "https://www.panewslab.com/rss.xml"}

REPLACEMENT_FEEDS = [
    {"name": "Odaily Newsflash", "url": "https://rss.odaily.news/rss/newsflash"},
    {"name": "Odaily Articles",  "url": "https://rss.odaily.news/rss/post"},
    {"name": "Chainalysis",      "url": "https://www.chainalysis.com/feed/"},
    {"name": "Protos",           "url": "https://protos.com/feed/"},
]

RSSHUB_FEEDS = [
    {"name": "ChainCatcher",  "url": f"{RSSHUB_URL}/chaincatcher/news"},
    {"name": "TechFlow",      "url": f"{RSSHUB_URL}/techflowpost/express"},
    {"name": "SlowMist",      "url": f"{RSSHUB_URL}/slowmist/research"},
]

FEEDS = CORE_FEEDS[:]
if ENABLE_PANEWS:
    FEEDS.append(PANEWS_FEED)
if ENABLE_REPLACEMENT_FEEDS:
    FEEDS.extend(REPLACEMENT_FEEDS)
if ENABLE_RSSHUB_FEEDS:
    FEEDS.extend(RSSHUB_FEEDS)


DEFAULT_SOURCE_METADATA = {
    "input_type": "media_news",
    "source_tier": "tier_3",
    "source_region": "global",
    "source_focus": "broad_crypto",
    "source_weight": 0.9,
}

SOURCE_METADATA = {
    # English crypto-native media
    "CoinDesk": {
        "input_type": "media_news",
        "source_tier": "tier_1",
        "source_region": "global",
        "source_focus": "broad_crypto",
        "source_weight": 1.15,
    },
    "The Block": {
        "input_type": "media_news",
        "source_tier": "tier_1",
        "source_region": "global",
        "source_focus": "institutional",
        "source_weight": 1.15,
    },
    "Blockworks": {
        "input_type": "media_news",
        "source_tier": "tier_1",
        "source_region": "us",
        "source_focus": "institutional",
        "source_weight": 1.15,
    },
    "Decrypt": {
        "input_type": "media_news",
        "source_tier": "tier_2",
        "source_region": "global",
        "source_focus": "culture",
        "source_weight": 1.0,
    },
    "The Defiant": {
        "input_type": "media_news",
        "source_tier": "tier_2",
        "source_region": "global",
        "source_focus": "defi",
        "source_weight": 1.0,
    },
    "Unchained": {
        "input_type": "media_news",
        "source_tier": "tier_2",
        "source_region": "us",
        "source_focus": "broad_crypto",
        "source_weight": 1.0,
    },
    "Cointelegraph": {
        "input_type": "media_news",
        "source_tier": "tier_3",
        "source_region": "global",
        "source_focus": "broad_crypto",
        "source_weight": 0.9,
    },
    "CryptoSlate": {
        "input_type": "media_news",
        "source_tier": "tier_3",
        "source_region": "global",
        "source_focus": "market",
        "source_weight": 0.9,
    },
    "Forkast": {
        "input_type": "media_news",
        "source_tier": "tier_3",
        "source_region": "asia",
        "source_focus": "regulatory",
        "source_weight": 0.9,
    },
    "Investing.com": {
        "input_type": "media_news",
        "source_tier": "tier_3",
        "source_region": "global",
        "source_focus": "market",
        "source_weight": 0.75,
    },

    # Chinese and Asia media
    "Foresight News": {
        "input_type": "media_news",
        "source_tier": "tier_1",
        "source_region": "china",
        "source_focus": "broad_crypto",
        "source_weight": 1.1,
    },
    "Wu Blockchain": {
        "input_type": "media_news",
        "source_tier": "tier_2",
        "source_region": "asia",
        "source_focus": "exchange",
        "source_weight": 1.0,
    },
    "Odaily Newsflash": {
        "input_type": "media_news",
        "source_tier": "tier_3",
        "source_region": "china",
        "source_focus": "broad_crypto",
        "source_weight": 0.65,
    },
    "Odaily Articles": {
        "input_type": "media_news",
        "source_tier": "tier_3",
        "source_region": "china",
        "source_focus": "broad_crypto",
        "source_weight": 0.75,
    },
    "PANews": {
        "input_type": "media_news",
        "source_tier": "fallback",
        "source_region": "china",
        "source_focus": "broad_crypto",
        "source_weight": 0.5,
    },
    "ChainCatcher": {
        "input_type": "media_news",
        "source_tier": "fallback",
        "source_region": "china",
        "source_focus": "broad_crypto",
        "source_weight": 0.5,
    },
    "TechFlow": {
        "input_type": "media_news",
        "source_tier": "fallback",
        "source_region": "china",
        "source_focus": "broad_crypto",
        "source_weight": 0.5,
    },

    # Specialist and security signals
    "Protos": {
        "input_type": "specialist_signal",
        "source_tier": "tier_2",
        "source_region": "global",
        "source_focus": "security",
        "source_weight": 1.1,
    },
    "Chainalysis": {
        "input_type": "specialist_signal",
        "source_tier": "tier_2",
        "source_region": "global",
        "source_focus": "regulatory",
        "source_weight": 1.1,
    },
    "SlowMist": {
        "input_type": "specialist_signal",
        "source_tier": "tier_2",
        "source_region": "asia",
        "source_focus": "security",
        "source_weight": 1.1,
    },

    # First-party exchange announcements
    "Binance": {
        "input_type": "official_announcement",
        "source_tier": "tier_2",
        "source_region": "global",
        "source_focus": "exchange",
        "source_weight": 1.05,
    },
    "OKX": {
        "input_type": "official_announcement",
        "source_tier": "tier_2",
        "source_region": "global",
        "source_focus": "exchange",
        "source_weight": 1.05,
    },
    "Bybit": {
        "input_type": "official_announcement",
        "source_tier": "tier_2",
        "source_region": "global",
        "source_focus": "exchange",
        "source_weight": 1.05,
    },
}

TOPICS = {
    "Portfolio": [
        # Company names — specific enough to avoid false positives
        "mavrick", "cetus protocol", "cetus",
        "ola finance", "ola network", "ola protocol",
        "gravity protocol", "gravity chain", "gravity labs",
        "polyhedra", "zkbridge",
        "redbrick",
        "bbox", "apriori",
        "ethena", "ethena labs", "usde stablecoin",
        "cyber games arena",
        "solv protocol", "solv finance",
        "movement labs", "movement network",
        "sidekick",
        "hologram ai",
        "le poker",
        "gaib",
        "tonark",
        "sonic labs", "sonic chain", "sonic blockchain",
        "sonex",
        "gte protocol",
        "haedal",
        "kaiju",
        "gamerboom", "gamer boom",
        "cap protocol", "cap finance",
        "perena",
        "aspecta",
        "ratex",
        "nunchi",
        "echox",
        "stormbit",
    ],
    "Exchange Listings": [
        "now listed on binance", "binance lists", "binance will list",
        "now listed on coinbase", "coinbase lists", "coinbase adds",
        "now listed on okx", "okx lists", "okx will list",
        "now listed on bybit", "bybit lists",
        "now listed on kraken", "kraken lists",
        "new listing", "newly listed", "spot trading",
        "trading pair added", "token listing", "listing announcement",
    ],
    "Deal Flow & Funding": [
        "raises", "raised", "funding round", "series a", "series b", "seed round",
        "valuation", "backed by", "venture", "a16z", "andreessen", "paradigm",
        "dragonfly", "polychain", "multicoin", "pantera", "coinbase ventures",
        "binance labs", "y combinator", "ycombinator", "sequoia",
    ],
    "Infrastructure & Tech": [
        "layer 2", "l2", "rollup", "zk proof", "zero knowledge", "zkvm",
        "layer 1", "mainnet launch", "testnet", "account abstraction",
        "cross-chain", "bridge", "developer tool", "sdk",
        "solana", "arbitrum", "optimism", "base", "sui", "aptos",
    ],
    "Security & Exploits": [
        "hack", "hacked", "exploit", "exploited", "vulnerability", "bug",
        "stolen", "drained", "phishing", "scam", "fraud", "compromised",
        "private key", "multisig", "lazarus", "north korea", "freeze",
        "frozen", "seized", "security incident", "attack", "attacker",
        "被盗", "攻击", "漏洞", "黑客", "钓鱼", "私钥", "冻结", "安全事件",
    ],
    "Stablecoins & Payments": [
        "stablecoin", "stablecoins", "usdt", "usdc", "usde", "usdd",
        "tether", "circle", "payments", "payment", "remittance",
        "cross-border payment", "x402", "pay", "checkout", "merchant",
        "稳定币", "支付", "跨境支付", "汇款",
    ],
    "Governance & Protocol Updates": [
        "governance", "proposal", "vote", "dao", "aip", "upgrade",
        "roadmap", "protocol update", "foundation", "grant", "grants",
        "token unlock", "unlocking", "治理", "提案", "投票", "升级", "基金会",
    ],
    "Market Structure": [
        "market structure", "derivatives", "options", "futures", "perpetual",
        "volatility", "clearing", "custody", "trust charter", "occ charter",
        "broker", "dealer", "prediction market", "exchange-traded",
        "期权", "衍生品", "永续", "波动率", "托管", "预测市场",
    ],
    "RWA & Institutional": [
        "real world asset", "rwa", "tokenized", "tokenization", "tokenised",
        "on-chain treasury", "tokenized bond", "tokenized fund",
        "blackrock", "fidelity", "franklin templeton",
        "ondo", "centrifuge", "maple", "tradfi", "institutional",
        "spot etf", "bitcoin etf", "eth etf", "etf inflow", "etf outflow",
    ],
    "DeFi & New Primitives": [
        "defi", "decentralized finance", "tvl", "total value locked",
        "yield", "liquidity pool", "amm", "dex", "lending protocol",
        "stablecoin", "restaking", "liquid staking", "lrt", "lst",
        "uniswap", "aave", "compound", "curve", "eigenlayer",
        "perpetual", "derivatives", "options protocol",
    ],
    "Regulatory & Policy": [
        "sec", "cftc", "regulation", "regulatory", "congress", "senate",
        "legislation", "bill", "compliance", "enforcement", "lawsuit",
        "ban", "license", "framework", "policy", "government",
        "eu", "mica", "fatf", "aml", "kyc",
    ],
    "Macro & Market": [
        "federal reserve", "fed rate", "interest rate", "inflation", "cpi",
        "gdp", "recession", "treasury yield", "dollar",
        "bitcoin price", "btc", "ethereum price", "eth", "market cap",
        "all-time high", "ath", "rally", "correction", "bull", "bear",
        "inflows", "outflows", "liquidation", "open interest",
    ],
    "Emerging Narratives": [
        "ai agent", "ai x crypto", "onchain ai", "autonomous agent",
        "consumer crypto", "crypto gaming", "web3 game", "nft game",
        "social protocol", "decentralized social", "farcaster", "lens protocol",
        "desci", "depin", "physical infrastructure", "meme coin", "pump.fun",
    ],
}

TOPIC_EMOJI = {
    "Portfolio":             "🗂️",
    "Exchange Listings":     "📋",
    "Deal Flow & Funding":   "💰",
    "Infrastructure & Tech": "⚙️",
    "Security & Exploits":   "🚨",
    "Stablecoins & Payments":"💵",
    "Governance & Protocol Updates": "🗳️",
    "Market Structure":      "🏗️",
    "RWA & Institutional":   "🏦",
    "DeFi & New Primitives": "🔁",
    "Regulatory & Policy":   "⚖️",
    "Macro & Market":        "📊",
    "Emerging Narratives":   "🚀",
    "General":               "📌",
}
