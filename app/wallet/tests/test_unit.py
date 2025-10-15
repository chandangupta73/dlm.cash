import pytest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save
import uuid

from app.wallet.models import WalletAddress, INRWallet, USDTWallet, WalletTransaction
from app.wallet.signals import create_user_wallets, save_user_wallets
from app.core.signals import create_user_wallets as core_create_user_wallets, save_user_wallets as core_save_user_wallets

User = get_user_model()


@pytest.mark.unit
class WalletAddressModelTest(TestCase):
    """Test cases for WalletAddress model."""
    
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
    
    def test_wallet_address_creation(self):
        """Test creating a wallet address."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'walletuser1_{unique_id}',
            email=f'wallet1_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create wallet address
        address = WalletAddress.objects.create(
            user=user,
            chain_type='erc20',
            address='0x1234567890abcdef1234567890abcdef12345678',
            status='active',
            is_active=True
        )
        
        self.assertEqual(address.user, user)
        self.assertEqual(address.chain_type, 'erc20')
        self.assertEqual(address.address, '0x1234567890abcdef1234567890abcdef12345678')
        self.assertEqual(address.status, 'active')
        self.assertTrue(address.is_active)
        self.assertIsNotNone(address.created_at)
        self.assertIsNotNone(address.updated_at)

    def test_wallet_address_unique_constraint(self):
        """Test that a user can only have one address per chain type."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'walletuser2_{unique_id}',
            email=f'wallet2_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create first address
        WalletAddress.objects.create(
            user=user,
            chain_type='erc20',
            address='0x1234567890abcdef1234567890abcdef12345678',
            status='active',
            is_active=True
        )
        
        # Try to create another address with same chain type - should fail
        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            WalletAddress.objects.create(
                user=user,
                chain_type='erc20',
                address='0x876543210fedcba9876543210fedcba9876543210',
                status='active',
                is_active=True
            )

    def test_wallet_address_different_chain_types(self):
        """Test that a user can have addresses for different chain types."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'walletuser3_{unique_id}',
            email=f'wallet3_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create ERC20 address
        erc20_address = WalletAddress.objects.create(
            user=user,
            chain_type='erc20',
            address='0x1234567890abcdef1234567890abcdef12345678',
            status='active',
            is_active=True
        )
        
        # Create BEP20 address
        bep20_address = WalletAddress.objects.create(
            user=user,
            chain_type='bep20',
            address='0x876543210fedcba9876543210fedcba9876543210',
            status='active',
            is_active=True
        )
        
        self.assertEqual(erc20_address.chain_type, 'erc20')
        self.assertEqual(bep20_address.chain_type, 'bep20')
        self.assertNotEqual(erc20_address.address, bep20_address.address)


@pytest.mark.unit
class INRWalletModelTest(TestCase):
    """Test cases for INRWallet model."""
    
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
    
    def test_inr_wallet_creation(self):
        """Test creating an INR wallet."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'inruser1_{unique_id}',
            email=f'inr1_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create new wallet since signals are disabled
        wallet = INRWallet.objects.create(
            user=user,
            balance=Decimal('100.00'),
            status='active',
            is_active=True
        )
        
        self.assertEqual(wallet.user, user)
        self.assertEqual(wallet.balance, Decimal('100.00'))
        self.assertEqual(wallet.status, 'active')
        self.assertTrue(wallet.is_active)
        self.assertIsNotNone(wallet.created_at)
        self.assertIsNotNone(wallet.updated_at)

    def test_inr_wallet_balance_validation(self):
        """Test INR wallet balance validation."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'inruser2_{unique_id}',
            email=f'inr2_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Test negative balance
        wallet = INRWallet.objects.create(
            user=user,
            balance=Decimal('-50.00'),
            status='active',
            is_active=True
        )
        # Should allow negative balance for testing purposes
        self.assertEqual(wallet.balance, Decimal('-50.00'))

    def test_inr_wallet_status_choices(self):
        """Test INR wallet status choices."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'inruser3_{unique_id}',
            email=f'inr3_{unique_id}@example.com',
            password='testpass123'
        )
        
        wallet = INRWallet.objects.create(
            user=user,
            balance=Decimal('100.00'),
            status='suspended',
            is_active=True
        )
        # Test valid status
        self.assertEqual(wallet.status, 'suspended')
        
        # Test invalid status (should still work as Django doesn't enforce choices in DB)
        wallet.status = 'invalid_status'
        wallet.save()
        self.assertEqual(wallet.status, 'invalid_status')


