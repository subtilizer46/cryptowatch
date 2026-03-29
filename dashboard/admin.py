"""
dashboard/admin.py

Register models with Django Admin so you can view/manage data at /admin/
Concepts: ModelAdmin customization, list_display, list_filter, search_fields
"""

from django.contrib import admin
from .models import Coin, PriceSnapshot, ScrapeLog, WatchlistAlert


@admin.register(Coin)
class CoinAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'slug', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['symbol', 'name']


@admin.register(PriceSnapshot)
class PriceSnapshotAdmin(admin.ModelAdmin):
    list_display = ['coin', 'price_usd', 'change_24h_pct', 'volume_24h_usd', 'scraped_at']
    list_filter = ['coin']
    search_fields = ['coin__symbol']
    readonly_fields = ['scraped_at']
    date_hierarchy = 'scraped_at'


@admin.register(ScrapeLog)
class ScrapeLogAdmin(admin.ModelAdmin):
    list_display = ['status', 'coins_scraped', 'coins_failed', 'duration_seconds', 'started_at']
    list_filter = ['status']
    readonly_fields = ['started_at', 'completed_at']


@admin.register(WatchlistAlert)
class WatchlistAlertAdmin(admin.ModelAdmin):
    list_display = ['coin', 'condition', 'target_price', 'is_triggered', 'created_at']
    list_filter = ['condition', 'is_triggered']
