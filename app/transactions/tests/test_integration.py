"""
Integration tests for the Transactions module.

These tests verify that the Transactions module correctly integrates with:
- Wallet module (deposits, withdrawals, balance updates)
- Investment module (ROI payouts, plan purchases)
- Referral module (bonus distributions)
- User module (authentication, permissions)
"""
import pytest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from freezegun import freeze_time
from datetime import timedelta

from app.transactions.models import Transaction
from app.transactions.services import TransactionService, TransactionIntegrationService
from app.wallet.models import INRWallet, USDTWallet
from app.investment.models import Investment, InvestmentPlan, InvestmentROI
from app.referral.models import Referral, ReferralBonus

User = get_user_model()


class TransactionWalletIntegrationTest(TestCase):
    """Test integration between Transactions and Wallet modules."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create wallets
        self.inr_wallet = INRWallet.objects.create(
            user=self.user,
            balance=Decimal('0.00')
        )
        self.usdt_wallet = USDTWallet.objects.create(
            user=self.user,
            balance=Decimal('0.000000')
        )
    
    def test_deposit_inr_creates_transaction_and_updates_wallet(self):
        """Test that INR deposit creates transaction and updates wallet balance."""
        initial_balance = self.inr_wallet.balance
        deposit_amount = Decimal('1000.00')
        
        # Create deposit transaction
        transaction = TransactionIntegrationService.log_deposit(
            user=self.user,
            amount=deposit_amount,
            currency='INR',
            reference_id='DEP123',
            meta_data={'payment_method': 'bank_transfer'}
        )
        
        # Refresh wallet from database
        self.inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        self.assertEqual(transaction.type, 'DEPOSIT')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, deposit_amount)
        self.assertEqual(transaction.reference_id, 'DEP123')
        self.assertEqual(transaction.status, 'SUCCESS')
        self.assertEqual(transaction.meta_data['payment_method'], 'bank_transfer')
        
        # Verify wallet balance increased
        self.assertEqual(self.inr_wallet.balance, initial_balance + deposit_amount)
        
        # Verify transaction is linked to user
        self.assertEqual(transaction.user, self.user)
    
    def test_deposit_usdt_creates_transaction_and_updates_wallet(self):
        """Test that USDT deposit creates transaction and updates wallet balance."""
        initial_balance = self.usdt_wallet.balance
        deposit_amount = Decimal('100.000000')
        
        # Create deposit transaction
        transaction = TransactionIntegrationService.log_deposit(
            user=self.user,
            amount=deposit_amount,
            currency='USDT',
            reference_id='DEP456',
            meta_data={'tx_hash': '0x123abc'}
        )
        
        # Refresh wallet from database
        self.usdt_wallet.refresh_from_db()
        
        # Verify transaction was created
        self.assertEqual(transaction.type, 'DEPOSIT')
        self.assertEqual(transaction.currency, 'USDT')
        self.assertEqual(transaction.amount, deposit_amount)
        self.assertEqual(transaction.reference_id, 'DEP456')
        self.assertEqual(transaction.status, 'SUCCESS')
        self.assertEqual(transaction.meta_data['tx_hash'], '0x123abc')
        
        # Verify wallet balance increased
        self.assertEqual(self.usdt_wallet.balance, initial_balance + deposit_amount)
    
    def test_withdrawal_inr_creates_transaction_and_updates_wallet(self):
        """Test that INR withdrawal creates transaction and updates wallet balance."""
        # First deposit some funds
        TransactionIntegrationService.log_deposit(
            user=self.user,
            amount=Decimal('1000.00'),
            currency='INR',
            reference_id='DEP789'
        )
        
        self.inr_wallet.refresh_from_db()
        initial_balance = self.inr_wallet.balance
        withdrawal_amount = Decimal('500.00')
        
        # Create withdrawal transaction
        transaction = TransactionIntegrationService.log_withdrawal(
            user=self.user,
            amount=withdrawal_amount,
            currency='INR',
            reference_id='WTH123',
            meta_data={'bank_account': '1234567890'}
        )
        
        # Refresh wallet from database
        self.inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        self.assertEqual(transaction.type, 'WITHDRAWAL')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, withdrawal_amount)
        self.assertEqual(transaction.reference_id, 'WTH123')
        self.assertEqual(transaction.status, 'SUCCESS')
        self.assertEqual(transaction.meta_data['bank_account'], '1234567890')
        
        # Verify wallet balance decreased
        self.assertEqual(self.inr_wallet.balance, initial_balance - withdrawal_amount)
    
    def test_withdrawal_usdt_creates_transaction_and_updates_wallet(self):
        """Test that USDT withdrawal creates transaction and updates wallet balance."""
        # First deposit some funds
        TransactionIntegrationService.log_deposit(
            user=self.user,
            amount=Decimal('100.000000'),
            currency='USDT',
            reference_id='DEP999'
        )
        
        self.usdt_wallet.refresh_from_db()
        initial_balance = self.usdt_wallet.balance
        withdrawal_amount = Decimal('50.000000')
        
        # Create withdrawal transaction
        transaction = TransactionIntegrationService.log_withdrawal(
            user=self.user,
            amount=withdrawal_amount,
            currency='USDT',
            reference_id='WTH456',
            meta_data={'wallet_address': '0xabc123'}
        )
        
        # Refresh wallet from database
        self.usdt_wallet.refresh_from_db()
        
        # Verify transaction was created
        self.assertEqual(transaction.type, 'WITHDRAWAL')
        self.assertEqual(transaction.currency, 'USDT')
        self.assertEqual(transaction.amount, withdrawal_amount)
        self.assertEqual(transaction.reference_id, 'WTH456')
        self.assertEqual(transaction.status, 'SUCCESS')
        self.assertEqual(transaction.meta_data['wallet_address'], '0xabc123')
        
        # Verify wallet balance decreased
        self.assertEqual(self.usdt_wallet.balance, initial_balance - withdrawal_amount)
    
    def test_insufficient_balance_withdrawal_fails(self):
        """Test that withdrawal with insufficient balance fails."""
        # Try to withdraw more than available balance
        withdrawal_amount = Decimal('1000.00')
        
        with self.assertRaises(ValueError) as context:
            TransactionIntegrationService.log_withdrawal(
                user=self.user,
                amount=withdrawal_amount,
                currency='INR',
                reference_id='WTH789'
            )
        
        self.assertIn('Insufficient INR balance', str(context.exception))
        
        # Verify no transaction was created
        self.assertEqual(Transaction.objects.filter(type='WITHDRAWAL').count(), 0)
        
        # Verify wallet balance unchanged
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('0.00'))


class TransactionInvestmentIntegrationTest(TestCase):
    """Test integration between Transactions and Investment modules."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='investor',
            email='investor@example.com',
            password='testpass123'
        )
        
        # Create wallets
        self.inr_wallet = INRWallet.objects.create(
            user=self.user,
            balance=Decimal('10000.00')
        )
        self.usdt_wallet = USDTWallet.objects.create(
            user=self.user,
            balance=Decimal('1000.000000')
        )
        
        # Create investment plan
        self.investment_plan = InvestmentPlan.objects.create(
            name='Test Plan',
            min_amount=Decimal('1000.00'),
            max_amount=Decimal('10000.00'),
            roi_rate=Decimal('0.12'),  # 12% ROI
            duration_days=365,
            currency='INR'
        )
    
    def test_investment_purchase_creates_transaction_and_updates_wallet(self):
        """Test that investment purchase creates transaction and updates wallet balance."""
        initial_balance = self.inr_wallet.balance
        investment_amount = Decimal('5000.00')
        
        # Create investment purchase transaction
        transaction = TransactionIntegrationService.log_plan_purchase(
            user=self.user,
            amount=investment_amount,
            currency='INR',
            reference_id='INV123',
            meta_data={'plan_id': str(self.investment_plan.id)}
        )
        
        # Refresh wallet from database
        self.inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        self.assertEqual(transaction.type, 'PLAN_PURCHASE')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, investment_amount)
        self.assertEqual(transaction.reference_id, 'INV123')
        self.assertEqual(transaction.status, 'SUCCESS')
        self.assertEqual(transaction.meta_data['plan_id'], str(self.investment_plan.id))
        
        # Verify wallet balance decreased
        self.assertEqual(self.inr_wallet.balance, initial_balance - investment_amount)
    
    @freeze_time("2024-01-01")
    def test_roi_payout_creates_transaction_and_updates_wallet(self):
        """Test that ROI payout creates transaction and updates wallet balance."""
        # First create an investment
        investment_amount = Decimal('5000.00')
        investment = Investment.objects.create(
            user=self.user,
            plan=self.investment_plan,
            amount=investment_amount,
            currency='INR',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365)
        )
        
        # Create ROI payout transaction
        roi_amount = Decimal('600.00')  # 12% of 5000
        transaction = TransactionIntegrationService.log_roi_payout(
            user=self.user,
            amount=roi_amount,
            currency='INR',
            reference_id='ROI123',
            meta_data={
                'investment_id': str(investment.id),
                'roi_period': 'monthly',
                'roi_rate': '0.12'
            }
        )
        
        # Refresh wallet from database
        self.inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        self.assertEqual(transaction.type, 'ROI')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, roi_amount)
        self.assertEqual(transaction.reference_id, 'ROI123')
        self.assertEqual(transaction.status, 'SUCCESS')
        self.assertEqual(transaction.meta_data['investment_id'], str(investment.id))
        
        # Verify wallet balance increased
        self.assertEqual(self.inr_wallet.balance, Decimal('10000.00') + roi_amount)
    
    def test_investment_breakdown_refund_creates_transaction(self):
        """Test that investment breakdown refund creates transaction."""
        # Create breakdown refund transaction
        refund_amount = Decimal('2500.00')
        transaction = TransactionIntegrationService.log_breakdown_refund(
            user=self.user,
            amount=refund_amount,
            currency='INR',
            reference_id='REF123',
            meta_data={'reason': 'plan_discontinued'}
        )
        
        # Refresh wallet from database
        self.inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        self.assertEqual(transaction.type, 'BREAKDOWN_REFUND')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, refund_amount)
        self.assertEqual(transaction.reference_id, 'REF123')
        self.assertEqual(transaction.status, 'SUCCESS')
        self.assertEqual(transaction.meta_data['reason'], 'plan_discontinued')
        
        # Verify wallet balance increased
        self.assertEqual(self.inr_wallet.balance, Decimal('10000.00') + refund_amount)


