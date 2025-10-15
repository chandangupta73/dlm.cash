import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from unittest.mock import patch
from datetime import datetime, timedelta
from freezegun import freeze_time

from app.admin_panel.models import Announcement, AdminActionLog
from app.users.models import User
from app.admin_panel.services import AdminAnnouncementService
from app.admin_panel.permissions import log_admin_action

User = get_user_model()


class AdminAnnouncementServiceTest(TestCase):
    """Test announcement management service layer"""
    
    def setUp(self):
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
            password='testpass123',
            is_kyc_verified=True
        )
        
        self.unverified_user = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='testpass123',
            is_kyc_verified=False
        )
        
        self.announcement = Announcement.objects.create(
            title='Test Announcement',
            message='This is a test announcement for all users',
            target_group='ALL',
            status='ACTIVE',
            priority='NORMAL',
            display_from=datetime.now() - timedelta(days=1),
            display_until=datetime.now() + timedelta(days=30),
            created_by=self.admin_user,
            is_pinned=False
        )
        
        self.verified_only_announcement = Announcement.objects.create(
            title='Verified Users Only',
            message='This announcement is only for verified users',
            target_group='VERIFIED_ONLY',
            status='ACTIVE',
            priority='HIGH',
            display_from=datetime.now() - timedelta(days=1),
            display_until=datetime.now() + timedelta(days=30),
            created_by=self.admin_user,
            is_pinned=True
        )
        
        self.announcement_service = AdminAnnouncementService()
    
    def test_get_all_announcements(self):
        """Test retrieving all announcements"""
        announcements = self.announcement_service.get_all_announcements()
        
        self.assertEqual(len(announcements), 2)
        self.assertEqual(announcements[0].title, 'Test Announcement')
        self.assertEqual(announcements[1].title, 'Verified Users Only')
    
    def test_get_announcements_with_filters(self):
        """Test retrieving announcements with various filters"""
        # Test status filter
        active_announcements = self.announcement_service.get_announcements(status='ACTIVE')
        self.assertEqual(len(active_announcements), 2)
        
        inactive_announcements = self.announcement_service.get_announcements(status='INACTIVE')
        self.assertEqual(len(inactive_announcements), 0)
        
        # Test target group filter
        all_user_announcements = self.announcement_service.get_announcements(target_group='ALL')
        self.assertEqual(len(all_user_announcements), 1)
        self.assertEqual(all_user_announcements[0].title, 'Test Announcement')
        
        verified_only_announcements = self.announcement_service.get_announcements(target_group='VERIFIED_ONLY')
        self.assertEqual(len(verified_only_announcements), 1)
        self.assertEqual(verified_only_announcements[0].title, 'Verified Users Only')
        
        # Test priority filter
        high_priority_announcements = self.announcement_service.get_announcements(priority='HIGH')
        self.assertEqual(len(high_priority_announcements), 1)
        self.assertEqual(high_priority_announcements[0].title, 'Verified Users Only')
        
        # Test created by filter
        admin_announcements = self.announcement_service.get_announcements(created_by=self.admin_user.id)
        self.assertEqual(len(admin_announcements), 2)
    
    def test_get_active_announcements_for_user(self):
        """Test retrieving active announcements for a specific user"""
        # Test for verified user
        verified_user_announcements = self.announcement_service.get_active_announcements_for_user(self.regular_user)
        
        self.assertEqual(len(verified_user_announcements), 2)  # Should see both ALL and VERIFIED_ONLY
        titles = [ann.title for ann in verified_user_announcements]
        self.assertIn('Test Announcement', titles)
        self.assertIn('Verified Users Only', titles)
        
        # Test for unverified user
        unverified_user_announcements = self.announcement_service.get_active_announcements_for_user(self.unverified_user)
        
        self.assertEqual(len(unverified_user_announcements), 1)  # Should only see ALL
        self.assertEqual(unverified_user_announcements[0].title, 'Test Announcement')
    
    def test_create_announcement(self):
        """Test creating a new announcement"""
        announcement_data = {
            'title': 'New System Update',
            'message': 'Important system update coming soon',
            'target_group': 'ALL',
            'status': 'ACTIVE',
            'priority': 'HIGH',
            'display_from': datetime.now(),
            'display_until': datetime.now() + timedelta(days=7),
            'is_pinned': True
        }
        
        result = self.announcement_service.create_announcement(
            announcement_data=announcement_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check announcement created
        new_announcement = Announcement.objects.get(title='New System Update')
        self.assertEqual(new_announcement.message, 'Important system update coming soon')
        self.assertEqual(new_announcement.target_group, 'ALL')
        self.assertEqual(new_announcement.priority, 'HIGH')
        self.assertTrue(new_announcement.is_pinned)
        self.assertEqual(new_announcement.created_by, self.admin_user)
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='ANNOUNCEMENT_CREATION',
            target_model='Announcement'
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('New System Update', action_log.action_description)
    
    def test_update_announcement(self):
        """Test updating an announcement"""
        update_data = {
            'title': 'Updated Test Announcement',
            'message': 'This announcement has been updated',
            'priority': 'HIGH',
            'is_pinned': True
        }
        
        result = self.announcement_service.update_announcement(
            announcement_id=self.announcement.id,
            update_data=update_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check announcement updated
        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.title, 'Updated Test Announcement')
        self.assertEqual(self.announcement.message, 'This announcement has been updated')
        self.assertEqual(self.announcement.priority, 'HIGH')
        self.assertTrue(self.announcement.is_pinned)
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='ANNOUNCEMENT_UPDATE',
            target_model='Announcement'
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Updated Test Announcement', action_log.action_description)
    
    def test_delete_announcement(self):
        """Test deleting an announcement"""
        result = self.announcement_service.delete_announcement(
            announcement_id=self.announcement.id,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check announcement deleted
        self.assertFalse(Announcement.objects.filter(id=self.announcement.id).exists())
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='ANNOUNCEMENT_DELETION',
            target_model='Announcement'
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Test Announcement', action_log.action_description)
    
    def test_toggle_announcement_status(self):
        """Test toggling announcement status"""
        result = self.announcement_service.toggle_announcement_status(
            announcement_id=self.announcement.id,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check status toggled
        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.status, 'INACTIVE')
        
        # Toggle back
        result = self.announcement_service.toggle_announcement_status(
            announcement_id=self.announcement.id,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.status, 'ACTIVE')
    
    def test_toggle_announcement_pin(self):
        """Test toggling announcement pin status"""
        result = self.announcement_service.toggle_announcement_pin(
            announcement_id=self.announcement.id,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check pin status toggled
        self.announcement.refresh_from_db()
        self.assertTrue(self.announcement.is_pinned)
        
        # Toggle back
        result = self.announcement_service.toggle_announcement_pin(
            announcement_id=self.announcement.id,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        self.announcement.refresh_from_db()
        self.assertFalse(self.announcement.is_pinned)
    
    def test_increment_announcement_view_count(self):
        """Test incrementing announcement view count"""
        initial_view_count = self.announcement.view_count
        
        result = self.announcement_service.increment_view_count(
            announcement_id=self.announcement.id,
            user=self.regular_user
        )
        
        self.assertTrue(result['success'])
        
        # Check view count incremented
        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.view_count, initial_view_count + 1)
    
    def test_create_announcement_validation_error(self):
        """Test creating announcement with validation error"""
        invalid_announcement_data = {
            'title': '',  # Empty title
            'message': 'Test message',
            'target_group': 'ALL'
        }
        
        result = self.announcement_service.create_announcement(
            announcement_data=invalid_announcement_data,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('title', result['error'])
    
    def test_update_announcement_validation_error(self):
        """Test updating announcement with validation error"""
        invalid_update_data = {
            'title': '',  # Empty title
            'priority': 'INVALID_PRIORITY'  # Invalid priority
        }
        
        result = self.announcement_service.update_announcement(
            announcement_id=self.announcement.id,
            update_data=invalid_update_data,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('title', result['error'])
    
    def test_create_nonexistent_announcement(self):
        """Test creating announcement with non-existent announcement"""
        result = self.announcement_service.update_announcement(
            announcement_id=99999,
            update_data={'title': 'Test'},
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_delete_nonexistent_announcement(self):
        """Test deleting non-existent announcement"""
        result = self.announcement_service.delete_announcement(
            announcement_id=99999,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_toggle_nonexistent_announcement_status(self):
        """Test toggling status of non-existent announcement"""
        result = self.announcement_service.toggle_announcement_status(
            announcement_id=99999,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_staff_user_cannot_delete_announcement(self):
        """Test staff user cannot delete announcement"""
        result = self.announcement_service.delete_announcement(
            announcement_id=self.announcement.id,
            admin_user=self.staff_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('permission denied', result['error'])
    
    def test_announcement_creation_with_notification(self):
        """Test announcement creation triggers notification"""
        with patch('app.admin_panel.services.send_announcement_creation_notification') as mock_notify:
            announcement_data = {
                'title': 'Notification Test Announcement',
                'message': 'Test announcement for notifications',
                'target_group': 'ALL',
                'status': 'ACTIVE',
                'priority': 'NORMAL',
                'display_from': datetime.now(),
                'display_until': datetime.now() + timedelta(days=7)
            }
            
            result = self.announcement_service.create_announcement(
                announcement_data=announcement_data,
                admin_user=self.admin_user
            )
            
            self.assertTrue(result['success'])
            mock_notify.assert_called_once()
    
    def test_announcement_with_date_validation(self):
        """Test announcement creation with date validation"""
        # Test with display_until before display_from
        invalid_announcement_data = {
            'title': 'Date Validation Test',
            'message': 'Test message',
            'target_group': 'ALL',
            'display_from': datetime.now() + timedelta(days=7),
            'display_until': datetime.now()  # Before display_from
        }
        
        result = self.announcement_service.create_announcement(
            announcement_data=invalid_announcement_data,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('display_until', result['error'])
    
    def test_announcement_target_group_validation(self):
        """Test announcement creation with invalid target group"""
        invalid_announcement_data = {
            'title': 'Target Group Test',
            'message': 'Test message',
            'target_group': 'INVALID_GROUP',  # Invalid target group
            'status': 'ACTIVE'
        }
        
        result = self.announcement_service.create_announcement(
            announcement_data=invalid_announcement_data,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('target_group', result['error'])


class AdminAnnouncementAPITest(TestCase):
    """Test announcement management API endpoints"""
    
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
            password='testpass123',
            is_kyc_verified=True
        )
        
        self.unverified_user = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='testpass123',
            is_kyc_verified=False
        )
        
        self.announcement = Announcement.objects.create(
            title='Test Announcement',
            message='This is a test announcement for all users',
            target_group='ALL',
            status='ACTIVE',
            priority='NORMAL',
            display_from=datetime.now() - timedelta(days=1),
            display_until=datetime.now() + timedelta(days=30),
            created_by=self.admin_user,
            is_pinned=False
        )
        
        self.verified_only_announcement = Announcement.objects.create(
            title='Verified Users Only',
            message='This announcement is only for verified users',
            target_group='VERIFIED_ONLY',
            status='ACTIVE',
            priority='HIGH',
            display_from=datetime.now() - timedelta(days=1),
            display_until=datetime.now() + timedelta(days=30),
            created_by=self.admin_user,
            is_pinned=True
        )
        
        self.client.force_authenticate(user=self.admin_user)
    
    def test_list_announcements(self):
        """Test listing announcements"""
        url = reverse('admin-announcement-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['results'][0]['title'], 'Test Announcement')
        self.assertEqual(response.data['results'][1]['title'], 'Verified Users Only')
    
    def test_list_announcements_with_filters(self):
        """Test listing announcements with filters"""
        url = reverse('admin-announcement-list')
        response = self.client.get(url, {
            'status': 'ACTIVE',
            'target_group': 'ALL',
            'priority': 'NORMAL'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Test Announcement')
    
    def test_retrieve_announcement(self):
        """Test retrieving a specific announcement"""
        url = reverse('admin-announcement-detail', kwargs={'pk': self.announcement.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.announcement.id)
        self.assertEqual(response.data['title'], 'Test Announcement')
    
    def test_create_announcement_api(self):
        """Test creating announcement via API"""
        url = reverse('admin-announcement-list')
        data = {
            'title': 'API Test Announcement',
            'message': 'Test announcement created via API',
            'target_group': 'ALL',
            'status': 'ACTIVE',
            'priority': 'HIGH',
            'display_from': (datetime.now() - timedelta(days=1)).isoformat(),
            'display_until': (datetime.now() + timedelta(days=7)).isoformat(),
            'is_pinned': True
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'API Test Announcement')
        self.assertEqual(response.data['target_group'], 'ALL')
        self.assertEqual(response.data['priority'], 'HIGH')
        self.assertTrue(response.data['is_pinned'])
    
    def test_update_announcement_api(self):
        """Test updating announcement via API"""
        url = reverse('admin-announcement-detail', kwargs={'pk': self.announcement.id})
        data = {
            'title': 'Updated API Test Announcement',
            'message': 'This announcement has been updated via API',
            'priority': 'HIGH'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated API Test Announcement')
        self.assertEqual(response.data['priority'], 'HIGH')
    
    def test_delete_announcement_api(self):
        """Test deleting announcement via API"""
        url = reverse('admin-announcement-detail', kwargs={'pk': self.announcement.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_toggle_announcement_status_api(self):
        """Test toggling announcement status via API"""
        url = reverse('admin-announcement-toggle-status', kwargs={'pk': self.announcement.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check status toggled
        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.status, 'INACTIVE')
    
    def test_toggle_announcement_pin_api(self):
        """Test toggling announcement pin status via API"""
        url = reverse('admin-announcement-toggle-pin', kwargs={'pk': self.announcement.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check pin status toggled
        self.announcement.refresh_from_db()
        self.assertTrue(self.announcement.is_pinned)
    
    def test_get_active_announcements_for_user_api(self):
        """Test getting active announcements for user via API"""
        url = reverse('admin-announcement-active-for-user', kwargs={'pk': self.regular_user.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Should see both ALL and VERIFIED_ONLY
        
        # Test for unverified user
        url = reverse('admin-announcement-active-for-user', kwargs={'pk': self.unverified_user.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Should only see ALL
    
    def test_create_announcement_validation_error(self):
        """Test creating announcement with validation error"""
        url = reverse('admin-announcement-list')
        data = {
            'title': '',  # Empty title
            'message': 'Test message',
            'target_group': 'ALL'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)
    
    def test_update_announcement_validation_error(self):
        """Test updating announcement with validation error"""
        url = reverse('admin-announcement-detail', kwargs={'pk': self.announcement.id})
        data = {
            'title': '',  # Empty title
            'priority': 'INVALID_PRIORITY'  # Invalid priority
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)
    
    def test_announcement_api_permission_denied_non_admin(self):
        """Test announcement API access denied for non-admin users"""
        self.client.force_authenticate(user=self.regular_user)
        
        url = reverse('admin-announcement-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_announcement_api_permission_denied_staff(self):
        """Test announcement API access denied for staff users without permission"""
        self.client.force_authenticate(user=self.staff_user)
        
        url = reverse('admin-announcement-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_announcement_api_unauthorized(self):
        """Test announcement API access denied for unauthenticated users"""
        self.client.force_authenticate(user=None)
        
        url = reverse('admin-announcement-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_nonexistent_announcement(self):
        """Test creating announcement with non-existent announcement"""
        url = reverse('admin-announcement-detail', kwargs={'pk': 99999})
        data = {'title': 'Test'}
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_delete_nonexistent_announcement(self):
        """Test deleting non-existent announcement"""
        url = reverse('admin-announcement-detail', kwargs={'pk': 99999})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_toggle_nonexistent_announcement_status(self):
        """Test toggling status of non-existent announcement"""
        url = reverse('admin-announcement-toggle-status', kwargs={'pk': 99999})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_toggle_nonexistent_announcement_pin(self):
        """Test toggling pin status of non-existent announcement"""
        url = reverse('admin-announcement-toggle-pin', kwargs={'pk': 99999})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_get_active_announcements_nonexistent_user(self):
        """Test getting active announcements for non-existent user"""
        url = reverse('admin-announcement-active-for-user', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminAnnouncementIntegrationTest(TestCase):
    """Test announcement management integration with other modules"""
    
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
            is_kyc_verified=True
        )
        
        self.unverified_user = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='testpass123',
            is_kyc_verified=False
        )
        
        self.announcement = Announcement.objects.create(
            title='Integration Test Announcement',
            message='Test announcement for integration tests',
            target_group='ALL',
            status='ACTIVE',
            priority='NORMAL',
            display_from=datetime.now() - timedelta(days=1),
            display_until=datetime.now() + timedelta(days=30),
            created_by=self.admin_user,
            is_pinned=False
        )
        
        self.verified_only_announcement = Announcement.objects.create(
            title='Integration Verified Only',
            message='Verified users only announcement',
            target_group='VERIFIED_ONLY',
            status='ACTIVE',
            priority='HIGH',
            display_from=datetime.now() - timedelta(days=1),
            display_until=datetime.now() + timedelta(days=30),
            created_by=self.admin_user,
            is_pinned=True
        )
        
        self.announcement_service = AdminAnnouncementService()
    
    def test_announcement_creation_logs_admin_action(self):
        """Test that announcement creation creates admin action log"""
        announcement_data = {
            'title': 'Integration Test Creation',
            'message': 'Test announcement for admin action log',
            'target_group': 'ALL',
            'status': 'ACTIVE',
            'priority': 'NORMAL',
            'display_from': datetime.now(),
            'display_until': datetime.now() + timedelta(days=7)
        }
        
        result = self.announcement_service.create_announcement(
            announcement_data=announcement_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log exists
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='ANNOUNCEMENT_CREATION',
            target_model='Announcement'
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertIn('Integration Test Creation', action_log.action_description)
    
    def test_announcement_update_logs_admin_action(self):
        """Test that announcement update creates admin action log"""
        update_data = {
            'title': 'Updated Integration Test',
            'message': 'Updated message for admin action log test',
            'priority': 'HIGH'
        }
        
        result = self.announcement_service.update_announcement(
            announcement_id=self.announcement.id,
            update_data=update_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log exists
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='ANNOUNCEMENT_UPDATE',
            target_model='Announcement'
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertIn('Updated Integration Test', action_log.action_description)
    
    def test_announcement_deletion_logs_admin_action(self):
        """Test that announcement deletion creates admin action log"""
        result = self.announcement_service.delete_announcement(
            announcement_id=self.announcement.id,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log exists
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='ANNOUNCEMENT_DELETION',
            target_model='Announcement'
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertIn('Integration Test Announcement', action_log.action_description)
    
    def test_announcement_target_group_filtering_works_correctly(self):
        """Test that announcement target group filtering works correctly for different user types"""
        # Test for verified user
        verified_user_announcements = self.announcement_service.get_active_announcements_for_user(self.regular_user)
        
        self.assertEqual(len(verified_user_announcements), 2)  # Should see both ALL and VERIFIED_ONLY
        titles = [ann.title for ann in verified_user_announcements]
        self.assertIn('Integration Test Announcement', titles)
        self.assertIn('Integration Verified Only', titles)
        
        # Test for unverified user
        unverified_user_announcements = self.announcement_service.get_active_announcements_for_user(self.unverified_user)
        
        self.assertEqual(len(unverified_user_announcements), 1)  # Should only see ALL
        self.assertEqual(unverified_user_announcements[0].title, 'Integration Test Announcement')
    
    def test_announcement_status_toggle_maintains_integrity(self):
        """Test that announcement status toggle maintains data integrity"""
        # Get initial status
        initial_status = self.announcement.status
        
        # Toggle status
        result = self.announcement_service.toggle_announcement_status(
            announcement_id=self.announcement.id,
            admin_user=self.admin_user
        )
        self.assertTrue(result['success'])
        
        # Check status toggled
        self.announcement.refresh_from_db()
        expected_status = 'INACTIVE' if initial_status == 'ACTIVE' else 'ACTIVE'
        self.assertEqual(self.announcement.status, expected_status)
        
        # Toggle back
        result = self.announcement_service.toggle_announcement_status(
            announcement_id=self.announcement.id,
            admin_user=self.admin_user
        )
        self.assertTrue(result['success'])
        
        # Check status back to original
        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.status, initial_status)
    
    def test_announcement_pin_toggle_maintains_integrity(self):
        """Test that announcement pin toggle maintains data integrity"""
        # Get initial pin status
        initial_pin_status = self.announcement.is_pinned
        
        # Toggle pin status
        result = self.announcement_service.toggle_announcement_pin(
            announcement_id=self.announcement.id,
            admin_user=self.admin_user
        )
        self.assertTrue(result['success'])
        
        # Check pin status toggled
        self.announcement.refresh_from_db()
        expected_pin_status = not initial_pin_status
        self.assertEqual(self.announcement.is_pinned, expected_pin_status)
        
        # Toggle back
        result = self.announcement_service.toggle_announcement_pin(
            announcement_id=self.announcement.id,
            admin_user=self.admin_user
        )
        self.assertTrue(result['success'])
        
        # Check pin status back to original
        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.is_pinned, initial_pin_status)
    
    def test_multiple_announcement_operations_maintain_consistency(self):
        """Test that multiple announcement operations maintain data consistency"""
        # Create multiple announcements
        announcements_data = [
            {
                'title': 'Multiple Test 1',
                'message': 'First test announcement',
                'target_group': 'ALL',
                'status': 'ACTIVE',
                'priority': 'NORMAL',
                'display_from': datetime.now(),
                'display_until': datetime.now() + timedelta(days=7)
            },
            {
                'title': 'Multiple Test 2',
                'message': 'Second test announcement',
                'target_group': 'VERIFIED_ONLY',
                'status': 'ACTIVE',
                'priority': 'HIGH',
                'display_from': datetime.now(),
                'display_until': datetime.now() + timedelta(days=14)
            }
        ]
        
        created_announcements = []
        for data in announcements_data:
            result = self.announcement_service.create_announcement(
                announcement_data=data,
                admin_user=self.admin_user
            )
            self.assertTrue(result['success'])
            
            # Get created announcement
            created_announcement = Announcement.objects.get(title=data['title'])
            created_announcements.append(created_announcement)
        
        # Check all announcements created
        self.assertEqual(len(created_announcements), 2)
        
        # Test filtering still works correctly
        all_announcements = self.announcement_service.get_all_announcements()
        self.assertEqual(len(all_announcements), 4)  # 2 original + 2 new
        
        # Test user-specific filtering still works
        verified_user_announcements = self.announcement_service.get_active_announcements_for_user(self.regular_user)
        self.assertEqual(len(verified_user_announcements), 4)  # Should see all
        
        unverified_user_announcements = self.announcement_service.get_active_announcements_for_user(self.unverified_user)
        self.assertEqual(len(unverified_user_announcements), 2)  # Should only see ALL
    
    def test_announcement_date_filtering_works_correctly(self):
        """Test that announcement date filtering works correctly"""
        with freeze_time('2024-01-15'):
            # Create announcement with past display_from
            past_announcement_data = {
                'title': 'Past Display From',
                'message': 'Announcement with past display_from',
                'target_group': 'ALL',
                'status': 'ACTIVE',
                'display_from': datetime.now() - timedelta(days=10),
                'display_until': datetime.now() + timedelta(days=20)
            }
            
            result = self.announcement_service.create_announcement(
                announcement_data=past_announcement_data,
                admin_user=self.admin_user
            )
            self.assertTrue(result['success'])
            
            # Create announcement with future display_from
            future_announcement_data = {
                'title': 'Future Display From',
                'message': 'Announcement with future display_from',
                'target_group': 'ALL',
                'status': 'ACTIVE',
                'display_from': datetime.now() + timedelta(days=10),
                'display_until': datetime.now() + timedelta(days=30)
            }
            
            result = self.announcement_service.create_announcement(
                announcement_data=future_announcement_data,
                admin_user=self.admin_user
            )
            self.assertTrue(result['success'])
            
            # Test that only past announcements are visible to users
            user_announcements = self.announcement_service.get_active_announcements_for_user(self.regular_user)
            
            # Should see past announcements but not future ones
            titles = [ann.title for ann in user_announcements]
            self.assertIn('Past Display From', titles)
            self.assertNotIn('Future Display From', titles)
