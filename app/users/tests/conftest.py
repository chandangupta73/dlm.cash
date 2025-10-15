import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import override_settings
from freezegun import freeze_time
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory
from rest_framework.test import APIClient

from app.users.models import User, OTP, UserSession

User = get_user_model()


# User Factories
class UserFactory(DjangoModelFactory):
    """Factory for creating test users"""
    
    class Meta:
        model = User
    
    username = Faker('user_name')
    email = Faker('email')
    password = Faker('password', length=12, special_chars=True, digits=True, upper_case=True, lower_case=True)
    first_name = Faker('first_name')
    last_name = Faker('last_name')
    phone_number = Faker('phone_number')
    date_of_birth = Faker('date_of_birth', minimum_age=18, maximum_age=65)
    address = Faker('address')
    city = Faker('city')
    state = Faker('state')
    country = Faker('country')
    postal_code = Faker('postcode')
    is_kyc_verified = False
    kyc_status = 'PENDING'
    email_verified = False
    phone_verified = False
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to properly hash password"""
        password = kwargs.pop('password', 'testpass123')
        user = super()._create(model_class, *args, **kwargs)
        user.set_password(password)
        user.save()
        return user


class AdminUserFactory(UserFactory):
    """Factory for creating admin users"""
    
    is_staff = True
    is_superuser = True
    is_kyc_verified = True
    kyc_status = 'APPROVED'
    email_verified = True
    phone_verified = True


class KYCUserFactory(UserFactory):
    """Factory for creating users with approved KYC"""
    
    is_kyc_verified = True
    kyc_status = 'APPROVED'
    email_verified = True
    phone_verified = True


class PendingKYCUserFactory(UserFactory):
    """Factory for creating users with pending KYC"""
    
    is_kyc_verified = False
    kyc_status = 'PENDING'
    email_verified = True
    phone_verified = True


class RejectedKYCUserFactory(UserFactory):
    """Factory for creating users with rejected KYC"""
    
    is_kyc_verified = False
    kyc_status = 'REJECTED'
    email_verified = True
    phone_verified = True


# OTP Factory
class OTPFactory(DjangoModelFactory):
    """Factory for creating OTP instances"""
    
    class Meta:
        model = OTP
    
    user = SubFactory(UserFactory)
    otp_type = 'EMAIL'
    otp_code = Faker('numerify', text='######')
    is_used = False
    expires_at = Faker('future_datetime', end_date='+1h')


# UserSession Factory
class UserSessionFactory(DjangoModelFactory):
    """Factory for creating user sessions"""
    
    class Meta:
        model = UserSession
    
    user = SubFactory(UserFactory)
    session_key = Faker('uuid4')
    ip_address = Faker('ipv4')
    user_agent = Faker('user_agent')
    is_active = True


# Test Fixtures
@pytest.fixture
def admin_user():
    """Admin user for testing admin operations"""
    return AdminUserFactory()


@pytest.fixture
def kyc_user():
    """User with approved KYC"""
    return KYCUserFactory()


@pytest.fixture
def pending_kyc_user():
    """User with pending KYC"""
    return PendingKYCUserFactory()


@pytest.fixture
def rejected_kyc_user():
    """User with rejected KYC"""
    return RejectedKYCUserFactory()


@pytest.fixture
def regular_user():
    """Regular user without special permissions"""
    return UserFactory()


@pytest.fixture
def otp_instance():
    """OTP instance for testing"""
    return OTPFactory()


@pytest.fixture
def user_session():
    """User session for testing"""
    return UserSessionFactory()


@pytest.fixture
def api_client():
    """Django REST Framework test client"""
    return APIClient()


@pytest.fixture
def frozen_time():
    """Freeze time for date-dependent tests"""
    with freeze_time('2024-01-01 12:00:00') as frozen:
        yield frozen


@pytest.fixture
def time_travel():
    """Time travel utility for testing"""
    def _time_travel(target_time):
        return freeze_time(target_time)
    return _time_travel


@pytest.fixture
def db_transaction():
    """Database transaction fixture"""
    from django.test import TransactionTestCase
    return TransactionTestCase()


@pytest.fixture
def celery_mock():
    """Mock Celery for testing"""
    with pytest.mock.patch('celery.app.task.Task.delay') as mock:
        yield mock
