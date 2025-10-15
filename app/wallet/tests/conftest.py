import pytest
from factory import Faker, SubFactory, LazyAttribute
from factory.django import DjangoModelFactory
from rest_framework.test import APIClient
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from unittest.mock import patch

from app.wallet.models import (
    INRWallet, USDTWallet, WalletTransaction, DepositRequest, 
    USDTDepositRequest, WalletAddress, SweepLog
)
from app.users.models import User

# User Factories (reused from users app)
class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    
    username = Faker('user_name')
    email = Faker('email')
    first_name = Faker('first_name')
    last_name = Faker('last_name')
    phone_number = Faker('phone_number')
    date_of_birth = Faker('date_of_birth', minimum_age=18, maximum_age=90)
    address = Faker('address')
    city = Faker('city')
    state = Faker('state')
    country = Faker('country')
    postal_code = Faker('postcode')
    is_active = True
    is_staff = False
    is_superuser = False
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop('password', 'testpass123')
        user = super()._create(model_class, *args, **kwargs)
        user.set_password(password)
        # Don't call save() here to avoid triggering signals
        return user

    @classmethod
    def _after_postgeneration(cls, obj, create, results=None):
        """Override to handle password setting without triggering signals."""
        if create:
            obj.save(update_fields=['password'])
        return obj


class AdminUserFactory(UserFactory):
    is_staff = True
    is_superuser = True


class KYCUserFactory(UserFactory):
    kyc_status = 'approved'


class PendingKYCUserFactory(UserFactory):
    kyc_status = 'pending'


class RejectedKYCUserFactory(UserFactory):
    kyc_status = 'rejected'


# Wallet Factories - Modified to work with existing wallets or create new ones
class INRWalletFactory(DjangoModelFactory):
    class Meta:
        model = INRWallet
    
    user = SubFactory(UserFactory)
    balance = Faker('pydecimal', left_digits=6, right_digits=2, positive=True)
    status = 'active'
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        user = kwargs.get('user')
        if user:
            # Check if wallet already exists for this user
            existing_wallet = INRWallet.objects.filter(user=user).first()
            if existing_wallet:
                # Update existing wallet instead of creating new one
                for key, value in kwargs.items():
                    if key != 'user':
                        setattr(existing_wallet, key, value)
                existing_wallet.save()
                return existing_wallet
        
        return super()._create(model_class, *args, **kwargs)


class USDTWalletFactory(DjangoModelFactory):
    class Meta:
        model = USDTWallet
    
    user = SubFactory(UserFactory)
    balance = Faker('pydecimal', left_digits=8, right_digits=6, positive=True)
    status = 'active'
    is_active = True
    wallet_address = Faker('sha256')
    private_key_encrypted = Faker('text', max_nb_chars=100)
    chain_type = Faker('random_element', elements=['erc20', 'bep20'])
    is_real_wallet = False
    last_sweep_at = None

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        user = kwargs.get('user')
        if user:
            # Check if wallet already exists for this user
            existing_wallet = USDTWallet.objects.filter(user=user).first()
            if existing_wallet:
                # Update existing wallet instead of creating new one
                for key, value in kwargs.items():
                    if key != 'user':
                        setattr(existing_wallet, key, value)
                existing_wallet.save()
                return existing_wallet
        
        return super()._create(model_class, *args, **kwargs)


class WalletAddressFactory(DjangoModelFactory):
    class Meta:
        model = WalletAddress
    
    user = SubFactory(UserFactory)
    chain_type = Faker('random_element', elements=['erc20', 'bep20'])
    address = Faker('sha256')
    status = 'active'
    is_active = True
    last_used = None

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        user = kwargs.get('user')
        chain_type = kwargs.get('chain_type')
        if user and chain_type:
            # Check if address already exists for this user and chain type
            existing_address = WalletAddress.objects.filter(
                user=user, chain_type=chain_type
            ).first()
            if existing_address:
                # Update existing address instead of creating new one
                for key, value in kwargs.items():
                    if key not in ['user', 'chain_type']:
                        setattr(existing_address, key, value)
                existing_address.save()
                return existing_address
        
        return super()._create(model_class, *args, **kwargs)


class WalletTransactionFactory(DjangoModelFactory):
    class Meta:
        model = WalletTransaction
    
    user = SubFactory(UserFactory)
    transaction_type = Faker('random_element', elements=[
        'deposit', 'withdrawal', 'transfer', 'roi_credit', 
        'referral_bonus', 'admin_adjustment', 'investment', 'refund', 'sweep', 'usdt_deposit'
    ])
    wallet_type = Faker('random_element', elements=['inr', 'usdt'])
    chain_type = Faker('random_element', elements=['erc20', 'bep20'])
    amount = Faker('pydecimal', left_digits=6, right_digits=2, positive=True)
    balance_before = Faker('pydecimal', left_digits=6, right_digits=2, positive=True)
    balance_after = LazyAttribute(lambda obj: obj.balance_before + obj.amount)
    status = 'completed'
    reference_id = Faker('uuid4')
    description = Faker('text', max_nb_chars=100)
    metadata = {}


class DepositRequestFactory(DjangoModelFactory):
    class Meta:
        model = DepositRequest
    
    user = SubFactory(UserFactory)
    amount = Faker('pydecimal', left_digits=6, right_digits=2, positive=True, min_value=100)
    payment_method = Faker('random_element', elements=['bank_transfer', 'upi', 'razorpay', 'crypto'])
    status = 'pending'
    reference_number = Faker('uuid4')
    transaction_id = Faker('uuid4')
    screenshot = None
    notes = Faker('text', max_nb_chars=200)
    admin_notes = None
    processed_by = None
    processed_at = None


