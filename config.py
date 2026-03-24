TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHANNEL_ID = "@your_channel"  # or numeric ID like -100xxxxxxxxx

FEEDS = [
    {"name": "CoinDesk",      "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss"},
    {"name": "The Block",     "url": "https://www.theblock.co/rss.xml"},
    {"name": "Decrypt",       "url": "https://decrypt.co/feed"},
    {"name": "Blockworks",    "url": "https://blockworks.co/feed"},
    {"name": "Reuters",       "url": "https://feeds.reuters.com/reuters/businessNews"},
    {"name": "FT",            "url": "https://www.ft.com/rss/home"},
]

TOPICS = {
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
    "Deal Flow & Funding":   "💰",
    "Infrastructure & Tech": "⚙️",
    "RWA & Institutional":   "🏦",
    "DeFi & New Primitives": "🔁",
    "Regulatory & Policy":   "⚖️",
    "Macro & Market":        "📊",
    "Emerging Narratives":   "🚀",
    "General":               "📌",
}
