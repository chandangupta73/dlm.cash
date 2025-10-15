import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from unittest.mock import patch
from datetime import datetime, timedelta

from app.referral.models import Referral, ReferralConfig, ReferralMilestone
from app.wallet.models import INRWallet, USDTWallet, WalletTransaction
from app.admin_panel.models import AdminActionLog
from app.admin_panel.services import AdminReferralService
from app.admin_panel.permissions import log_admin_action

User = get_user_model()


class AdminReferralServiceTest(TestCase):
    """Test referral management service layer"""
    
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
        
        # Create referral chain: admin -> user1 -> user2 -> user3
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='testpass123'
        )
        
        self.user3 = User.objects.create_user(
            username='user3',
            email='user3@test.com',
            password='testpass123'
        )
        
        # Create wallets
        self.user1_inr_wallet = INRWallet.objects.create(
            user=self.user1,
            balance=Decimal('1000.00')
        )
        
        self.user2_inr_wallet = INRWallet.objects.create(
            user=self.user2,
            balance=Decimal('500.00')
        )
        
        self.user3_inr_wallet = INRWallet.objects.create(
            user=self.user3,
            balance=Decimal('200.00')
        )
        
        # Create referral relationships
        self.referral1 = Referral.objects.create(
            referrer=self.admin_user,
            referred=self.user1,
            level=1,
            commission_rate=Decimal('5.00')
        )
        
        self.referral2 = Referral.objects.create(
            referrer=self.user1,
            referred=self.user2,
            level=2,
            commission_rate=Decimal('3.00')
        )
        
        self.referral3 = Referral.objects.create(
            referrer=self.user2,
            referred=self.user3,
            level=3,
            commission_rate=Decimal('1.00')
        )
        
        # Create referral config
        self.referral_config = ReferralConfig.objects.create(
            max_levels=5,
            level1_commission=Decimal('5.00'),
            level2_commission=Decimal('3.00'),
            level3_commission=Decimal('1.00'),
            is_active=True
        )
        
        # Create referral milestone
        self.milestone = ReferralMilestone.objects.create(
            name='First Investment',
            description='Complete first investment',
            requirement_type='INVESTMENT_COUNT',
            requirement_value=1,
            reward_type='BONUS_AMOUNT',
            reward_value=Decimal('100.00'),
            is_active=True
        )
        
        self.referral_service = AdminReferralService()
    
    def test_get_user_referral_tree(self):
        """Test retrieving user referral tree"""
        tree = self.referral_service.get_user_referral_tree(self.user1.id)
        
        self.assertIsNotNone(tree)
        self.assertEqual(tree['user']['id'], self.user1.id)
        self.assertEqual(len(tree['referrals']), 1)  # user2
        self.assertEqual(tree['referrals'][0]['user']['id'], self.user2.id)
        self.assertEqual(len(tree['referrals'][0]['referrals']), 1)  # user3
        self.assertEqual(tree['referrals'][0]['referrals'][0]['user']['id'], self.user3.id)
    
    def test_get_user_referral_tree_nonexistent_user(self):
        """Test retrieving referral tree for non-existent user"""
        tree = self.referral_service.get_user_referral_tree(99999)
        self.assertIsNone(tree)
    
    def test_get_user_referral_tree_no_referrals(self):
        """Test retrieving referral tree for user with no referrals"""
        tree = self.referral_service.get_user_referral_tree(self.user3.id)
        
        self.assertIsNotNone(tree)
        self.assertEqual(tree['user']['id'], self.user3.id)
        self.assertEqual(len(tree['referrals']), 0)
    
    def test_get_referral_statistics(self):
        """Test retrieving referral statistics"""
        stats = self.referral_service.get_referral_statistics()
        
        self.assertIsNotNone(stats)
        self.assertEqual(stats['total_referrals'], 3)
        self.assertEqual(stats['total_users_with_referrals'], 3)
        self.assertEqual(stats['max_referral_level'], 3)
    
    def test_get_referral_milestones(self):
        """Test retrieving referral milestones"""
        milestones = self.referral_service.get_referral_milestones()
        
        self.assertEqual(len(milestones), 1)
        self.assertEqual(milestones[0].id, self.milestone.id)
        self.assertEqual(milestones[0].name, 'First Investment')
    
    def test_create_referral_milestone(self):
        """Test creating a new referral milestone"""
        milestone_data = {
            'name': 'High Roller',
            'description': 'Invest more than 10000 INR',
            'requirement_type': 'INVESTMENT_AMOUNT',
            'requirement_value': 10000,
            'reward_type': 'BONUS_PERCENTAGE',
            'reward_value': Decimal('2.50'),
            'is_active': True
        }
        
        result = self.referral_service.create_referral_milestone(
            milestone_data=milestone_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check milestone created
        new_milestone = ReferralMilestone.objects.get(name='High Roller')
        self.assertEqual(new_milestone.requirement_type, 'INVESTMENT_AMOUNT')
        self.assertEqual(new_milestone.requirement_value, 10000)
        self.assertEqual(new_milestone.reward_type, 'BONUS_PERCENTAGE')
        self.assertEqual(new_milestone.reward_value, Decimal('2.50'))
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='REFERRAL_MILESTONE_CREATION',
            target_model='ReferralMilestone'
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('High Roller', action_log.action_description)
    
    def test_update_referral_milestone(self):
        """Test updating a referral milestone"""
        update_data = {
            'requirement_value': 15000,
            'reward_value': Decimal('3.00'),
            'is_active': False
        }
        
        result = self.referral_service.update_referral_milestone(
            milestone_id=self.milestone.id,
            update_data=update_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check milestone updated
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.requirement_value, 15000)
        self.assertEqual(self.milestone.reward_value, Decimal('3.00'))
        self.assertFalse(self.milestone.is_active)
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='REFERRAL_MILESTONE_UPDATE',
            target_model='ReferralMilestone'
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('First Investment', action_log.action_description)
    
    def test_delete_referral_milestone(self):
        """Test deleting a referral milestone"""
        result = self.referral_service.delete_referral_milestone(
            milestone_id=self.milestone.id,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check milestone deleted
        self.assertFalse(ReferralMilestone.objects.filter(id=self.milestone.id).exists())
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='REFERRAL_MILESTONE_DELETION',
            target_model='ReferralMilestone'
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('First Investment', action_log.action_description)
    
    def test_adjust_referral_earnings(self):
        """Test manually adjusting referral earnings"""
        result = self.referral_service.adjust_referral_earnings(
            user_id=self.user1.id,
            amount=Decimal('50.00'),
            reason='Manual adjustment for service',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance updated
        self.user1_inr_wallet.refresh_from_db()
        self.assertEqual(self.user1_inr_wallet.balance, Decimal('1050.00'))  # 1000 + 50
        
        # Check transaction log created
        transaction = WalletTransaction.objects.filter(
            user=self.user1,
            transaction_type='referral_bonus',
            amount=Decimal('50.00')
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.description, 'Referral earnings adjustment by admin')
        
        # Check admin action logged
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='REFERRAL_EARNINGS_ADJUSTMENT',
            target_user=self.user1
        ).first()
        self.assertIsNotNone(action_log)
        self.assertIn('Manual adjustment for service', action_log.action_description)
    
    def test_adjust_referral_earnings_negative(self):
        """Test manually adjusting referral earnings (negative adjustment)"""
        result = self.referral_service.adjust_referral_earnings(
            user_id=self.user1.id,
            amount=Decimal('-25.00'),
            reason='Correction for overpayment',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance updated
        self.user1_inr_wallet.refresh_from_db()
        self.assertEqual(self.user1_inr_wallet.balance, Decimal('975.00'))  # 1000 - 25
        
        # Check transaction log created
        transaction = WalletTransaction.objects.filter(
            user=self.user1,
            transaction_type='referral_bonus',
            amount=Decimal('-25.00')
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.description, 'Referral earnings adjustment by admin')
    
    def test_create_referral_milestone_validation_error(self):
        """Test creating referral milestone with validation error"""
        invalid_milestone_data = {
            'name': '',  # Empty name
            'requirement_type': 'INVESTMENT_COUNT',
            'requirement_value': 1,
            'reward_type': 'BONUS_AMOUNT',
            'reward_value': Decimal('100.00')
        }
        
        result = self.referral_service.create_referral_milestone(
            milestone_data=invalid_milestone_data,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('name', result['error'])
    
    def test_update_referral_milestone_validation_error(self):
        """Test updating referral milestone with validation error"""
        invalid_update_data = {
            'requirement_value': -5,  # Negative value
            'reward_value': Decimal('0.00')  # Zero reward
        }
        
        result = self.referral_service.update_referral_milestone(
            milestone_id=self.milestone.id,
            update_data=invalid_update_data,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('requirement_value', result['error'])
    
    def test_adjust_nonexistent_user_referral_earnings(self):
        """Test adjusting referral earnings for non-existent user"""
        result = self.referral_service.adjust_referral_earnings(
            user_id=99999,
            amount=Decimal('50.00'),
            reason='Test',
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_create_nonexistent_referral_milestone(self):
        """Test creating referral milestone with non-existent milestone"""
        result = self.referral_service.update_referral_milestone(
            milestone_id=99999,
            update_data={'name': 'Test'},
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_delete_nonexistent_referral_milestone(self):
        """Test deleting non-existent referral milestone"""
        result = self.referral_service.delete_referral_milestone(
            milestone_id=99999,
            admin_user=self.admin_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_staff_user_cannot_delete_referral_milestone(self):
        """Test staff user cannot delete referral milestone"""
        result = self.referral_service.delete_referral_milestone(
            milestone_id=self.milestone.id,
            admin_user=self.staff_user
        )
        
        self.assertFalse(result['success'])
        self.assertIn('permission denied', result['error'])
    
    def test_referral_milestone_creation_with_notification(self):
        """Test referral milestone creation triggers notification"""
        with patch('app.admin_panel.services.send_referral_milestone_creation_notification') as mock_notify:
            milestone_data = {
                'name': 'Notification Test Milestone',
                'description': 'Test milestone for notifications',
                'requirement_type': 'INVESTMENT_COUNT',
                'requirement_value': 5,
                'reward_type': 'BONUS_AMOUNT',
                'reward_value': Decimal('200.00'),
                'is_active': True
            }
            
            result = self.referral_service.create_referral_milestone(
                milestone_data=milestone_data,
                admin_user=self.admin_user
            )
            
            self.assertTrue(result['success'])
            mock_notify.assert_called_once()


class AdminReferralAPITest(TestCase):
    """Test referral management API endpoints"""
    
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
        
        # Create referral chain
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='testpass123'
        )
        
        self.user1_inr_wallet = INRWallet.objects.create(
            user=self.user1,
            balance=Decimal('1000.00')
        )
        
        self.referral = Referral.objects.create(
            referrer=self.admin_user,
            referred=self.user1,
            level=1,
            commission_rate=Decimal('5.00')
        )
        
        self.referral2 = Referral.objects.create(
            referrer=self.user1,
            referred=self.user2,
            level=2,
            commission_rate=Decimal('3.00')
        )
        
        self.milestone = ReferralMilestone.objects.create(
            name='Test Milestone',
            description='Test milestone description',
            requirement_type='INVESTMENT_COUNT',
            requirement_value=1,
            reward_type='BONUS_AMOUNT',
            reward_value=Decimal('100.00'),
            is_active=True
        )
        
        self.client.force_authenticate(user=self.admin_user)
    
    def test_list_referrals(self):
        """Test listing referrals"""
        url = reverse('admin-referral-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_list_referrals_with_filters(self):
        """Test listing referrals with filters"""
        url = reverse('admin-referral-list')
        response = self.client.get(url, {
            'referrer_id': self.admin_user.id,
            'level': 1
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['level'], 1)
    
    def test_retrieve_referral(self):
        """Test retrieving a specific referral"""
        url = reverse('admin-referral-detail', kwargs={'pk': self.referral.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.referral.id)
        self.assertEqual(response.data['level'], 1)
    
    def test_get_user_referral_tree_api(self):
        """Test getting user referral tree via API"""
        url = reverse('admin-referral-user-tree', kwargs={'pk': self.user1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['id'], self.user1.id)
        self.assertEqual(len(response.data['referrals']), 1)  # user2
        self.assertEqual(response.data['referrals'][0]['user']['id'], self.user2.id)
    
    def test_list_referral_milestones(self):
        """Test listing referral milestones"""
        url = reverse('admin-referral-milestones')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.milestone.id)
    
    def test_create_referral_milestone_api(self):
        """Test creating referral milestone via API"""
        url = reverse('admin-referral-milestones')
        data = {
            'name': 'API Test Milestone',
            'description': 'Test milestone created via API',
            'requirement_type': 'INVESTMENT_AMOUNT',
            'requirement_value': 10000,
            'reward_type': 'BONUS_PERCENTAGE',
            'reward_value': '2.50',
            'is_active': True
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'API Test Milestone')
        self.assertEqual(response.data['requirement_type'], 'INVESTMENT_AMOUNT')
    
    def test_update_referral_milestone_api(self):
        """Test updating referral milestone via API"""
        url = reverse('admin-referral-milestone-detail', kwargs={'pk': self.milestone.id})
        data = {
            'requirement_value': 5,
            'reward_value': '150.00'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['requirement_value'], 5)
        self.assertEqual(response.data['reward_value'], '150.00')
    
    def test_delete_referral_milestone_api(self):
        """Test deleting referral milestone via API"""
        url = reverse('admin-referral-milestone-detail', kwargs={'pk': self.milestone.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_adjust_referral_earnings_api(self):
        """Test adjusting referral earnings via API"""
        url = reverse('admin-referral-adjust-earnings', kwargs={'pk': self.user1.id})
        data = {
            'amount': '75.00',
            'reason': 'API earnings adjustment test'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check wallet balance updated
        self.user1_inr_wallet.refresh_from_db()
        self.assertEqual(self.user1_inr_wallet.balance, Decimal('1075.00'))  # 1000 + 75
    
    def test_create_referral_milestone_validation_error(self):
        """Test creating referral milestone with validation error"""
        url = reverse('admin-referral-milestones')
        data = {
            'name': '',  # Empty name
            'requirement_type': 'INVESTMENT_COUNT',
            'requirement_value': 1
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)
    
    def test_update_referral_milestone_validation_error(self):
        """Test updating referral milestone with validation error"""
        url = reverse('admin-referral-milestone-detail', kwargs={'pk': self.milestone.id})
        data = {
            'requirement_value': -5  # Negative value
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('requirement_value', response.data)
    
    def test_adjust_referral_earnings_validation_error(self):
        """Test adjusting referral earnings with validation error"""
        url = reverse('admin-referral-adjust-earnings', kwargs={'pk': self.user1.id})
        data = {
            'amount': '',  # Empty amount
            'reason': 'Test'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('amount', response.data)
    
    def test_referral_api_permission_denied_non_admin(self):
        """Test referral API access denied for non-admin users"""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('admin-referral-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_referral_api_permission_denied_staff(self):
        """Test referral API access denied for staff users without permission"""
        self.client.force_authenticate(user=self.staff_user)
        
        url = reverse('admin-referral-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_referral_api_unauthorized(self):
        """Test referral API access denied for unauthenticated users"""
        self.client.force_authenticate(user=None)
        
        url = reverse('admin-referral-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_nonexistent_user_referral_tree(self):
        """Test getting referral tree for non-existent user"""
        url = reverse('admin-referral-user-tree', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_adjust_nonexistent_user_referral_earnings(self):
        """Test adjusting referral earnings for non-existent user"""
        url = reverse('admin-referral-adjust-earnings', kwargs={'pk': 99999})
        data = {'amount': '50.00', 'reason': 'Test'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_update_nonexistent_referral_milestone(self):
        """Test updating non-existent referral milestone"""
        url = reverse('admin-referral-milestone-detail', kwargs={'pk': 99999})
        data = {'name': 'Test'}
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_delete_nonexistent_referral_milestone(self):
        """Test deleting non-existent referral milestone"""
        url = reverse('admin-referral-milestone-detail', kwargs={'pk': 99999})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminReferralIntegrationTest(TestCase):
    """Test referral management integration with other modules"""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create referral chain
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='testpass123'
        )
        
        self.user1_inr_wallet = INRWallet.objects.create(
            user=self.user1,
            balance=Decimal('1000.00')
        )
        
        self.user2_inr_wallet = INRWallet.objects.create(
            user=self.user2,
            balance=Decimal('500.00')
        )
        
        self.referral = Referral.objects.create(
            referrer=self.admin_user,
            referred=self.user1,
            level=1,
            commission_rate=Decimal('5.00')
        )
        
        self.referral2 = Referral.objects.create(
            referrer=self.user1,
            referred=self.user2,
            level=2,
            commission_rate=Decimal('3.00')
        )
        
        self.milestone = ReferralMilestone.objects.create(
            name='Integration Test Milestone',
            description='Test milestone for integration tests',
            requirement_type='INVESTMENT_COUNT',
            requirement_value=1,
            reward_type='BONUS_AMOUNT',
            reward_value=Decimal('100.00'),
            is_active=True
        )
        
        self.referral_service = AdminReferralService()
    
    def test_referral_earnings_adjustment_updates_wallet_balance(self):
        """Test that referral earnings adjustment correctly updates wallet balance"""
        initial_balance = self.user1_inr_wallet.balance
        
        result = self.referral_service.adjust_referral_earnings(
            user_id=self.user1.id,
            amount=Decimal('75.00'),
            reason='Integration test adjustment',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check wallet balance updated
        self.user1_inr_wallet.refresh_from_db()
        expected_balance = initial_balance + Decimal('75.00')
        self.assertEqual(self.user1_inr_wallet.balance, expected_balance)
    
    def test_referral_earnings_adjustment_creates_transaction_log(self):
        """Test that referral earnings adjustment creates proper transaction log"""
        result = self.referral_service.adjust_referral_earnings(
            user_id=self.user1.id,
            amount=Decimal('50.00'),
            reason='Transaction log test',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check transaction log exists
        transaction = WalletTransaction.objects.filter(
            user=self.user1,
            transaction_type='referral_bonus',
            amount=Decimal('50.00')
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.admin_user, self.admin_user)
    
    def test_referral_earnings_adjustment_logs_admin_action(self):
        """Test that referral earnings adjustment creates admin action log"""
        result = self.referral_service.adjust_referral_earnings(
            user_id=self.user1.id,
            amount=Decimal('25.00'),
            reason='Admin action log test',
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log exists
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='REFERRAL_EARNINGS_ADJUSTMENT',
            target_user=self.user1
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertEqual(action_log.target_model, 'Referral')
        self.assertIn('Admin action log test', action_log.action_description)
    
    def test_referral_milestone_creation_logs_admin_action(self):
        """Test that referral milestone creation creates admin action log"""
        milestone_data = {
            'name': 'Integration Test Milestone 2',
            'description': 'Second test milestone',
            'requirement_type': 'INVESTMENT_AMOUNT',
            'requirement_value': 5000,
            'reward_type': 'BONUS_PERCENTAGE',
            'reward_value': Decimal('1.50'),
            'is_active': True
        }
        
        result = self.referral_service.create_referral_milestone(
            milestone_data=milestone_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log exists
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='REFERRAL_MILESTONE_CREATION',
            target_model='ReferralMilestone'
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertIn('Integration Test Milestone 2', action_log.action_description)
    
    def test_referral_milestone_update_logs_admin_action(self):
        """Test that referral milestone update creates admin action log"""
        update_data = {
            'requirement_value': 3,
            'reward_value': Decimal('150.00')
        }
        
        result = self.referral_service.update_referral_milestone(
            milestone_id=self.milestone.id,
            update_data=update_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check admin action log exists
        action_log = AdminActionLog.objects.filter(
            admin_user=self.admin_user,
            action_type='REFERRAL_MILESTONE_UPDATE',
            target_model='ReferralMilestone'
        ).first()
        
        self.assertIsNotNone(action_log)
        self.assertIn('Integration Test Milestone', action_log.action_description)
    
    def test_multiple_referral_operations_maintain_consistency(self):
        """Test that multiple referral operations maintain data consistency"""
        initial_balance = self.user1_inr_wallet.balance
        
        # Multiple earnings adjustments
        adjustments = [
            (Decimal('25.00'), 'First adjustment'),
            (Decimal('50.00'), 'Second adjustment'),
            (Decimal('-10.00'), 'Correction adjustment')
        ]
        
        for amount, reason in adjustments:
            result = self.referral_service.adjust_referral_earnings(
                user_id=self.user1.id,
                amount=amount,
                reason=reason,
                admin_user=self.admin_user
            )
            self.assertTrue(result['success'])
        
        # Check final balance
        self.user1_inr_wallet.refresh_from_db()
        expected_balance = initial_balance + Decimal('25.00') + Decimal('50.00') + Decimal('-10.00')
        self.assertEqual(self.user1_inr_wallet.balance, expected_balance)
        
        # Check transaction count
        transaction_count = WalletTransaction.objects.filter(
            user=self.user1,
            transaction_type='referral_bonus'
        ).count()
        self.assertEqual(transaction_count, 3)
    
    def test_referral_tree_structure_maintains_integrity(self):
        """Test that referral tree structure maintains integrity after operations"""
        # Get initial tree structure
        initial_tree = self.referral_service.get_user_referral_tree(self.user1.id)
        initial_referral_count = len(initial_tree['referrals'])
        
        # Perform operations that shouldn't affect tree structure
        result = self.referral_service.adjust_referral_earnings(
            user_id=self.user1.id,
            amount=Decimal('100.00'),
            reason='Tree integrity test',
            admin_user=self.admin_user
        )
        self.assertTrue(result['success'])
        
        # Check tree structure unchanged
        updated_tree = self.referral_service.get_user_referral_tree(self.user1.id)
        updated_referral_count = len(updated_tree['referrals'])
        
        self.assertEqual(initial_referral_count, updated_referral_count)
        self.assertEqual(initial_tree['user']['id'], updated_tree['user']['id'])
    
    def test_referral_milestone_changes_affect_new_users_only(self):
        """Test that referral milestone changes only affect new users"""
        # Update milestone requirement
        update_data = {'requirement_value': 5}
        result = self.referral_service.update_referral_milestone(
            milestone_id=self.milestone.id,
            update_data=update_data,
            admin_user=self.admin_user
        )
        self.assertTrue(result['success'])
        
        # Check milestone updated
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.requirement_value, 5)
        
        # Create new milestone with updated values
        new_milestone_data = {
            'name': 'New Integration Milestone',
            'description': 'New milestone with updated values',
            'requirement_type': 'INVESTMENT_COUNT',
            'requirement_value': 5,  # Uses updated value
            'reward_type': 'BONUS_AMOUNT',
            'reward_value': Decimal('200.00'),
            'is_active': True
        }
        
        result = self.referral_service.create_referral_milestone(
            milestone_data=new_milestone_data,
            admin_user=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        # Check new milestone created with updated values
        new_milestone = ReferralMilestone.objects.get(name='New Integration Milestone')
        self.assertEqual(new_milestone.requirement_value, 5)
