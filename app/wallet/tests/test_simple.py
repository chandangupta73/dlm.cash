from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from decimal import Decimal

from app.wallet.models import INRWallet, USDTWallet
from app.wallet.signals import create_user_wallets, save_user_wallets
from app.core.signals import create_user_wallets as core_create_user_wallets, save_user_wallets as core_save_user_wallets

User = get_user_model()

class SimpleWalletTest(TestCase):
    """Simple test to isolate the database issue."""

    def setUp(self):
        """Disable wallet creation signals for this test."""
        # Disconnect the wallet app signals
        post_save.disconnect(create_user_wallets, sender=User)
        post_save.disconnect(save_user_wallets, sender=User)
        
        # Disconnect the core app signals
        post_save.disconnect(core_create_user_wallets, sender=User)
        post_save.disconnect(core_save_user_wallets, sender=User)

    def tearDown(self):
        """Reconnect wallet creation signals after test."""
        # Reconnect the wallet app signals
        post_save.connect(create_user_wallets, sender=User)
        post_save.connect(save_user_wallets, sender=User)
        
        # Reconnect the core app signals
        post_save.connect(core_create_user_wallets, sender=User)
        post_save.connect(core_save_user_wallets, sender=User)

    def test_simple_inr_wallet_creation(self):
        """Test simple INR wallet creation."""
        user = User.objects.create_user(
            username='simpleuser1',
            email='simple1@example.com',
            password='testpass123'
        )
        
        # Create new wallet since signals are disabled
        wallet = INRWallet.objects.create(
            user=user,
            balance=Decimal('100.00'),
            status='active',
            is_active=True
        )
        
        self.assertEqual(wallet.balance, Decimal('100.00'))
        self.assertEqual(wallet.status, 'active')
        self.assertTrue(wallet.is_active)

    def test_simple_usdt_wallet_creation(self):
        """Test simple USDT wallet creation."""
        user = User.objects.create_user(
            username='simpleuser2',
            email='simple2@example.com',
            password='testpass123'
        )
        
        # Create new wallet since signals are disabled
        wallet = USDTWallet.objects.create(
            user=user,
            balance=Decimal('50.000000'),
            wallet_address='0x1234567890abcdef1234567890abcdef12345678',
            chain_type='erc20',
            is_real_wallet=False
        )
        
        self.assertEqual(wallet.balance, Decimal('50.000000'))
        self.assertEqual(wallet.chain_type, 'erc20')
        self.assertTrue(wallet.is_active)
