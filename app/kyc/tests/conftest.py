import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import override_settings
from freezegun import freeze_time
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile

from app.kyc.models import KYCDocument, VideoKYC, OfflineKYCRequest, KYCVerificationLog
from app.users.models import User

User = get_user_model()


# User Factories (reuse from users app)
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


# KYC Document Factory
class KYCDocumentFactory(DjangoModelFactory):
    """Factory for creating KYC documents"""
    
    class Meta:
        model = KYCDocument
    
    user = SubFactory(UserFactory)
    document_type = Faker('random_element', elements=['PAN', 'AADHAAR', 'PASSPORT', 'DRIVING_LICENSE', 'VOTER_ID'])
    document_number = Faker('numerify', text='##########')
    document_file = SimpleUploadedFile(
        "test_document.pdf",
        b"fake pdf content",
        content_type="application/pdf"
    )
    document_front = SimpleUploadedFile(
        "test_front.jpg",
        b"fake image content",
        content_type="image/jpeg"
    )
    document_back = SimpleUploadedFile(
        "test_back.jpg",
        b"fake image content",
        content_type="image/jpeg"
    )
    status = 'PENDING'
    rejection_reason = None
    verified_by = None
    verified_at = None


class ApprovedKYCDocumentFactory(KYCDocumentFactory):
    """Factory for creating approved KYC documents"""
    
    status = 'APPROVED'
    verified_by = SubFactory(AdminUserFactory)
    verified_at = Faker('past_datetime', start_date='-1d')


class RejectedKYCDocumentFactory(KYCDocumentFactory):
    """Factory for creating rejected KYC documents"""
    
    status = 'REJECTED'
    rejection_reason = Faker('sentence', nb_words=6)
    verified_by = SubFactory(AdminUserFactory)
    verified_at = Faker('past_datetime', start_date='-1d')


# Video KYC Factory
class VideoKYCFactory(DjangoModelFactory):
    """Factory for creating video KYC sessions"""
    
    class Meta:
        model = VideoKYC
    
    user = SubFactory(UserFactory)
    video_file = SimpleUploadedFile(
        "test_video.mp4",
        b"fake video content",
        content_type="video/mp4"
    )
    session_id = Faker('uuid4')
    status = 'PENDING'
    rejection_reason = None
    verified_by = None
    verified_at = None
    duration = Faker('random_int', min=30, max=300)


class ApprovedVideoKYCFactory(VideoKYCFactory):
    """Factory for creating approved video KYC sessions"""
    
    status = 'APPROVED'
    verified_by = SubFactory(AdminUserFactory)
    verified_at = Faker('past_datetime', start_date='-1d')


class RejectedVideoKYCFactory(VideoKYCFactory):
    """Factory for creating rejected video KYC sessions"""
    
    status = 'REJECTED'
    rejection_reason = Faker('sentence', nb_words=6)
    verified_by = SubFactory(AdminUserFactory)
    verified_at = Faker('past_datetime', start_date='-1d')


# Offline KYC Request Factory
class OfflineKYCRequestFactory(DjangoModelFactory):
    """Factory for creating offline KYC requests"""
    
    class Meta:
        model = OfflineKYCRequest
    
    user = SubFactory(UserFactory)
    request_type = Faker('random_element', elements=['DOCUMENT_UPLOAD', 'VIDEO_KYC', 'MANUAL_VERIFICATION'])
    description = Faker('paragraph', nb_sentences=3)
    status = 'PENDING'
    assigned_to = None
    notes = None


class InProgressOfflineKYCRequestFactory(OfflineKYCRequestFactory):
    """Factory for creating in-progress offline KYC requests"""
    
    status = 'IN_PROGRESS'
    assigned_to = SubFactory(AdminUserFactory)
    notes = Faker('paragraph', nb_sentences=2)


class CompletedOfflineKYCRequestFactory(OfflineKYCRequestFactory):
    """Factory for creating completed offline KYC requests"""
    
    status = 'COMPLETED'
    assigned_to = SubFactory(AdminUserFactory)
    notes = Faker('paragraph', nb_sentences=2)


# KYC Verification Log Factory
class KYCVerificationLogFactory(DjangoModelFactory):
    """Factory for creating KYC verification logs"""
    
    class Meta:
        model = KYCVerificationLog
    
    user = SubFactory(UserFactory)
    action = Faker('random_element', elements=[
        'DOCUMENT_UPLOADED', 'DOCUMENT_APPROVED', 'DOCUMENT_REJECTED',
        'VIDEO_KYC_UPLOADED', 'VIDEO_KYC_APPROVED', 'VIDEO_KYC_REJECTED',
        'OFFLINE_REQUEST_CREATED', 'OFFLINE_REQUEST_COMPLETED'
    ])
    document_type = Faker('random_element', elements=['PAN', 'AADHAAR', 'PASSPORT', 'DRIVING_LICENSE', 'VOTER_ID'])
    performed_by = SubFactory(AdminUserFactory)
    details = Faker('paragraph', nb_sentences=2)


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
def kyc_document():
    """KYC document for testing"""
    return KYCDocumentFactory()


@pytest.fixture
def approved_kyc_document():
    """Approved KYC document for testing"""
    return ApprovedKYCDocumentFactory()


@pytest.fixture
def rejected_kyc_document():
    """Rejected KYC document for testing"""
    return RejectedKYCDocumentFactory()


@pytest.fixture
def video_kyc():
    """Video KYC for testing"""
    return VideoKYCFactory()


@pytest.fixture
def approved_video_kyc():
    """Approved video KYC for testing"""
    return ApprovedVideoKYCFactory()


@pytest.fixture
def rejected_video_kyc():
    """Rejected video KYC for testing"""
    return RejectedVideoKYCFactory()


@pytest.fixture
def offline_kyc_request():
    """Offline KYC request for testing"""
    return OfflineKYCRequestFactory()


@pytest.fixture
def in_progress_offline_kyc_request():
    """In-progress offline KYC request for testing"""
    return InProgressOfflineKYCRequestFactory()


@pytest.fixture
def completed_offline_kyc_request():
    """Completed offline KYC request for testing"""
    return CompletedOfflineKYCRequestFactory()


@pytest.fixture
def kyc_verification_log():
    """KYC verification log for testing"""
    return KYCVerificationLogFactory()


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


@pytest.fixture
def mock_file_upload():
    """Mock file upload for testing"""
    def _create_mock_file(filename, content_type, content=b"fake content"):
        return SimpleUploadedFile(filename, content, content_type=content_type)
    return _create_mock_file
