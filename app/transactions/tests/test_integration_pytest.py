"""
Pytest-style integration tests for the Transactions module.

These tests use pytest fixtures and markers for better organization and performance.
"""
import pytest
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time
from datetime import timedelta

from app.transactions.models import Transaction
from app.transactions.services import TransactionService, TransactionIntegrationService


@pytest.mark.integration
@pytest.mark.wallet
class TestWalletIntegration:
    """Test integration between Transactions and Wallet modules."""
    
    def test_deposit_inr_creates_transaction_and_updates_wallet(
        self, test_user, inr_wallet
    ):
        """Test that INR deposit creates transaction and updates wallet balance."""
        initial_balance = inr_wallet.balance
        deposit_amount = Decimal('1000.00')
        
        # Create deposit transaction
        transaction = TransactionIntegrationService.log_deposit(
            user=test_user,
            amount=deposit_amount,
            currency='INR',
            reference_id='DEP_PYTEST1',
            meta_data={'payment_method': 'bank_transfer'}
        )
        
        # Refresh wallet from database
        inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        assert transaction.type == 'DEPOSIT'
        assert transaction.currency == 'INR'
        assert transaction.amount == deposit_amount
        assert transaction.reference_id == 'DEP_PYTEST1'
        assert transaction.status == 'SUCCESS'
        assert transaction.meta_data['payment_method'] == 'bank_transfer'
        
        # Verify wallet balance increased
        assert inr_wallet.balance == initial_balance + deposit_amount
        
        # Verify transaction is linked to user
        assert transaction.user == test_user
    
    def test_deposit_usdt_creates_transaction_and_updates_wallet(
        self, test_user, usdt_wallet
    ):
        """Test that USDT deposit creates transaction and updates wallet balance."""
        initial_balance = usdt_wallet.balance
        deposit_amount = Decimal('100.000000')
        
        # Create deposit transaction
        transaction = TransactionIntegrationService.log_deposit(
            user=test_user,
            amount=deposit_amount,
            currency='USDT',
            reference_id='DEP_PYTEST2',
            meta_data={'tx_hash': '0x456def'}
        )
        
        # Refresh wallet from database
        usdt_wallet.refresh_from_db()
        
        # Verify transaction was created
        assert transaction.type == 'DEPOSIT'
        assert transaction.currency == 'USDT'
        assert transaction.amount == deposit_amount
        assert transaction.reference_id == 'DEP_PYTEST2'
        assert transaction.status == 'SUCCESS'
        assert transaction.meta_data['tx_hash'] == '0x456def'
        
        # Verify wallet balance increased
        assert usdt_wallet.balance == initial_balance + deposit_amount
    
    def test_withdrawal_inr_creates_transaction_and_updates_wallet(
        self, test_user, inr_wallet
    ):
        """Test that INR withdrawal creates transaction and updates wallet balance."""
        # First deposit some funds
        TransactionIntegrationService.log_deposit(
            user=test_user,
            amount=Decimal('1000.00'),
            currency='INR',
            reference_id='DEP_PYTEST3'
        )
        
        inr_wallet.refresh_from_db()
        initial_balance = inr_wallet.balance
        withdrawal_amount = Decimal('500.00')
        
        # Create withdrawal transaction
        transaction = TransactionIntegrationService.log_withdrawal(
            user=test_user,
            amount=withdrawal_amount,
            currency='INR',
            reference_id='WTH_PYTEST1',
            meta_data={'bank_account': '1234567890'}
        )
        
        # Refresh wallet from database
        inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        assert transaction.type == 'WITHDRAWAL'
        assert transaction.currency == 'INR'
        assert transaction.amount == withdrawal_amount
        assert transaction.reference_id == 'WTH_PYTEST1'
        assert transaction.status == 'SUCCESS'
        assert transaction.meta_data['bank_account'] == '1234567890'
        
        # Verify wallet balance decreased
        assert inr_wallet.balance == initial_balance - withdrawal_amount
    
    def test_insufficient_balance_withdrawal_fails(self, test_user, inr_wallet):
        """Test that withdrawal with insufficient balance fails."""
        # Try to withdraw more than available balance
        withdrawal_amount = Decimal('1000.00')
        
        with pytest.raises(ValueError) as exc_info:
            TransactionIntegrationService.log_withdrawal(
                user=test_user,
                amount=withdrawal_amount,
                currency='INR',
                reference_id='WTH_PYTEST2'
            )
        
        assert 'Insufficient INR balance' in str(exc_info.value)
        
        # Verify no transaction was created
        assert Transaction.objects.filter(type='WITHDRAWAL').count() == 0
        
        # Verify wallet balance unchanged
        inr_wallet.refresh_from_db()
        assert inr_wallet.balance == Decimal('0.00')


