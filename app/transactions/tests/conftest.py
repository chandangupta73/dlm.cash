"""
Pytest configuration and fixtures for transaction integration tests.

This file provides:
- Database configuration
- Test data factories
- Common fixtures
- Performance monitoring
"""
import pytest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from freezegun import freeze_time
from datetime import timedelta

from app.transactions.models import Transaction
from app.transactions.services import TransactionIntegrationService
from app.wallet.models import INRWallet, USDTWallet
from app.investment.models import Investment, InvestmentPlan, InvestmentROI
from app.referral.models import Referral, ReferralBonus

User = get_user_model()


@pytest.fixture
def test_user():
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def admin_user():
    """Create an admin user."""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )


@pytest.fixture
def referrer_user():
    """Create a referrer user."""
    return User.objects.create_user(
        username='referrer',
        email='referrer@example.com',
        password='testpass123'
    )


@pytest.fixture
def referred_user():
    """Create a referred user."""
    return User.objects.create_user(
        username='referred',
        email='referred@example.com',
        password='testpass123'
    )


@pytest.fixture
def inr_wallet(test_user):
    """Create INR wallet for test user."""
    return INRWallet.objects.create(
        user=test_user,
        balance=Decimal('0.00')
    )


@pytest.fixture
def usdt_wallet(test_user):
    """Create USDT wallet for test user."""
    return USDTWallet.objects.create(
        user=test_user,
        balance=Decimal('0.000000')
    )


@pytest.fixture
def referrer_wallets(referrer_user):
    """Create wallets for referrer user."""
    inr_wallet = INRWallet.objects.create(
        user=referrer_user,
        balance=Decimal('0.00')
    )
    usdt_wallet = USDTWallet.objects.create(
        user=referrer_user,
        balance=Decimal('0.000000')
    )
    return inr_wallet, usdt_wallet


@pytest.fixture
def referred_wallets(referred_user):
    """Create wallets for referred user."""
    inr_wallet = INRWallet.objects.create(
        user=referred_user,
        balance=Decimal('10000.00')
    )
    usdt_wallet = USDTWallet.objects.create(
        user=referred_user,
        balance=Decimal('1000.000000')
    )
    return inr_wallet, usdt_wallet


@pytest.fixture
def investment_plan():
    """Create a test investment plan."""
    return InvestmentPlan.objects.create(
        name='Test Plan',
        min_amount=Decimal('1000.00'),
        max_amount=Decimal('10000.00'),
        roi_rate=Decimal('0.12'),  # 12% ROI
        duration_days=365,
        currency='INR'
    )


@pytest.fixture
def referral_relationship(referrer_user, referred_user):
    """Create a referral relationship."""
    return Referral.objects.create(
        user=referrer_user,
        referred_user=referred_user,
        level=1
    )


@pytest.fixture
def sample_transactions(test_user, inr_wallet):
    """Create sample transactions for testing."""
    # Deposit
    deposit = TransactionIntegrationService.log_deposit(
        user=test_user,
        amount=Decimal('1000.00'),
        currency='INR',
        reference_id='SAMPLE_DEP1'
    )
    
    # Withdrawal
    withdrawal = TransactionIntegrationService.log_withdrawal(
        user=test_user,
        amount=Decimal('500.00'),
        currency='INR',
        reference_id='SAMPLE_WTH1'
    )
    
    # ROI payout
    roi = TransactionIntegrationService.log_roi_payout(
        user=test_user,
        amount=Decimal('100.00'),
        currency='INR',
        reference_id='SAMPLE_ROI1'
    )
    
    return {
        'deposit': deposit,
        'withdrawal': withdrawal,
        'roi': roi
    }


@pytest.fixture
def complete_transaction_flow(referrer_user, referred_user, referrer_wallets, referred_wallets, investment_plan, referral_relationship):
    """Create a complete transaction flow for end-to-end testing."""
    
    with freeze_time("2024-01-01 10:00:00"):
        # Step 1: Referred user deposits funds
        deposit = TransactionIntegrationService.log_deposit(
            user=referred_user,
            amount=Decimal('10000.00'),
            currency='INR',
            reference_id='FLOW_DEP1'
        )
    
    with freeze_time("2024-01-01 10:01:00"):
        # Step 2: Referred user buys investment
        investment = TransactionIntegrationService.log_plan_purchase(
            user=referred_user,
            amount=Decimal('5000.00'),
            currency='INR',
            reference_id='FLOW_INV1'
        )
    
    with freeze_time("2024-01-01 10:02:00"):
        # Step 3: ROI payout
        roi = TransactionIntegrationService.log_roi_payout(
            user=referred_user,
            amount=Decimal('600.00'),
            currency='INR',
            reference_id='FLOW_ROI1'
        )
    
    with freeze_time("2024-01-01 10:03:00"):
        # Step 4: Referral bonus
        referral_bonus = TransactionIntegrationService.log_referral_bonus(
            user=referrer_user,
            amount=Decimal('250.00'),
            currency='INR',
            reference_id='FLOW_REF1'
        )
    
    with freeze_time("2024-01-01 10:04:00"):
        # Step 5: Withdrawal
        withdrawal = TransactionIntegrationService.log_withdrawal(
            user=referred_user,
            amount=Decimal('2000.00'),
            currency='INR',
            reference_id='FLOW_WTH1'
        )
    
    return {
        'deposit': deposit,
        'investment': investment,
        'roi': roi,
        'referral_bonus': referral_bonus,
        'withdrawal': withdrawal
    }


