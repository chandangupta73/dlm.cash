from django.apps import AppConfig


class WalletConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.wallet'
    verbose_name = 'Wallet Management'
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            import app.wallet.signals
        except ImportError:
            pass 