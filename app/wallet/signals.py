from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import INRWallet, USDTWallet
from .services import WalletService


@receiver(post_save, sender=User)
def create_user_wallets(sender, instance, created, **kwargs):
    """Create wallets for new users."""
    if created:
        # Create INR wallet
        WalletService.get_or_create_inr_wallet(instance)
        # Create USDT wallet
        WalletService.get_or_create_usdt_wallet(instance)


# Signal removed to prevent double wallet saves
# @receiver(post_save, sender=User)
# def save_user_wallets(sender, instance, **kwargs):
#     """Save wallets when user is saved."""
#     if hasattr(instance, 'inr_wallet'):
#         instance.inr_wallet.save()
#     if hasattr(instance, 'usdt_wallet'):
#         instance.usdt_wallet.save() 