class TransactionReferralIntegrationTest(TestCase):
    """Test integration between Transactions and Referral modules."""
    
    def setUp(self):
        """Set up test data."""
        # Create referrer user
        self.referrer = User.objects.create_user(
            username='referrer',
            email='referrer@example.com',
            password='testpass123'
        )
        
        # Create referred user
        self.referred = User.objects.create_user(
            username='referred',
            email='referred@example.com',
            password='testpass123'
        )
        
        # Create wallets for referrer
        self.referrer_inr_wallet = INRWallet.objects.create(
            user=self.referrer,
            balance=Decimal('0.00')
        )
        self.referrer_usdt_wallet = USDTWallet.objects.create(
            user=self.referrer,
            balance=Decimal('0.000000')
        )
        
        # Create wallets for referred user
        self.referred_inr_wallet = INRWallet.objects.create(
            user=self.referred,
            balance=Decimal('10000.00')
        )
        
        # Create referral relationship
        self.referral = Referral.objects.create(
            user=self.referrer,
            referred_user=self.referred,
            level=1
        )
    
    def test_referral_bonus_creates_transaction_and_updates_wallet(self):
        """Test that referral bonus creates transaction and updates wallet balance."""
        initial_balance = self.referrer_inr_wallet.balance
        bonus_amount = Decimal('500.00')
        
        # Create referral bonus transaction
        transaction = TransactionIntegrationService.log_referral_bonus(
            user=self.referrer,
            amount=bonus_amount,
            currency='INR',
            reference_id='REF_BONUS123',
            meta_data={
                'referral_id': str(self.referral.id),
                'level': 1,
                'referred_username': self.referred.username
            }
        )
        
        # Refresh wallet from database
        self.referrer_inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        self.assertEqual(transaction.type, 'REFERRAL_BONUS')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, bonus_amount)
        self.assertEqual(transaction.reference_id, 'REF_BONUS123')
        self.assertEqual(transaction.status, 'SUCCESS')
        self.assertEqual(transaction.meta_data['referral_id'], str(self.referral.id))
        self.assertEqual(transaction.meta_data['level'], 1)
        self.assertEqual(transaction.meta_data['referred_username'], self.referred.username)
        
        # Verify wallet balance increased
        self.assertEqual(self.referrer_inr_wallet.balance, initial_balance + bonus_amount)
    
    def test_milestone_bonus_creates_transaction_and_updates_wallet(self):
        """Test that milestone bonus creates transaction and updates wallet balance."""
        initial_balance = self.referrer_inr_wallet.balance
        bonus_amount = Decimal('1000.00')
        
        # Create milestone bonus transaction
        transaction = TransactionIntegrationService.log_milestone_bonus(
            user=self.referrer,
            amount=bonus_amount,
            currency='INR',
            reference_id='MILESTONE123',
            meta_data={
                'milestone': 'first_investment',
                'referred_user_id': str(self.referred.id)
            }
        )
        
        # Refresh wallet from database
        self.referrer_inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        self.assertEqual(transaction.type, 'MILESTONE_BONUS')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.amount, bonus_amount)
        self.assertEqual(transaction.reference_id, 'MILESTONE123')
        self.assertEqual(transaction.status, 'SUCCESS')
        self.assertEqual(transaction.meta_data['milestone'], 'first_investment')
        
        # Verify wallet balance increased
        self.assertEqual(self.referrer_inr_wallet.balance, initial_balance + bonus_amount)