@pytest.mark.integration
@pytest.mark.investment
class TestInvestmentIntegration:
    """Test integration between Transactions and Investment modules."""
    
    def test_investment_purchase_creates_transaction_and_updates_wallet(
        self, test_user, inr_wallet, investment_plan
    ):
        """Test that investment purchase creates transaction and updates wallet balance."""
        # First deposit funds
        TransactionIntegrationService.log_deposit(
            user=test_user,
            amount=Decimal('10000.00'),
            currency='INR',
            reference_id='DEP_INV1'
        )
        
        inr_wallet.refresh_from_db()
        initial_balance = inr_wallet.balance
        investment_amount = Decimal('5000.00')
        
        # Create investment purchase transaction
        transaction = TransactionIntegrationService.log_plan_purchase(
            user=test_user,
            amount=investment_amount,
            currency='INR',
            reference_id='INV_PYTEST1',
            meta_data={'plan_id': str(investment_plan.id)}
        )
        
        # Refresh wallet from database
        inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        assert transaction.type == 'PLAN_PURCHASE'
        assert transaction.currency == 'INR'
        assert transaction.amount == investment_amount
        assert transaction.reference_id == 'INV_PYTEST1'
        assert transaction.status == 'SUCCESS'
        assert transaction.meta_data['plan_id'] == str(investment_plan.id)
        
        # Verify wallet balance decreased
        assert inr_wallet.balance == initial_balance - investment_amount
    
    @freeze_time("2024-01-01")
    def test_roi_payout_creates_transaction_and_updates_wallet(
        self, test_user, inr_wallet, investment_plan
    ):
        """Test that ROI payout creates transaction and updates wallet balance."""
        # First create an investment
        investment_amount = Decimal('5000.00')
        from app.investment.models import Investment
        
        investment = Investment.objects.create(
            user=test_user,
            plan=investment_plan,
            amount=investment_amount,
            currency='INR',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365)
        )
        
        # Create ROI payout transaction
        roi_amount = Decimal('600.00')  # 12% of 5000
        transaction = TransactionIntegrationService.log_roi_payout(
            user=test_user,
            amount=roi_amount,
            currency='INR',
            reference_id='ROI_PYTEST1',
            meta_data={
                'investment_id': str(investment.id),
                'roi_period': 'monthly',
                'roi_rate': '0.12'
            }
        )
        
        # Refresh wallet from database
        inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        assert transaction.type == 'ROI'
        assert transaction.currency == 'INR'
        assert transaction.amount == roi_amount
        assert transaction.reference_id == 'ROI_PYTEST1'
        assert transaction.status == 'SUCCESS'
        assert transaction.meta_data['investment_id'] == str(investment.id)
        
        # Verify wallet balance increased
        assert inr_wallet.balance == roi_amount
    
    def test_investment_breakdown_refund_creates_transaction(
        self, test_user, inr_wallet
    ):
        """Test that investment breakdown refund creates transaction."""
        # Create breakdown refund transaction
        refund_amount = Decimal('2500.00')
        transaction = TransactionIntegrationService.log_breakdown_refund(
            user=test_user,
            amount=refund_amount,
            currency='INR',
            reference_id='REF_PYTEST1',
            meta_data={'reason': 'plan_discontinued'}
        )
        
        # Refresh wallet from database
        inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        assert transaction.type == 'BREAKDOWN_REFUND'
        assert transaction.currency == 'INR'
        assert transaction.amount == refund_amount
        assert transaction.reference_id == 'REF_PYTEST1'
        assert transaction.status == 'SUCCESS'
        assert transaction.meta_data['reason'] == 'plan_discontinued'
        
        # Verify wallet balance increased
        assert inr_wallet.balance == refund_amount


