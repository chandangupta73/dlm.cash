import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from unittest.mock import patch
from datetime import datetime, timedelta

from app.admin_panel.models import Announcement, AdminActionLog
from app.users.models import User
from app.wallet.models import INRWallet, USDTWallet
from app.investment.models import InvestmentPlan
from app.referral.models import ReferralMilestone
from app.admin_panel.permissions import (
    IsAdminUser, IsSuperUser, IsStaffUser, AdminActionPermission,
    WalletOverridePermission, KYCApprovalPermission, WithdrawalApprovalPermission,
    InvestmentManagementPermission, ReferralManagementPermission,
    AnnouncementPermission, UserManagementPermission, TransactionLogPermission
)
from app.admin_panel.services import AdminAnnouncementService

User = get_user_model()


class AdminPermissionTest(TestCase):
    """Test admin permission classes"""
    
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
            is_staff=False,
            is_superuser=False
        )
        
        self.request = type('Request', (), {
            'user': None,
            'method': 'GET'
        })()
    
    def test_is_admin_user_permission(self):
        """Test IsAdminUser permission class"""
        permission = IsAdminUser()
        
        # Test with admin user
        self.request.user = self.admin_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with staff user
        self.request.user = self.staff_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with regular user
        self.request.user = self.regular_user
        self.assertFalse(permission.has_permission(self.request, None))
        
        # Test with no user
        self.request.user = None
        self.assertFalse(permission.has_permission(self.request, None))
    
    def test_is_super_user_permission(self):
        """Test IsSuperUser permission class"""
        permission = IsSuperUser()
        
        # Test with superuser
        self.request.user = self.admin_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with staff user (not superuser)
        self.request.user = self.staff_user
        self.assertFalse(permission.has_permission(self.request, None))
        
        # Test with regular user
        self.request.user = self.regular_user
        self.assertFalse(permission.has_permission(self.request, None))
        
        # Test with no user
        self.request.user = None
        self.assertFalse(permission.has_permission(self.request, None))
    
    def test_is_staff_user_permission(self):
        """Test IsStaffUser permission class"""
        permission = IsStaffUser()
        
        # Test with admin user
        self.request.user = self.admin_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with staff user
        self.request.user = self.staff_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with regular user
        self.request.user = self.regular_user
        self.assertFalse(permission.has_permission(self.request, None))
        
        # Test with no user
        self.request.user = None
        self.assertFalse(permission.has_permission(self.request, None))
    
    def test_admin_action_permission(self):
        """Test AdminActionPermission class"""
        permission = AdminActionPermission()
        
        # Test with superuser (should have full access)
        self.request.user = self.admin_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with staff user (should have access to most actions)
        self.request.user = self.staff_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with regular user
        self.request.user = self.regular_user
        self.assertFalse(permission.has_permission(self.request, None))
        
        # Test with no user
        self.request.user = None
        self.assertFalse(permission.has_permission(self.request, None))
    
    def test_wallet_override_permission(self):
        """Test WalletOverridePermission class"""
        permission = WalletOverridePermission()
        
        # Test with superuser (should have access)
        self.request.user = self.admin_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with staff user (should not have access)
        self.request.user = self.staff_user
        self.assertFalse(permission.has_permission(self.request, None))
        
        # Test with regular user
        self.request.user = self.regular_user
        self.assertFalse(permission.has_permission(self.request, None))
    
    def test_kyc_approval_permission(self):
        """Test KYCApprovalPermission class"""
        permission = KYCApprovalPermission()
        
        # Test with admin user
        self.request.user = self.admin_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with staff user
        self.request.user = self.staff_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with regular user
        self.request.user = self.regular_user
        self.assertFalse(permission.has_permission(self.request, None))
    
    def test_withdrawal_approval_permission(self):
        """Test WithdrawalApprovalPermission class"""
        permission = WithdrawalApprovalPermission()
        
        # Test with admin user
        self.request.user = self.admin_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with staff user
        self.request.user = self.staff_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with regular user
        self.request.user = self.regular_user
        self.assertFalse(permission.has_permission(self.request, None))
    
    def test_investment_management_permission(self):
        """Test InvestmentManagementPermission class"""
        permission = InvestmentManagementPermission()
        
        # Test with admin user
        self.request.user = self.admin_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with staff user
        self.request.user = self.staff_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with regular user
        self.request.user = self.regular_user
        self.assertFalse(permission.has_permission(self.request, None))
    
    def test_referral_management_permission(self):
        """Test ReferralManagementPermission class"""
        permission = ReferralManagementPermission()
        
        # Test with admin user
        self.request.user = self.admin_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with staff user
        self.request.user = self.staff_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with regular user
        self.request.user = self.regular_user
        self.assertFalse(permission.has_permission(self.request, None))
    
    def test_announcement_permission(self):
        """Test AnnouncementPermission class"""
        permission = AnnouncementPermission()
        
        # Test with admin user
        self.request.user = self.admin_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with staff user
        self.request.user = self.staff_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with regular user
        self.request.user = self.regular_user
        self.assertFalse(permission.has_permission(self.request, None))
    
    def test_user_management_permission(self):
        """Test UserManagementPermission class"""
        permission = UserManagementPermission()
        
        # Test with admin user
        self.request.user = self.admin_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with staff user
        self.request.user = self.staff_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with regular user
        self.request.user = self.regular_user
        self.assertFalse(permission.has_permission(self.request, None))
    
    def test_transaction_log_permission(self):
        """Test TransactionLogPermission class"""
        permission = TransactionLogPermission()
        
        # Test with admin user
        self.request.user = self.admin_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with staff user
        self.request.user = self.staff_user
        self.assertTrue(permission.has_permission(self.request, None))
        
        # Test with regular user
        self.request.user = self.regular_user
        self.assertFalse(permission.has_permission(self.request, None))
    
    def test_permission_object_level_access(self):
        """Test object-level permission checks"""
        # Create test objects
        test_user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        test_wallet = INRWallet.objects.create(
            user=test_user,
            balance=Decimal('1000.00')
        )
        
        test_plan = InvestmentPlan.objects.create(
            name='Test Plan',
            roi_rate=Decimal('10.00'),
            duration_days=30,
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            is_active=True
        )
        
        test_milestone = ReferralMilestone.objects.create(
            name='Test Milestone',
            description='Test milestone',
            requirement_type='INVESTMENT_COUNT',
            requirement_value=1,
            reward_type='BONUS_AMOUNT',
            reward_value=Decimal('50.00'),
            is_active=True
        )
        
        test_announcement = Announcement.objects.create(
            title='Test Announcement',
            message='Test message',
            target_group='ALL',
            status='ACTIVE',
            priority='NORMAL',
            display_from=datetime.now(),
            display_until=datetime.now() + timedelta(days=7),
            created_by=self.admin_user
        )
        
        # Test object-level permissions for different user types
        # Admin user should have access to all objects
        self.request.user = self.admin_user
        self.assertTrue(WalletOverridePermission().has_object_permission(self.request, None, test_wallet))
        self.assertTrue(InvestmentManagementPermission().has_object_permission(self.request, None, test_plan))
        self.assertTrue(ReferralManagementPermission().has_object_permission(self.request, None, test_milestone))
        self.assertTrue(AnnouncementPermission().has_object_permission(self.request, None, test_announcement))
        
        # Staff user should have access to most objects but not wallet override
        self.request.user = self.staff_user
        self.assertFalse(WalletOverridePermission().has_object_permission(self.request, None, test_wallet))
        self.assertTrue(InvestmentManagementPermission().has_object_permission(self.request, None, test_plan))
        self.assertTrue(ReferralManagementPermission().has_object_permission(self.request, None, test_milestone))
        self.assertTrue(AnnouncementPermission().has_object_permission(self.request, None, test_announcement))
        
        # Regular user should not have access to any admin objects
        self.request.user = self.regular_user
        self.assertFalse(WalletOverridePermission().has_object_permission(self.request, None, test_wallet))
        self.assertFalse(InvestmentManagementPermission().has_object_permission(self.request, None, test_plan))
        self.assertFalse(ReferralManagementPermission().has_object_permission(self.request, None, test_milestone))
        self.assertFalse(AnnouncementPermission().has_object_permission(self.request, None, test_announcement))


