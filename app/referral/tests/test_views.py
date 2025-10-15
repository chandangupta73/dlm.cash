from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from freezegun import freeze_time

from app.referral.models import (
    ReferralConfig, UserReferralProfile, Referral, 
    ReferralEarning, ReferralMilestone
)
from app.referral.tests.factories import (
    UserFactory, ReferralConfigFactory, UserReferralProfileFactory,
    ReferralFactory, ReferralMilestoneFactory, ReferralEarningFactory
)

User = get_user_model()


class ReferralViewsTestCase(TestCase):
    """Test cases for referral API views."""
    
    @classmethod
    def setUpClass(cls):
        """Disable signals during tests."""
        super().setUpClass()
        from app.referral.signals import create_user_referral_profile
        from django.db.models.signals import post_save
        post_save.disconnect(create_user_referral_profile, sender=User)
    
    @classmethod
    def tearDownClass(cls):
        """Re-enable signals after tests."""
        from app.referral.signals import create_user_referral_profile
        from django.db.models.signals import post_save
        post_save.connect(create_user_referral_profile, sender=User)
        super().tearDownClass()

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create users
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()
        self.admin_user = UserFactory(is_staff=True, is_superuser=True)
        
        # Create referral config
        self.config = ReferralConfigFactory(
            max_levels=3,
            level_1_percentage=Decimal('5.0'),
            level_2_percentage=Decimal('3.0'),
            level_3_percentage=Decimal('1.0'),
            is_active=True
        )
        
        # Create referral profiles
        self.profile1 = UserReferralProfileFactory(user=self.user1)
        self.profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        self.profile3 = UserReferralProfileFactory(user=self.user3, referred_by=self.user2)

    def test_referral_profile_view_get_success(self):
        """Test getting user's own referral profile."""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('referral:profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertEqual(data['user'], str(self.user1.id))
        self.assertEqual(data['referral_code'], self.profile1.referral_code)
        self.assertIsNone(data['referred_by'])
        self.assertEqual(data['total_referrals'], 0)
        self.assertEqual(data['total_earnings_inr'], '0.00')
        self.assertEqual(data['total_earnings_usdt'], '0.000000')

    def test_referral_profile_view_get_unauthorized(self):
        """Test getting referral profile without authentication."""
        url = reverse('referral:profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_referral_profile_view_get_other_user(self):
        """Test getting another user's referral profile (should fail)."""
        self.client.force_authenticate(user=self.user2)
        
        url = reverse('referral:profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return user2's own profile, not user1's
        self.assertEqual(response.data['user'], str(self.user2.id))

    def test_referral_tree_view_get_success(self):
        """Test getting user's referral tree."""
        self.client.force_authenticate(user=self.user1)
        
        # Create referral objects
        ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        ReferralFactory(user=self.user2, referred_user=self.user3, level=1, referrer=self.user1)
        ReferralFactory(user=self.user1, referred_user=self.user3, level=2, referrer=None)
        
        url = reverse('referral:tree')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertIn('direct_referrals', data)
        self.assertIn('sub_referrals', data)
        self.assertIn('total_referrals', data)
        self.assertIn('total_earnings', data)
        
        # Check direct referrals
        direct_refs = data['direct_referrals']
        self.assertEqual(len(direct_refs), 1)
        self.assertEqual(direct_refs[0]['user_id'], str(self.user2.id))
        self.assertEqual(direct_refs[0]['level'], 1)
        
        # Check sub-referrals
        sub_refs = data['sub_referrals']
        self.assertEqual(len(sub_refs), 1)
        self.assertEqual(sub_refs[0]['user_id'], str(self.user3.id))
        self.assertEqual(sub_refs[0]['level'], 2)

    def test_referral_tree_view_get_no_referrals(self):
        """Test getting referral tree for user with no referrals."""
        self.client.force_authenticate(user=self.user3)
        
        url = reverse('referral:tree')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertEqual(len(data['direct_referrals']), 0)
        self.assertEqual(len(data['sub_referrals']), 0)
        self.assertEqual(data['total_referrals'], 0)

    def test_referral_earnings_view_get_success(self):
        """Test getting user's referral earnings."""
        self.client.force_authenticate(user=self.user1)
        
        # Clear any existing earnings for this user
        ReferralEarning.objects.filter(referral__user=self.user1).delete()
        
        # Create referral earnings
        referral1 = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        referral2 = ReferralFactory(user=self.user1, referred_user=self.user3, level=2, referrer=None)
        
        earning1 = ReferralEarningFactory(
            referral=referral1,
            level=1,
            amount=Decimal('50.00'),
            currency='INR'
        )
        earning2 = ReferralEarningFactory(
            referral=referral2,
            level=2,
            amount=Decimal('30.00'),
            currency='USDT'
        )
        
        url = reverse('referral:earnings')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertEqual(len(data), 2)
        
        # Check first earning
        self.assertEqual(data[0]['level'], 1)
        self.assertEqual(data[0]['amount'], '50.00')
        self.assertEqual(data[0]['currency'], 'INR')
        
        # Check second earning
        self.assertEqual(data[1]['level'], 2)
        self.assertEqual(data[1]['amount'], '30.00')
        self.assertEqual(data[1]['currency'], 'USDT')

    def test_referral_earnings_view_get_with_filters(self):
        """Test getting referral earnings with filters."""
        self.client.force_authenticate(user=self.user1)
        
        # Clear any existing earnings for this user
        ReferralEarning.objects.filter(referral__user=self.user1).delete()
        
        # Create referral earnings
        referral = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        earning = ReferralEarningFactory(
            referral=referral,
            level=1,
            amount=Decimal('50.00'),
            currency='INR'
        )
        
        # Test with currency filter
        url = reverse('referral:earnings')
        response = self.client.get(url, {'currency': 'INR'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['currency'], 'INR')
        
        # Test with level filter
        response = self.client.get(url, {'level': 1})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['level'], 1)

    def test_referral_earnings_summary_view_get_success(self):
        """Test getting referral earnings summary."""
        self.client.force_authenticate(user=self.user1)
        
        # Create referral earnings
        referral = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        ReferralEarningFactory(
            referral=referral,
            level=1,
            amount=Decimal('50.00'),
            currency='INR'
        )
        ReferralEarningFactory(
            referral=referral,
            level=1,
            amount=Decimal('30.00'),
            currency='USDT'
        )
        
        url = reverse('referral:earnings-summary')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertIn('total_earnings_inr', data)
        self.assertIn('total_earnings_usdt', data)
        self.assertIn('total_earnings', data)
        self.assertIn('total_referrals', data)
        self.assertIn('last_earning_date', data)

    def test_validate_referral_code_view_post_success(self):
        """Test validating a valid referral code."""
        self.client.force_authenticate(user=self.user2)
        
        url = reverse('referral:validate-code')
        data = {'referral_code': self.profile1.referral_code}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertTrue(data['is_valid'])
        self.assertEqual(data['referrer_id'], self.user1.id)
        self.assertEqual(data['referrer_email'], self.user1.email)

    def test_validate_referral_code_view_post_invalid(self):
        """Test validating an invalid referral code."""
        self.client.force_authenticate(user=self.user2)
        
        url = reverse('referral:validate-code')
        data = {'referral_code': 'INVALID_CODE'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertFalse(data['is_valid'])
        self.assertIsNone(data['referrer_id'])
        self.assertIsNone(data['referrer_email'])

    def test_validate_referral_code_view_post_own_code(self):
        """Test validating user's own referral code (should fail)."""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('referral:validate-code')
        data = {'referral_code': self.profile1.referral_code}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertFalse(data['is_valid'])
        self.assertIsNone(data['referrer_id'])

    def test_validate_referral_code_view_post_missing_code(self):
        """Test validating referral code with missing data."""
        self.client.force_authenticate(user=self.user2)
        
        url = reverse('referral:validate-code')
        response = self.client.post(url, {})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AdminReferralViewsTestCase(TestCase):
    """Test cases for admin referral API views."""
    
    @classmethod
    def setUpClass(cls):
        """Disable signals during tests."""
        super().setUpClass()
        from app.referral.signals import create_user_referral_profile
        from django.db.models.signals import post_save
        post_save.disconnect(create_user_referral_profile, sender=User)
    
    @classmethod
    def tearDownClass(cls):
        """Re-enable signals after tests."""
        from app.referral.signals import create_user_referral_profile
        from django.db.models.signals import post_save
        post_save.connect(create_user_referral_profile, sender=User)
        super().tearDownClass()

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create users
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()
        self.admin_user = UserFactory(is_staff=True, is_superuser=True)
        self.regular_user = UserFactory()
        
        # Create referral config
        self.config = ReferralConfigFactory(
            max_levels=3,
            level_1_percentage=Decimal('5.0'),
            level_2_percentage=Decimal('3.0'),
            level_3_percentage=Decimal('1.0'),
            is_active=True
        )
        
        # Create referral profiles and referrals
        self.profile1 = UserReferralProfileFactory(user=self.user1)
        self.profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        self.profile3 = UserReferralProfileFactory(user=self.user3, referred_by=self.user2)
        
        self.referral1 = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        self.referral2 = ReferralFactory(user=self.user2, referred_user=self.user3, level=1, referrer=self.user1)

    def test_admin_referral_list_view_get_success(self):
        """Test admin getting referral list."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('referral:admin-referral-list-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertGreaterEqual(data['count'], 2)

    def test_admin_referral_list_view_get_unauthorized(self):
        """Test getting referral list without admin privileges."""
        self.client.force_authenticate(user=self.regular_user)
        
        url = reverse('referral:admin-referral-list-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_referral_list_view_get_with_filters(self):
        """Test admin getting referral list with filters."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('referral:admin-referral-list-list')
        
        # Test with user filter
        response = self.client.get(url, {'user': self.user1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test with level filter
        response = self.client.get(url, {'level': 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test with date filter
        response = self.client.get(url, {'created_after': '2023-01-01'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_referral_earning_list_view_get_success(self):
        """Test admin getting referral earnings list."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create referral earnings
        earning = ReferralEarningFactory(
            referral=self.referral1,
            level=1,
            amount=Decimal('50.00'),
            currency='INR'
        )
        
        url = reverse('referral:admin-earning-list-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertGreaterEqual(data['count'], 1)

    def test_admin_milestone_list_view_get_success(self):
        """Test admin getting milestone list."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create milestones
        milestone1 = ReferralMilestoneFactory(
            name="10 Referrals",
            condition_type="total_referrals",
            condition_value=10,
            bonus_amount=Decimal('50.00'),
            currency="INR"
        )
        milestone2 = ReferralMilestoneFactory(
            name="500 INR Earnings",
            condition_type="total_earnings",
            condition_value=Decimal('500.00'),
            bonus_amount=Decimal('25.00'),
            currency="USDT"
        )
        
        url = reverse('referral:admin-milestone-list-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertGreaterEqual(data['count'], 2)

    def test_admin_milestone_detail_view_get_success(self):
        """Test admin getting milestone detail."""
        self.client.force_authenticate(user=self.admin_user)
        
        milestone = ReferralMilestoneFactory(
            name="Test Milestone",
            condition_type="total_referrals",
            condition_value=10,
            bonus_amount=Decimal('50.00'),
            currency="INR"
        )
        
        url = reverse('referral:admin-milestone-detail-detail', kwargs={'pk': milestone.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertEqual(data['name'], "Test Milestone")
        self.assertEqual(data['condition_type'], "total_referrals")
        self.assertEqual(Decimal(data['condition_value']), Decimal('10.00'))
        self.assertEqual(Decimal(data['bonus_amount']), Decimal('50.00'))
        self.assertEqual(data['currency'], "INR")

    def test_admin_milestone_detail_view_post_create_success(self):
        """Test admin creating a new milestone."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('referral:admin-milestone-detail-list')
        data = {
            'name': 'New Milestone',
            'condition_type': 'total_referrals',
            'condition_value': '15.00',
            'bonus_amount': '75.00',
            'currency': 'INR',
            'is_active': True
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check milestone was created
        milestone = ReferralMilestone.objects.get(name='New Milestone')
        self.assertEqual(milestone.condition_value, 15)
        self.assertEqual(milestone.bonus_amount, Decimal('75.00'))

    def test_admin_milestone_detail_view_post_update_success(self):
        """Test admin updating an existing milestone."""
        self.client.force_authenticate(user=self.admin_user)
        
        milestone = ReferralMilestoneFactory(
            name="Update Test",
            condition_type="total_referrals",
            condition_value=10,
            bonus_amount=Decimal('50.00'),
            currency="INR"
        )
        
        url = reverse('referral:admin-milestone-detail-detail', kwargs={'pk': milestone.pk})
        data = {
            'name': 'Updated Milestone',
            'condition_type': 'total_earnings',
            'condition_value': '1000.00',
            'bonus_amount': '100.00',
            'currency': 'USDT',
            'is_active': True
        }
        response = self.client.put(url, data, content_type='application/json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check milestone was updated
        milestone.refresh_from_db()
        self.assertEqual(milestone.name, 'Updated Milestone')
        self.assertEqual(milestone.condition_type, 'total_earnings')
        self.assertEqual(milestone.condition_value, 1000)

    def test_admin_milestone_detail_view_post_invalid_data(self):
        """Test admin creating milestone with invalid data."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('referral:admin-milestone-detail-list')
        data = {
            'name': '',  # Invalid: empty name
            'condition_type': 'invalid_type',  # Invalid condition type
            'condition_value': -5,  # Invalid: negative value
            'bonus_amount': 'invalid_amount',  # Invalid amount
            'currency': 'INVALID'  # Invalid currency
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_referral_config_view_get_success(self):
        """Test admin getting referral configuration."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('referral:admin-config-config')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertIn('max_levels', data)
        self.assertIn('level_1_percentage', data)
        self.assertIn('level_2_percentage', data)
        self.assertIn('level_3_percentage', data)
        self.assertIn('is_active', data)

    def test_admin_referral_config_view_post_update_success(self):
        """Test admin updating referral configuration."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('referral:admin-config-config')
        data = {
            'max_levels': 5,
            'level_1_percentage': '7.0',
            'level_2_percentage': '5.0',
            'level_3_percentage': '3.0',
            'is_active': True
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check config was updated
        config = ReferralConfig.objects.get(is_active=True)
        self.assertEqual(config.max_levels, 5)
        self.assertEqual(config.level_1_percentage, Decimal('7.0'))
        self.assertEqual(config.level_3_percentage, Decimal('3.0'))

    def test_admin_referral_stats_view_get_success(self):
        """Test admin getting referral statistics."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('referral:admin-stats-stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertIn('total_users', data)
        self.assertIn('total_referrals', data)
        self.assertIn('total_earnings', data)
        self.assertIn('active_milestones', data)


class UtilityViewsTestCase(TestCase):
    """Test cases for utility views."""
    
    @classmethod
    def setUpClass(cls):
        """Disable signals during tests."""
        super().setUpClass()
        from app.referral.signals import create_user_referral_profile
        from django.db.models.signals import post_save
        post_save.disconnect(create_user_referral_profile, sender=User)
    
    @classmethod
    def tearDownClass(cls):
        """Re-enable signals after tests."""
        from app.referral.signals import create_user_referral_profile
        from django.db.models.signals import post_save
        post_save.connect(create_user_referral_profile, sender=User)
        super().tearDownClass()

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create users
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.admin_user = UserFactory(is_staff=True, is_superuser=True)
        
        # Create referral config
        self.config = ReferralConfigFactory(
            max_levels=3,
            level_1_percentage=Decimal('5.0'),
            level_2_percentage=Decimal('3.0'),
            level_3_percentage=Decimal('1.0'),
            is_active=True
        )

    def test_process_referral_bonus_view_post_success(self):
        """Test manually processing referral bonus."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create referral chain
        profile1 = UserReferralProfileFactory(user=self.user1)
        profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        
        referral = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        
        url = reverse('referral:process-bonus')
        data = {
            'investment_id': 123,
            'amount': '1000.00',
            'currency': 'INR',
            'user_id': self.user2.id
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertIn('success', data)
        self.assertIn('message', data)

    def test_process_referral_bonus_view_post_unauthorized(self):
        """Test processing referral bonus without admin privileges."""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('referral:process-bonus')
        data = {'investment_id': 123, 'amount': '1000.00', 'currency': 'INR', 'user_id': self.user2.id}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_check_user_milestones_view_post_success(self):
        """Test manually checking user milestones."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create user profile with stats
        profile = UserReferralProfileFactory(
            user=self.user1,
            total_referrals=15
        )
        
        # Create milestone
        milestone = ReferralMilestoneFactory(
            name="15 Referrals",
            condition_type="total_referrals",
            condition_value=15,
            bonus_amount=Decimal('50.00'),
            currency="INR",
            is_active=True
        )
        
        url = reverse('referral:check-milestones')
        data = {'user_id': self.user1.id}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertIn('success', data)
        self.assertIn('message', data)
        self.assertIn('triggered_milestones', data)

    def test_check_user_milestones_view_post_unauthorized(self):
        """Test checking user milestones without admin privileges."""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('referral:check-milestones')
        data = {'user_id': self.user1.id}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