class USDTDepositRequestFactory(DjangoModelFactory):
    class Meta:
        model = USDTDepositRequest
    
    user = SubFactory(UserFactory)
    chain_type = Faker('random_element', elements=['erc20', 'bep20'])
    amount = Faker('pydecimal', left_digits=8, right_digits=6, positive=True, min_value=0.000001)
    transaction_hash = Faker('sha256')
    from_address = Faker('sha256')
    to_address = Faker('sha256')
    status = 'pending'
    sweep_type = 'none'
    sweep_tx_hash = None
    gas_fee = Faker('pydecimal', left_digits=4, right_digits=6, positive=True)
    block_number = Faker('random_int', min=1, max=99999999)
    confirmation_count = 0
    required_confirmations = 12
    processed_by = None
    processed_at = None
    notes = Faker('text', max_nb_chars=200)


class SweepLogFactory(DjangoModelFactory):
    class Meta:
        model = SweepLog
    
    user = SubFactory(UserFactory)
    chain_type = Faker('random_element', elements=['erc20', 'bep20'])
    from_address = Faker('sha256')
    to_address = Faker('sha256')
    amount = Faker('pydecimal', left_digits=8, right_digits=6, positive=True)
    gas_fee = Faker('pydecimal', left_digits=4, right_digits=6, positive=True)
    transaction_hash = Faker('sha256')
    sweep_type = Faker('random_element', elements=['auto', 'manual'])
    status = 'pending'
    initiated_by = SubFactory(AdminUserFactory)
    error_message = None


# Pre-loaded wallet factories
class PreLoadedINRWalletFactory(INRWalletFactory):
    balance = Decimal('10000.00')  # Pre-loaded with ₹10,000


class PreLoadedUSDTWalletFactory(USDTWalletFactory):
    balance = Decimal('1000.000000')  # Pre-loaded with 1000 USDT


# Pytest Fixtures
@pytest.fixture
def api_client():
    """Return an API client for testing."""
    return APIClient()


@pytest.fixture
def user():
    """Return a regular user."""
    return UserFactory()


@pytest.fixture
def admin_user():
    """Return an admin user."""
    return AdminUserFactory()


@pytest.fixture
def kyc_user():
    """Return a user with approved KYC."""
    return KYCUserFactory()


@pytest.fixture
def pending_kyc_user():
    """Return a user with pending KYC."""
    return PendingKYCUserFactory()


@pytest.fixture
def inr_wallet():
    """Return an INR wallet."""
    return INRWalletFactory()


@pytest.fixture
def usdt_wallet():
    """Return a USDT wallet."""
    return USDTWalletFactory()


@pytest.fixture
def pre_loaded_inr_wallet():
    """Return a pre-loaded INR wallet."""
    return PreLoadedINRWalletFactory()


@pytest.fixture
def pre_loaded_usdt_wallet():
    """Return a pre-loaded USDT wallet."""
    return PreLoadedUSDTWalletFactory()


@pytest.fixture
def wallet_transaction():
    """Return a wallet transaction."""
    return WalletTransactionFactory()


@pytest.fixture
def deposit_request():
    """Return a deposit request."""
    return DepositRequestFactory()


@pytest.fixture
def usdt_deposit_request():
    """Return a USDT deposit request."""
    return USDTDepositRequestFactory()


@pytest.fixture
def sweep_log():
    """Return a sweep log."""
    return SweepLogFactory()


@pytest.fixture
def mock_file_upload():
    """Return a mock file upload for testing."""
    return SimpleUploadedFile(
        "test_screenshot.jpg",
        b"fake-image-content",
        content_type="image/jpeg"
    )


@pytest.fixture
def frozen_time():
    """Freeze time for consistent testing."""
    from freezegun import freeze_time
    with freeze_time("2024-01-01 12:00:00"):
        yield


@pytest.fixture
def time_travel():
    """Allow time travel for testing."""
    from freezegun import freeze_time
    return freeze_time


@pytest.fixture
def db_transaction():
    """Database transaction fixture."""
    with transaction.atomic():
        yield


@pytest.fixture
def celery_mock():
    """Mock Celery for testing."""
    with patch('celery.app.control.Control.inspect') as mock_inspect:
        mock_inspect.return_value.active.return_value = {}
        mock_inspect.return_value.reserved.return_value = {}
        yield mock_inspect


@pytest.fixture
def disable_wallet_signals():
    """Disable wallet creation signals during testing."""
    from django.db.models.signals import post_save
    from app.wallet.signals import create_user_wallets, save_user_wallets
    from app.core.signals import create_user_wallets as core_create_user_wallets, save_user_wallets as core_save_user_wallets
    
    # Disconnect the wallet app signals
    post_save.disconnect(create_user_wallets, sender=User)
    post_save.disconnect(save_user_wallets, sender=User)
    
    # Disconnect the core app signals
    post_save.disconnect(core_create_user_wallets, sender=User)
    post_save.disconnect(core_save_user_wallets, sender=User)
    
    yield
    
    # Reconnect the wallet app signals
    post_save.connect(create_user_wallets, sender=User)
    post_save.connect(save_user_wallets, sender=User)
    
    # Reconnect the core app signals
    post_save.connect(core_create_user_wallets, sender=User)
    post_save.connect(core_save_user_wallets, sender=User)


@pytest.fixture
def clean_user():
    """Create a user without triggering wallet signals."""
    user = UserFactory()
    # Manually save without triggering signals
    user.save(update_fields=['username', 'email', 'first_name', 'last_name', 'phone_number', 
                            'date_of_birth', 'address', 'city', 'state', 'country', 'postal_code',
                            'is_active', 'is_staff', 'is_superuser'])
    return user