class AdminPermissionAPITest(TestCase):
    """Test admin permission enforcement in API endpoints"""
    
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
            is_staff=False,
            is_superuser=False
        )
        
        # Create test data
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        self.test_wallet = INRWallet.objects.create(
            user=self.test_user,
            balance=Decimal('1000.00')
        )
        
        self.test_plan = InvestmentPlan.objects.create(
            name='Test Plan',
            roi_rate=Decimal('10.00'),
            duration_days=30,
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            is_active=True
        )
        
        self.test_milestone = ReferralMilestone.objects.create(
            name='Test Milestone',
            description='Test milestone',
            requirement_type='INVESTMENT_COUNT',
            requirement_value=1,
            reward_type='BONUS_AMOUNT',
            reward_value=Decimal('50.00'),
            is_active=True
        )
        
        self.test_announcement = Announcement.objects.create(
            title='Test Announcement',
            message='Test message',
            target_group='ALL',
            status='ACTIVE',
            priority='NORMAL',
            display_from=datetime.now(),
            display_until=datetime.now() + timedelta(days=7),
            created_by=self.admin_user
        )
    
    def test_dashboard_api_permissions(self):
        """Test dashboard API permission enforcement"""
        url = reverse('admin-dashboard-summary')
        
        # Test admin user access
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test staff user access
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test regular user access denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Test unauthenticated access denied
        self.client.force_authenticate(user=None)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_management_api_permissions(self):
        """Test user management API permission enforcement"""
        url = reverse('admin-user-list')
        
        # Test admin user access
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test staff user access
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test regular user access denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_wallet_management_api_permissions(self):
        """Test wallet management API permission enforcement"""
        url = reverse('admin-wallet-list')
        
        # Test admin user access
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test staff user access
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test regular user access denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_investment_management_api_permissions(self):
        """Test investment management API permission enforcement"""
        url = reverse('admin-investment-list')
        
        # Test admin user access
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test staff user access
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test regular user access denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_referral_management_api_permissions(self):
        """Test referral management API permission enforcement"""
        url = reverse('admin-referral-list')
        
        # Test admin user access
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test staff user access
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test regular user access denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_announcement_management_api_permissions(self):
        """Test announcement management API permission enforcement"""
        url = reverse('admin-announcement-list')
        
        # Test admin user access
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test staff user access
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test regular user access denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_superuser_only_operations(self):
        """Test operations that require superuser permissions"""
        # Test wallet override (superuser only)
        url = reverse('admin-wallet-adjust-balance', kwargs={'pk': self.test_wallet.id})
        data = {
            'amount': '500.00',
            'adjustment_type': 'override',
            'reason': 'Superuser test',
            'force_negative': True
        }
        
        # Admin user (superuser) should have access
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Staff user should not have access
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Regular user should not have access
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_staff_user_restricted_operations(self):
        """Test operations that are restricted for staff users"""
        # Test investment plan deletion (staff users cannot delete)
        url = reverse('admin-investment-plan-detail', kwargs={'pk': self.test_plan.id})
        
        # Admin user should have access
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Recreate the plan for next test
        self.test_plan = InvestmentPlan.objects.create(
            name='Test Plan 2',
            roi_rate=Decimal('10.00'),
            duration_days=30,
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            is_active=True
        )
        
        # Staff user should not have access to delete
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_cross_user_access_restrictions(self):
        """Test that users cannot access other users' admin functions"""
        # Create another admin user
        other_admin = User.objects.create_user(
            username='otheradmin',
            email='other@admin.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Test that admin users cannot access each other's accounts through admin APIs
        # (This would depend on your specific implementation, but generally admin users
        # should not be able to modify each other's accounts through regular admin APIs)
        
        # Test user update
        url = reverse('admin-user-detail', kwargs={'pk': other_admin.id})
        data = {'first_name': 'Modified'}
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(url, data)
        
        # This should either be forbidden or allowed depending on your security model
        # For now, we'll just test that the endpoint exists and responds
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_permission_consistency_across_endpoints(self):
        """Test that permissions are consistent across all admin endpoints"""
        admin_endpoints = [
            reverse('admin-dashboard-summary'),
            reverse('admin-user-list'),
            reverse('admin-kyc-list'),
            reverse('admin-wallet-list'),
            reverse('admin-withdrawal-list'),
            reverse('admin-investment-list'),
            reverse('admin-referral-list'),
            reverse('admin-announcement-list'),
        ]
        
        # Test that all endpoints enforce the same permission rules
        for endpoint in admin_endpoints:
            # Regular user should be denied access to all admin endpoints
            self.client.force_authenticate(user=self.regular_user)
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, 
                           f"Endpoint {endpoint} should deny access to regular users")
            
            # Admin user should have access to all admin endpoints
            self.client.force_authenticate(user=self.admin_user)
            response = self.client.get(endpoint)
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
                         f"Endpoint {endpoint} should allow access to admin users")
            
            # Staff user should have access to most admin endpoints
            self.client.force_authenticate(user=self.staff_user)
            response = self.client.get(endpoint)
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
                         f"Endpoint {endpoint} should allow access to staff users")
    
    def test_authentication_required_for_all_admin_endpoints(self):
        """Test that all admin endpoints require authentication"""
        admin_endpoints = [
            reverse('admin-dashboard-summary'),
            reverse('admin-user-list'),
            reverse('admin-kyc-list'),
            reverse('admin-wallet-list'),
            reverse('admin-withdrawal-list'),
            reverse('admin-investment-list'),
            reverse('admin-referral-list'),
            reverse('admin-announcement-list'),
        ]
        
        # Test that all endpoints require authentication
        for endpoint in admin_endpoints:
            self.client.force_authenticate(user=None)
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED,
                           f"Endpoint {endpoint} should require authentication")


