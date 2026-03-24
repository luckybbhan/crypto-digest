TELEGRAM_BOT_TOKEN = "8382725878:AAGqb-IwoPxSThcmSvo1AhoV7DfNXqecjGY"
TELEGRAM_CHANNEL_ID = "-1003723061243"

DEEPSEEK_API_KEY = "sk-9a0e263cdd8e4883b8ae6ae501260c59"

FEEDS = [
    {"name": "CoinDesk",      "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss"},
    {"name": "The Block",     "url": "https://www.theblock.co/rss.xml"},
    {"name": "Decrypt",       "url": "https://decrypt.co/feed"},
    {"name": "Blockworks",    "url": "https://blockworks.co/feed"},
    {"name": "Reuters",       "url": "https://feeds.reuters.com/reuters/technologyNews"},
    {"name": "Investing.com", "url": "https://www.investing.com/rss/news_301.rss"},
    # Exchange announcement feeds
    {"name": "Coinbase Blog", "url": "https://blog.coinbase.com/feed"},
]

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
    "RWA & Institutional":   "🏦",
    "DeFi & New Primitives": "🔁",
    "Regulatory & Policy":   "⚖️",
    "Macro & Market":        "📊",
    "Emerging Narratives":   "🚀",
    "General":               "📌",
}
