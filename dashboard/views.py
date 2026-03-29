"""
dashboard/views.py

Contains:
 1. HTML views  — render templates (the dashboard page)
 2. REST API views — return JSON (used by JavaScript for live updates)
 3. Action views  — trigger scrape, create alerts, etc.

Concepts covered:
 - Function-based views (FBV)
 - Class-based views using DRF APIView
 - QuerySets with annotate, aggregate, select_related
 - JSON responses
 - Error handling in views
"""

import csv
import logging
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Avg, Min, Max, Count
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Coin, PriceSnapshot, ScrapeLog, WatchlistAlert
from .serializers import (
    CoinSerializer,
    PriceSnapshotSerializer,
    ScrapeLogSerializer,
    WatchlistAlertSerializer,
)

logger = logging.getLogger('dashboard')


# ══════════════════════════════════════════════════════════════════════════════
# HTML VIEWS — Return rendered HTML templates
# ══════════════════════════════════════════════════════════════════════════════

def dashboard(request):
    """
    Main dashboard page.
    Pre-fetches data server-side for the initial page load.
    The JS frontend then uses the REST API for live updates.
    """
    # Get all active coins with their latest price
    coins = Coin.objects.filter(is_active=True)

    # Build a list of coins with their latest snapshot
    coin_data = []
    for coin in coins:
        latest = coin.latest_price()
        if latest:
            coin_data.append({
                "coin": coin,
                "snapshot": latest,
            })

    # Recent scrape logs (last 5)
    recent_logs = ScrapeLog.objects.all()[:5]

    # Stats
    total_snapshots = PriceSnapshot.objects.count()
    last_scrape = ScrapeLog.objects.filter(status='success').first()

    context = {
        "coin_data": coin_data,
        "recent_logs": recent_logs,
        "total_snapshots": total_snapshots,
        "last_scrape": last_scrape,
        "page_title": "CryptoWatch Dashboard",
    }
    return render(request, "dashboard/index.html", context)


def coin_detail(request, symbol):
    """
    Detail page for a single coin showing price history chart.
    """
    coin = get_object_or_404(Coin, symbol=symbol.upper())

    # Last 50 snapshots for the chart
    snapshots = coin.price_snapshots.all()[:50]
    # Reverse for chronological order in chart
    snapshots_list = list(reversed(list(snapshots)))

    # 24h stats
    stats = coin.price_snapshots.aggregate(
        avg_price=Avg('price_usd'),
        min_price=Min('price_usd'),
        max_price=Max('price_usd'),
    )

    # Active alerts for this coin
    alerts = WatchlistAlert.objects.filter(coin=coin, is_triggered=False)

    context = {
        "coin": coin,
        "snapshots": snapshots_list,
        "stats": stats,
        "alerts": alerts,
        "latest": coin.latest_price(),
        "page_title": f"{coin.name} ({coin.symbol})",
    }
    return render(request, "dashboard/coin_detail.html", context)


# ══════════════════════════════════════════════════════════════════════════════
# REST API VIEWS — Return JSON
# ══════════════════════════════════════════════════════════════════════════════

class CoinListAPIView(APIView):
    """
    GET /api/coins/
    Returns all active coins with their latest price.
    Used by the dashboard for live price refresh.
    """
    def get(self, request):
        coins = Coin.objects.filter(is_active=True)
        result = []
        for coin in coins:
            latest = coin.latest_price()
            if latest:
                coin_data = CoinSerializer(coin).data
                snapshot_data = PriceSnapshotSerializer(latest).data
                coin_data['latest'] = snapshot_data
                result.append(coin_data)

        return Response(result)


class PriceHistoryAPIView(APIView):
    """
    GET /api/coins/<symbol>/history/?limit=50
    Returns price history for a specific coin.
    Used for the chart on the detail page.
    """
    def get(self, request, symbol):
        coin = get_object_or_404(Coin, symbol=symbol.upper())
        limit = int(request.query_params.get('limit', 50))

        snapshots = coin.price_snapshots.all()[:limit]
        # Reverse for chronological order
        snapshots = list(reversed(list(snapshots)))

        serializer = PriceSnapshotSerializer(snapshots, many=True)
        return Response({
            "coin": CoinSerializer(coin).data,
            "history": serializer.data,
        })


class ScrapeLogsAPIView(APIView):
    """
    GET /api/logs/
    Returns recent scrape logs.
    """
    def get(self, request):
        logs = ScrapeLog.objects.all()[:20]
        serializer = ScrapeLogSerializer(logs, many=True)
        return Response(serializer.data)


