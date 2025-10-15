from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.core'
    verbose_name = 'Core'

    def ready(self):
        """Import signals when app is ready."""
        try:
            import app.core.signals
        except ImportError:
            pass 