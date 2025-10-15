import pytest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from unittest.mock import patch, MagicMock

from app.transactions.models import Transaction
from app.transactions.services import TransactionService, TransactionIntegrationService
from app.transactions.tests.conftest import (
    UserFactory, TransactionFactory, INRWalletFactory, USDTWalletFactory
)

User = get_user_model()


class TransactionServiceTest(TestCase):
    """Test cases for the TransactionService class."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.inr_wallet = INRWalletFactory(user=self.user)
        self.usdt_wallet = USDTWalletFactory(user=self.user)
    
    def test_create_transaction_with_wallet_update(self):
        """Test creating a transaction with wallet balance update."""
        initial_inr_balance = self.inr_wallet.balance
        
        # Create a deposit transaction
        transaction = TransactionService.create_transaction(
            user=self.user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('100.00'),
            reference_id='test_ref',
            update_wallet=True
        )
        
        # Verify transaction was created
        self.assertIsInstance(transaction, Transaction)
        self.assertEqual(transaction.type, 'DEPOSIT')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.status, 'SUCCESS')
        
        # Verify wallet balance was updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, initial_inr_balance + Decimal('100.00'))
    
    def test_create_transaction_without_wallet_update(self):
        """Test creating a transaction without updating wallet balance."""
        initial_inr_balance = self.inr_wallet.balance
        
        # Create a transaction without wallet update
        transaction = TransactionService.create_transaction(
            user=self.user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('100.00'),
            reference_id='test_ref',
            update_wallet=False
        )
        
        # Verify transaction was created
        self.assertIsInstance(transaction, Transaction)
        
        # Verify wallet balance was NOT updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, initial_inr_balance)
    
    def test_create_transaction_inr_credit(self):
        """Test creating INR credit transactions."""
        initial_balance = self.inr_wallet.balance
        
        # Test different credit transaction types
        credit_types = ['DEPOSIT', 'ROI', 'REFERRAL_BONUS', 'MILESTONE_BONUS', 'ADMIN_ADJUSTMENT', 'BREAKDOWN_REFUND']
        
        for transaction_type in credit_types:
            with self.subTest(transaction_type=transaction_type):
                transaction = TransactionService.create_transaction(
                    user=self.user,
                    type=transaction_type,
                    currency='INR',
                    amount=Decimal('50.00'),
                    reference_id=f'ref_{transaction_type}'
                )
                
                # Verify transaction
                self.assertEqual(transaction.type, transaction_type)
                self.assertEqual(transaction.currency, 'INR')
                
                # Verify wallet balance increased
                self.inr_wallet.refresh_from_db()
                expected_balance = initial_balance + Decimal('50.00')
                self.assertEqual(self.inr_wallet.balance, expected_balance)
                
                # Reset balance for next test
                self.inr_wallet.balance = initial_balance
                self.inr_wallet.save()
    
    def test_create_transaction_inr_debit(self):
        """Test creating INR debit transactions."""
        # Set sufficient balance
        self.inr_wallet.balance = Decimal('1000.00')
        self.inr_wallet.save()
        
        initial_balance = self.inr_wallet.balance
        
        # Test different debit transaction types
        debit_types = ['WITHDRAWAL', 'PLAN_PURCHASE']
        
        for transaction_type in debit_types:
            with self.subTest(transaction_type=transaction_type):
                transaction = TransactionService.create_transaction(
                    user=self.user,
                    type=transaction_type,
                    currency='INR',
                    amount=Decimal('100.00'),
                    reference_id=f'ref_{transaction_type}'
                )
                
                # Verify transaction
                self.assertEqual(transaction.type, transaction_type)
                self.assertEqual(transaction.currency, 'INR')
                
                # Verify wallet balance decreased
                self.inr_wallet.refresh_from_db()
                expected_balance = initial_balance - Decimal('100.00')
                self.assertEqual(self.inr_wallet.balance, expected_balance)
                
                # Reset balance for next test
                self.inr_wallet.balance = initial_balance
                self.inr_wallet.save()
    
    def test_create_transaction_usdt_credit(self):
        """Test creating USDT credit transactions."""
        initial_balance = self.usdt_wallet.balance
        
        # Test different credit transaction types
        credit_types = ['DEPOSIT', 'ROI', 'REFERRAL_BONUS', 'MILESTONE_BONUS', 'ADMIN_ADJUSTMENT', 'BREAKDOWN_REFUND']
        
        for transaction_type in credit_types:
            with self.subTest(transaction_type=transaction_type):
                transaction = TransactionService.create_transaction(
                    user=self.user,
                    type=transaction_type,
                    currency='USDT',
                    amount=Decimal('50.000000'),
                    reference_id=f'ref_{transaction_type}'
                )
                
                # Verify transaction
                self.assertEqual(transaction.type, transaction_type)
                self.assertEqual(transaction.currency, 'USDT')
                
                # Verify wallet balance increased
                self.usdt_wallet.refresh_from_db()
                expected_balance = initial_balance + Decimal('50.000000')
                self.assertEqual(self.usdt_wallet.balance, expected_balance)
                
                # Reset balance for next test
                self.usdt_wallet.balance = initial_balance
                self.usdt_wallet.save()
    
    def test_create_transaction_usdt_debit(self):
        """Test creating USDT debit transactions."""
        # Set sufficient balance
        self.usdt_wallet.balance = Decimal('1000.000000')
        self.usdt_wallet.save()
        
        initial_balance = self.usdt_wallet.balance
        
        # Test different debit transaction types
        debit_types = ['WITHDRAWAL', 'PLAN_PURCHASE']
        
        for transaction_type in debit_types:
            with self.subTest(transaction_type=transaction_type):
                transaction = TransactionService.create_transaction(
                    user=self.user,
                    type=transaction_type,
                    currency='USDT',
                    amount=Decimal('100.000000'),
                    reference_id=f'ref_{transaction_type}'
                )
                
                # Verify transaction
                self.assertEqual(transaction.type, transaction_type)
                self.assertEqual(transaction.currency, 'USDT')
                
                # Verify wallet balance decreased
                self.usdt_wallet.refresh_from_db()
                expected_balance = initial_balance - Decimal('100.000000')
                self.assertEqual(self.usdt_wallet.balance, expected_balance)
                
                # Reset balance for next test
                self.usdt_wallet.balance = initial_balance
                self.usdt_wallet.save()
    
    def test_create_transaction_insufficient_balance(self):
        """Test that transactions fail when there's insufficient balance."""
        # Set low balance
        self.inr_wallet.balance = Decimal('50.00')
        self.inr_wallet.save()
        
        # Try to withdraw more than available
        with self.assertRaises(ValueError, msg="Should fail with insufficient balance"):
            TransactionService.create_transaction(
                user=self.user,
                type='WITHDRAWAL',
                currency='INR',
                amount=Decimal('100.00'),
                reference_id='test_ref'
            )
        
        # Verify balance wasn't changed
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('50.00'))
    
    def test_create_transaction_creates_wallet_if_not_exists(self):
        """Test that wallets are created if they don't exist."""
        new_user = UserFactory()
        
        # Verify no wallet exists
        self.assertFalse(INRWallet.objects.filter(user=new_user).exists())
        
        # Create transaction - should create wallet
        transaction = TransactionService.create_transaction(
            user=new_user,
            type='DEPOSIT',
            currency='INR',
            amount=Decimal('100.00'),
            reference_id='test_ref'
        )
        
        # Verify wallet was created
        wallet = INRWallet.objects.get(user=new_user)
        self.assertEqual(wallet.balance, Decimal('100.00'))
        self.assertEqual(wallet.status, 'active')
        self.assertTrue(wallet.is_active)
    
    def test_get_user_transactions(self):
        """Test getting user transactions with pagination."""
        # Create multiple transactions
        for i in range(25):
            TransactionFactory(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal(f'{100 + i}.00')
            )
        
        # Test pagination
        result = TransactionService.get_user_transactions(
            user=self.user,
            page=1,
            page_size=10
        )
        
        self.assertEqual(len(result['transactions']), 10)
        self.assertEqual(result['pagination']['page'], 1)
        self.assertEqual(result['pagination']['page_size'], 10)
        self.assertEqual(result['pagination']['total_count'], 25)
        self.assertEqual(result['pagination']['total_pages'], 3)
        self.assertTrue(result['pagination']['has_next'])
        self.assertFalse(result['pagination']['has_previous'])
    
    def test_get_user_transactions_with_filters(self):
        """Test getting user transactions with filters."""
        # Create transactions of different types
        TransactionFactory(user=self.user, type='DEPOSIT', currency='INR')
        TransactionFactory(user=self.user, type='WITHDRAWAL', currency='INR')
        TransactionFactory(user=self.user, type='ROI', currency='USDT')
        
        # Filter by type
        result = TransactionService.get_user_transactions(
            user=self.user,
            filters={'type': 'DEPOSIT'}
        )
        
        self.assertEqual(len(result['transactions']), 1)
        self.assertEqual(result['transactions'][0].type, 'DEPOSIT')
        
        # Filter by currency
        result = TransactionService.get_user_transactions(
            user=self.user,
            filters={'currency': 'USDT'}
        )
        
        self.assertEqual(len(result['transactions']), 1)
        self.assertEqual(result['transactions'][0].currency, 'USDT')
    
    def test_get_admin_transactions(self):
        """Test getting admin transactions with pagination."""
        # Create multiple transactions for different users
        for i in range(30):
            user = UserFactory()
            TransactionFactory(
                user=user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal(f'{100 + i}.00')
            )
        
        # Test pagination
        result = TransactionService.get_admin_transactions(
            page=1,
            page_size=20
        )
        
        self.assertEqual(len(result['transactions']), 20)
        self.assertEqual(result['pagination']['page'], 1)
        self.assertEqual(result['pagination']['page_size'], 20)
        self.assertEqual(result['pagination']['total_count'], 30)
        self.assertEqual(result['pagination']['total_pages'], 2)
        self.assertTrue(result['pagination']['has_next'])
        self.assertFalse(result['pagination']['has_previous'])
    
    def test_export_transactions_csv(self):
        """Test CSV export functionality."""
        # Create some transactions
        for i in range(5):
            TransactionFactory(
                user=self.user,
                type='DEPOSIT',
                currency='INR',
                amount=Decimal(f'{100 + i}.00')
            )
        
        # Export to CSV
        response = TransactionService.export_transactions_csv()
        
        # Verify response
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        
        # Verify CSV content
        csv_content = response.content.decode('utf-8')
        lines = csv_content.strip().split('\n')
        
        # Should have header + 5 data rows
        self.assertEqual(len(lines), 6)
        
        # Check header
        header = lines[0]
        expected_headers = ['Transaction ID', 'Username', 'Email', 'Type', 'Currency', 'Amount', 'Status', 'Reference ID', 'Created At', 'Updated At']
        for header_field in expected_headers:
            self.assertIn(header_field, header)
    
    def test_get_transaction_summary(self):
        """Test getting transaction summary for a user."""
        # Create transactions of different types
        TransactionFactory(user=self.user, type='DEPOSIT', currency='INR', amount=Decimal('100.00'))
        TransactionFactory(user=self.user, type='WITHDRAWAL', currency='INR', amount=Decimal('50.00'))
        TransactionFactory(user=self.user, type='ROI', currency='USDT', amount=Decimal('25.000000'))
        
        # Get summary
        summary = TransactionService.get_transaction_summary(self.user)
        
        # Verify summary structure
        self.assertIn('DEPOSIT', summary)
        self.assertIn('WITHDRAWAL', summary)
        self.assertIn('ROI', summary)
        self.assertIn('overall', summary)
        
        # Verify counts
        self.assertEqual(summary['DEPOSIT']['count'], 1)
        self.assertEqual(summary['WITHDRAWAL']['count'], 1)
        self.assertEqual(summary['ROI']['count'], 1)
        self.assertEqual(summary['overall']['total_transactions'], 3)
        
        # Verify amounts
        self.assertEqual(summary['DEPOSIT']['total_amount'], Decimal('100.00'))
        self.assertEqual(summary['WITHDRAWAL']['total_amount'], Decimal('50.00'))
        self.assertEqual(summary['ROI']['total_amount'], Decimal('25.000000'))
    
    def test_get_transaction_summary_with_currency_filter(self):
        """Test getting transaction summary filtered by currency."""
        # Create transactions in different currencies
        TransactionFactory(user=self.user, type='DEPOSIT', currency='INR', amount=Decimal('100.00'))
        TransactionFactory(user=self.user, type='WITHDRAWAL', currency='INR', amount=Decimal('50.00'))
        TransactionFactory(user=self.user, type='ROI', currency='USDT', amount=Decimal('25.000000'))
        
        # Get INR summary
        inr_summary = TransactionService.get_transaction_summary(self.user, currency='INR')
        
        # Should only include INR transactions
        self.assertEqual(inr_summary['overall']['total_transactions'], 2)
        self.assertEqual(inr_summary['overall']['total_volume'], Decimal('150.00'))
        
        # Get USDT summary
        usdt_summary = TransactionService.get_transaction_summary(self.user, currency='USDT')
        
        # Should only include USDT transactions
        self.assertEqual(usdt_summary['overall']['total_transactions'], 1)
        self.assertEqual(usdt_summary['overall']['total_volume'], Decimal('25.000000'))


