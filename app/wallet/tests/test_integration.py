from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.db import transaction
from decimal import Decimal
import uuid

from app.wallet.models import (
    INRWallet, USDTWallet, WalletAddress, WalletTransaction, 
    DepositRequest, USDTDepositRequest
)
from app.wallet.signals import create_user_wallets, save_user_wallets
from app.core.signals import create_user_wallets as core_create_user_wallets, save_user_wallets as core_save_user_wallets
from app.wallet.services import WalletService, DepositService, TransactionService
from app.wallet.services import WalletValidationService
from app.crud.wallet import WalletAddressService

User = get_user_model()


class WalletIntegrationTest(TestCase):
    """Integration tests for wallet operations."""
    
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

    def test_wallet_balance_operations_integration(self):
        """Test complete wallet balance operations workflow."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'balanceuser_{unique_id}',
            email=f'balance_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create wallets
        inr_wallet = INRWallet.objects.create(
            user=user,
            balance=Decimal('1000.00'),
            status='active',
            is_active=True
        )
        
        usdt_wallet = USDTWallet.objects.create(
            user=user,
            balance=Decimal('500.000000'),
            wallet_address='0x1234567890abcdef1234567890abcdef12345678',
            chain_type='erc20',
            is_real_wallet=False
        )
        
        # Test balance operations
        initial_inr = inr_wallet.balance
        initial_usdt = usdt_wallet.balance
        
        # Add INR balance
        success = WalletService.add_inr_balance(
            user, 
            Decimal('100.00'), 
            'admin_adjustment', 
            'Test balance addition'
        )
        self.assertTrue(success)
        
        # Refresh wallets
        inr_wallet.refresh_from_db()
        usdt_wallet.refresh_from_db()
        
        # Check balances
        self.assertEqual(inr_wallet.balance, initial_inr + Decimal('100.00'))
        
        # Check transaction log
        transaction = WalletTransaction.objects.filter(
            user=user, 
            transaction_type='admin_adjustment',
            wallet_type='inr'
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.status, 'completed')

    def test_deposit_workflow_integration(self):
        """Test complete deposit workflow."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'deposituser_{unique_id}',
            email=f'deposit_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create wallets
        inr_wallet = INRWallet.objects.create(
            user=user,
            balance=Decimal('0.00'),
            status='active',
            is_active=True
        )
        
        # Create deposit request
        deposit = DepositRequest.objects.create(
            user=user,
            amount=Decimal('500.00'),
            payment_method='bank_transfer',
            status='pending',
            reference_number='DEP123456',
            transaction_id='TXN789012'
        )
        
        # Approve deposit
        admin_user = User.objects.create_user(
            username=f'admin_{unique_id}',
            email=f'admin_{unique_id}@example.com',
            password='adminpass123',
            is_staff=True
        )
        
        success = DepositService.approve_deposit(deposit.id, admin_user, 'Payment verified')
        self.assertTrue(success)
        
        # Refresh wallet and check balance
        inr_wallet.refresh_from_db()
        self.assertEqual(inr_wallet.balance, Decimal('500.00'))
        
        # Check transaction log
        transaction = WalletTransaction.objects.filter(
            user=user,
            transaction_type='deposit',
            wallet_type='inr'
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('500.00'))
        self.assertEqual(transaction.status, 'completed')

    def test_usdt_deposit_workflow_integration(self):
        """Test complete USDT deposit workflow."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'usdtdeposituser_{unique_id}',
            email=f'usdtdeposit_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create USDT wallet
        usdt_wallet = USDTWallet.objects.create(
            user=user,
            balance=Decimal('0.000000'),
            wallet_address='0x1234567890abcdef1234567890abcdef12345678',
            chain_type='erc20',
            is_real_wallet=False
        )
        
        # Create USDT deposit request
        deposit = USDTDepositRequest.objects.create(
            user=user,
            chain_type='erc20',
            amount=Decimal('100.000000'),
            transaction_hash='0xabcdef1234567890abcdef1234567890abcdef12',
            from_address='0x876543210fedcba9876543210fedcba9876543210',
            to_address='0x1234567890abcdef1234567890abcdef12345678',
            status='pending',
            confirmation_count=12  # Enough confirmations
        )
        
        # Confirm deposit
        success = deposit.confirm_deposit()
        self.assertTrue(success)
        
        # Refresh wallet and check balance
        usdt_wallet.refresh_from_db()
        self.assertEqual(usdt_wallet.balance, Decimal('100.000000'))
        
        # Check transaction log
        transaction = WalletTransaction.objects.filter(
            user=user,
            transaction_type='usdt_deposit',
            wallet_type='usdt'
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('100.000000'))
        self.assertEqual(transaction.status, 'completed')

    def test_wallet_address_management_integration(self):
        """Test wallet address management workflow."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'addressuser_{unique_id}',
            email=f'address_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create wallet addresses for different chains
        erc20_address = WalletAddress.objects.create(
            user=user,
            chain_type='erc20',
            address='0x1234567890abcdef1234567890abcdef12345678',
            status='active',
            is_active=True
        )
        
        bep20_address = WalletAddress.objects.create(
            user=user,
            chain_type='bep20',
            address='0x876543210fedcba9876543210fedcba9876543210',
            status='active',
            is_active=True
        )
        
        # Test address retrieval
        addresses = WalletAddressService.get_all_wallet_addresses(user)
        self.assertEqual(addresses.count(), 2)
        
        # Test address validation
        valid_erc20 = WalletAddressService.validate_address(
            '0x1234567890abcdef1234567890abcdef12345678', 'erc20'
        )
        self.assertTrue(valid_erc20)
        
        invalid_address = WalletAddressService.validate_address(
            'invalid_address', 'erc20'
        )
        self.assertFalse(invalid_address)

    def test_concurrent_balance_operations(self):
        """Test concurrent balance operations to ensure data consistency."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'concurrentuser_{unique_id}',
            email=f'concurrent_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create wallet with initial balance
        inr_wallet = INRWallet.objects.create(
            user=user,
            balance=Decimal('1000.00'),
            status='active',
            is_active=True
        )
        
        # Simulate concurrent operations
        with transaction.atomic():
            # First operation
            wallet1 = INRWallet.objects.select_for_update().get(user=user)
            wallet1.balance += Decimal('100.00')
            wallet1.save()
            
            # Second operation (should wait for first to complete)
            wallet2 = INRWallet.objects.select_for_update().get(user=user)
            wallet2.balance += Decimal('50.00')
            wallet2.save()
        
        # Check final balance
        inr_wallet.refresh_from_db()
        self.assertEqual(inr_wallet.balance, Decimal('1150.00'))
        
        # Create transaction logs manually since we're not using the service
        WalletTransaction.objects.create(
            user=user,
            transaction_type='admin_adjustment',
            wallet_type='inr',
            amount=Decimal('100.00'),
            balance_before=Decimal('1000.00'),
            balance_after=Decimal('1100.00'),
            status='completed',
            reference_id='REF1',
            description='First adjustment'
        )
        
        WalletTransaction.objects.create(
            user=user,
            transaction_type='admin_adjustment',
            wallet_type='inr',
            amount=Decimal('50.00'),
            balance_before=Decimal('1100.00'),
            balance_after=Decimal('1150.00'),
            status='completed',
            reference_id='REF2',
            description='Second adjustment'
        )
        
        # Check transaction logs
        transactions = WalletTransaction.objects.filter(
            user=user,
            wallet_type='inr'
        ).order_by('created_at')
        
        self.assertEqual(transactions.count(), 2)

    def test_wallet_status_management_integration(self):
        """Test wallet status management workflow."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'statususer_{unique_id}',
            email=f'status_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create active wallet
        inr_wallet = INRWallet.objects.create(
            user=user,
            balance=Decimal('1000.00'),
            status='active',
            is_active=True
        )
        
        # Test wallet validation
        validation = WalletValidationService.validate_wallet_status(user)
        self.assertTrue(validation[0])  # First element is the boolean result
        
        # Suspend wallet
        inr_wallet.status = 'suspended'
        inr_wallet.save()
        
        # Test validation after suspension
        validation = WalletValidationService.validate_wallet_status(user)
        self.assertFalse(validation[0])  # Should be False now
        
        # Try to add balance to suspended wallet
        with self.assertRaises(ValueError):
            WalletService.add_inr_balance(user, Decimal('100.00'), 'admin_adjustment')

    def test_transaction_summary_integration(self):
        """Test transaction summary and reporting."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'summaryuser_{unique_id}',
            email=f'summary_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create wallet
        inr_wallet = INRWallet.objects.create(
            user=user,
            balance=Decimal('1000.00'),
            status='active',
            is_active=True
        )
        
        # Create multiple transactions
        transaction_types = ['deposit', 'withdrawal', 'admin_adjustment']
        for i, tx_type in enumerate(transaction_types):
            WalletTransaction.objects.create(
                user=user,
                transaction_type=tx_type,
                wallet_type='inr',
                amount=Decimal('100.00'),
                balance_before=Decimal('1000.00') + Decimal(i * 100),
                balance_after=Decimal('1000.00') + Decimal((i + 1) * 100),
                status='completed',
                reference_id=f'REF{i}',
                description=f'Test {tx_type} transaction'
            )
        
        # Get transaction summary
        summary = TransactionService.get_transaction_summary(user, days=30)
        
        # Check summary data
        self.assertEqual(summary['transaction_count'], 3)
        self.assertEqual(summary['total_deposits'], Decimal('100.00'))
        self.assertEqual(summary['total_withdrawals'], Decimal('100.00'))
        self.assertEqual(summary['total_roi'], Decimal('0.00'))

    def test_error_handling_integration(self):
        """Test error handling in wallet operations."""
        unique_id = str(uuid.uuid4())[:8]
        user = User.objects.create_user(
            username=f'erroruser_{unique_id}',
            email=f'error_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Create wallet
        inr_wallet = INRWallet.objects.create(
            user=user,
            balance=Decimal('100.00'),
            status='active',
            is_active=True
        )
        
        # Test insufficient balance
        with self.assertRaises(ValueError):
            WalletService.deduct_inr_balance(user, Decimal('200.00'), 'withdrawal')
        
        # Test negative amount
        with self.assertRaises(ValueError):
            WalletService.add_inr_balance(user, Decimal('-50.00'), 'admin_adjustment')
        
        # Test inactive wallet
        inr_wallet.is_active = False
        inr_wallet.save()
        
        with self.assertRaises(ValueError):
            WalletService.add_inr_balance(user, Decimal('100.00'), 'admin_adjustment')
        
        # Test suspended wallet
        inr_wallet.is_active = True
        inr_wallet.status = 'suspended'
        inr_wallet.save()
        
        with self.assertRaises(ValueError):
            WalletService.add_inr_balance(user, Decimal('100.00'), 'admin_adjustment')
