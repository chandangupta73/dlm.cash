import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from freezegun import freeze_time

from app.users.models import User, OTP, UserSession

User = get_user_model()


@pytest.mark.unit
class UserModelTest(TestCase):
    """Test cases for User model."""
    
    def setUp(self):
        """Set up test data."""
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User',
            'phone_number': '+1234567890',
            'date_of_birth': datetime.strptime('1990-01-01', '%Y-%m-%d').date(),
            'address': '123 Test Street',
            'city': 'Test City',
            'state': 'Test State',
            'country': 'Test Country',
            'postal_code': '12345'
        }
    
    def test_user_creation(self):
        """Test user creation with all fields."""
        user = User.objects.create_user(**self.user_data)
        
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.phone_number, '+1234567890')
        self.assertEqual(user.date_of_birth, datetime.strptime('1990-01-01', '%Y-%m-%d').date())
        self.assertEqual(user.address, '123 Test Street')
        self.assertEqual(user.city, 'Test City')
        self.assertEqual(user.state, 'Test State')
        self.assertEqual(user.country, 'Test Country')
        self.assertEqual(user.postal_code, '12345')
        
        # Default values
        self.assertFalse(user.is_kyc_verified)
        self.assertEqual(user.kyc_status, 'PENDING')
        self.assertFalse(user.email_verified)
        self.assertFalse(user.phone_verified)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
    
    def test_user_creation_minimal(self):
        """Test user creation with minimal required fields."""
        user = User.objects.create_user(
            username='minimal',
            email='minimal@example.com',
            password='testpass123'
        )
        
        self.assertEqual(user.username, 'minimal')
        self.assertEqual(user.email, 'minimal@example.com')
        self.assertEqual(user.kyc_status, 'PENDING')
        self.assertFalse(user.is_kyc_verified)
    
    def test_user_full_name_property(self):
        """Test full_name property calculation."""
        user = User.objects.create_user(
            username='fullname',
            email='fullname@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        
        self.assertEqual(user.full_name, 'John Doe')
        
        # Test with only first name
        user.last_name = ''
        user.save()
        self.assertEqual(user.full_name, 'John')
        
        # Test with only last name
        user.first_name = ''
        user.last_name = 'Doe'
        user.save()
        self.assertEqual(user.full_name, 'Doe')
        
        # Test with no names
        user.first_name = ''
        user.last_name = ''
        user.save()
        self.assertEqual(user.full_name, '')
    
    def test_user_kyc_status_validation(self):
        """Test KYC status validation."""
        user = User.objects.create_user(
            username='kycuser',
            email='kyc@example.com',
            password='testpass123'
        )
        
        # Valid statuses
        valid_statuses = ['PENDING', 'APPROVED', 'REJECTED']
        for status in valid_statuses:
            user.kyc_status = status
            user.save()
            user.refresh_from_db()
            self.assertEqual(user.kyc_status, status)
        
        # Invalid status should raise error
        with self.assertRaises(ValidationError):
            user.kyc_status = 'INVALID_STATUS'
            user.full_clean()
    
    def test_user_phone_number_validation(self):
        """Test phone number validation."""
        user = User.objects.create_user(
            username='phoneuser',
            email='phone@example.com',
            password='testpass123'
        )
        
        # Valid phone numbers
        valid_numbers = ['+1234567890', '1234567890', '+44123456789']
        for number in valid_numbers:
            user.phone_number = number
            user.save()
            user.refresh_from_db()
            self.assertEqual(user.phone_number, number)
        
        # Invalid phone number should raise error
        with self.assertRaises(ValidationError):
            user.phone_number = 'invalid'
            user.full_clean()
    
    def test_user_email_uniqueness(self):
        """Test email uniqueness constraint."""
        User.objects.create_user(
            username='user1',
            email='unique@example.com',
            password='testpass123'
        )
        
        # Creating another user with same email should fail
        with self.assertRaises(Exception):
            User.objects.create_user(
                username='user2',
                email='unique@example.com',
                password='testpass123'
            )
    
    def test_user_kyc_verification_flow(self):
        """Test KYC verification status changes."""
        user = User.objects.create_user(
            username='kycflow',
            email='kycflow@example.com',
            password='testpass123'
        )
        
        # Initial state
        self.assertFalse(user.is_kyc_verified)
        self.assertEqual(user.kyc_status, 'PENDING')
        
        # Approve KYC
        user.kyc_status = 'APPROVED'
        user.is_kyc_verified = True
        user.save()
        
        user.refresh_from_db()
        self.assertTrue(user.is_kyc_verified)
        self.assertEqual(user.kyc_status, 'APPROVED')
        
        # Reject KYC
        user.kyc_status = 'REJECTED'
        user.is_kyc_verified = False
        user.save()
        
        user.refresh_from_db()
        self.assertFalse(user.is_kyc_verified)
        self.assertEqual(user.kyc_status, 'REJECTED')
    
    def test_user_verification_status(self):
        """Test email and phone verification status."""
        user = User.objects.create_user(
            username='verifyuser',
            email='verify@example.com',
            password='testpass123'
        )
        
        # Initial state
        self.assertFalse(user.email_verified)
        self.assertFalse(user.phone_verified)
        
        # Verify email
        user.email_verified = True
        user.save()
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        
        # Verify phone
        user.phone_verified = True
        user.save()
        user.refresh_from_db()
        self.assertTrue(user.phone_verified)
    
    def test_user_string_representation(self):
        """Test user string representation."""
        user = User.objects.create_user(
            username='stringuser',
            email='string@example.com',
            password='testpass123'
        )
        
        self.assertEqual(str(user), 'string@example.com')
    
    def test_user_meta_options(self):
        """Test user model meta options."""
        user = User.objects.create_user(
            username='metauser',
            email='meta@example.com',
            password='testpass123'
        )
        
        self.assertEqual(user._meta.db_table, 'users')
        self.assertEqual(user._meta.verbose_name, 'User')
        self.assertEqual(user._meta.verbose_name_plural, 'Users')


@pytest.mark.unit
class OTPModelTest(TestCase):
    """Test cases for OTP model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='otpuser',
            email='otp@example.com',
            password='testpass123'
        )
    
    def test_otp_creation(self):
        """Test OTP creation."""
        otp = OTP.objects.create(
            user=self.user,
            otp_type='EMAIL',
            otp_code='123456',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        self.assertEqual(otp.user, self.user)
        self.assertEqual(otp.otp_type, 'EMAIL')
        self.assertEqual(otp.otp_code, '123456')
        self.assertFalse(otp.is_used)
        self.assertIsNotNone(otp.expires_at)
        self.assertIsNotNone(otp.created_at)
    
    def test_otp_types(self):
        """Test different OTP types."""
        # Email OTP
        email_otp = OTP.objects.create(
            user=self.user,
            otp_type='EMAIL',
            otp_code='123456',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        self.assertEqual(email_otp.otp_type, 'EMAIL')
        
        # Phone OTP
        phone_otp = OTP.objects.create(
            user=self.user,
            otp_type='PHONE',
            otp_code='654321',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        self.assertEqual(phone_otp.otp_type, 'PHONE')
    
    def test_otp_expiration(self):
        """Test OTP expiration logic."""
        # Create expired OTP
        expired_otp = OTP.objects.create(
            user=self.user,
            otp_type='EMAIL',
            otp_code='123456',
            expires_at=timezone.now() - timedelta(hours=1)
        )
        
        # Create valid OTP
        valid_otp = OTP.objects.create(
            user=self.user,
            otp_type='EMAIL',
            otp_code='654321',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        # Check expiration
        self.assertTrue(expired_otp.expires_at < timezone.now())
        self.assertFalse(valid_otp.expires_at < timezone.now())
    
    def test_otp_usage_status(self):
        """Test OTP usage status."""
        otp = OTP.objects.create(
            user=self.user,
            otp_type='EMAIL',
            otp_code='123456',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        # Initially not used
        self.assertFalse(otp.is_used)
        
        # Mark as used
        otp.is_used = True
        otp.save()
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)
    
    def test_otp_string_representation(self):
        """Test OTP string representation."""
        otp = OTP.objects.create(
            user=self.user,
            otp_type='EMAIL',
            otp_code='123456',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        expected_str = f"{self.user.email} - EMAIL - 123456"
        self.assertEqual(str(otp), expected_str)
    
    def test_otp_meta_options(self):
        """Test OTP model meta options."""
        otp = OTP.objects.create(
            user=self.user,
            otp_type='EMAIL',
            otp_code='123456',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        self.assertEqual(otp._meta.db_table, 'otps')
        self.assertEqual(otp._meta.verbose_name, 'OTP')
        self.assertEqual(otp._meta.verbose_name_plural, 'OTPs')


@pytest.mark.unit
class UserSessionModelTest(TestCase):
    """Test cases for UserSession model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='sessionuser',
            email='session@example.com',
            password='testpass123'
        )
    
    def test_user_session_creation(self):
        """Test user session creation."""
        session = UserSession.objects.create(
            user=self.user,
            session_key='test_session_key_123',
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0 Test Browser'
        )
        
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.session_key, 'test_session_key_123')
        self.assertEqual(session.ip_address, '192.168.1.1')
        self.assertEqual(session.user_agent, 'Mozilla/5.0 Test Browser')
        self.assertTrue(session.is_active)
        self.assertIsNotNone(session.created_at)
        self.assertIsNotNone(session.last_activity)
    
    def test_user_session_activity_tracking(self):
        """Test user session activity tracking."""
        session = UserSession.objects.create(
            user=self.user,
            session_key='activity_test',
            ip_address='192.168.1.1',
            user_agent='Test Browser'
        )
        
        initial_activity = session.last_activity
        
        # Simulate activity update
        session.save()  # This should update last_activity
        session.refresh_from_db()
        
        self.assertGreater(session.last_activity, initial_activity)
    
    def test_user_session_status(self):
        """Test user session active/inactive status."""
        session = UserSession.objects.create(
            user=self.user,
            session_key='status_test',
            ip_address='192.168.1.1',
            user_agent='Test Browser'
        )
        
        # Initially active
        self.assertTrue(session.is_active)
        
        # Deactivate
        session.is_active = False
        session.save()
        session.refresh_from_db()
        self.assertFalse(session.is_active)
    
    def test_user_session_string_representation(self):
        """Test user session string representation."""
        session = UserSession.objects.create(
            user=self.user,
            session_key='string_test',
            ip_address='192.168.1.1',
            user_agent='Test Browser'
        )
        
        expected_str = f"{self.user.email} - {session.ip_address}"
        self.assertEqual(str(session), expected_str)
    
    def test_user_session_meta_options(self):
        """Test user session model meta options."""
        session = UserSession.objects.create(
            user=self.user,
            session_key='meta_test',
            ip_address='192.168.1.1',
            user_agent='Test Browser'
        )
        
        self.assertEqual(session._meta.db_table, 'user_sessions')
        self.assertEqual(session._meta.verbose_name, 'User Session')
        self.assertEqual(session._meta.verbose_name_plural, 'User Sessions')
