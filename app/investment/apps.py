from django.apps import AppConfig


class InvestmentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.investment'
    verbose_name = 'Investment Management'

    def ready(self):
        """Import signals when app is ready."""
        import app.investment.signals
