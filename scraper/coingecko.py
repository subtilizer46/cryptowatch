"""
scraper/coingecko.py

Data scraping module using CoinGecko's FREE public API.
No API key needed. We use requests + manual JSON parsing (same concept as BeautifulSoup).

Concepts covered:
- requests.get() with headers and timeout
- Rate limiting / retry logic
- Data cleaning and validation
- Error handling
- Saving scraped data to Django ORM
"""

import time
import logging
import requests
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.utils import timezone

logger = logging.getLogger('dashboard')

# CoinGecko free API — no key needed, but rate limited to ~10-30 req/min
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Default coins to track — these are CoinGecko slugs
# Tier 1 — Large Cap
DEFAULT_COINS = [
    {"slug": "bitcoin",            "symbol": "BTC",   "name": "Bitcoin"},
    {"slug": "ethereum",           "symbol": "ETH",   "name": "Ethereum"},
    {"slug": "binancecoin",        "symbol": "BNB",   "name": "BNB"},
    {"slug": "solana",             "symbol": "SOL",   "name": "Solana"},
    {"slug": "ripple",             "symbol": "XRP",   "name": "XRP"},
    {"slug": "cardano",            "symbol": "ADA",   "name": "Cardano"},
    {"slug": "dogecoin",           "symbol": "DOGE",  "name": "Dogecoin"},
    {"slug": "polkadot",           "symbol": "DOT",   "name": "Polkadot"},
    {"slug": "avalanche-2",        "symbol": "AVAX",  "name": "Avalanche"},
    {"slug": "chainlink",          "symbol": "LINK",  "name": "Chainlink"},
    # Tier 2 — Mid Cap
    {"slug": "litecoin",           "symbol": "LTC",   "name": "Litecoin"},
    {"slug": "uniswap",            "symbol": "UNI",   "name": "Uniswap"},
    {"slug": "stellar",            "symbol": "XLM",   "name": "Stellar"},
    {"slug": "monero",             "symbol": "XMR",   "name": "Monero"},
    {"slug": "ethereum-classic",   "symbol": "ETC",   "name": "Ethereum Classic"},
    {"slug": "filecoin",           "symbol": "FIL",   "name": "Filecoin"},
    {"slug": "cosmos",             "symbol": "ATOM",  "name": "Cosmos"},
    {"slug": "near",               "symbol": "NEAR",  "name": "NEAR Protocol"},
    {"slug": "internet-computer",  "symbol": "ICP",   "name": "Internet Computer"},
    {"slug": "aptos",              "symbol": "APT",   "name": "Aptos"},
    # Tier 3 — Trending / DeFi / Meme
    {"slug": "shiba-inu",          "symbol": "SHIB",  "name": "Shiba Inu"},
    {"slug": "pepe",               "symbol": "PEPE",  "name": "Pepe"},
    {"slug": "the-sandbox",        "symbol": "SAND",  "name": "The Sandbox"},
    {"slug": "decentraland",       "symbol": "MANA",  "name": "Decentraland"},
    {"slug": "aave",               "symbol": "AAVE",  "name": "Aave"},
]

# ─── HTTP Session ────────────────────────────────────────────────────────────