class TransactionEndToEndIntegrationTest(TestCase):
    """Test complete end-to-end transaction flow."""
    
    def setUp(self):
        """Set up test data."""
        # Create referrer user
        self.referrer = User.objects.create_user(
            username='referrer',
            email='referrer@example.com',
            password='testpass123'
        )
        
        # Create referred user
        self.referred = User.objects.create_user(
            username='referred',
            email='referred@example.com',
            password='testpass123'
        )
        
        # Create wallets for both users
        self.referrer_inr_wallet = INRWallet.objects.create(
            user=self.referrer,
            balance=Decimal('0.00')
        )
        self.referred_inr_wallet = INRWallet.objects.create(
            user=self.referred,
            balance=Decimal('0.00')
        )
        
        # Create referral relationship
        self.referral = Referral.objects.create(
            user=self.referrer,
            referred_user=self.referred,
            level=1
        )
        
        # Create investment plan
        self.investment_plan = InvestmentPlan.objects.create(
            name='Test Plan',
            min_amount=Decimal('1000.00'),
            max_amount=Decimal('10000.00'),
            roi_rate=Decimal('0.12'),
            duration_days=365,
            currency='INR'
        )
    
    @freeze_time("2024-01-01")
    def test_complete_transaction_flow(self):
        """Test complete transaction flow: deposit → invest → ROI → referral → withdrawal."""
        
        # Step 1: Referred user deposits funds
        deposit_amount = Decimal('10000.00')
        deposit_transaction = TransactionIntegrationService.log_deposit(
            user=self.referred,
            amount=deposit_amount,
            currency='INR',
            reference_id='DEP_FLOW123'
        )
        
        self.referred_inr_wallet.refresh_from_db()
        self.assertEqual(self.referred_inr_wallet.balance, deposit_amount)
        
        # Step 2: Referred user buys investment
        investment_amount = Decimal('5000.00')
        investment_transaction = TransactionIntegrationService.log_plan_purchase(
            user=self.referred,
            amount=investment_amount,
            currency='INR',
            reference_id='INV_FLOW123'
        )
        
        self.referred_inr_wallet.refresh_from_db()
        self.assertEqual(self.referred_inr_wallet.balance, deposit_amount - investment_amount)
        
        # Step 3: ROI payout
        roi_amount = Decimal('600.00')  # 12% of 5000
        roi_transaction = TransactionIntegrationService.log_roi_payout(
            user=self.referred,
            amount=roi_amount,
            currency='INR',
            reference_id='ROI_FLOW123'
        )
        
        self.referred_inr_wallet.refresh_from_db()
        self.assertEqual(self.referred_inr_wallet.balance, deposit_amount - investment_amount + roi_amount)
        
        # Step 4: Referral bonus for referrer
        referral_bonus = Decimal('250.00')  # 5% of investment
        referral_transaction = TransactionIntegrationService.log_referral_bonus(
            user=self.referrer,
            amount=referral_bonus,
            currency='INR',
            reference_id='REF_FLOW123'
        )
        
        self.referrer_inr_wallet.refresh_from_db()
        self.assertEqual(self.referrer_inr_wallet.balance, referral_bonus)
        
        # Step 5: Referred user withdraws some funds
        withdrawal_amount = Decimal('2000.00')
        withdrawal_transaction = TransactionIntegrationService.log_withdrawal(
            user=self.referred,
            amount=withdrawal_amount,
            currency='INR',
            reference_id='WTH_FLOW123'
        )
        
        self.referred_inr_wallet.refresh_from_db()
        expected_balance = deposit_amount - investment_amount + roi_amount - withdrawal_amount
        self.assertEqual(self.referred_inr_wallet.balance, expected_balance)
        
        # Verify all transactions were created in correct order
        all_transactions = Transaction.objects.filter(
            user__in=[self.referrer, self.referred]
        ).order_by('created_at')
        
        self.assertEqual(all_transactions.count(), 5)
        
        # Verify transaction types and amounts
        transaction_types = [t.type for t in all_transactions]
        expected_types = ['DEPOSIT', 'PLAN_PURCHASE', 'ROI', 'REFERRAL_BONUS', 'WITHDRAWAL']
        self.assertEqual(transaction_types, expected_types)
        
        # Verify no duplicate reference IDs
        reference_ids = [t.reference_id for t in all_transactions]
        self.assertEqual(len(reference_ids), len(set(reference_ids)))
        
        # Verify all transactions are linked to valid users
        for t in all_transactions:
            self.assertIsNotNone(t.user)
            self.assertTrue(t.user.is_active)
    
    def test_transaction_chronological_order(self):
        """Test that transactions are created in correct chronological order."""
        with freeze_time("2024-01-01 10:00:00"):
            deposit_transaction = TransactionIntegrationService.log_deposit(
                user=self.referred,
                amount=Decimal('1000.00'),
                currency='INR',
                reference_id='TIME_TEST1'
            )
        
        with freeze_time("2024-01-01 10:01:00"):
            investment_transaction = TransactionIntegrationService.log_plan_purchase(
                user=self.referred,
                amount=Decimal('500.00'),
                currency='INR',
                reference_id='TIME_TEST2'
            )
        
        with freeze_time("2024-01-01 10:02:00"):
            roi_transaction = TransactionIntegrationService.log_roi_payout(
                user=self.referred,
                amount=Decimal('60.00'),
                currency='INR',
                reference_id='TIME_TEST3'
            )
        
        # Verify chronological order
        transactions = Transaction.objects.filter(
            user=self.referred
        ).order_by('created_at')
        
        self.assertEqual(transactions[0].type, 'DEPOSIT')
        self.assertEqual(transactions[1].type, 'PLAN_PURCHASE')
        self.assertEqual(transactions[2].type, 'ROI')
        
        # Verify timestamps are in order
        self.assertLess(transactions[0].created_at, transactions[1].created_at)
        self.assertLess(transactions[1].created_at, transactions[2].created_at)


