"""Central config: env-driven settings + source whitelist + tickers + cities + keyword weights.

Lists are module constants (hardcoded, version-controlled). Runtime knobs
(DB path, bind, cadence, retention) come from .env via pydantic-settings.
"""
from dataclasses import dataclass
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    db_path: str = "./data/news.db"
    host: str = "127.0.0.1"
    port: int = 8000
    news_interval_min: int = 15
    weather_interval_min: int = 60
    major_sticky_hours: int = 12
    article_retention_hours: int = 72
    log_level: str = "INFO"


settings = Settings()


# ---------- Sources ----------
@dataclass(frozen=True)
class Source:
    name: str
    domain: str
    fetcher: Literal["rss", "google_news"]
    url: str
    weight: float
    region: Literal["global", "gulf", "mixed"]


# Whitelist of professional, non-partisan sources. Free access only.
# Reuters / Bloomberg ME / Nikkei Asia pulled via Google News (no public RSS).
SOURCES: list[Source] = [
    # --- International wires / broadcasters ---
    Source("Associated Press", "apnews.com", "rss", "https://feeds.apnews.com/rss/apf-topnews", 1.00, "global"),
    Source("AP Business", "apnews.com", "rss", "https://feeds.apnews.com/rss/apf-business", 1.00, "global"),
    Source("Reuters", "reuters.com", "google_news",
           "https://news.google.com/rss/search?q=site:reuters.com+when:1d&hl=en-US&gl=US&ceid=US:en", 1.00, "global"),
    Source("BBC World", "bbc.co.uk", "rss", "http://feeds.bbci.co.uk/news/world/rss.xml", 0.90, "global"),
    Source("BBC Business", "bbc.co.uk", "rss", "http://feeds.bbci.co.uk/news/business/rss.xml", 0.90, "global"),
    Source("BBC Middle East", "bbc.co.uk", "rss", "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml", 0.95, "mixed"),
    Source("Deutsche Welle", "dw.com", "rss", "https://rss.dw.com/rdf/rss-en-all", 0.80, "global"),
    Source("France 24", "france24.com", "rss", "https://www.france24.com/en/rss", 0.80, "global"),
    Source("NPR Business", "npr.org", "rss", "https://feeds.npr.org/1006/rss.xml", 0.80, "global"),
    Source("Al Jazeera News", "aljazeera.com", "rss", "https://www.aljazeera.com/xml/rss/all.xml", 0.85, "mixed"),
    Source("CNBC Top", "cnbc.com", "rss", "https://www.cnbc.com/id/100003114/device/rss/rss.html", 0.85, "global"),
    Source("CNBC Markets", "cnbc.com", "rss", "https://www.cnbc.com/id/10000664/device/rss/rss.html", 0.85, "global"),
    Source("MarketWatch", "marketwatch.com", "rss", "http://feeds.marketwatch.com/marketwatch/topstories/", 0.80, "global"),
    Source("Bloomberg ME", "bloomberg.com", "google_news",
           "https://news.google.com/rss/search?q=site:bloomberg.com+middle+east+OR+gulf+OR+UAE+OR+saudi+when:1d&hl=en-US&gl=US&ceid=US:en", 0.95, "mixed"),
    Source("Nikkei Asia ME", "asia.nikkei.com", "google_news",
           "https://news.google.com/rss/search?q=site:asia.nikkei.com+middle+east+when:1d&hl=en-US&gl=US&ceid=US:en", 0.85, "mixed"),

    # --- Gulf / regional ---
    # Direct RSS for these four returns malformed XML (publisher-side); Google News is reliable.
    Source("The National", "thenationalnews.com", "google_news",
           "https://news.google.com/rss/search?q=site:thenationalnews.com+when:1d&hl=en-US&gl=US&ceid=US:en", 0.95, "gulf"),
    Source("Khaleej Times", "khaleejtimes.com", "google_news",
           "https://news.google.com/rss/search?q=site:khaleejtimes.com+when:1d&hl=en-US&gl=US&ceid=US:en", 0.85, "gulf"),
    Source("Gulf News", "gulfnews.com", "google_news",
           "https://news.google.com/rss/search?q=site:gulfnews.com+when:1d&hl=en-US&gl=US&ceid=US:en", 0.85, "gulf"),
    Source("Arab News", "arabnews.com", "google_news",
           "https://news.google.com/rss/search?q=site:arabnews.com+when:1d&hl=en-US&gl=US&ceid=US:en", 0.90, "gulf"),
    Source("Zawya", "zawya.com", "google_news",
           "https://news.google.com/rss/search?q=site:zawya.com+when:1d&hl=en-US&gl=US&ceid=US:en", 0.80, "gulf"),
    Source("MEED", "meed.com", "google_news",
           "https://news.google.com/rss/search?q=site:meed.com+when:1d&hl=en-US&gl=US&ceid=US:en", 0.85, "gulf"),
    Source("Gulf Business", "gulfbusiness.com", "google_news",
           "https://news.google.com/rss/search?q=site:gulfbusiness.com+when:1d&hl=en-US&gl=US&ceid=US:en", 0.75, "gulf"),
]


