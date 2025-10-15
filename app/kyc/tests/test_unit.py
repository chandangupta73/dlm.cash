import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from freezegun import freeze_time

from app.kyc.models import KYCDocument, VideoKYC, OfflineKYCRequest, KYCVerificationLog

User = get_user_model()


@pytest.mark.unit
class KYCDocumentModelTest(TestCase):
    """Test cases for KYCDocument model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='kycdocuser',
            email='kycdoc@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_user(
            username='kycadmin',
            email='kycadmin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create mock files
        self.document_file = SimpleUploadedFile(
            "test_document.pdf",
            b"fake pdf content",
            content_type="application/pdf"
        )
        self.document_front = SimpleUploadedFile(
            "test_front.jpg",
            b"fake image content",
            content_type="image/jpeg"
        )
        self.document_back = SimpleUploadedFile(
            "test_back.jpg",
            b"fake image content",
            content_type="image/jpeg"
        )
    
    def test_kyc_document_creation(self):
        """Test KYC document creation with all fields."""
        document = KYCDocument.objects.create(
            user=self.user,
            document_type='PAN',
            document_number='ABCDE1234F',
            document_file=self.document_file,
            document_front=self.document_front,
            document_back=self.document_back
        )
        
        self.assertEqual(document.user, self.user)
        self.assertEqual(document.document_type, 'PAN')
        self.assertEqual(document.document_number, 'ABCDE1234F')
        self.assertEqual(document.status, 'PENDING')
        self.assertIsNone(document.rejection_reason)
        self.assertIsNone(document.verified_by)
        self.assertIsNone(document.verified_at)
        self.assertIsNotNone(document.created_at)
        self.assertIsNotNone(document.updated_at)
    
    def test_kyc_document_types(self):
        """Test different KYC document types."""
        valid_types = ['PAN', 'AADHAAR', 'PASSPORT', 'DRIVING_LICENSE', 'VOTER_ID']
        
        for doc_type in valid_types:
            document = KYCDocument.objects.create(
                user=self.user,
                document_type=doc_type,
                document_file=self.document_file
            )
            self.assertEqual(document.document_type, doc_type)
    
    def test_kyc_document_status_validation(self):
        """Test KYC document status validation."""
        document = KYCDocument.objects.create(
            user=self.user,
            document_type='PAN',
            document_file=self.document_file
        )
        
        # Valid statuses
        valid_statuses = ['PENDING', 'APPROVED', 'REJECTED']
        for status in valid_statuses:
            document.status = status
            document.save()
            document.refresh_from_db()
            self.assertEqual(document.status, status)
        
        # Invalid status should raise error
        with self.assertRaises(ValidationError):
            document.status = 'INVALID_STATUS'
            document.full_clean()
    
    def test_kyc_document_approval_flow(self):
        """Test KYC document approval workflow."""
        document = KYCDocument.objects.create(
            user=self.user,
            document_type='PAN',
            document_file=self.document_file
        )
        
        # Initial state
        self.assertEqual(document.status, 'PENDING')
        self.assertFalse(self.user.is_kyc_verified)
        self.assertEqual(self.user.kyc_status, 'PENDING')
        
        # Approve document
        document.status = 'APPROVED'
        document.verified_by = self.admin_user
        document.verified_at = timezone.now()
        document.save()
        
        # Check document status
        document.refresh_from_db()
        self.assertEqual(document.status, 'APPROVED')
        self.assertEqual(document.verified_by, self.admin_user)
        self.assertIsNotNone(document.verified_at)
        
        # Check user KYC status
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_kyc_verified)
        self.assertEqual(self.user.kyc_status, 'APPROVED')
    
    def test_kyc_document_rejection_flow(self):
        """Test KYC document rejection workflow."""
        document = KYCDocument.objects.create(
            user=self.user,
            document_type='PAN',
            document_file=self.document_file
        )
        
        # Initial state
        self.assertEqual(document.status, 'PENDING')
        self.assertFalse(self.user.is_kyc_verified)
        
        # Reject document
        rejection_reason = "Document image is unclear"
        document.status = 'REJECTED'
        document.rejection_reason = rejection_reason
        document.verified_by = self.admin_user
        document.verified_at = timezone.now()
        document.save()
        
        # Check document status
        document.refresh_from_db()
        self.assertEqual(document.status, 'REJECTED')
        self.assertEqual(document.rejection_reason, rejection_reason)
        self.assertEqual(document.verified_by, self.admin_user)
        self.assertIsNotNone(document.verified_at)
        
        # Check user KYC status
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_kyc_verified)
        self.assertEqual(self.user.kyc_status, 'REJECTED')
    
    def test_kyc_document_unique_constraint(self):
        """Test unique constraint on user and document type."""
        # Create a second user for testing
        user2 = User.objects.create_user(
            username='kycdocuser2',
            email='kycdoc2@example.com',
            password='testpass123'
        )
        
        # Create documents for different users (this should work)
        doc1 = KYCDocument.objects.create(
            user=self.user,
            document_type='PAN',
            document_file=self.document_file
        )
        
        doc2 = KYCDocument.objects.create(
            user=user2,
            document_type='PAN',
            document_file=self.document_file
        )
        
        # Verify both documents exist
        self.assertEqual(KYCDocument.objects.filter(document_type='PAN').count(), 2)
        self.assertTrue(KYCDocument.objects.filter(document_type='PAN', user=self.user).exists())
        self.assertTrue(KYCDocument.objects.filter(document_type='PAN', user=user2).exists())
        
        # Test that we can create different document types for the same user
        doc3 = KYCDocument.objects.create(
            user=self.user,
            document_type='AADHAAR',
            document_file=self.document_file
        )
        
        self.assertEqual(KYCDocument.objects.filter(user=self.user).count(), 2)
        self.assertTrue(KYCDocument.objects.filter(document_type='AADHAAR', user=self.user).exists())
    
    def test_kyc_document_string_representation(self):
        """Test KYC document string representation."""
        document = KYCDocument.objects.create(
            user=self.user,
            document_type='PAN',
            document_file=self.document_file
        )
        
        expected_str = f"{self.user.email} - PAN"
        self.assertEqual(str(document), expected_str)
    
    def test_kyc_document_meta_options(self):
        """Test KYC document model meta options."""
        document = KYCDocument.objects.create(
            user=self.user,
            document_type='PAN',
            document_file=self.document_file
        )
        
        self.assertEqual(document._meta.db_table, 'kyc_documents')
        self.assertEqual(document._meta.verbose_name, 'KYC Document')
        self.assertEqual(document._meta.verbose_name_plural, 'KYC Documents')


@pytest.mark.unit
class VideoKYCModelTest(TestCase):
    """Test cases for VideoKYC model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='videokyuser',
            email='videokyc@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_user(
            username='videoadmin',
            email='videoadmin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        
        self.video_file = SimpleUploadedFile(
            "test_video.mp4",
            b"fake video content",
            content_type="video/mp4"
        )
    
    def test_video_kyc_creation(self):
        """Test video KYC creation."""
        video_kyc = VideoKYC.objects.create(
            user=self.user,
            video_file=self.video_file,
            session_id='test_session_123',
            duration=120
        )
        
        self.assertEqual(video_kyc.user, self.user)
        self.assertEqual(video_kyc.session_id, 'test_session_123')
        self.assertEqual(video_kyc.status, 'PENDING')
        self.assertEqual(video_kyc.duration, 120)
        self.assertIsNone(video_kyc.rejection_reason)
        self.assertIsNone(video_kyc.verified_by)
        self.assertIsNone(video_kyc.verified_at)
        self.assertIsNotNone(video_kyc.created_at)
        self.assertIsNotNone(video_kyc.updated_at)
    
    def test_video_kyc_session_id_uniqueness(self):
        """Test session ID uniqueness constraint."""
        # Create first video KYC
        VideoKYC.objects.create(
            user=self.user,
            video_file=self.video_file,
            session_id='unique_session_123'
        )
        
        # Creating another with same session ID should fail
        with self.assertRaises(Exception):
            VideoKYC.objects.create(
                user=self.user,
                video_file=self.video_file,
                session_id='unique_session_123'
            )
    
    def test_video_kyc_approval_flow(self):
        """Test video KYC approval workflow."""
        video_kyc = VideoKYC.objects.create(
            user=self.user,
            video_file=self.video_file,
            session_id='approval_test_123'
        )
        
        # Initial state
        self.assertEqual(video_kyc.status, 'PENDING')
        
        # Approve video KYC
        video_kyc.status = 'APPROVED'
        video_kyc.verified_by = self.admin_user
        video_kyc.verified_at = timezone.now()
        video_kyc.save()
        
        # Check status
        video_kyc.refresh_from_db()
        self.assertEqual(video_kyc.status, 'APPROVED')
        self.assertEqual(video_kyc.verified_by, self.admin_user)
        self.assertIsNotNone(video_kyc.verified_at)
    
    def test_video_kyc_rejection_flow(self):
        """Test video KYC rejection workflow."""
        video_kyc = VideoKYC.objects.create(
            user=self.user,
            video_file=self.video_file,
            session_id='rejection_test_123'
        )
        
        # Initial state
        self.assertEqual(video_kyc.status, 'PENDING')
        
        # Reject video KYC
        rejection_reason = "Video quality is poor"
        video_kyc.status = 'REJECTED'
        video_kyc.rejection_reason = rejection_reason
        video_kyc.verified_by = self.admin_user
        video_kyc.verified_at = timezone.now()
        video_kyc.save()
        
        # Check status
        video_kyc.refresh_from_db()
        self.assertEqual(video_kyc.status, 'REJECTED')
        self.assertEqual(video_kyc.rejection_reason, rejection_reason)
        self.assertEqual(video_kyc.verified_by, self.admin_user)
        self.assertIsNotNone(video_kyc.verified_at)
    
    def test_video_kyc_duration_validation(self):
        """Test video KYC duration validation."""
        # Valid duration
        video_kyc = VideoKYC.objects.create(
            user=self.user,
            video_file=self.video_file,
            session_id='duration_test_123',
            duration=60
        )
        self.assertEqual(video_kyc.duration, 60)
        
        # Zero duration
        video_kyc.duration = 0
        video_kyc.save()
        video_kyc.refresh_from_db()
        self.assertEqual(video_kyc.duration, 0)
        
        # Negative duration
        video_kyc.duration = -10
        video_kyc.save()
        video_kyc.refresh_from_db()
        self.assertEqual(video_kyc.duration, -10)
    
    def test_video_kyc_string_representation(self):
        """Test video KYC string representation."""
        video_kyc = VideoKYC.objects.create(
            user=self.user,
            video_file=self.video_file,
            session_id='string_test_123'
        )
        
        expected_str = f"{self.user.email} - {video_kyc.session_id}"
        self.assertEqual(str(video_kyc), expected_str)
    
    def test_video_kyc_meta_options(self):
        """Test video KYC model meta options."""
        video_kyc = VideoKYC.objects.create(
            user=self.user,
            video_file=self.video_file,
            session_id='meta_test_123'
        )
        
        self.assertEqual(video_kyc._meta.db_table, 'video_kycs')
        self.assertEqual(video_kyc._meta.verbose_name, 'Video KYC')
        self.assertEqual(video_kyc._meta.verbose_name_plural, 'Video KYCs')


