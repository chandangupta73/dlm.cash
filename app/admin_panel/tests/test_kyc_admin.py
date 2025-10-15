import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from unittest.mock import patch

from app.kyc.models import KYCDocument
from app.admin_panel.models import AdminActionLog
from app.admin_panel.services import AdminKYCService
from app.admin_panel.permissions import log_admin_action

User = get_user_model()


class AdminKYCServiceTest(TestCase):
    """Test KYC management service layer"""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        self.regular_user = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123',
            phone_number='+1234567890'
        )
        
        self.kyc_doc = KYCDocument.objects.create(
            user=self.regular_user,
            document_type='PASSPORT',
            document_file='test_docs/passport.pdf',
            status='PENDING'
        )
        
        self.kyc_service = AdminKYCService()
    
    def test_get_kyc_documents_with_filters(self):
        """Test retrieving KYC documents with various filters"""
        # Test no filters
        docs = self.kyc_service.get_kyc_documents()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].id, self.kyc_doc.id)
        
        # Test status filter
        docs = self.kyc_service.get_kyc_documents(status='PENDING')
        self.assertEqual(len(docs), 1)
        
        docs = self.kyc_service.get_kyc_documents(status='APPROVED')
        self.assertEqual(len(docs), 0)
        
        # Test user filter
        docs = self.kyc_service.get_kyc_documents(user_id=self.regular_user.id)
        self.assertEqual(len(docs), 1)
        
        docs = self.kyc_service.get_kyc_documents(user_id=99999)
        self.assertEqual(len(docs), 0)
    
    def test_approve_kyc_document(self):
        """Test approving a KYC document"""
        result = self.kyc_service.approve_kyc_document(
            kyc_doc_id=self.kyc_doc.id,
            admin_user=self.admin_user,
            notes='Document verified successfully'
        )
        
        self.assertTrue(result['success'])
        
        # Check KYC document status updated
        self.kyc_doc.refresh_from_db()
        self.assertEqual(self.kyc_doc.status, 'APPROVED')
        self.assertEqual(self.kyc_doc.verified_by, self.admin_user)
        self.assertEqual(self.kyc_doc.verification_notes, 'Document verified successfully')
        
        # Check user KYC status updated
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.is_kyc_verified)
        self.assertEqual(self.regular_user.kyc_status, 'APPROVED')
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='KYC_APPROVAL',
            target_user=self.regular_user
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Document verified successfully', action_log.action_description)
    
    def test_reject_kyc_document(self):
        """Test rejecting a KYC document"""
        result = self.kyc_service.reject_kyc_document(
            kyc_doc_id=self.kyc_doc.id,
            admin_user=self.admin_user,
            rejection_reason='Document unclear, please resubmit'
        )
        
        self.assertTrue(result['success'])
        
        # Check KYC document status updated
        self.kyc_doc.refresh_from_db()
        self.assertEqual(self.kyc_doc.status, 'REJECTED')
        self.assertEqual(self.kyc_doc.verified_by, self.admin_user)
        self.assertEqual(self.kyc_doc.rejection_reason, 'Document unclear, please resubmit')
        
        # Check user KYC status updated
        self.regular_user.refresh_from_db()
        self.assertFalse(self.regular_user.is_kyc_verified)
        self.assertEqual(self.regular_user.kyc_status, 'REJECTED')
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='KYC_REJECTION',
            target_user=self.regular_user
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Document unclear, please resubmit', action_log.action_description)
    
    def test_approve_nonexistent_kyc_document(self):
        """Test approving a non-existent KYC document"""
        result = self.kyc_service.approve_kyc_document(
            kyc_doc_id=99999,
            admin_user=self.admin_user,
            notes='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_approve_already_approved_kyc_document(self):
        """Test approving an already approved KYC document"""
        self.kyc_doc.status = 'APPROVED'
        self.kyc_doc.save()
        
        result = self.kyc_service.approve_kyc_document(
            kyc_doc_id=self.kyc_doc.id,
            admin_user=self.admin_user,
            notes='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('already approved', result['error'])
    
    def test_reject_already_rejected_kyc_document(self):
        """Test rejecting an already rejected KYC document"""
        self.kyc_doc.status = 'REJECTED'
        self.kyc_doc.save()
        
        result = self.kyc_service.reject_kyc_document(
            kyc_doc_id=self.kyc_doc.id,
            admin_user=self.admin_user,
            rejection_reason='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('already rejected', result['error'])
    
    def test_kyc_approval_with_notification(self):
        """Test KYC approval triggers notification"""
        with patch('app.admin_panel.services.send_kyc_approval_notification') as mock_notify:
            result = self.kyc_service.approve_kyc_document(
                kyc_doc_id=self.kyc_doc.id,
                admin_user=self.admin_user,
                notes='Document verified'
            )
            
            self.assertTrue(result['success'])
            mock_notify.assert_called_once_with(self.regular_user)
    
    def test_kyc_rejection_with_notification(self):
        """Test KYC rejection triggers notification"""
        with patch('app.admin_panel.services.send_kyc_rejection_notification') as mock_notify:
            result = self.kyc_service.reject_kyc_document(
                kyc_doc_id=self.kyc_doc.id,
                admin_user=self.admin_user,
                rejection_reason='Document unclear'
            )
            
            self.assertTrue(result['success'])
            mock_notify.assert_called_once_with(self.regular_user, 'Document unclear')
    
    def test_kyc_document_validation(self):
        """Test KYC document validation"""
        # Test with invalid status
        result = self.kyc_service.approve_kyc_document(
            kyc_doc_id=self.kyc_doc.id,
            admin_user=self.admin_user,
            notes=''
        )
        
        self.assertFalse(result['success'])
        self.assertIn('notes required', result['error'])
        
        # Test with invalid rejection reason
        result = self.kyc_service.reject_kyc_document(
            kyc_doc_id=self.kyc_doc.id,
            admin_user=self.admin_user,
            rejection_reason=''
        )
        
        self.assertFalse(result['success'])
        self.assertIn('rejection reason required', result['error'])


class AdminKYCAPITest(TestCase):
    """Test KYC management API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=False
        )
        
        self.regular_user = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        
        self.kyc_doc = KYCDocument.objects.create(
            user=self.regular_user,
            document_type='PASSPORT',
            document_file='test_docs/passport.pdf',
            status='PENDING'
        )
        
        self.client.force_authenticate(user=self.admin_user)
    
    def test_list_kyc_documents(self):
        """Test listing KYC documents"""
        url = reverse('admin-kyc-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.kyc_doc.id)
    
    def test_list_kyc_documents_with_filters(self):
        """Test listing KYC documents with filters"""
        url = reverse('admin-kyc-list')
        response = self.client.get(url, {
            'status': 'PENDING',
            'user_id': self.regular_user.id
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_retrieve_kyc_document(self):
        """Test retrieving a specific KYC document"""
        url = reverse('admin-kyc-detail', kwargs={'pk': self.kyc_doc.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.kyc_doc.id)
        self.assertEqual(response.data['status'], 'PENDING')
    
    def test_approve_kyc_document_api(self):
        """Test approving KYC document via API"""
        url = reverse('admin-kyc-approve', kwargs={'pk': self.kyc_doc.id})
        data = {'notes': 'Document verified successfully'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check document status updated
        self.kyc_doc.refresh_from_db()
        self.assertEqual(self.kyc_doc.status, 'APPROVED')
    
    def test_reject_kyc_document_api(self):
        """Test rejecting KYC document via API"""
        url = reverse('admin-kyc-reject', kwargs={'pk': self.kyc_doc.id})
        data = {'rejection_reason': 'Document unclear'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check document status updated
        self.kyc_doc.refresh_from_db()
        self.assertEqual(self.kyc_doc.status, 'REJECTED')
    
    def test_approve_kyc_document_validation_error(self):
        """Test KYC approval with validation error"""
        url = reverse('admin-kyc-approve', kwargs={'pk': self.kyc_doc.id})
        data = {'notes': ''}  # Empty notes
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('notes', response.data)
    
    def test_reject_kyc_document_validation_error(self):
        """Test KYC rejection with validation error"""
        url = reverse('admin-kyc-reject', kwargs={'pk': self.kyc_doc.id})
        data = {'rejection_reason': ''}  # Empty reason
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rejection_reason', response.data)
    
    def test_kyc_api_permission_denied_non_admin(self):
        """Test KYC API access denied for non-admin users"""
        self.client.force_authenticate(user=self.regular_user)
        
        url = reverse('admin-kyc-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_kyc_api_permission_denied_staff(self):
        """Test KYC API access denied for staff users without KYC permission"""
        self.client.force_authenticate(user=self.staff_user)
        
        url = reverse('admin-kyc-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_kyc_api_unauthorized(self):
        """Test KYC API access denied for unauthenticated users"""
        self.client.force_authenticate(user=None)
        
        url = reverse('admin-kyc-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_kyc_approval_nonexistent_document(self):
        """Test approving non-existent KYC document"""
        url = reverse('admin-kyc-approve', kwargs={'pk': 99999})
        data = {'notes': 'Test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_kyc_rejection_nonexistent_document(self):
        """Test rejecting non-existent KYC document"""
        url = reverse('admin-kyc-reject', kwargs={'pk': 99999})
        data = {'rejection_reason': 'Test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_kyc_approval_already_approved(self):
        """Test approving already approved KYC document"""
        self.kyc_doc.status = 'APPROVED'
        self.kyc_doc.save()
        
        url = reverse('admin-kyc-approve', kwargs={'pk': self.kyc_doc.id})
        data = {'notes': 'Test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already approved', response.data['error'])
    
    def test_kyc_rejection_already_rejected(self):
        """Test rejecting already rejected KYC document"""
        self.kyc_doc.status = 'REJECTED'
        self.kyc_doc.save()
        
        url = reverse('admin-kyc-reject', kwargs={'pk': self.kyc_doc.id})
        data = {'rejection_reason': 'Test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already rejected', response.data['error'])


class AdminKYCIntegrationTest(TestCase):
    """Test KYC management integration with other modules"""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        self.regular_user = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        
        self.kyc_doc = KYCDocument.objects.create(
            user=self.regular_user,
            document_type='PASSPORT',
            document_file='test_docs/passport.pdf',
            status='PENDING'
        )
        
        self.kyc_service = AdminKYCService()
    
    def test_kyc_approval_enables_investments(self):
        """Test that KYC approval enables user to make investments"""
        # Initially user should not be able to invest
        self.assertFalse(self.regular_user.is_kyc_verified)
        
        # Approve KYC
        result = self.kyc_service.approve_kyc_document(
            kyc_doc_id=self.kyc_doc.id,
            admin_user=self.admin_user,
            notes='Document verified'
        )
        
        self.assertTrue(result['success'])
        
        # User should now be able to invest
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.is_kyc_verified)
    
    def test_kyc_rejection_prevents_withdrawals(self):
        """Test that KYC rejection prevents user withdrawals"""
        # Initially user should be able to withdraw
        self.regular_user.is_kyc_verified = True
        self.regular_user.save()
        
        # Reject KYC
        result = self.kyc_service.reject_kyc_document(
            kyc_doc_id=self.kyc_doc.id,
            admin_user=self.admin_user,
            rejection_reason='Document unclear'
        )
        
        self.assertTrue(result['success'])
        
        # User should not be able to withdraw
        self.regular_user.refresh_from_db()
        self.assertFalse(self.regular_user.is_kyc_verified)
    
    def test_kyc_approval_logs_admin_action(self):
        """Test that KYC approval creates proper admin action log"""
        result = self.kyc_service.approve_kyc_document(
            kyc_doc_id=self.kyc_doc.id,
            admin_user=self.admin_user,
            notes='Document verified'
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='KYC_APPROVAL',
            target_user=self.regular_user
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertEqual(action_log.target_model, 'KYCDocument')
        self.assertEqual(action_log.target_id, str(self.kyc_doc.id))
    
    def test_kyc_rejection_logs_admin_action(self):
        """Test that KYC rejection creates proper admin action log"""
        result = self.kyc_service.reject_kyc_document(
            kyc_doc_id=self.kyc_doc.id,
            admin_user=self.admin_user,
            rejection_reason='Document unclear'
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='KYC_REJECTION',
            target_user=self.regular_user
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertEqual(action_log.target_model, 'KYCDocument')
        self.assertEqual(action_log.target_id, str(self.kyc_doc.id))
    
    def test_kyc_status_synchronization(self):
        """Test that KYC status changes are properly synchronized"""
        # Approve KYC
        self.kyc_service.approve_kyc_document(
            kyc_doc_id=self.kyc_doc.id,
            admin_user=self.admin_user,
            notes='Document verified'
        )
        
        # Check both KYC document and user status updated
        self.kyc_doc.refresh_from_db()
        self.regular_user.refresh_from_db()
        
        self.assertEqual(self.kyc_doc.status, 'APPROVED')
        self.assertTrue(self.regular_user.is_kyc_verified)
        self.assertEqual(self.regular_user.kyc_status, 'APPROVED')
        
        # Reject KYC
        self.kyc_service.reject_kyc_document(
            kyc_doc_id=self.kyc_doc.id,
            admin_user=self.admin_user,
            rejection_reason='Document unclear'
        )
        
        # Check both statuses updated again
        self.kyc_doc.refresh_from_db()
        self.regular_user.refresh_from_db()
        
        self.assertEqual(self.kyc_doc.status, 'REJECTED')
        self.assertFalse(self.regular_user.is_kyc_verified)
        self.assertEqual(self.regular_user.kyc_status, 'REJECTED')
