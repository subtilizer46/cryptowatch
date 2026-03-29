from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'

    def ready(self):
        """
        Called once when Django starts up.
        We use it to start the background scheduler.
        """
        import os
        # Only start in the main process, not in Django's auto-reloader child process
        if os.environ.get('RUN_MAIN') != 'true':
            from .scheduler import start_scheduler
            try:
                start_scheduler()
            except Exception as e:
                import logging
                logging.getLogger('dashboard').error(f"Could not start scheduler: {e}")
