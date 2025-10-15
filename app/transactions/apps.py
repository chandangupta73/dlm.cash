from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.transactions'
    verbose_name = 'Transactions'
    
    def ready(self):
        """Import signals when the app is ready."""
        try:
            import app.transactions.signals
        except ImportError:
            pass