# ---------- Markets ----------
# Commodities + indices: stooq daily CSV. FX: open.er-api.com (single batch call).
# Gulf exchange indices other than Tadawul aren't available via any reliable free
# source. Upgrade path: add a paid vendor (Polygon/TwelveData) later if needed.
COMMODITIES: dict[str, str] = {
    "Brent Crude":   "cb.c",
    "WTI Crude":     "cl.c",
    "Gold":          "gc.c",
}

INDICES: dict[str, str] = {
    "S&P 500":       "^spx",
    "Dow Jones":     "^dji",
    "Nasdaq":        "^ndq",
    "Tadawul (KSA)": "^tasi",
}

# FX: (label, ISO currency to look up vs USD, invert?).
# open.er-api.com returns rates as USD->X. For EUR/USD we flip; for USD/XXX we don't.
FX_PAIRS: list[tuple[str, str, bool]] = [
    ("EUR/USD", "EUR", True),
    ("USD/AED", "AED", False),
    ("USD/SAR", "SAR", False),
    ("USD/QAR", "QAR", False),
    ("USD/KWD", "KWD", False),
    ("USD/BHD", "BHD", False),
    ("USD/OMR", "OMR", False),
    ("USD/EGP", "EGP", False),
]


# ---------- Weather ----------
# (name, latitude, longitude) — Open-Meteo takes lat/lon, no API key.
WEATHER_CITIES: list[tuple[str, float, float]] = [
    ("Dubai",       25.2048, 55.2708),
    ("Abu Dhabi",   24.4539, 54.3773),
    ("Riyadh",      24.7136, 46.6753),
    ("Doha",        25.2854, 51.5310),
    ("Kuwait City", 29.3759, 47.9774),
    ("Manama",      26.2285, 50.5860),
    ("Muscat",      23.5880, 58.3829),
]


# ---------- Classifier keywords ----------
# Higher weight = more important. Negative keywords discount the article.
KEYWORDS: dict[str, dict[str, float]] = {
    "gulf": {
        "uae": 1.5, "dubai": 1.5, "abu dhabi": 1.5, "sharjah": 1.0,
        "saudi": 1.5, "saudi arabia": 1.5, "riyadh": 1.2, "jeddah": 1.0,
        "qatar": 1.3, "doha": 1.2,
        "kuwait": 1.2, "bahrain": 1.0, "oman": 1.0, "muscat": 1.0,
        "gcc": 1.4, "gulf cooperation": 1.4, "emirates": 1.2,
        "aramco": 1.6, "adnoc": 1.6, "mubadala": 1.4, "pif": 1.4,
        "public investment fund": 1.4, "sama": 1.2, "difc": 1.2, "adgm": 1.2,
        "dp world": 1.3, "emaar": 1.1, "etihad": 1.0, "emirates airline": 1.0,
        "neom": 1.2, "red sea global": 1.0,
    },
    "iran_war": {
        "iran": 1.2, "tehran": 1.1, "irgc": 1.1, "revolutionary guard": 1.1,
        "israel": 1.0, "gaza": 1.0, "hezbollah": 1.0, "lebanon": 0.9,
        "houthi": 1.2, "yemen": 1.0, "red sea": 1.2,
        "strait of hormuz": 1.5, "hormuz": 1.3,
    },
    "oil_markets": {
        "opec": 1.3, "opec+": 1.3, "brent": 1.1, "wti": 1.0, "crude oil": 1.1,
        "barrel": 0.7, "lng": 1.0, "refinery": 0.8, "oil price": 1.1,
        "oil cut": 1.2, "production cut": 1.2,
    },
    "markets_macro": {
        "federal reserve": 0.9, "fed rate": 1.0, "ecb": 0.8, "interest rate": 0.8,
        "inflation": 0.7, "recession": 0.9, "gdp": 0.6, "bond yield": 0.7,
        "treasury": 0.6, "s&p 500": 0.7, "nasdaq": 0.6,
    },
    # Negative — discounted. Ukraine/Russia drops unless oil-adjacent (handled in classifier).
    "drop": {
        "ukraine": -1.2, "kyiv": -1.2, "zelensky": -1.2,
        "russia": -0.6, "moscow": -0.8, "putin": -0.6,
        "celebrity": -2.0, "entertainment": -2.0, "royal wedding": -2.0,
        "football": -1.5, "soccer": -1.5, "world cup": -1.0,
        "recipe": -2.0, "lifestyle": -1.5, "horoscope": -3.0,
    },
}

# Region bucket base multipliers applied after keyword hits.
REGION_WEIGHTS: dict[str, float] = {
    "gulf": 1.5,
    "iran_war": 1.1,
    "oil_markets": 1.1,
    "markets_macro": 0.9,
    "global": 0.7,
    "drop": 0.0,
}