class AlertListCreateAPIView(APIView):
    """
    GET  /api/alerts/         — list all alerts
    POST /api/alerts/         — create a new alert
    """
    def get(self, request):
        alerts = WatchlistAlert.objects.select_related('coin').all()
        serializer = WatchlistAlertSerializer(alerts, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = WatchlistAlertSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AlertDeleteAPIView(APIView):
    """
    DELETE /api/alerts/<id>/  — delete an alert
    """
    def delete(self, request, pk):
        alert = get_object_or_404(WatchlistAlert, pk=pk)
        alert.delete()
        return Response({"message": "Alert deleted"}, status=status.HTTP_204_NO_CONTENT)


# ══════════════════════════════════════════════════════════════════════════════
# ACTION VIEWS — Trigger operations
# ══════════════════════════════════════════════════════════════════════════════

@require_http_methods(["POST"])
def trigger_scrape(request):
    """
    POST /api/scrape/
    Manually triggers a scrape. Used by the 'Refresh Now' button in the UI.
    In production this runs automatically via APScheduler.
    """
    from scraper.coingecko import scrape_prices
    try:
        result = scrape_prices()
        return JsonResponse({
            "success": result.get("success", False),
            "coins_scraped": result.get("coins_scraped", 0),
            "message": f"Scraped {result.get('coins_scraped', 0)} coins successfully"
        })
    except Exception as e:
        logger.error(f"Manual scrape failed: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["DELETE"])
def delete_alert(request, pk):
    alert = get_object_or_404(WatchlistAlert, pk=pk)
    alert.delete()
    return JsonResponse({"success": True})


# ══════════════════════════════════════════════════════════════════════════════
# CSV EXPORT VIEWS
# ══════════════════════════════════════════════════════════════════════════════

def export_coin_csv(request, symbol):
    """
    GET /export/<symbol>/csv/?limit=200
    Downloads a CSV file of price history for one coin.

    How it works:
    - HttpResponse with content_type='text/csv' tells the browser it's a file download
    - Content-Disposition header with 'attachment' triggers the Save dialog
    - csv.writer writes rows directly into the response object (it acts like a file)
    """
    coin = get_object_or_404(Coin, symbol=symbol.upper())
    limit = int(request.GET.get('limit', 200))

    # Build the HTTP response as a CSV file download
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="{coin.symbol}_price_history.csv"'
    )

    writer = csv.writer(response)

    # Header row
    writer.writerow([
        'Timestamp',
        'Price (USD)',
        '24h Change (%)',
        '7d Change (%)',
        'Market Cap (USD)',
        'Volume 24h (USD)',
        '24h High',
        '24h Low',
    ])

    # Data rows — newest first (default ordering from model)
    snapshots = coin.price_snapshots.all()[:limit]
    for snap in snapshots:
        writer.writerow([
            snap.scraped_at.strftime('%Y-%m-%d %H:%M:%S'),
            snap.price_usd,
            snap.change_24h_pct if snap.change_24h_pct is not None else '',
            snap.change_7d_pct  if snap.change_7d_pct  is not None else '',
            snap.market_cap_usd if snap.market_cap_usd is not None else '',
            snap.volume_24h_usd if snap.volume_24h_usd is not None else '',
            snap.high_24h       if snap.high_24h       is not None else '',
            snap.low_24h        if snap.low_24h        is not None else '',
        ])

    logger.info(f"CSV export: {coin.symbol}, {snapshots.count()} rows")
    return response


def export_all_csv(request):
    """
    GET /export/all/csv/
    Downloads a single CSV with the LATEST price snapshot for every coin.
    Useful for a quick portfolio snapshot.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="cryptowatch_snapshot.csv"'

    writer = csv.writer(response)

    # Header
    writer.writerow([
        'Symbol',
        'Name',
        'Price (USD)',
        '24h Change (%)',
        '7d Change (%)',
        'Market Cap (USD)',
        'Volume 24h (USD)',
        '24h High',
        '24h Low',
        'Last Updated',
    ])

    coins = Coin.objects.filter(is_active=True).order_by('symbol')
    for coin in coins:
        latest = coin.latest_price()
        if not latest:
            continue
        writer.writerow([
            coin.symbol,
            coin.name,
            latest.price_usd,
            latest.change_24h_pct if latest.change_24h_pct is not None else '',
            latest.change_7d_pct  if latest.change_7d_pct  is not None else '',
            latest.market_cap_usd if latest.market_cap_usd is not None else '',
            latest.volume_24h_usd if latest.volume_24h_usd is not None else '',
            latest.high_24h       if latest.high_24h       is not None else '',
            latest.low_24h        if latest.low_24h        is not None else '',
            latest.scraped_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])

    return response