@pytest.fixture
def performance_test_data(test_user, inr_wallet):
    """Create performance test data."""
    transactions = []
    
    # Create 100 transactions for performance testing
    for i in range(100):
        transaction = TransactionIntegrationService.log_deposit(
            user=test_user,
            amount=Decimal('10.00'),
            currency='INR',
            reference_id=f'PERF_TEST_{i}'
        )
        transactions.append(transaction)
    
    return transactions


# Test data factories
class TransactionTestDataFactory:
    """Factory for creating test transaction data."""
    
    @staticmethod
    def create_user_with_wallets(username='factoryuser', email='factory@example.com'):
        """Create a user with wallets."""
        user = User.objects.create_user(
            username=username,
            email=email,
            password='testpass123'
        )
        
        inr_wallet = INRWallet.objects.create(
            user=user,
            balance=Decimal('0.00')
        )
        usdt_wallet = USDTWallet.objects.create(
            user=user,
            balance=Decimal('0.000000')
        )
        
        return user, inr_wallet, usdt_wallet
    
    @staticmethod
    def create_investment_plan(name='Factory Plan', roi_rate=Decimal('0.15')):
        """Create an investment plan."""
        return InvestmentPlan.objects.create(
            name=name,
            min_amount=Decimal('500.00'),
            max_amount=Decimal('5000.00'),
            roi_rate=roi_rate,
            duration_days=180,
            currency='INR'
        )
    
    @staticmethod
    def create_referral_chain(depth=3):
        """Create a multi-level referral chain."""
        users = []
        referrals = []
        
        # Create users
        for i in range(depth + 1):
            user = User.objects.create_user(
                username=f'referral_user_{i}',
                email=f'referral{i}@example.com',
                password='testpass123'
            )
            users.append(user)
            
            # Create wallets
            INRWallet.objects.create(user=user, balance=Decimal('0.00'))
            USDTWallet.objects.create(user=user, balance=Decimal('0.000000'))
        
        # Create referral relationships
        for i in range(depth):
            referral = Referral.objects.create(
                user=users[i],
                referred_user=users[i + 1],
                level=i + 1
            )
            referrals.append(referral)
        
        return users, referrals
    
    @staticmethod
    def create_transaction_batch(user, count=10, transaction_type='DEPOSIT'):
        """Create a batch of transactions."""
        transactions = []
        
        for i in range(count):
            if transaction_type == 'DEPOSIT':
                transaction = TransactionIntegrationService.log_deposit(
                    user=user,
                    amount=Decimal('100.00'),
                    currency='INR',
                    reference_id=f'BATCH_{transaction_type}_{i}'
                )
            elif transaction_type == 'WITHDRAWAL':
                transaction = TransactionIntegrationService.log_withdrawal(
                    user=user,
                    amount=Decimal('50.00'),
                    currency='INR',
                    reference_id=f'BATCH_{transaction_type}_{i}'
                )
            elif transaction_type == 'ROI':
                transaction = TransactionIntegrationService.log_roi_payout(
                    user=user,
                    amount=Decimal('25.00'),
                    currency='INR',
                    reference_id=f'BATCH_{transaction_type}_{i}'
                )
            
            transactions.append(transaction)
        
        return transactions


# Performance monitoring fixtures
@pytest.fixture
def performance_monitor():
    """Monitor performance of tests."""
    import time
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        def get_duration(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
        
        def assert_fast_enough(self, max_duration):
            duration = self.get_duration()
            if duration:
                assert duration < max_duration, f"Operation took {duration:.2f}s, expected < {max_duration}s"
    
    return PerformanceMonitor()


# Database transaction fixtures
@pytest.fixture
def db_transaction():
    """Provide database transaction context."""
    from django.db import transaction
    
    class DatabaseTransaction:
        def __enter__(self):
            self.transaction = transaction.atomic()
            self.transaction.__enter__()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                # Rollback on exception
                self.transaction.__exit__(exc_type, exc_val, exc_tb)
            else:
                # Commit on success
                self.transaction.__exit__(None, None, None)
    
    return DatabaseTransaction()


# Time control fixtures
@pytest.fixture
def time_controller():
    """Control time for tests."""
    class TimeController:
        def __init__(self):
            self.freezer = None
        
        def freeze_at(self, datetime_str):
            """Freeze time at specific datetime."""
            self.freezer = freeze_time(datetime_str)
            return self.freezer.start()
        
        def unfreeze(self):
            """Unfreeze time."""
            if self.freezer:
                self.freezer.stop()
        
        def advance_by(self, timedelta_obj):
            """Advance time by specific amount."""
            if self.freezer:
                self.freezer.tick(timedelta_obj)
    
    controller = TimeController()
    yield controller
    controller.unfreeze()


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Clean up test data after each test."""
    yield
    
    # Clean up transactions
    Transaction.objects.all().delete()
    
    # Clean up wallets
    INRWallet.objects.all().delete()
    USDTWallet.objects.all().delete()
    
    # Clean up users
    User.objects.all().delete()
    
    # Clean up other models
    InvestmentPlan.objects.all().delete()
    Referral.objects.all().delete()


# Test markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running tests"
    )
    config.addinivalue_line(
        "markers", "wallet: marks tests related to wallet integration"
    )
    config.addinivalue_line(
        "markers", "investment: marks tests related to investment integration"
    )
    config.addinivalue_line(
        "markers", "referral: marks tests related to referral integration"
    )
    config.addinivalue_line(
        "markers", "api: marks tests related to API integration"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
