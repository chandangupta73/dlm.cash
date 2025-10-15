from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.db import transaction
from .models import INRWallet, USDTWallet, WalletTransaction, DepositRequest
from .services import WalletService, DepositService, TransactionService


class WalletModelTest(TestCase):
    """Test cases for wallet models."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_inr_wallet_creation(self):
        """Test INR wallet creation."""
        wallet = INRWallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00')
        )
        self.assertEqual(wallet.balance, Decimal('1000.00'))
        self.assertEqual(wallet.status, 'active')
        self.assertTrue(wallet.is_active)
    
    def test_usdt_wallet_creation(self):
        """Test USDT wallet creation."""
        wallet = USDTWallet.objects.create(
            user=self.user,
            balance=Decimal('50.000000'),
            wallet_address='TRC20_ADDRESS_HERE'
        )
        self.assertEqual(wallet.balance, Decimal('50.000000'))
        self.assertEqual(wallet.status, 'active')
        self.assertTrue(wallet.is_active)
    
    def test_wallet_transaction_creation(self):
        """Test wallet transaction creation."""
        transaction = WalletTransaction.objects.create(
            user=self.user,
            transaction_type='deposit',
            wallet_type='inr',
            amount=Decimal('500.00'),
            balance_before=Decimal('0.00'),
            balance_after=Decimal('500.00'),
            status='completed',
            description='Test deposit'
        )
        self.assertEqual(transaction.amount, Decimal('500.00'))
        self.assertEqual(transaction.status, 'completed')
    
    def test_deposit_request_creation(self):
        """Test deposit request creation."""
        deposit = DepositRequest.objects.create(
            user=self.user,
            amount=Decimal('1000.00'),
            payment_method='bank_transfer',
            reference_number='TXN123456'
        )
        self.assertEqual(deposit.amount, Decimal('1000.00'))
        self.assertEqual(deposit.status, 'pending')


class WalletServiceTest(TestCase):
    """Test cases for wallet services."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_get_or_create_inr_wallet(self):
        """Test INR wallet get or create."""
        wallet = WalletService.get_or_create_inr_wallet(self.user)
        self.assertIsInstance(wallet, INRWallet)
        self.assertEqual(wallet.user, self.user)
        self.assertEqual(wallet.balance, Decimal('0.00'))
        
        # Should return same wallet on second call
        wallet2 = WalletService.get_or_create_inr_wallet(self.user)
        self.assertEqual(wallet.id, wallet2.id)
    
    def test_get_or_create_usdt_wallet(self):
        """Test USDT wallet get or create."""
        wallet = WalletService.get_or_create_usdt_wallet(self.user)
        self.assertIsInstance(wallet, USDTWallet)
        self.assertEqual(wallet.user, self.user)
        self.assertEqual(wallet.balance, Decimal('0.000000'))
    
    def test_get_wallet_balance(self):
        """Test getting wallet balance."""
        balance_data = WalletService.get_wallet_balance(self.user)
        self.assertIn('inr_balance', balance_data)
        self.assertIn('usdt_balance', balance_data)
        self.assertIn('inr_wallet_status', balance_data)
        self.assertIn('usdt_wallet_status', balance_data)
    
    def test_add_inr_balance(self):
        """Test adding INR balance."""
        success = WalletService.add_inr_balance(
            self.user, 
            Decimal('500.00'), 
            'deposit', 
            'Test deposit'
        )
        self.assertTrue(success)
        
        wallet = INRWallet.objects.get(user=self.user)
        self.assertEqual(wallet.balance, Decimal('500.00'))
        
        # Check transaction was created
        transaction = WalletTransaction.objects.filter(
            user=self.user,
            transaction_type='deposit',
            wallet_type='inr'
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('500.00'))
    
    def test_deduct_inr_balance(self):
        """Test deducting INR balance."""
        # First add balance
        WalletService.add_inr_balance(self.user, Decimal('1000.00'), 'deposit')
        
        # Then deduct
        success = WalletService.deduct_inr_balance(
            self.user, 
            Decimal('300.00'), 
            'withdrawal', 
            'Test withdrawal'
        )
        self.assertTrue(success)
        
        wallet = INRWallet.objects.get(user=self.user)
        self.assertEqual(wallet.balance, Decimal('700.00'))
    
    def test_insufficient_balance_deduction(self):
        """Test deducting more than available balance."""
        # Add some balance
        WalletService.add_inr_balance(self.user, Decimal('100.00'), 'deposit')
        
        # Try to deduct more
        with self.assertRaises(ValueError):
            WalletService.deduct_inr_balance(
                self.user, 
                Decimal('200.00'), 
                'withdrawal'
            )