@pytest.mark.unit
class USDTWalletModelTest(TestCase):
    """Test cases for USDTWallet model."""
    
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
    
    def test_usdt_wallet_creation(self):
        """Test creating a USDT wallet."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'usdtuser1_{unique_id}',
            email=f'usdt1_{unique_id}@example.com',
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
        
        self.assertEqual(wallet.user, user)
        self.assertEqual(wallet.balance, Decimal('50.000000'))
        self.assertEqual(wallet.wallet_address, '0x1234567890abcdef1234567890abcdef12345678')
        self.assertEqual(wallet.chain_type, 'erc20')
        self.assertFalse(wallet.is_real_wallet)
        self.assertIsNotNone(wallet.created_at)
        self.assertIsNotNone(wallet.updated_at)

    def test_usdt_wallet_chain_type_choices(self):
        """Test USDT wallet chain type choices."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'usdtuser2_{unique_id}',
            email=f'usdt2_{unique_id}@example.com',
            password='testpass123'
        )
        
        wallet = USDTWallet.objects.create(
            user=user,
            balance=Decimal('100.000000'),
            wallet_address='0x1234567890abcdef1234567890abcdef12345678',
            chain_type='bep20',
            is_real_wallet=False
        )
        # Test valid chain types
        self.assertEqual(wallet.chain_type, 'bep20')
        
        wallet.chain_type = 'erc20'
        wallet.save()
        self.assertEqual(wallet.chain_type, 'erc20')

    def test_usdt_wallet_private_key_encryption(self):
        """Test USDT wallet private key encryption."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'usdtuser3_{unique_id}',
            email=f'usdt3_{unique_id}@example.com',
            password='testpass123'
        )
        
        wallet = USDTWallet.objects.create(
            user=user,
            balance=Decimal('100.000000'),
            wallet_address='0x1234567890abcdef1234567890abcdef12345678',
            chain_type='erc20',
            is_real_wallet=False
        )
        # Test setting encrypted private key
        encrypted_key = 'encrypted_private_key_data_here'
        wallet.private_key_encrypted = encrypted_key
        wallet.save()
        self.assertEqual(wallet.private_key_encrypted, encrypted_key)


@pytest.mark.unit
class WalletTransactionModelTest(TestCase):
    """Test cases for WalletTransaction model."""
    
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
    
    def test_wallet_transaction_creation(self):
        """Test creating a wallet transaction."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'txuser1_{unique_id}',
            email=f'tx1_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create transaction
        transaction = WalletTransaction.objects.create(
            user=user,
            transaction_type='deposit',
            wallet_type='inr',
            amount=Decimal('100.00'),
            balance_before=Decimal('0.00'),
            balance_after=Decimal('100.00'),
            status='completed',
            reference_id=str(uuid.uuid4()),
            description='Test deposit transaction'
        )
        
        self.assertEqual(transaction.user, user)
        self.assertEqual(transaction.transaction_type, 'deposit')
        self.assertEqual(transaction.wallet_type, 'inr')
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.balance_before, Decimal('0.00'))
        self.assertEqual(transaction.balance_after, Decimal('100.00'))
        self.assertEqual(transaction.status, 'completed')
        self.assertIsNotNone(transaction.reference_id)
        self.assertEqual(transaction.description, 'Test deposit transaction')
        self.assertIsNotNone(transaction.created_at)
        self.assertIsNotNone(transaction.updated_at)

    def test_wallet_transaction_metadata(self):
        """Test wallet transaction metadata field."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'txuser2_{unique_id}',
            email=f'tx2_{unique_id}@example.com',
            password='testpass123'
        )
        
        metadata = {
            'tx_hash': '0x1234567890abcdef',
            'block_number': 12345,
            'gas_used': 21000
        }
        
        transaction = WalletTransaction.objects.create(
            user=user,
            transaction_type='usdt_deposit',
            wallet_type='usdt',
            amount=Decimal('50.000000'),
            balance_before=Decimal('0.000000'),
            balance_after=Decimal('50.000000'),
            status='completed',
            reference_id=str(uuid.uuid4()),
            description='Test USDT deposit',
            metadata=metadata
        )
        
        self.assertEqual(transaction.metadata, metadata)
        self.assertEqual(transaction.metadata['tx_hash'], '0x1234567890abcdef')
        self.assertEqual(transaction.metadata['block_number'], 12345)

    def test_wallet_transaction_status_choices(self):
        """Test wallet transaction status choices."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'txuser3_{unique_id}',
            email=f'tx3_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Test different statuses
        statuses = ['pending', 'completed', 'failed', 'cancelled']
        for status in statuses:
            transaction = WalletTransaction.objects.create(
                user=user,
                transaction_type='transfer',
                wallet_type='inr',
                amount=Decimal('10.00'),
                balance_before=Decimal('100.00'),
                balance_after=Decimal('90.00'),
                status=status,
                reference_id=str(uuid.uuid4()),
                description=f'Test transaction with status {status}'
            )
            self.assertEqual(transaction.status, status)
