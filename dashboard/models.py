from django.db import models
from django.utils import timezone


class Coin(models.Model):
    """
    Represents a tracked cryptocurrency.
    Each coin has a symbol (BTC), name (Bitcoin), and metadata.
    """
    symbol = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)  # used in CoinGecko URLs
    logo_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['symbol']

    def __str__(self):
        return f"{self.symbol} - {self.name}"

    def latest_price(self):
        """Get the most recent price snapshot for this coin."""
        return self.price_snapshots.order_by('-scraped_at').first()


class PriceSnapshot(models.Model):
    """
    A single price data point for a coin at a specific time.
    Scraped from CoinGecko's public API.
    This is the core time-series data table.
    """
    coin = models.ForeignKey(
        Coin,
        on_delete=models.CASCADE,
        related_name='price_snapshots'
    )
    price_usd = models.DecimalField(max_digits=20, decimal_places=8)
    market_cap_usd = models.DecimalField(max_digits=30, decimal_places=2, null=True, blank=True)
    volume_24h_usd = models.DecimalField(max_digits=30, decimal_places=2, null=True, blank=True)
    change_24h_pct = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    change_7d_pct = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    high_24h = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    low_24h = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    scraped_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-scraped_at']
        indexes = [
            models.Index(fields=['coin', 'scraped_at']),
        ]

    def __str__(self):
        return f"{self.coin.symbol} @ ${self.price_usd} ({self.scraped_at:%Y-%m-%d %H:%M})"

    @property
    def change_24h_color(self):
        """Returns 'positive', 'negative', or 'neutral' for UI styling."""
        if self.change_24h_pct is None:
            return 'neutral'
        if self.change_24h_pct > 0:
            return 'positive'
        if self.change_24h_pct < 0:
            return 'negative'
        return 'neutral'


class ScrapeLog(models.Model):
    """
    Tracks every scrape attempt — success or failure.
    Good practice: always log your scraping jobs for debugging.
    """
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed'),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    coins_scraped = models.IntegerField(default=0)
    coins_failed = models.IntegerField(default=0)
    duration_seconds = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Scrape [{self.status}] at {self.started_at:%Y-%m-%d %H:%M} — {self.coins_scraped} coins"


class WatchlistAlert(models.Model):
    """
    User-defined price alerts.
    Example: "Alert me when BTC goes above $70,000"
    """
    CONDITION_CHOICES = [
        ('above', 'Price goes above'),
        ('below', 'Price goes below'),
    ]

    coin = models.ForeignKey(Coin, on_delete=models.CASCADE, related_name='alerts')
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES)
    target_price = models.DecimalField(max_digits=20, decimal_places=8)
    is_triggered = models.BooleanField(default=False)
    triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alert: {self.coin.symbol} {self.condition} ${self.target_price}"