@pytest.mark.integration
@pytest.mark.referral
class TestReferralIntegration:
    """Test integration between Transactions and Referral modules."""
    
    def test_referral_bonus_creates_transaction_and_updates_wallet(
        self, referrer_user, referrer_wallets, referral_relationship
    ):
        """Test that referral bonus creates transaction and updates wallet balance."""
        referrer_inr_wallet, _ = referrer_wallets
        initial_balance = referrer_inr_wallet.balance
        bonus_amount = Decimal('500.00')
        
        # Create referral bonus transaction
        transaction = TransactionIntegrationService.log_referral_bonus(
            user=referrer_user,
            amount=bonus_amount,
            currency='INR',
            reference_id='REF_BONUS_PYTEST1',
            meta_data={
                'referral_id': str(referral_relationship.id),
                'level': 1,
                'referred_username': referral_relationship.referred_user.username
            }
        )
        
        # Refresh wallet from database
        referrer_inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        assert transaction.type == 'REFERRAL_BONUS'
        assert transaction.currency == 'INR'
        assert transaction.amount == bonus_amount
        assert transaction.reference_id == 'REF_BONUS_PYTEST1'
        assert transaction.status == 'SUCCESS'
        assert transaction.meta_data['referral_id'] == str(referral_relationship.id)
        assert transaction.meta_data['level'] == 1
        
        # Verify wallet balance increased
        assert referrer_inr_wallet.balance == initial_balance + bonus_amount
    
    def test_milestone_bonus_creates_transaction_and_updates_wallet(
        self, referrer_user, referrer_wallets, referral_relationship
    ):
        """Test that milestone bonus creates transaction and updates wallet balance."""
        referrer_inr_wallet, _ = referrer_wallets
        initial_balance = referrer_inr_wallet.balance
        bonus_amount = Decimal('1000.00')
        
        # Create milestone bonus transaction
        transaction = TransactionIntegrationService.log_milestone_bonus(
            user=referrer_user,
            amount=bonus_amount,
            currency='INR',
            reference_id='MILESTONE_PYTEST1',
            meta_data={
                'milestone': 'first_investment',
                'referred_user_id': str(referral_relationship.referred_user.id)
            }
        )
        
        # Refresh wallet from database
        referrer_inr_wallet.refresh_from_db()
        
        # Verify transaction was created
        assert transaction.type == 'MILESTONE_BONUS'
        assert transaction.currency == 'INR'
        assert transaction.amount == bonus_amount
        assert transaction.reference_id == 'MILESTONE_PYTEST1'
        assert transaction.status == 'SUCCESS'
        assert transaction.meta_data['milestone'] == 'first_investment'
        
        # Verify wallet balance increased
        assert referrer_inr_wallet.balance == initial_balance + bonus_amount


@pytest.mark.integration
@pytest.mark.e2e
class TestEndToEndIntegration:
    """Test complete end-to-end transaction flow."""
    
    def test_complete_transaction_flow(self, complete_transaction_flow):
        """Test complete transaction flow: deposit → invest → ROI → referral → withdrawal."""
        flow = complete_transaction_flow
        
        # Verify all transactions were created
        assert len(flow) == 5
        assert 'deposit' in flow
        assert 'investment' in flow
        assert 'roi' in flow
        assert 'referral_bonus' in flow
        assert 'withdrawal' in flow
        
        # Verify transaction types
        assert flow['deposit'].type == 'DEPOSIT'
        assert flow['investment'].type == 'PLAN_PURCHASE'
        assert flow['roi'].type == 'ROI'
        assert flow['referral_bonus'].type == 'REFERRAL_BONUS'
        assert flow['withdrawal'].type == 'WITHDRAWAL'
        
        # Verify all transactions are successful
        for transaction in flow.values():
            assert transaction.status == 'SUCCESS'
            assert transaction.currency == 'INR'
    
    def test_transaction_chronological_order(self, referred_user):
        """Test that transactions are created in correct chronological order."""
        with freeze_time("2024-01-01 10:00:00"):
            deposit_transaction = TransactionIntegrationService.log_deposit(
                user=referred_user,
                amount=Decimal('1000.00'),
                currency='INR',
                reference_id='TIME_PYTEST1'
            )
        
        with freeze_time("2024-01-01 10:01:00"):
            investment_transaction = TransactionIntegrationService.log_plan_purchase(
                user=referred_user,
                amount=Decimal('500.00'),
                currency='INR',
                reference_id='TIME_PYTEST2'
            )
        
        with freeze_time("2024-01-01 10:02:00"):
            roi_transaction = TransactionIntegrationService.log_roi_payout(
                user=referred_user,
                amount=Decimal('60.00'),
                currency='INR',
                reference_id='TIME_PYTEST3'
            )
        
        # Verify chronological order
        transactions = Transaction.objects.filter(
            user=referred_user
        ).order_by('created_at')
        
        assert len(transactions) == 3
        assert transactions[0].type == 'DEPOSIT'
        assert transactions[1].type == 'PLAN_PURCHASE'
        assert transactions[2].type == 'ROI'
        
        # Verify timestamps are in order
        assert transactions[0].created_at < transactions[1].created_at
        assert transactions[1].created_at < transactions[2].created_at