class TransactionIntegrationServiceTest(TestCase):
    """Test cases for the TransactionIntegrationService class."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.inr_wallet = INRWalletFactory(user=self.user)
        self.usdt_wallet = USDTWalletFactory(user=self.user)
    
    def test_log_deposit(self):
        """Test logging deposit transactions."""
        initial_balance = self.inr_wallet.balance
        
        transaction = TransactionIntegrationService.log_deposit(
            user=self.user,
            amount=Decimal('100.00'),
            currency='INR',
            reference_id='deposit_ref_123',
            meta_data={'payment_method': 'bank_transfer'}
        )
        
        # Verify transaction
        self.assertEqual(transaction.type, 'DEPOSIT')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.reference_id, 'deposit_ref_123')
        self.assertEqual(transaction.meta_data['payment_method'], 'bank_transfer')
        
        # Verify wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, initial_balance + Decimal('100.00'))
    
    def test_log_withdrawal(self):
        """Test logging withdrawal transactions."""
        # Set sufficient balance
        self.inr_wallet.balance = Decimal('1000.00')
        self.inr_wallet.save()
        
        initial_balance = self.inr_wallet.balance
        
        transaction = TransactionIntegrationService.log_withdrawal(
            user=self.user,
            amount=Decimal('200.00'),
            currency='INR',
            reference_id='withdrawal_ref_456',
            meta_data={'bank_account': '1234567890'}
        )
        
        # Verify transaction
        self.assertEqual(transaction.type, 'WITHDRAWAL')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, Decimal('200.00'))
        self.assertEqual(transaction.reference_id, 'withdrawal_ref_456')
        self.assertEqual(transaction.meta_data['bank_account'], '1234567890')
        
        # Verify wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, initial_balance - Decimal('200.00'))
    
    def test_log_roi_payout(self):
        """Test logging ROI payout transactions."""
        initial_balance = self.usdt_wallet.balance
        
        transaction = TransactionIntegrationService.log_roi_payout(
            user=self.user,
            amount=Decimal('50.000000'),
            currency='USDT',
            reference_id='roi_ref_789',
            meta_data={'investment_id': 'inv_123', 'period': 'monthly'}
        )
        
        # Verify transaction
        self.assertEqual(transaction.type, 'ROI')
        self.assertEqual(transaction.currency, 'USDT')
        self.assertEqual(transaction.amount, Decimal('50.000000'))
        self.assertEqual(transaction.reference_id, 'roi_ref_789')
        self.assertEqual(transaction.meta_data['investment_id'], 'inv_123')
        
        # Verify wallet balance updated
        self.usdt_wallet.refresh_from_db()
        self.assertEqual(self.usdt_wallet.balance, initial_balance + Decimal('50.000000'))
    
    def test_log_referral_bonus(self):
        """Test logging referral bonus transactions."""
        initial_balance = self.inr_wallet.balance
        
        transaction = TransactionIntegrationService.log_referral_bonus(
            user=self.user,
            amount=Decimal('25.00'),
            currency='INR',
            reference_id='referral_ref_101',
            meta_data={'referrer_id': 'user_456', 'level': 1}
        )
        
        # Verify transaction
        self.assertEqual(transaction.type, 'REFERRAL_BONUS')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, Decimal('25.00'))
        self.assertEqual(transaction.reference_id, 'referral_ref_101')
        self.assertEqual(transaction.meta_data['level'], 1)
        
        # Verify wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, initial_balance + Decimal('25.00'))
    
    def test_log_milestone_bonus(self):
        """Test logging milestone bonus transactions."""
        initial_balance = self.inr_wallet.balance
        
        transaction = TransactionIntegrationService.log_milestone_bonus(
            user=self.user,
            amount=Decimal('100.00'),
            currency='INR',
            reference_id='milestone_ref_202',
            meta_data={'milestone': 'first_investment', 'achieved_at': '2024-01-15'}
        )
        
        # Verify transaction
        self.assertEqual(transaction.type, 'MILESTONE_BONUS')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.reference_id, 'milestone_ref_202')
        self.assertEqual(transaction.meta_data['milestone'], 'first_investment')
        
        # Verify wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, initial_balance + Decimal('100.00'))
    
    def test_log_admin_adjustment(self):
        """Test logging admin adjustment transactions."""
        initial_balance = self.inr_wallet.balance
        
        transaction = TransactionIntegrationService.log_admin_adjustment(
            user=self.user,
            amount=Decimal('75.00'),
            currency='INR',
            reference_id='admin_ref_303',
            meta_data={'admin_note': 'Compensation for service issue', 'admin_id': 'admin_123'}
        )
        
        # Verify transaction
        self.assertEqual(transaction.type, 'ADMIN_ADJUSTMENT')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, Decimal('75.00'))
        self.assertEqual(transaction.reference_id, 'admin_ref_303')
        self.assertEqual(transaction.meta_data['admin_note'], 'Compensation for service issue')
        
        # Verify wallet balance updated
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, initial_balance + Decimal('75.00'))
    
    def test_log_plan_purchase(self):
        """Test logging investment plan purchase transactions."""
        # Set sufficient balance
        self.usdt_wallet.balance = Decimal('1000.000000')
        self.usdt_wallet.save()
        
        initial_balance = self.usdt_wallet.balance
        
        transaction = TransactionIntegrationService.log_plan_purchase(
            user=self.user,
            amount=Decimal('500.000000'),
            currency='USDT',
            reference_id='plan_ref_404',
            meta_data={'plan_name': 'Premium Plan', 'duration': '365 days'}
        )
        
        # Verify transaction
        self.assertEqual(transaction.type, 'PLAN_PURCHASE')
        self.assertEqual(transaction.currency, 'USDT')
        self.assertEqual(transaction.amount, Decimal('500.000000'))
        self.assertEqual(transaction.reference_id, 'plan_ref_404')
        self.assertEqual(transaction.meta_data['plan_name'], 'Premium Plan')
        
        # Verify wallet balance updated
        self.usdt_wallet.refresh_from_db()
        self.assertEqual(self.usdt_wallet.balance, initial_balance - Decimal('500.000000'))
    
    def test_log_breakdown_refund(self):
        """Test logging investment breakdown refund transactions."""
        initial_balance = self.usdt_wallet.balance
        
        transaction = TransactionIntegrationService.log_breakdown_refund(
            user=self.user,
            amount=Decimal('250.000000'),
            currency='USDT',
            reference_id='refund_ref_505',
            meta_data={'investment_id': 'inv_789', 'breakdown_reason': 'early_termination'}
        )
        
        # Verify transaction
        self.assertEqual(transaction.type, 'BREAKDOWN_REFUND')
        self.assertEqual(transaction.currency, 'USDT')
        self.assertEqual(transaction.amount, Decimal('250.000000'))
        self.assertEqual(transaction.reference_id, 'refund_ref_505')
        self.assertEqual(transaction.meta_data['breakdown_reason'], 'early_termination')
        
        # Verify wallet balance updated
        self.usdt_wallet.refresh_from_db()
        self.assertEqual(self.usdt_wallet.balance, initial_balance + Decimal('250.000000'))
    
    def test_integration_service_creates_wallets_if_not_exist(self):
        """Test that integration service creates wallets if they don't exist."""
        new_user = UserFactory()
        
        # Verify no wallets exist
        self.assertFalse(INRWallet.objects.filter(user=new_user).exists())
        self.assertFalse(USDTWallet.objects.filter(user=new_user).exists())
        
        # Log transactions - should create wallets
        TransactionIntegrationService.log_deposit(
            user=new_user,
            amount=Decimal('100.00'),
            currency='INR',
            reference_id='test_ref'
        )
        
        TransactionIntegrationService.log_roi_payout(
            user=new_user,
            amount=Decimal('50.000000'),
            currency='USDT',
            reference_id='test_ref'
        )
        
        # Verify wallets were created
        inr_wallet = INRWallet.objects.get(user=new_user)
        usdt_wallet = USDTWallet.objects.get(user=new_user)
        
        self.assertEqual(inr_wallet.balance, Decimal('100.00'))
        self.assertEqual(usdt_wallet.balance, Decimal('50.000000'))
