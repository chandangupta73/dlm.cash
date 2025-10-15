from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from app.wallet.models import INRWallet, USDTWallet, WalletAddress
from app.crud.wallet import WalletService, WalletAddressService

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_wallets(sender, instance, created, **kwargs):
    """Create wallets and wallet addresses for all chains for new users."""
    if created:
        # Create INR wallet
        WalletService.get_or_create_inr_wallet(instance)
        # Create USDT wallet
        WalletService.get_or_create_usdt_wallet(instance)
        # Create wallet addresses for ERC20/BEP20 (same address)
        WalletAddressService.get_or_create_wallet_address(instance, 'erc20')


# Signal removed to prevent double wallet saves
# @receiver(post_save, sender=User)
# def save_user_wallets(sender, instance, **kwargs):
#     """Save wallets when user is saved."""
#     if hasattr(instance, 'inr_wallet'):
#         instance.inr_wallet.save()
#     if hasattr(instance, 'usdt_wallet'):
#         instance.usdt_wallet.save()
#     # Save all wallet addresses
#     for wallet_address in instance.wallet_addresses.all():
#         wallet_address.save() 