def get_session():
    """
    Create a requests.Session with headers that look like a real browser.
    Sessions reuse TCP connections — more efficient than repeated requests.get().
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session


# ─── Core Scraping Functions ─────────────────────────────────────────────────

def fetch_with_retry(session, url, params=None, retries=3, backoff=2):
    """
    Fetch a URL with automatic retry on failure.

    Args:
        session: requests.Session object
        url: URL to fetch
        params: query parameters dict
        retries: number of attempts
        backoff: seconds to wait between retries (doubles each time)

    Returns:
        dict (parsed JSON) or None on failure
    """
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Fetching {url} (attempt {attempt}/{retries})")
            response = session.get(url, params=params, timeout=15)

            # Check for rate limiting
            if response.status_code == 429:
                wait = backoff * (2 ** attempt)
                logger.warning(f"Rate limited. Waiting {wait}s before retry...")
                time.sleep(wait)
                continue

            response.raise_for_status()  # Raises HTTPError for 4xx/5xx
            return response.json()

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error on attempt {attempt}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            break  # Don't retry on 4xx errors
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

        if attempt < retries:
            time.sleep(backoff * attempt)

    return None


def scrape_prices():
    """
    Main scraping function. Fetches current prices for all tracked coins.

    CoinGecko /coins/markets endpoint returns everything we need in one call:
    price, market_cap, volume, 24h change, etc.

    Returns:
        dict with 'success', 'data', 'failed' keys
    """
    from dashboard.models import Coin, PriceSnapshot, ScrapeLog, WatchlistAlert

    start_time = time.time()
    log = ScrapeLog.objects.create(status='failed', started_at=timezone.now())

    session = get_session()
    coin_ids = [c["slug"] for c in DEFAULT_COINS]

    # ── Step 1: Ensure all coins exist in DB ──────────────────────────────
    for coin_data in DEFAULT_COINS:
        Coin.objects.get_or_create(
            symbol=coin_data["symbol"],
            defaults={
                "name": coin_data["name"],
                "slug": coin_data["slug"],
                "is_active": True,
            }
        )

    # ── Step 2: Fetch price data from CoinGecko ───────────────────────────
    params = {
        "vs_currency": "usd",
        "ids": ",".join(coin_ids),
        "order": "market_cap_desc",
        "per_page": 50,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "24h,7d",
    }

    data = fetch_with_retry(session, f"{COINGECKO_BASE}/coins/markets", params=params)

    if not data:
        log.status = 'failed'
        log.error_message = "Failed to fetch data from CoinGecko after retries"
        log.completed_at = timezone.now()
        log.duration_seconds = time.time() - start_time
        log.save()
        return {"success": False, "error": log.error_message}

    # ── Step 3: Parse and save each coin's data ───────────────────────────
    coins_scraped = 0
    coins_failed = 0
    snapshots_created = []

    for item in data:
        try:
            coin_id = item.get("id")  # e.g., "bitcoin"
            coin = Coin.objects.filter(slug=coin_id).first()
            if not coin:
                logger.warning(f"Unknown coin slug: {coin_id}")
                continue

            # Update logo URL if we have it
            logo = item.get("image")
            if logo and not coin.logo_url:
                coin.logo_url = logo
                coin.save(update_fields=["logo_url"])

            # ── Data cleaning ─────────────────────────────────────────────
            # safe_decimal() converts any value to Decimal, returns None if invalid
            def safe_decimal(value, default=None):
                if value is None:
                    return default
                try:
                    return Decimal(str(value))
                except (InvalidOperation, ValueError):
                    return default

            price = safe_decimal(item.get("current_price"))
            if price is None:
                logger.error(f"No price for {coin_id}, skipping")
                coins_failed += 1
                continue

            snapshot = PriceSnapshot.objects.create(
                coin=coin,
                price_usd=price,
                market_cap_usd=safe_decimal(item.get("market_cap")),
                volume_24h_usd=safe_decimal(item.get("total_volume")),
                change_24h_pct=safe_decimal(item.get("price_change_percentage_24h")),
                change_7d_pct=safe_decimal(item.get("price_change_percentage_7d_in_currency")),
                high_24h=safe_decimal(item.get("high_24h")),
                low_24h=safe_decimal(item.get("low_24h")),
                scraped_at=timezone.now(),
            )
            snapshots_created.append(snapshot)
            coins_scraped += 1

            # ── Check alerts ──────────────────────────────────────────────
            check_alerts(coin, price)

        except Exception as e:
            logger.error(f"Error processing {item.get('id', 'unknown')}: {e}")
            coins_failed += 1

    # ── Step 4: Update scrape log ─────────────────────────────────────────
    duration = time.time() - start_time
    status = 'success' if coins_failed == 0 else ('partial' if coins_scraped > 0 else 'failed')

    log.status = status
    log.coins_scraped = coins_scraped
    log.coins_failed = coins_failed
    log.duration_seconds = round(duration, 2)
    log.completed_at = timezone.now()
    log.save()

    logger.info(
        f"Scrape complete: {coins_scraped} success, {coins_failed} failed, {duration:.2f}s"
    )

    return {
        "success": True,
        "coins_scraped": coins_scraped,
        "coins_failed": coins_failed,
        "duration": duration,
    }


def check_alerts(coin, current_price):
    """
    Check if any price alerts should be triggered for this coin.
    Called after each successful price scrape.
    """
    from dashboard.models import WatchlistAlert

    active_alerts = WatchlistAlert.objects.filter(
        coin=coin,
        is_triggered=False
    )

    for alert in active_alerts:
        triggered = False
        if alert.condition == 'above' and current_price >= alert.target_price:
            triggered = True
        elif alert.condition == 'below' and current_price <= alert.target_price:
            triggered = True

        if triggered:
            alert.is_triggered = True
            alert.triggered_at = timezone.now()
            alert.save()
            logger.info(
                f"ALERT TRIGGERED: {coin.symbol} is "
                f"{'above' if alert.condition == 'above' else 'below'} "
                f"${alert.target_price} (current: ${current_price})"
            )
