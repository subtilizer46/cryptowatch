"""
dashboard/management/commands/seed_and_scrape.py

Custom Django management command.
Run with: python manage.py seed_and_scrape

Concepts:
- Custom management commands (BaseCommand)
- self.stdout.write() for colored output
- Initial data seeding
"""

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Seeds the database with default coins and runs the first scrape'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scrape-only',
            action='store_true',
            help='Skip seeding, just run a scrape',
        )

    def handle(self, *args, **options):
        from scraper.coingecko import DEFAULT_COINS, scrape_prices
        from dashboard.models import Coin

        if not options['scrape_only']:
            self.stdout.write(self.style.MIGRATE_HEADING('\n📦 Seeding default coins...'))
            for coin_data in DEFAULT_COINS:
                coin, created = Coin.objects.get_or_create(
                    symbol=coin_data['symbol'],
                    defaults={
                        'name': coin_data['name'],
                        'slug': coin_data['slug'],
                        'is_active': True,
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'  ✅ Created: {coin}'))
                else:
                    self.stdout.write(f'  ⚡ Already exists: {coin}')

        self.stdout.write(self.style.MIGRATE_HEADING('\n🔍 Running first price scrape...'))
        self.stdout.write('  (This may take 10-15 seconds...)\n')

        result = scrape_prices()

        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Done! Scraped {result["coins_scraped"]} coins '
                f'in {result["duration"]:.2f}s'
            ))
            self.stdout.write(self.style.SUCCESS('\n🚀 Visit http://localhost:8000 to see your dashboard!'))
        else:
            self.stdout.write(self.style.ERROR(
                f'\n❌ Scrape failed: {result.get("error", "Unknown error")}'
            ))
            self.stdout.write(self.style.WARNING(
                '  Tip: Check your internet connection. CoinGecko API may also be rate-limited.'
            ))
            self.stdout.write(self.style.WARNING(
                '  You can retry anytime with: python manage.py seed_and_scrape --scrape-only'
            ))
