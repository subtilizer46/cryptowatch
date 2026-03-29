"""
dashboard/serializers.py

DRF Serializers — convert Django model instances to/from JSON.
Think of them as a schema layer between your database and API responses.

Concepts covered:
- ModelSerializer (auto-generates fields from model)
- SerializerMethodField (compute custom values)
- Nested serializers
- Custom validation
"""

from rest_framework import serializers
from .models import Coin, PriceSnapshot, ScrapeLog, WatchlistAlert


class CoinSerializer(serializers.ModelSerializer):
    """Serializes a Coin model to JSON."""

    class Meta:
        model = Coin
        fields = ['id', 'symbol', 'name', 'slug', 'logo_url', 'is_active']


class PriceSnapshotSerializer(serializers.ModelSerializer):
    """
    Serializes a PriceSnapshot.
    We add a human-readable 'scraped_at_formatted' field using SerializerMethodField.
    """
    scraped_at_formatted = serializers.SerializerMethodField()
    change_24h_color = serializers.SerializerMethodField()

    class Meta:
        model = PriceSnapshot
        fields = [
            'id',
            'coin_id',
            'price_usd',
            'market_cap_usd',
            'volume_24h_usd',
            'change_24h_pct',
            'change_7d_pct',
            'high_24h',
            'low_24h',
            'scraped_at',
            'scraped_at_formatted',
            'change_24h_color',
        ]

    def get_scraped_at_formatted(self, obj):
        """Returns human-readable timestamp like '12 Jan 2025, 14:30'"""
        return obj.scraped_at.strftime('%d %b %Y, %H:%M')

    def get_change_24h_color(self, obj):
        return obj.change_24h_color


class ScrapeLogSerializer(serializers.ModelSerializer):
    """Serializes ScrapeLog for the activity feed."""
    started_at_formatted = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = ScrapeLog
        fields = [
            'id',
            'status',
            'status_display',
            'coins_scraped',
            'coins_failed',
            'duration_seconds',
            'error_message',
            'started_at',
            'started_at_formatted',
        ]

    def get_started_at_formatted(self, obj):
        return obj.started_at.strftime('%d %b, %H:%M:%S')

    def get_status_display(self, obj):
        return obj.get_status_display()


class WatchlistAlertSerializer(serializers.ModelSerializer):
    """
    Serializes WatchlistAlert.
    Includes coin symbol via SerializerMethodField for display.
    Uses custom validation to ensure target_price is positive.
    """
    coin_symbol = serializers.SerializerMethodField(read_only=True)
    coin_name = serializers.SerializerMethodField(read_only=True)
    condition_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = WatchlistAlert
        fields = [
            'id',
            'coin',
            'coin_symbol',
            'coin_name',
            'condition',
            'condition_display',
            'target_price',
            'is_triggered',
            'triggered_at',
            'created_at',
        ]
        read_only_fields = ['is_triggered', 'triggered_at', 'created_at']

    def get_coin_symbol(self, obj):
        return obj.coin.symbol

    def get_coin_name(self, obj):
        return obj.coin.name

    def get_condition_display(self, obj):
        return obj.get_condition_display()

    def validate_target_price(self, value):
        """Custom field-level validation."""
        if value <= 0:
            raise serializers.ValidationError("Target price must be greater than 0.")
        return value

    def validate(self, data):
        """Object-level validation (cross-field checks)."""
        # Could add more complex validation here, e.g., check if coin exists and is active
        return data