@pytest.mark.integration
@pytest.mark.api
class TestAPIIntegration:
    """Test API integration for transactions."""
    
    def test_user_transactions_api_returns_only_own_transactions(
        self, test_user, sample_transactions
    ):
        """Test that user transactions API returns only user's own transactions."""
        from app.transactions.views import TransactionViewSet
        from rest_framework.test import APIRequestFactory
        from rest_framework.test import force_authenticate
        
        factory = APIRequestFactory()
        request = factory.get('/api/transactions/')
        force_authenticate(request, user=test_user)
        
        view = TransactionViewSet.as_view({'get': 'list'})
        response = view(request)
        
        assert response.status_code == 200
        assert len(response.data['results']) == 3
        
        # Verify all transactions belong to the user
        for transaction in response.data['results']:
            assert transaction['user']['username'] == test_user.username
    
    def test_admin_transactions_api_returns_all_transactions(
        self, admin_user, sample_transactions
    ):
        """Test that admin transactions API returns all transactions."""
        from app.transactions.views import AdminTransactionViewSet
        from rest_framework.test import APIRequestFactory
        from rest_framework.test import force_authenticate
        
        factory = APIRequestFactory()
        request = factory.get('/api/admin/transactions/')
        force_authenticate(request, user=admin_user)
        
        view = AdminTransactionViewSet.as_view({'get': 'list'})
        response = view(request)
        
        assert response.status_code == 200
        assert len(response.data['results']) == 3
    
    def test_transaction_filters_work_correctly(self, test_user, sample_transactions):
        """Test that transaction filters work correctly."""
        # Test type filter
        deposit_transactions = TransactionService.get_user_transactions(
            user=test_user,
            filters={'type': 'DEPOSIT'}
        )
        assert len(deposit_transactions['transactions']) == 1
        assert deposit_transactions['transactions'][0].type == 'DEPOSIT'
        
        # Test currency filter
        inr_transactions = TransactionService.get_user_transactions(
            user=test_user,
            filters={'currency': 'INR'}
        )
        assert len(inr_transactions['transactions']) == 3
        
        # Test status filter
        success_transactions = TransactionService.get_user_transactions(
            user=test_user,
            filters={'status': 'SUCCESS'}
        )
        assert len(success_transactions['transactions']) == 3