class TransactionAPIIntegrationTest(TestCase):
    """Test API integration for transactions."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='apiuser',
            email='api@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create wallets
        self.inr_wallet = INRWallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00')
        )
        
        # Create some test transactions
        TransactionIntegrationService.log_deposit(
            user=self.user,
            amount=Decimal('500.00'),
            currency='INR',
            reference_id='API_TEST1'
        )
        
        TransactionIntegrationService.log_withdrawal(
            user=self.user,
            amount=Decimal('200.00'),
            currency='INR',
            reference_id='API_TEST2'
        )
    
    def test_user_transactions_api_returns_only_own_transactions(self):
        """Test that user transactions API returns only user's own transactions."""
        from app.transactions.views import TransactionViewSet
        from rest_framework.test import APIRequestFactory
        from rest_framework.test import force_authenticate
        
        factory = APIRequestFactory()
        request = factory.get('/api/transactions/')
        force_authenticate(request, user=self.user)
        
        view = TransactionViewSet.as_view({'get': 'list'})
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 2)
        
        # Verify all transactions belong to the user
        for transaction in response.data['results']:
            self.assertEqual(transaction['user']['username'], self.user.username)
    
    def test_admin_transactions_api_returns_all_transactions(self):
        """Test that admin transactions API returns all transactions."""
        from app.transactions.views import AdminTransactionViewSet
        from rest_framework.test import APIRequestFactory
        from rest_framework.test import force_authenticate
        
        factory = APIRequestFactory()
        request = factory.get('/api/admin/transactions/')
        force_authenticate(request, user=self.admin_user)
        
        view = AdminTransactionViewSet.as_view({'get': 'list'})
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_transaction_filters_work_correctly(self):
        """Test that transaction filters work correctly."""
        from app.transactions.services import TransactionService
        
        # Test type filter
        deposit_transactions = TransactionService.get_user_transactions(
            user=self.user,
            filters={'type': 'DEPOSIT'}
        )
        self.assertEqual(len(deposit_transactions['transactions']), 1)
        self.assertEqual(deposit_transactions['transactions'][0].type, 'DEPOSIT')
        
        # Test currency filter
        inr_transactions = TransactionService.get_user_transactions(
            user=self.user,
            filters={'currency': 'INR'}
        )
        self.assertEqual(len(inr_transactions['transactions']), 2)
        
        # Test status filter
        success_transactions = TransactionService.get_user_transactions(
            user=self.user,
            filters={'status': 'SUCCESS'}
        )
        self.assertEqual(len(success_transactions['transactions']), 2)


