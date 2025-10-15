import pytest
import os
import sys
from decimal import Decimal
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import tempfile
from io import BytesIO
from PIL import Image

# Django imports will be handled inside fixtures to avoid app registry issues
# from rest_framework.test import APIClient
# from rest_framework_simplejwt.tokens import RefreshToken
# from django.contrib.auth import get_user_model
# from app.users.models import User, KYCVerification
# from app.wallet.models import Wallet, DepositRequest, WithdrawalRequest, Transaction
# from app.investment.models import InvestmentPlan, Investment
# from app.referral.models import ReferralConfig, ReferralEarning
# from app.admin.models import AdminAction
# from freezegun import freeze_time

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# User = get_user_model()

@pytest.fixture(scope="session")
def django_db_setup():
    """Setup Django database for testing"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investment_system.settings')
    import django
    django.setup()
    return True

@pytest.fixture
def api_client():
    """Basic API client without authentication"""
    from rest_framework.test import APIClient
    return APIClient()

@pytest.fixture
def admin_user(django_db_setup):
    """Create admin user for testing"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    user = User.objects.create_user(
        username='admin_test',
        email='admin@test.com',
        password='adminpass123',
        is_staff=True,
        is_superuser=True
    )
    return user

@pytest.fixture
def regular_user(django_db_setup):
    """Create regular user for testing"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    user = User.objects.create_user(
        username='user_test',
        email='user@test.com',
        password='userpass123',
        is_staff=False,
        is_superuser=False,
        kyc_status='APPROVED',
        is_kyc_verified=True
    )
    return user

@pytest.fixture
def admin_token(admin_user):
    """Get JWT token for admin user"""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(admin_user)
    return str(refresh.access_token)

@pytest.fixture
def user_token(regular_user):
    """Get JWT token for regular user"""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(regular_user)
    return str(refresh.access_token)

@pytest.fixture
def admin_api_client(admin_token):
    """API client authenticated as admin"""
    from rest_framework.test import APIClient
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_token}')
    return client

@pytest.fixture
def user_api_client(user_token):
    """API client authenticated as regular user"""
    from rest_framework.test import APIClient
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {user_token}')
    return client

@pytest.fixture
def test_kyc_user(django_db_setup):
    """Create KYC-verified user for referral tests"""
    from django.contrib.auth import get_user_model
    from app.users.models import KYCVerification
    User = get_user_model()
    
    user = User.objects.create_user(
        username='kyc_user',
        email='kyc@test.com',
        password='kycpass123'
    )
    
    # Create KYC verification
    kyc = KYCVerification.objects.create(
        user=user,
        document_type='PAN',
        document_number='ABCDE1234F',
        status='approved',
        verified_at=datetime.now()
    )
    
    return user

@pytest.fixture
def test_investment_plan(django_db_setup):
    """Create test investment plan"""
    from app.investment.models import InvestmentPlan
    
    plan = InvestmentPlan.objects.create(
        name='Test Plan',
        min_amount=Decimal('1000.00'),
        max_amount=Decimal('10000.00'),
        roi_percentage=Decimal('12.50'),
        duration_days=365,
        is_active=True
    )
    return plan

@pytest.fixture
def test_referral_config(django_db_setup):
    """Create test referral configuration"""
    from app.referral.models import ReferralConfig
    
    config = ReferralConfig.objects.create(
        level_1_percentage=Decimal('5.00'),
        level_2_percentage=Decimal('3.00'),
        level_3_percentage=Decimal('1.00'),
        milestone_bonus=Decimal('100.00'),
        milestone_threshold=Decimal('10000.00'),
        is_active=True
    )
    return config

@pytest.fixture
def test_wallet(django_db_setup, regular_user):
    """Create test wallet for user"""
    from app.wallet.models import Wallet
    
    wallet = Wallet.objects.create(
        user=regular_user,
        currency='INR',
        balance=Decimal('0.00'),
        is_active=True
    )
    return wallet

@pytest.fixture
def test_transaction(django_db_setup, test_wallet):
    """Create test transaction"""
    from app.wallet.models import Transaction
    
    transaction = Transaction.objects.create(
        wallet=test_wallet,
        transaction_type='credit',
        amount=Decimal('1000.00'),
        balance_before=Decimal('0.00'),
        balance_after=Decimal('1000.00'),
        description='Test transaction',
        status='completed'
    )
    return transaction

@pytest.fixture
def mock_datetime():
    """Mock datetime for testing"""
    from freezegun import freeze_time
    with freeze_time('2024-01-15 10:00:00'):
        yield

@pytest.fixture
def sample_image_file():
    """Create a sample image file for testing"""
    file = BytesIO()
    image = Image.new('RGB', size=(100, 100), color='red')
    image.save(file, 'png')
    file.name = 'test.png'
    file.seek(0)
    return file

@pytest.fixture
def db_access(django_db_setup):
    """Override database access for in-memory SQLite in tests"""
    from django.test.utils import override_settings
    with override_settings(
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        }
    ):
        yield

class TestUtils:
    """Static methods to generate common request body data"""
    
    @staticmethod
    def get_user_registration_data():
        return {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User'
        }
    
    @staticmethod
    def get_kyc_data():
        return {
            'document_type': 'PAN',
            'document_number': 'ABCDE1234F',
            'full_name': 'Test User',
            'date_of_birth': '1990-01-01',
            'address': '123 Test Street, Test City'
        }
    
    @staticmethod
    def get_deposit_data(amount='1000.00', currency='INR'):
        return {
            'amount': amount,
            'currency': currency,
            'payment_method': 'bank_transfer',
            'reference_number': 'REF123456'
        }
    
    @staticmethod
    def get_withdrawal_data(amount='500.00', currency='INR'):
        return {
            'amount': amount,
            'currency': currency,
            'bank_account': '1234567890',
            'ifsc_code': 'TEST0001234'
        }
    
    @staticmethod
    def get_investment_data(plan_id=1, amount='5000.00'):
        return {
            'plan_id': plan_id,
            'amount': amount
        }
