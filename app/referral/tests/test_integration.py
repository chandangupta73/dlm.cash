from decimal import Decimal
from django.test import TestCase, TransactionTestCase
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
from app.referral.services import ReferralService
from app.referral.tests.factories import (
    UserFactory, ReferralConfigFactory, UserReferralProfileFactory,
    ReferralFactory, ReferralMilestoneFactory, ReferralEarningFactory
)

User = get_user_model()


class ReferralSystemIntegrationTestCase(TransactionTestCase):
    """Integration tests for the complete referral system workflow."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create users
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()
        self.user4 = UserFactory()
        self.admin_user = UserFactory(is_staff=True, is_superuser=True)
        
        # Create referral config
        self.config = ReferralConfigFactory(
            max_levels=3,
            level_1_percentage=Decimal('5.0'),
            level_2_percentage=Decimal('3.0'),
            level_3_percentage=Decimal('1.0'),
            is_active=True
        )

    def test_complete_referral_workflow(self):
        """Test the complete referral workflow from user registration to earnings."""
        # Step 1: User1 registers (gets referral profile automatically)
        profile1 = UserReferralProfile.objects.get(user=self.user1)
        self.assertIsNotNone(profile1.referral_code)
        self.assertIsNone(profile1.referred_by)
        
        # Step 2: User2 registers using User1's referral code
        ReferralService.create_referral_chain(self.user2, profile1.referral_code)
        profile2 = UserReferralProfile.objects.get(user=self.user2)
        self.assertEqual(profile2.referred_by, self.user1)
        
        # Step 3: User3 registers using User2's referral code
        ReferralService.create_referral_chain(self.user3, profile2.referral_code)
        profile3 = UserReferralProfile.objects.get(user=self.user3)
        self.assertEqual(profile3.referred_by, self.user2)
        
        # Step 4: User4 registers using User3's referral code
        ReferralService.create_referral_chain(self.user4, profile3.referral_code)
        profile4 = UserReferralProfile.objects.get(user=self.user4)
        self.assertEqual(profile4.referred_by, self.user3)
        
        # Step 5: Check referral chain structure
        # User1 should have referrals at levels 1, 2, and 3
        user1_referrals = Referral.objects.filter(user=self.user1)
        self.assertEqual(user1_referrals.count(), 3)
        
        level1_ref = user1_referrals.get(level=1)
        self.assertEqual(level1_ref.referred_user, self.user2)
        
        level2_ref = user1_referrals.get(level=2)
        self.assertEqual(level2_ref.referred_user, self.user3)
        
        level3_ref = user1_referrals.get(level=3)
        self.assertEqual(level3_ref.referred_user, self.user4)
        
        # Step 6: Simulate investment by User4 (should trigger referral bonuses)
        investment = MagicMock()
        investment.amount = Decimal('1000.00')
        investment.currency = 'INR'
        investment.id = 123
        
        # Mock wallet crediting
        with patch.object(ReferralEarning, 'credit_to_wallet') as mock_credit:
            mock_credit.return_value = True
            
            result = ReferralService.process_investment_referral_bonus(investment)
            self.assertTrue(result)
            
            # Check that earnings were created for all levels
            earnings = ReferralEarning.objects.filter(investment_id=123)
            self.assertEqual(earnings.count(), 3)
            
            # Level 1: User3 gets 5% of 1000 = 50 INR
            level1_earning = earnings.get(level=1)
            self.assertEqual(level1_earning.amount, Decimal('50.00'))
            self.assertEqual(level1_earning.currency, 'INR')
            self.assertEqual(level1_earning.referral.referred_user, self.user4)
            
            # Level 2: User2 gets 3% of 1000 = 30 INR
            level2_earning = earnings.get(level=2)
            self.assertEqual(level2_earning.amount, Decimal('30.00'))
            self.assertEqual(level2_earning.currency, 'INR')
            self.assertEqual(level2_earning.referral.referred_user, self.user4)
            
            # Level 3: User1 gets 1% of 1000 = 10 INR
            level3_earning = earnings.get(level=3)
            self.assertEqual(level3_earning.amount, Decimal('10.00'))
            self.assertEqual(level3_earning.currency, 'INR')
            self.assertEqual(level3_earning.referral.referred_user, self.user4)
        
        # Step 7: Check that user stats were updated
        profile1.refresh_from_db()
        profile2.refresh_from_db()
        profile3.refresh_from_db()
        
        self.assertEqual(profile1.total_referrals, 3)
        self.assertEqual(profile1.total_earnings_inr, Decimal('10.00'))
        
        self.assertEqual(profile2.total_referrals, 2)
        self.assertEqual(profile2.total_earnings_inr, Decimal('30.00'))
        
        self.assertEqual(profile3.total_referrals, 1)
        self.assertEqual(profile3.total_earnings_inr, Decimal('50.00'))

    def test_milestone_integration(self):
        """Test milestone system integration with referral earnings."""
        # Create milestones
        milestone1 = ReferralMilestoneFactory(
            name="5 Referrals",
            condition_type="total_referrals",
            condition_value=5,
            bonus_amount=Decimal('100.00'),
            currency="INR",
            is_active=True
        )
        
        milestone2 = ReferralMilestoneFactory(
            name="100 INR Earnings",
            condition_type="total_earnings",
            condition_value=Decimal('100.00'),
            bonus_amount=Decimal('50.00'),
            currency="USDT",
            is_active=True
        )
        
        # Create referral chain
        profile1 = UserReferralProfileFactory(user=self.user1)
        profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        profile3 = UserReferralProfileFactory(user=self.user3, referred_by=self.user1)
        profile4 = UserReferralProfileFactory(user=self.user4, referred_by=self.user1)
        profile5 = UserReferralProfileFactory(user=self.user5, referred_by=self.user1)
        
        # Create referrals
        ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        ReferralFactory(user=self.user1, referred_user=self.user3, level=1, referrer=None)
        ReferralFactory(user=self.user1, referred_user=self.user4, level=1, referrer=None)
        ReferralFactory(user=self.user1, referred_user=self.user5, level=1, referrer=None)
        
        # Update profile stats
        profile1.total_referrals = 5
        profile1.save()
        
        # Check milestones
        triggered_milestones = ReferralService.check_milestones(self.user1)
        self.assertEqual(len(triggered_milestones), 1)
        self.assertIn(milestone1, triggered_milestones)
        
        # Create earnings to trigger second milestone
        referral = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        earning = ReferralEarningFactory(
            referral=referral,
            level=1,
            amount=Decimal('100.00'),
            currency='INR'
        )
        
        # Check milestones again
        triggered_milestones = ReferralService.check_milestones(self.user1)
        self.assertEqual(len(triggered_milestones), 2)
        self.assertIn(milestone1, triggered_milestones)
        self.assertIn(milestone2, triggered_milestones)

    def test_api_integration_workflow(self):
        """Test complete API workflow for referral system."""
        # Step 1: Get user's referral profile
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('referral:profile')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        profile_data = response.data
        self.assertEqual(profile_data['user'], self.user1.id)
        self.assertIsNotNone(profile_data['referral_code'])
        
        # Step 2: Validate referral code
        url = reverse('referral:validate-code')
        data = {'referral_code': profile_data['referral_code']}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        validation_data = response.data
        self.assertFalse(validation_data['is_valid'])  # User can't refer themselves
        self.assertIsNone(validation_data['referrer_id'])
        
        # Step 3: Create referral chain via service
        ReferralService.create_referral_chain(self.user2, profile_data['referral_code'])
        
        # Step 4: Get referral tree
        url = reverse('referral:tree')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        tree_data = response.data
        self.assertEqual(len(tree_data['direct_referrals']), 1)
        self.assertEqual(tree_data['direct_referrals'][0]['user_id'], self.user2.id)
        
        # Step 5: Get referral earnings (should be empty initially)
        url = reverse('referral:earnings')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        
        # Step 6: Get earnings summary
        url = reverse('referral:earnings-summary')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        summary_data = response.data
        self.assertEqual(summary_data['total_referrals'], 1)
        self.assertEqual(summary_data['total_earnings_inr'], '0.00')

    def test_admin_api_integration(self):
        """Test admin API integration workflow."""
        # Step 1: Admin gets referral list
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('referral:admin-referral-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 2: Admin creates milestone
        url = reverse('referral:admin-milestone-detail')
        data = {
            'name': 'Integration Test Milestone',
            'condition_type': 'total_referrals',
            'condition_value': 3,
            'bonus_amount': '75.00',
            'currency': 'INR',
            'is_active': True
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        milestone_id = response.data['id']
        
        # Step 3: Admin gets milestone detail
        url = reverse('referral:admin-milestone-detail', kwargs={'pk': milestone_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 4: Admin updates milestone
        data['bonus_amount'] = '100.00'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 5: Admin gets referral config
        url = reverse('referral:admin-config-config')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 6: Admin updates referral config
        data = {
            'max_levels': 5,
            'level_1_percentage': '7.0',
            'level_2_percentage': '5.0',
            'level_3_percentage': '3.0',
            'level_4_percentage': '2.0',
            'level_5_percentage': '1.0',
            'is_active': True
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 7: Admin gets referral stats
        url = reverse('referral:admin-stats-stats')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_error_handling_integration(self):
        """Test error handling in the referral system."""
        # Test invalid referral code
        result = ReferralService.create_referral_chain(self.user2, "INVALID_CODE")
        self.assertTrue(result)  # Should succeed but create no referrals
        
        profile = UserReferralProfile.objects.get(user=self.user2)
        self.assertIsNone(profile.referred_by)
        
        # Test referral chain with no active config
        with patch.object(ReferralConfig, 'get_active_config') as mock_get_config:
            mock_get_config.return_value = None
            
            investment = MagicMock()
            investment.amount = Decimal('1000.00')
            investment.currency = 'INR'
            
            result = ReferralService.process_investment_referral_bonus(investment)
            self.assertFalse(result)
        
        # Test milestone with invalid condition
        milestone = ReferralMilestoneFactory(
            name="Invalid Milestone",
            condition_type="invalid_type",
            condition_value=10,
            bonus_amount=Decimal('50.00'),
            currency="INR",
            is_active=True
        )
        
        profile = UserReferralProfileFactory(user=self.user1, total_referrals=15)
        triggered_milestones = ReferralService.check_milestones(self.user1)
        self.assertEqual(len(triggered_milestones), 0)

    def test_performance_integration(self):
        """Test performance aspects of the referral system."""
        # Create many users and referrals
        users = []
        for i in range(100):
            user = UserFactory()
            users.append(user)
            UserReferralProfileFactory(user=user)
        
        # Create referral chain
        for i in range(1, len(users)):
            ReferralService.create_referral_chain(users[i], users[i-1].referralprofile.referral_code)
        
        # Test referral tree generation performance
        start_time = timezone.now()
        tree = ReferralService.get_user_referral_tree(users[0], max_levels=3)
        end_time = timezone.now()
        
        # Should complete within reasonable time
        duration = (end_time - start_time).total_seconds()
        self.assertLess(duration, 1.0)  # Should complete in less than 1 second
        
        # Test earnings calculation performance
        start_time = timezone.now()
        earnings = ReferralService.get_referral_earnings(users[0])
        end_time = timezone.now()
        
        duration = (end_time - start_time).total_seconds()
        self.assertLess(duration, 1.0)

    def test_concurrent_operations_integration(self):
        """Test concurrent operations in the referral system."""
        import threading
        import time
        
        # Create users
        users = [UserFactory() for _ in range(10)]
        for user in users:
            UserReferralProfileFactory(user=user)
        
        # Create referral chain
        for i in range(1, len(users)):
            ReferralService.create_referral_chain(users[i], users[i-1].referralprofile.referral_code)
        
        # Simulate concurrent investment processing
        def process_investment(user_id):
            investment = MagicMock()
            investment.amount = Decimal('100.00')
            investment.currency = 'INR'
            investment.id = user_id
            
            with patch.object(ReferralEarning, 'credit_to_wallet') as mock_credit:
                mock_credit.return_value = True
                ReferralService.process_investment_referral_bonus(investment)
        
        # Start concurrent threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=process_investment, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check that all operations completed successfully
        total_earnings = ReferralEarning.objects.count()
        self.assertGreater(total_earnings, 0)

    def test_data_consistency_integration(self):
        """Test data consistency across the referral system."""
        # Create referral chain
        profile1 = UserReferralProfileFactory(user=self.user1)
        profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        profile3 = UserReferralProfileFactory(user=self.user3, referred_by=self.user2)
        
        # Create referrals
        referral1 = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        referral2 = ReferralFactory(user=self.user2, referred_user=self.user3, level=1, referrer=self.user1)
        referral3 = ReferralFactory(user=self.user1, referred_user=self.user3, level=2, referrer=None)
        
        # Create earnings
        earning1 = ReferralEarningFactory(
            referral=referral1,
            level=1,
            amount=Decimal('50.00'),
            currency='INR'
        )
        earning2 = ReferralEarningFactory(
            referral=referral3,
            level=2,
            amount=Decimal('30.00'),
            currency='INR'
        )
        
        # Check data consistency
        profile1.refresh_from_db()
        profile2.refresh_from_db()
        
        # User1 should have 2 referrals and 80 INR earnings
        self.assertEqual(profile1.total_referrals, 2)
        self.assertEqual(profile1.total_earnings_inr, Decimal('80.00'))
        
        # User2 should have 1 referral and 50 INR earnings
        self.assertEqual(profile2.total_referrals, 1)
        self.assertEqual(profile2.total_earnings_inr, Decimal('50.00'))
        
        # Verify referral relationships
        self.assertEqual(referral1.user, self.user1)
        self.assertEqual(referral1.referred_user, self.user2)
        self.assertEqual(referral1.level, 1)
        
        self.assertEqual(referral2.user, self.user2)
        self.assertEqual(referral2.referred_user, self.user3)
        self.assertEqual(referral2.level, 1)
        self.assertEqual(referral2.referrer, self.user1)
        
        self.assertEqual(referral3.user, self.user1)
        self.assertEqual(referral3.referred_user, self.user3)
        self.assertEqual(referral3.level, 2)
        
        # Verify earnings
        self.assertEqual(earning1.amount, Decimal('50.00'))
        self.assertEqual(earning1.currency, 'INR')
        self.assertEqual(earning1.level, 1)
        
        self.assertEqual(earning2.amount, Decimal('30.00'))
        self.assertEqual(earning2.currency, 'INR')
        self.assertEqual(earning2.level, 2)