class TransactionDataIntegrityTest(TestCase):
    """Test data integrity for transactions."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='integrityuser',
            email='integrity@example.com',
            password='testpass123'
        )
        
        self.inr_wallet = INRWallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00')
        )
    
    def test_no_transaction_without_linked_user(self):
        """Test that no transaction can exist without a linked user."""
        with self.assertRaises(Exception):
            Transaction.objects.create(
                type='DEPOSIT',
                currency='INR',
                amount=Decimal('100.00'),
                status='SUCCESS'
                # user field is required
            )
    
    def test_no_duplicate_reference_id_for_same_type(self):
        """Test that no duplicate reference_id exists for the same transaction type."""
        # Create first transaction
        TransactionIntegrationService.log_deposit(
            user=self.user,
            amount=Decimal('100.00'),
            currency='INR',
            reference_id='DUPLICATE_TEST'
        )
        
        # Try to create second transaction with same reference_id and type
        with self.assertRaises(Exception):
            TransactionIntegrationService.log_deposit(
                user=self.user,
                amount=Decimal('200.00'),
                currency='INR',
                reference_id='DUPLICATE_TEST'  # Same reference_id
            )
    
    def test_no_negative_balances_from_mismatched_transactions(self):
        """Test that wallet balances never go negative."""
        # Try to withdraw more than available balance
        with self.assertRaises(ValueError):
            TransactionIntegrationService.log_withdrawal(
                user=self.user,
                amount=Decimal('2000.00'),  # More than available 1000.00
                currency='INR',
                reference_id='NEGATIVE_TEST'
            )
        
        # Verify wallet balance unchanged
        self.inr_wallet.refresh_from_db()
        self.assertEqual(self.inr_wallet.balance, Decimal('1000.00'))
        
        # Verify no transaction was created
        self.assertEqual(Transaction.objects.filter(type='WITHDRAWAL').count(), 0)
    
    def test_transaction_metadata_integrity(self):
        """Test that transaction metadata maintains integrity."""
        transaction = TransactionIntegrationService.log_deposit(
            user=self.user,
            amount=Decimal('100.00'),
            currency='INR',
            reference_id='METADATA_TEST',
            meta_data={
                'payment_method': 'bank_transfer',
                'bank_name': 'Test Bank',
                'account_number': '1234567890'
            }
        )
        
        # Verify metadata was stored correctly
        self.assertEqual(transaction.meta_data['payment_method'], 'bank_transfer')
        self.assertEqual(transaction.meta_data['bank_name'], 'Test Bank')
        self.assertEqual(transaction.meta_data['account_number'], '1234567890')
        
        # Update metadata
        transaction.add_metadata('status', 'confirmed')
        transaction.refresh_from_db()
        
        # Verify metadata update
        self.assertEqual(transaction.meta_data['status'], 'confirmed')
        self.assertEqual(transaction.meta_data['payment_method'], 'bank_transfer')  # Original preserved


class TransactionPerformanceTest(TestCase):
    """Test transaction performance and scalability."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='perfuser',
            email='perf@example.com',
            password='testpass123'
        )
        
        self.inr_wallet = INRWallet.objects.create(
            user=self.user,
            balance=Decimal('10000.00')
        )
    
    def test_bulk_transaction_creation_performance(self):
        """Test performance of creating multiple transactions."""
        import time
        
        start_time = time.time()
        
        # Create 100 transactions
        for i in range(100):
            TransactionIntegrationService.log_deposit(
                user=self.user,
                amount=Decimal('10.00'),
                currency='INR',
                reference_id=f'PERF_TEST_{i}'
            )
        
        end_time = time.time()
        creation_time = end_time - start_time
        
        # Verify all transactions were created
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 100)
        
        # Performance should be reasonable (less than 10 seconds for 100 transactions)
        self.assertLess(creation_time, 10.0)
    
    def test_transaction_query_performance(self):
        """Test performance of querying transactions."""
        # Create test data
        for i in range(50):
            TransactionIntegrationService.log_deposit(
                user=self.user,
                amount=Decimal('10.00'),
                currency='INR',
                reference_id=f'QUERY_TEST_{i}'
            )
        
        import time
        
        # Test query performance
        start_time = time.time()
        
        # Query with filters
        from app.transactions.services import TransactionService
        result = TransactionService.get_user_transactions(
            user=self.user,
            filters={'type': 'DEPOSIT', 'currency': 'INR'},
            page=1,
            page_size=20
        )
        
        end_time = time.time()
        query_time = end_time - start_time
        
        # Verify results
        self.assertEqual(len(result['transactions']), 20)
        self.assertEqual(result['pagination']['total_count'], 50)
        
        # Query should be fast (less than 1 second)
        self.assertLess(query_time, 1.0)
    
    def test_wallet_balance_update_performance(self):
        """Test performance of wallet balance updates."""
        import time
        
        # Test multiple balance updates
        start_time = time.time()
        
        for i in range(100):
            TransactionIntegrationService.log_deposit(
                user=self.user,
                amount=Decimal('1.00'),
                currency='INR',
                reference_id=f'BALANCE_TEST_{i}'
            )
        
        end_time = time.time()
        update_time = end_time - start_time
        
        # Verify final balance
        self.inr_wallet.refresh_from_db()
        expected_balance = Decimal('10000.00') + Decimal('100.00')
        self.assertEqual(self.inr_wallet.balance, expected_balance)
        
        # Updates should be fast (less than 5 seconds for 100 updates)
        self.assertLess(update_time, 5.0)