class DepositServiceTest(TestCase):
    """Test cases for deposit services."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )
    
    def test_create_deposit_request(self):
        """Test creating deposit request."""
        deposit = DepositService.create_deposit_request(
            self.user,
            Decimal('1000.00'),
            'bank_transfer',
            reference_number='TXN123456'
        )
        self.assertEqual(deposit.user, self.user)
        self.assertEqual(deposit.amount, Decimal('1000.00'))
        self.assertEqual(deposit.status, 'pending')
    
    def test_approve_deposit(self):
        """Test approving deposit request."""
        deposit = DepositService.create_deposit_request(
            self.user,
            Decimal('500.00'),
            'bank_transfer'
        )
        
        success = DepositService.approve_deposit(deposit.id, self.admin_user)
        self.assertTrue(success)
        
        deposit.refresh_from_db()
        self.assertEqual(deposit.status, 'approved')
        self.assertEqual(deposit.processed_by, self.admin_user)
        
        # Check wallet balance was updated
        wallet = INRWallet.objects.get(user=self.user)
        self.assertEqual(wallet.balance, Decimal('500.00'))
    
    def test_reject_deposit(self):
        """Test rejecting deposit request."""
        deposit = DepositService.create_deposit_request(
            self.user,
            Decimal('500.00'),
            'bank_transfer'
        )
        
        success = DepositService.reject_deposit(
            deposit.id, 
            self.admin_user, 
            'Invalid payment proof'
        )
        self.assertTrue(success)
        
        deposit.refresh_from_db()
        self.assertEqual(deposit.status, 'rejected')
        self.assertEqual(deposit.processed_by, self.admin_user)
        self.assertEqual(deposit.admin_notes, 'Invalid payment proof')


class TransactionServiceTest(TestCase):
    """Test cases for transaction services."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create some test transactions
        WalletService.add_inr_balance(self.user, Decimal('1000.00'), 'deposit')
        WalletService.deduct_inr_balance(self.user, Decimal('200.00'), 'withdrawal')
        WalletService.add_inr_balance(self.user, Decimal('50.00'), 'roi_credit')
    
    def test_get_user_transactions(self):
        """Test getting user transactions."""
        history = TransactionService.get_user_transactions(
            self.user, 
            page=1, 
            page_size=10
        )
        
        self.assertIn('transactions', history)
        self.assertIn('total_count', history)
        self.assertIn('page', history)
        self.assertIn('page_size', history)
        self.assertIn('has_next', history)
        self.assertIn('has_previous', history)
        
        self.assertEqual(history['total_count'], 3)
        self.assertEqual(len(history['transactions']), 3)
    
    def test_get_transaction_summary(self):
        """Test getting transaction summary."""
        summary = TransactionService.get_transaction_summary(self.user, days=30)
        
        self.assertIn('total_deposits', summary)
        self.assertIn('total_withdrawals', summary)
        self.assertIn('total_roi', summary)
        self.assertIn('total_referrals', summary)
        self.assertIn('transaction_count', summary)
        
        self.assertEqual(summary['total_deposits'], Decimal('1050.00'))
        self.assertEqual(summary['total_withdrawals'], Decimal('200.00'))
        self.assertEqual(summary['total_roi'], Decimal('50.00'))
        self.assertEqual(summary['transaction_count'], 3) 