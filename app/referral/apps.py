from django.apps import AppConfig


class ReferralConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.referral'
    verbose_name = 'Referral System'
    
    def ready(self):
        """Import signals when app is ready."""
        import app.referral.signals