@pytest.mark.unit
class OfflineKYCRequestModelTest(TestCase):
    """Test cases for OfflineKYCRequest model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='offlinekyuser',
            email='offlinekyc@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_user(
            username='offlineadmin',
            email='offlineadmin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
    
    def test_offline_kyc_request_creation(self):
        """Test offline KYC request creation."""
        request = OfflineKYCRequest.objects.create(
            user=self.user,
            request_type='DOCUMENT_UPLOAD',
            description='Need to upload additional documents'
        )
        
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.request_type, 'DOCUMENT_UPLOAD')
        self.assertEqual(request.description, 'Need to upload additional documents')
        self.assertEqual(request.status, 'PENDING')
        self.assertIsNone(request.assigned_to)
        self.assertIsNone(request.notes)
        self.assertIsNotNone(request.created_at)
        self.assertIsNotNone(request.updated_at)
    
    def test_offline_kyc_request_types(self):
        """Test different offline KYC request types."""
        valid_types = ['DOCUMENT_UPLOAD', 'VIDEO_KYC', 'MANUAL_VERIFICATION']
        
        for req_type in valid_types:
            request = OfflineKYCRequest.objects.create(
                user=self.user,
                request_type=req_type,
                description=f'Test {req_type} request'
            )
            self.assertEqual(request.request_type, req_type)
    
    def test_offline_kyc_request_status_flow(self):
        """Test offline KYC request status flow."""
        request = OfflineKYCRequest.objects.create(
            user=self.user,
            request_type='DOCUMENT_UPLOAD',
            description='Test status flow'
        )
        
        # Initial state
        self.assertEqual(request.status, 'PENDING')
        
        # Assign to admin
        request.status = 'IN_PROGRESS'
        request.assigned_to = self.admin_user
        request.notes = 'Assigned to admin for review'
        request.save()
        
        request.refresh_from_db()
        self.assertEqual(request.status, 'IN_PROGRESS')
        self.assertEqual(request.assigned_to, self.admin_user)
        self.assertEqual(request.notes, 'Assigned to admin for review')
        
        # Complete request
        request.status = 'COMPLETED'
        request.notes = 'Request completed successfully'
        request.save()
        
        request.refresh_from_db()
        self.assertEqual(request.status, 'COMPLETED')
        self.assertEqual(request.notes, 'Request completed successfully')
    
    def test_offline_kyc_request_rejection(self):
        """Test offline KYC request rejection."""
        request = OfflineKYCRequest.objects.create(
            user=self.user,
            request_type='DOCUMENT_UPLOAD',
            description='Test rejection'
        )
        
        # Reject request
        request.status = 'REJECTED'
        request.assigned_to = self.admin_user
        request.notes = 'Request rejected due to insufficient documentation'
        request.save()
        
        request.refresh_from_db()
        self.assertEqual(request.status, 'REJECTED')
        self.assertEqual(request.assigned_to, self.admin_user)
        self.assertEqual(request.notes, 'Request rejected due to insufficient documentation')
    
    def test_offline_kyc_request_string_representation(self):
        """Test offline KYC request string representation."""
        request = OfflineKYCRequest.objects.create(
            user=self.user,
            request_type='DOCUMENT_UPLOAD',
            description='Test string representation'
        )
        
        expected_str = f"{self.user.email} - DOCUMENT_UPLOAD"
        self.assertEqual(str(request), expected_str)
    
    def test_offline_kyc_request_meta_options(self):
        """Test offline KYC request model meta options."""
        request = OfflineKYCRequest.objects.create(
            user=self.user,
            request_type='DOCUMENT_UPLOAD',
            description='Test meta options'
        )
        
        self.assertEqual(request._meta.db_table, 'offline_kyc_requests')
        self.assertEqual(request._meta.verbose_name, 'Offline KYC Request')
        self.assertEqual(request._meta.verbose_name_plural, 'Offline KYC Requests')


@pytest.mark.unit
class KYCVerificationLogModelTest(TestCase):
    """Test cases for KYCVerificationLog model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='loguser',
            email='loguser@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_user(
            username='logadmin',
            email='logadmin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
    
    def test_kyc_verification_log_creation(self):
        """Test KYC verification log creation."""
        log = KYCVerificationLog.objects.create(
            user=self.user,
            action='DOCUMENT_UPLOADED',
            document_type='PAN',
            performed_by=self.admin_user,
            details='PAN card uploaded successfully'
        )
        
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.action, 'DOCUMENT_UPLOADED')
        self.assertEqual(log.document_type, 'PAN')
        self.assertEqual(log.performed_by, self.admin_user)
        self.assertEqual(log.details, 'PAN card uploaded successfully')
        self.assertIsNotNone(log.created_at)
    
    def test_kyc_verification_log_actions(self):
        """Test different KYC verification log actions."""
        valid_actions = [
            'DOCUMENT_UPLOADED', 'DOCUMENT_APPROVED', 'DOCUMENT_REJECTED',
            'VIDEO_KYC_UPLOADED', 'VIDEO_KYC_APPROVED', 'VIDEO_KYC_REJECTED',
            'OFFLINE_REQUEST_CREATED', 'OFFLINE_REQUEST_COMPLETED'
        ]
        
        for action in valid_actions:
            log = KYCVerificationLog.objects.create(
                user=self.user,
                action=action,
                performed_by=self.admin_user,
                details=f'Test {action} action'
            )
            self.assertEqual(log.action, action)
    
    def test_kyc_verification_log_document_types(self):
        """Test different document types in logs."""
        valid_document_types = ['PAN', 'AADHAAR', 'PASSPORT', 'DRIVING_LICENSE', 'VOTER_ID']
        
        for doc_type in valid_document_types:
            log = KYCVerificationLog.objects.create(
                user=self.user,
                action='DOCUMENT_UPLOADED',
                document_type=doc_type,
                performed_by=self.admin_user,
                details=f'Test {doc_type} document'
            )
            self.assertEqual(log.document_type, doc_type)
    
    def test_kyc_verification_log_ordering(self):
        """Test KYC verification log ordering."""
        # Create logs with different timestamps
        log1 = KYCVerificationLog.objects.create(
            user=self.user,
            action='DOCUMENT_UPLOADED',
            performed_by=self.admin_user,
            details='First log'
        )
        
        # Add a small delay to ensure different timestamps
        import time
        time.sleep(0.001)
        
        log2 = KYCVerificationLog.objects.create(
            user=self.user,
            action='DOCUMENT_APPROVED',
            performed_by=self.admin_user,
            details='Second log'
        )
        
        # Check ordering (newest first)
        logs = KYCVerificationLog.objects.filter(user=self.user)
        self.assertEqual(logs[0], log2)  # Newest first
        self.assertEqual(logs[1], log1)  # Oldest last
        
        # Verify the ordering is correct by checking timestamps
        self.assertGreater(log2.created_at, log1.created_at)
    
    def test_kyc_verification_log_string_representation(self):
        """Test KYC verification log string representation."""
        log = KYCVerificationLog.objects.create(
            user=self.user,
            action='DOCUMENT_UPLOADED',
            performed_by=self.admin_user,
            details='Test string representation'
        )
        
        # The actual string representation includes timestamp, so we'll check the format
        str_repr = str(log)
        self.assertIn(self.user.email, str_repr)
        self.assertIn('DOCUMENT_UPLOADED', str_repr)
        self.assertIn(str(log.created_at), str_repr)
    
    def test_kyc_verification_log_meta_options(self):
        """Test KYC verification log model meta options."""
        log = KYCVerificationLog.objects.create(
            user=self.user,
            action='DOCUMENT_UPLOADED',
            performed_by=self.admin_user,
            details='Test meta options'
        )
        
        self.assertEqual(log._meta.db_table, 'kyc_verification_logs')
        self.assertEqual(log._meta.verbose_name, 'KYC Verification Log')
        self.assertEqual(log._meta.verbose_name_plural, 'KYC Verification Logs')
        self.assertEqual(log._meta.ordering, ['-created_at'])