# Factory classes for creating test data
class TransactionTestFactory:
    """Factory for creating test transaction data."""
    
    @staticmethod
    def create_user(username='testuser', email='test@example.com'):
        """Create a test user."""
        return User.objects.create_user(
            username=username,
            email=email,
            password='testpass123'
        )
    
    @staticmethod
    def create_wallets(user):
        """Create wallets for a user."""
        inr_wallet = INRWallet.objects.create(
            user=user,
            balance=Decimal('0.00')
        )
        usdt_wallet = USDTWallet.objects.create(
            user=user,
            balance=Decimal('0.000000')
        )
        return inr_wallet, usdt_wallet
    
    @staticmethod
    def create_investment_plan(name='Test Plan', roi_rate=Decimal('0.12')):
        """Create a test investment plan."""
        return InvestmentPlan.objects.create(
            name=name,
            min_amount=Decimal('1000.00'),
            max_amount=Decimal('10000.00'),
            roi_rate=roi_rate,
            duration_days=365,
            currency='INR'
        )
    
    @staticmethod
    def create_referral(referrer, referred_user, level=1):
        """Create a test referral relationship."""
        return Referral.objects.create(
            user=referrer,
            referred_user=referred_user,
            level=level
        )
    
    @staticmethod
    def create_transaction_flow(user, amount=Decimal('1000.00')):
        """Create a complete transaction flow for testing."""
        # Deposit
        deposit = TransactionIntegrationService.log_deposit(
            user=user,
            amount=amount,
            currency='INR',
            reference_id=f'FLOW_{user.id}_DEP'
        )
        
        # Withdrawal
        withdrawal = TransactionIntegrationService.log_withdrawal(
            user=user,
            amount=amount / 2,
            currency='INR',
            reference_id=f'FLOW_{user.id}_WTH'
        )
        
        return deposit, withdrawal