@pytest.mark.integration
class TestDataIntegrity:
    """Test data integrity for transactions."""
    
    def test_no_transaction_without_linked_user(self):
        """Test that no transaction can exist without a linked user."""
        with pytest.raises(Exception):
            Transaction.objects.create(
                type='DEPOSIT',
                currency='INR',
                amount=Decimal('100.00'),
                status='SUCCESS'
                # user field is required
            )
    
    def test_no_duplicate_reference_id_for_same_type(self, test_user):
        """Test that no duplicate reference_id exists for the same transaction type."""
        # Create first transaction
        TransactionIntegrationService.log_deposit(
            user=test_user,
            amount=Decimal('100.00'),
            currency='INR',
            reference_id='DUPLICATE_PYTEST'
        )
        
        # Try to create second transaction with same reference_id and type
        with pytest.raises(Exception):
            TransactionIntegrationService.log_deposit(
                user=test_user,
                amount=Decimal('200.00'),
                currency='INR',
                reference_id='DUPLICATE_PYTEST'  # Same reference_id
            )
    
    def test_no_negative_balances_from_mismatched_transactions(
        self, test_user, inr_wallet
    ):
        """Test that wallet balances never go negative."""
        # Try to withdraw more than available balance
        with pytest.raises(ValueError):
            TransactionIntegrationService.log_withdrawal(
                user=test_user,
                amount=Decimal('2000.00'),  # More than available 0.00
                currency='INR',
                reference_id='NEGATIVE_PYTEST'
            )
        
        # Verify wallet balance unchanged
        inr_wallet.refresh_from_db()
        assert inr_wallet.balance == Decimal('0.00')
        
        # Verify no transaction was created
        assert Transaction.objects.filter(type='WITHDRAWAL').count() == 0
    
    def test_transaction_metadata_integrity(self, test_user):
        """Test that transaction metadata maintains integrity."""
        transaction = TransactionIntegrationService.log_deposit(
            user=test_user,
            amount=Decimal('100.00'),
            currency='INR',
            reference_id='METADATA_PYTEST',
            meta_data={
                'payment_method': 'bank_transfer',
                'bank_name': 'Test Bank',
                'account_number': '1234567890'
            }
        )
        
        # Verify metadata was stored correctly
        assert transaction.meta_data['payment_method'] == 'bank_transfer'
        assert transaction.meta_data['bank_name'] == 'Test Bank'
        assert transaction.meta_data['account_number'] == '1234567890'
        
        # Update metadata
        transaction.add_metadata('status', 'confirmed')
        transaction.refresh_from_db()
        
        # Verify metadata update
        assert transaction.meta_data['status'] == 'confirmed'
        assert transaction.meta_data['payment_method'] == 'bank_transfer'  # Original preserved


@pytest.mark.integration
@pytest.mark.performance
class TestPerformance:
    """Test transaction performance and scalability."""
    
    def test_bulk_transaction_creation_performance(
        self, test_user, inr_wallet, performance_monitor
    ):
        """Test performance of creating multiple transactions."""
        performance_monitor.start()
        
        # Create 100 transactions
        for i in range(100):
            TransactionIntegrationService.log_deposit(
                user=test_user,
                amount=Decimal('10.00'),
                currency='INR',
                reference_id=f'PERF_PYTEST_{i}'
            )
        
        performance_monitor.stop()
        
        # Verify all transactions were created
        assert Transaction.objects.filter(user=test_user).count() == 100
        
        # Performance should be reasonable (less than 10 seconds for 100 transactions)
        performance_monitor.assert_fast_enough(10.0)
    
    def test_transaction_query_performance(
        self, test_user, inr_wallet, performance_monitor
    ):
        """Test performance of querying transactions."""
        # Create test data
        for i in range(50):
            TransactionIntegrationService.log_deposit(
                user=test_user,
                amount=Decimal('10.00'),
                currency='INR',
                reference_id=f'QUERY_PYTEST_{i}'
            )
        
        performance_monitor.start()
        
        # Query with filters
        result = TransactionService.get_user_transactions(
            user=test_user,
            filters={'type': 'DEPOSIT', 'currency': 'INR'},
            page=1,
            page_size=20
        )
        
        performance_monitor.stop()
        
        # Verify results
        assert len(result['transactions']) == 20
        assert result['pagination']['total_count'] == 50
        
        # Query should be fast (less than 1 second)
        performance_monitor.assert_fast_enough(1.0)
    
    def test_wallet_balance_update_performance(
        self, test_user, inr_wallet, performance_monitor
    ):
        """Test performance of wallet balance updates."""
        performance_monitor.start()
        
        # Test multiple balance updates
        for i in range(100):
            TransactionIntegrationService.log_deposit(
                user=test_user,
                amount=Decimal('1.00'),
                currency='INR',
                reference_id=f'BALANCE_PYTEST_{i}'
            )
        
        performance_monitor.stop()
        
        # Verify final balance
        inr_wallet.refresh_from_db()
        expected_balance = Decimal('100.00')
        assert inr_wallet.balance == expected_balance
        
        # Updates should be fast (less than 5 seconds for 100 updates)
        performance_monitor.assert_fast_enough(5.0)


