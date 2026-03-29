from django.urls import path
from . import views

urlpatterns = [
    # ── HTML Pages ────────────────────────────────────────────
    path('', views.dashboard, name='dashboard'),
    path('coin/<str:symbol>/', views.coin_detail, name='coin_detail'),

    # ── REST API ──────────────────────────────────────────────
    path('api/coins/', views.CoinListAPIView.as_view(), name='api_coins'),
    path('api/coins/<str:symbol>/history/', views.PriceHistoryAPIView.as_view(), name='api_history'),
    path('api/logs/', views.ScrapeLogsAPIView.as_view(), name='api_logs'),
    path('api/alerts/', views.AlertListCreateAPIView.as_view(), name='api_alerts'),
    path('api/alerts/<int:pk>/', views.AlertDeleteAPIView.as_view(), name='api_alert_delete'),

    # ── Actions ───────────────────────────────────────────────
    path('api/scrape/', views.trigger_scrape, name='api_scrape'),

    # ── CSV Exports ───────────────────────────────────────────
    # IMPORTANT: export/all/csv/ MUST be above export/<str:symbol>/csv/
    # Django matches top-to-bottom — if <str:symbol> comes first,
    # it captures the word "all" as a symbol and crashes with 404.
    path('export/all/csv/',          views.export_all_csv,   name='export_all_csv'),
    path('export/<str:symbol>/csv/', views.export_coin_csv,  name='export_coin_csv'),
]
