import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal

from app.admin_panel.services import AdminUserService
from app.wallet.models import INRWallet, USDTWallet

User = get_user_model()


class AdminUserServiceTest(TestCase):
    """Test cases for AdminUserService."""
    
    def setUp(self):
        """Set up test data."""
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create regular users
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123',
            first_name='John',
            last_name='Doe',
            phone_number='+1234567890'
        )
        
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='testpass123',
            first_name='Jane',
            last_name='Smith',
            phone_number='+0987654321',
            is_kyc_verified=True,
            kyc_status='APPROVED'
        )
        
        self.user3 = User.objects.create_user(
            username='user3',
            email='user3@test.com',
            password='testpass123',
            first_name='Bob',
            last_name='Johnson',
            phone_number='+1122334455'
        )
        
        # Get or create wallets (signals may have already created them)
        self.inr_wallet1, _ = INRWallet.objects.get_or_create(
            user=self.user1,
            defaults={
                'balance': Decimal('1000.00'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.inr_wallet1.balance != Decimal('1000.00'):
            self.inr_wallet1.balance = Decimal('1000.00')
            self.inr_wallet1.status = 'active'
            self.inr_wallet1.is_active = True
            self.inr_wallet1.save()
        
        self.usdt_wallet1, _ = USDTWallet.objects.get_or_create(
            user=self.user1,
            defaults={
                'balance': Decimal('100.000000'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.usdt_wallet1.balance != Decimal('100.000000'):
            self.usdt_wallet1.balance = Decimal('100.000000')
            self.usdt_wallet1.status = 'active'
            self.usdt_wallet1.is_active = True
            self.usdt_wallet1.save()
        
        self.inr_wallet2, _ = INRWallet.objects.get_or_create(
            user=self.user2,
            defaults={
                'balance': Decimal('2000.00'),
                'status': 'active',
                'is_active': True
            }
        )
        # Update balance if wallet already existed
        if self.inr_wallet2.balance != Decimal('2000.00'):
            self.inr_wallet2.balance = Decimal('2000.00')
            self.inr_wallet2.status = 'active'
            self.inr_wallet2.is_active = True
            self.inr_wallet2.save()
    
    def test_get_users_with_filters(self):
        """Test getting users with various filters."""
        # Test no filters
        users = AdminUserService.get_users_with_filters()
        self.assertEqual(users.count(), 4)  # admin + 3 users
        
        # Test KYC status filter
        users = AdminUserService.get_users_with_filters({'kyc_status': 'APPROVED'})
        self.assertEqual(users.count(), 1)  # user2 only
        
        # Test KYC verification filter
        users = AdminUserService.get_users_with_filters({'is_kyc_verified': True})
        self.assertEqual(users.count(), 1)  # user2 only
        
        # Test active status filter
        users = AdminUserService.get_users_with_filters({'is_active': True})
        self.assertEqual(users.count(), 4)  # all users
        
        # Test date range filter
        from datetime import date
        today = date.today()
        users = AdminUserService.get_users_with_filters({'date_joined_from': today})
        self.assertEqual(users.count(), 4)  # all users joined today
        
        # Test multiple filters
        users = AdminUserService.get_users_with_filters({
            'kyc_status': 'PENDING',
            'is_active': True
        })
        self.assertEqual(users.count(), 2)  # user1 and user3
        
        # Test that wallets are prefetched
        user = users.first()
        self.assertTrue(hasattr(user, '_prefetched_objects_cache'))
    
    def test_update_user(self):
        """Test updating user information."""
        update_data = {
            'first_name': 'Johnny',
            'last_name': 'Doe Jr.',
            'phone_number': '+1111111111'
        }
        
        updated_user = AdminUserService.update_user(
            self.user1.id, update_data, self.admin_user
        )
        
        # Check that user was updated
        self.assertEqual(updated_user.first_name, 'Johnny')
        self.assertEqual(updated_user.last_name, 'Doe Jr.')
        self.assertEqual(updated_user.phone_number, '+1111111111')
        
        # Check that original user object was updated
        self.user1.refresh_from_db()
        self.assertEqual(self.user1.first_name, 'Johnny')
        self.assertEqual(self.user1.last_name, 'Doe Jr.')
        self.assertEqual(self.user1.phone_number, '+1111111111')
    
    def test_update_user_not_found(self):
        """Test updating non-existent user."""
        import uuid
        fake_user_id = uuid.uuid4()
        
        with self.assertRaises(ValidationError) as context:
            AdminUserService.update_user(
                fake_user_id, {'first_name': 'Test'}, self.admin_user
            )
        
        self.assertIn('User not found', str(context.exception))
    
    def test_update_user_invalid_field(self):
        """Test updating user with invalid field."""
        update_data = {
            'first_name': 'Johnny',
            'invalid_field': 'invalid_value'
        }
        
        updated_user = AdminUserService.update_user(
            self.user1.id, update_data, self.admin_user
        )
        
        # Should only update valid fields
        self.assertEqual(updated_user.first_name, 'Johnny')
        self.assertFalse(hasattr(updated_user, 'invalid_field'))
    
    def test_block_user(self):
        """Test blocking a user."""
        blocked_user = AdminUserService.block_user(
            self.user1.id, self.admin_user, "Violation of terms"
        )
        
        # Check that user was blocked
        self.assertFalse(blocked_user.is_active)
        
        # Check that original user object was updated
        self.user1.refresh_from_db()
        self.assertFalse(self.user1.is_active)
    
    def test_block_user_not_found(self):
        """Test blocking non-existent user."""
        import uuid
        fake_user_id = uuid.uuid4()
        
        with self.assertRaises(ValidationError) as context:
            AdminUserService.block_user(fake_user_id, self.admin_user, "Test")
        
        self.assertIn('User not found', str(context.exception))
    
    def test_unblock_user(self):
        """Test unblocking a user."""
        # First block the user
        self.user1.is_active = False
        self.user1.save()
        
        unblocked_user = AdminUserService.unblock_user(
            self.user1.id, self.admin_user
        )
        
        # Check that user was unblocked
        self.assertTrue(unblocked_user.is_active)
        
        # Check that original user object was updated
        self.user1.refresh_from_db()
        self.assertTrue(self.user1.is_active)
    
    def test_unblock_user_not_found(self):
        """Test unblocking non-existent user."""
        import uuid
        fake_user_id = uuid.uuid4()
        
        with self.assertRaises(ValidationError) as context:
            AdminUserService.unblock_user(fake_user_id, self.admin_user)
        
        self.assertIn('User not found', str(context.exception))
    
    def test_bulk_user_action_activate(self):
        """Test bulk activating users."""
        # First deactivate some users
        self.user1.is_active = False
        self.user1.save()
        self.user3.is_active = False
        self.user3.save()
        
        user_ids = [self.user1.id, self.user3.id]
        updated_count = AdminUserService.bulk_user_action(
            user_ids, 'activate', self.admin_user, "Bulk activation test"
        )
        
        self.assertEqual(updated_count, 2)
        
        # Check that users were activated
        self.user1.refresh_from_db()
        self.user3.refresh_from_db()
        self.assertTrue(self.user1.is_active)
        self.assertTrue(self.user3.is_active)
    
    def test_bulk_user_action_deactivate(self):
        """Test bulk deactivating users."""
        user_ids = [self.user1.id, self.user2.id]
        updated_count = AdminUserService.bulk_user_action(
            user_ids, 'deactivate', self.admin_user, "Bulk deactivation test"
        )
        
        self.assertEqual(updated_count, 2)
        
        # Check that users were deactivated
        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.assertFalse(self.user1.is_active)
        self.assertFalse(self.user2.is_active)
    
    def test_bulk_user_action_verify_kyc(self):
        """Test bulk KYC verification."""
        user_ids = [self.user1.id, self.user3.id]
        updated_count = AdminUserService.bulk_user_action(
            user_ids, 'verify_kyc', self.admin_user, "Bulk KYC verification"
        )
        
        self.assertEqual(updated_count, 2)
        
        # Check that users were verified
        self.user1.refresh_from_db()
        self.user3.refresh_from_db()
        self.assertTrue(self.user1.is_kyc_verified)
        self.assertTrue(self.user3.is_kyc_verified)
        self.assertEqual(self.user1.kyc_status, 'APPROVED')
        self.assertEqual(self.user3.kyc_status, 'APPROVED')
    
    def test_bulk_user_action_reject_kyc(self):
        """Test bulk KYC rejection."""
        user_ids = [self.user2.id]  # user2 is already verified
        updated_count = AdminUserService.bulk_user_action(
            user_ids, 'reject_kyc', self.admin_user, "Bulk KYC rejection"
        )
        
        self.assertEqual(updated_count, 1)
        
        # Check that user was rejected
        self.user2.refresh_from_db()
        self.assertFalse(self.user2.is_kyc_verified)
        self.assertEqual(self.user2.kyc_status, 'REJECTED')
    
    def test_bulk_user_action_invalid_action(self):
        """Test bulk action with invalid action."""
        user_ids = [self.user1.id]
        
        with self.assertRaises(Exception):
            AdminUserService.bulk_user_action(
                user_ids, 'invalid_action', self.admin_user, "Test"
            )
    
    def test_bulk_user_action_empty_user_ids(self):
        """Test bulk action with empty user IDs."""
        user_ids = []
        updated_count = AdminUserService.bulk_user_action(
            user_ids, 'activate', self.admin_user, "Test"
        )
        
        self.assertEqual(updated_count, 0)
    
    def test_bulk_user_action_performance(self):
        """Test bulk action performance with many users."""
        # Create many users
        users = []
        for i in range(100):
            user = User.objects.create_user(
                username=f'bulkuser{i}',
                email=f'bulkuser{i}@test.com',
                password='testpass123'
            )
            users.append(user)
        
        user_ids = [user.id for user in users]
        
        # Test bulk activation
        import time
        start_time = time.time()
        updated_count = AdminUserService.bulk_user_action(
            user_ids, 'activate', self.admin_user, "Performance test"
        )
        end_time = time.time()
        
        self.assertEqual(updated_count, 100)
        
        # Should complete within reasonable time (less than 1 second)
        self.assertLess(end_time - start_time, 1.0)
    
    def test_user_filters_edge_cases(self):
        """Test user filters with edge cases."""
        # Test with None filters
        users = AdminUserService.get_users_with_filters(None)
        self.assertEqual(users.count(), 4)
        
        # Test with empty filters
        users = AdminUserService.get_users_with_filters({})
        self.assertEqual(users.count(), 4)
        
        # Test with invalid filter values
        users = AdminUserService.get_users_with_filters({'kyc_status': 'INVALID'})
        self.assertEqual(users.count(), 0)
        
        # Test with non-existent date
        from datetime import date
        future_date = date.today() + timedelta(days=365)
        users = AdminUserService.get_users_with_filters({'date_joined_from': future_date})
        self.assertEqual(users.count(), 0)