@pytest.mark.integration
@pytest.mark.slow
class TestComplexScenarios:
    """Test complex transaction scenarios."""
    
    def test_multi_user_transaction_flow(self):
        """Test transaction flow with multiple users."""
        # Create multiple users with wallets
        users = []
        wallets = []
        
        for i in range(5):
            user = User.objects.create_user(
                username=f'user_{i}',
                email=f'user{i}@example.com',
                password='testpass123'
            )
            inr_wallet = INRWallet.objects.create(
                user=user,
                balance=Decimal('1000.00')
            )
            users.append(user)
            wallets.append(inr_wallet)
        
        # Create referral chain
        referrals = []
        for i in range(4):
            referral = Referral.objects.create(
                user=users[i],
                referred_user=users[i + 1],
                level=i + 1
            )
            referrals.append(referral)
        
        # Simulate complex transaction flow
        transactions = []
        
        # All users deposit
        for i, user in enumerate(users):
            transaction = TransactionIntegrationService.log_deposit(
                user=user,
                amount=Decimal('500.00'),
                currency='INR',
                reference_id=f'COMPLEX_DEP_{i}'
            )
            transactions.append(transaction)
        
        # All users buy investments
        for i, user in enumerate(users):
            transaction = TransactionIntegrationService.log_plan_purchase(
                user=user,
                amount=Decimal('300.00'),
                currency='INR',
                reference_id=f'COMPLEX_INV_{i}'
            )
            transactions.append(transaction)
        
        # Generate referral bonuses
        for i, referral in enumerate(referrals):
            bonus_amount = Decimal('15.00')  # 5% of investment
            transaction = TransactionIntegrationService.log_referral_bonus(
                user=referral.user,
                amount=bonus_amount,
                currency='INR',
                reference_id=f'COMPLEX_REF_{i}'
            )
            transactions.append(transaction)
        
        # Verify all transactions were created
        assert len(transactions) == 15  # 5 deposits + 5 investments + 5 referral bonuses
        
        # Verify all transactions are successful
        for transaction in transactions:
            assert transaction.status == 'SUCCESS'
            assert transaction.currency == 'INR'
        
        # Verify wallet balances are correct
        for i, wallet in enumerate(wallets):
            wallet.refresh_from_db()
            # Initial: 1000, Deposit: +500, Investment: -300, Referral bonus: +15 (if referrer)
            expected_balance = Decimal('1000.00') + Decimal('500.00') - Decimal('300.00')
            if i < 4:  # Referrers get bonus
                expected_balance += Decimal('15.00')
            assert wallet.balance == expected_balance
        
        # Cleanup
        for user in users:
            user.delete()
    
    def test_concurrent_transaction_creation(self, test_user, inr_wallet):
        """Test concurrent transaction creation."""
        import threading
        import time
        
        def create_transaction(thread_id):
            """Create a transaction in a separate thread."""
            try:
                TransactionIntegrationService.log_deposit(
                    user=test_user,
                    amount=Decimal('10.00'),
                    currency='INR',
                    reference_id=f'CONCURRENT_{thread_id}'
                )
                return True
            except Exception as e:
                print(f"Thread {thread_id} failed: {e}")
                return False
        
        # Create multiple threads
        threads = []
        results = []
        
        for i in range(10):
            thread = threading.Thread(
                target=lambda tid=i: results.append(create_transaction(tid))
            )
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # Verify all transactions were created successfully
        assert len(results) == 10
        assert all(results)
        
        # Verify final wallet balance
        inr_wallet.refresh_from_db()
        assert inr_wallet.balance == Decimal('100.00')  # 10 * 10.00
        
        # Performance should be reasonable
        total_time = end_time - start_time
        assert total_time < 5.0, f"Concurrent transactions took {total_time:.2f}s, expected < 5s"