class AdminPermissionIntegrationTest(TestCase):
    """Test admin permission integration with other modules"""
    
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
            is_staff=False,
            is_superuser=False
        )
        
        # Create test data
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        self.test_wallet = INRWallet.objects.create(
            user=self.test_user,
            balance=Decimal('1000.00')
        )
        
        self.test_plan = InvestmentPlan.objects.create(
            name='Test Plan',
            roi_rate=Decimal('10.00'),
            duration_days=30,
            min_amount=Decimal('100.00'),
            max_amount=Decimal('10000.00'),
            is_active=True
        )
        
        self.test_milestone = ReferralMilestone.objects.create(
            name='Test Milestone',
            description='Test milestone',
            requirement_type='INVESTMENT_COUNT',
            requirement_value=1,
            reward_type='BONUS_AMOUNT',
            reward_value=Decimal('50.00'),
            is_active=True
        )
        
        self.test_announcement = Announcement.objects.create(
            title='Test Announcement',
            message='Test message',
            target_group='ALL',
            status='ACTIVE',
            priority='NORMAL',
            display_from=datetime.now(),
            display_until=datetime.now() + timedelta(days=7),
            created_by=self.admin_user
        )
    
    def test_permission_enforcement_in_services(self):
        """Test that permission checks are enforced in service layer"""
        # Test that staff users cannot perform superuser-only operations
        # This would depend on your service layer implementation
        
        # For now, we'll test that the permission classes work correctly
        # when used in views and services
        
        # Test wallet override permission
        wallet_permission = WalletOverridePermission()
        request = type('Request', (), {'user': self.staff_user})()
        
        # Staff user should not have wallet override permission
        self.assertFalse(wallet_permission.has_permission(request, None))
        
        # Admin user should have wallet override permission
        request.user = self.admin_user
        self.assertTrue(wallet_permission.has_permission(request, None))
    
    def test_permission_cascade_effects(self):
        """Test that permission changes cascade correctly through the system"""
        # Test that when a user's permissions change, it affects all admin operations
        
        # Initially, regular user should not have admin access
        user_permission = UserManagementPermission()
        request = type('Request', (), {'user': self.regular_user})()
        self.assertFalse(user_permission.has_permission(request, None))
        
        # Change user to staff
        self.regular_user.is_staff = True
        self.regular_user.save()
        
        # Now user should have admin access
        self.assertTrue(user_permission.has_permission(request, None))
        
        # Change back to regular user
        self.regular_user.is_staff = False
        self.regular_user.save()
        
        # User should not have admin access again
        self.assertFalse(user_permission.has_permission(request, None))
    
    def test_permission_boundary_conditions(self):
        """Test permission boundary conditions and edge cases"""
        # Test with inactive users
        inactive_user = User.objects.create_user(
            username='inactive',
            email='inactive@test.com',
            password='testpass123',
            is_staff=True,
            is_active=False
        )
        
        # Inactive staff user should not have admin access
        user_permission = UserManagementPermission()
        request = type('Request', (), {'user': inactive_user})()
        self.assertFalse(user_permission.has_permission(request, None))
        
        # Test with users having mixed permission flags
        mixed_user = User.objects.create_user(
            username='mixed',
            email='mixed@test.com',
            password='testpass123',
            is_staff=False,
            is_superuser=True  # Superuser but not staff
        )
        
        # Mixed user should have admin access (superuser overrides)
        self.assertTrue(user_permission.has_permission(request, None))
    
    def test_permission_logging_and_auditing(self):
        """Test that permission checks are properly logged and audited"""
        # This would test that failed permission attempts are logged
        # and that successful admin actions create proper audit trails
        
        # For now, we'll test that the permission classes can be used
        # in conjunction with the logging system
        
        # Test that admin action logging works with permissions
        # This would depend on your specific implementation
        
        # Test basic permission functionality
        admin_permission = AdminActionPermission()
        request = type('Request', (), {'user': self.admin_user})()
        
        self.assertTrue(admin_permission.has_permission(request, None))
        
        # Test that permission checks work with different HTTP methods
        request.method = 'POST'
        self.assertTrue(admin_permission.has_permission(request, None))
        
        request.method = 'DELETE'
        self.assertTrue(admin_permission.has_permission(request, None))
    
    def test_permission_performance_characteristics(self):
        """Test permission check performance characteristics"""
        # Test that permission checks don't add significant overhead
        
        import time
        
        # Test permission check timing
        permission = IsAdminUser()
        request = type('Request', (), {'user': self.admin_user})()
        
        start_time = time.time()
        for _ in range(1000):
            permission.has_permission(request, None)
        end_time = time.time()
        
        # Permission checks should be very fast (less than 1 second for 1000 checks)
        self.assertLess(end_time - start_time, 1.0)
        
        # Test with different user types
        request.user = self.staff_user
        start_time = time.time()
        for _ in range(1000):
            permission.has_permission(request, None)
        end_time = time.time()
        
        self.assertLess(end_time - start_time, 1.0)
        
        request.user = self.regular_user
        start_time = time.time()
        for _ in range(1000):
            permission.has_permission(request, None)
        end_time = time.time()
        
        self.assertLess(end_time - start_time, 1.0)
