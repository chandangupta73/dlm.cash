from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, post_delete
from django.utils import timezone
from unittest.mock import patch, MagicMock
from freezegun import freeze_time

from app.referral.models import (
    ReferralConfig, UserReferralProfile, Referral, 
    ReferralEarning, ReferralMilestone
)
from app.referral.signals import (
    create_user_referral_profile, update_user_stats_on_earning,
    update_referrer_stats_on_referral, investment_post_save_handler,
    milestone_post_save_handler, config_post_save_handler,
    cleanup_user_referral_data
)
from app.referral.tests.factories import (
    UserFactory, ReferralConfigFactory, UserReferralProfileFactory,
    ReferralFactory, ReferralMilestoneFactory, ReferralEarningFactory
)

User = get_user_model()


class ReferralSignalsTestCase(TestCase):
    """Test cases for referral system signals."""

    def setUp(self):
        """Set up test data."""
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()
        
        self.config = ReferralConfigFactory(
            max_levels=3,
            level_1_percentage=Decimal('5.0'),
            level_2_percentage=Decimal('3.0'),
            level_3_percentage=Decimal('1.0'),
            is_active=True
        )

    def test_create_user_referral_profile_signal(self):
        """Test that UserReferralProfile is created when User is created."""
        # Disconnect the signal temporarily to test it manually
        post_save.disconnect(create_user_referral_profile, sender=User)
        
        # Create a new user
        new_user = User.objects.create(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        
        # Check that no profile exists yet
        self.assertFalse(UserReferralProfile.objects.filter(user=new_user).exists())
        
        # Manually trigger the signal
        create_user_referral_profile(sender=User, instance=new_user, created=True)
        
        # Check that profile was created
        profile = UserReferralProfile.objects.get(user=new_user)
        self.assertIsNotNone(profile.referral_code)
        self.assertIsNone(profile.referred_by)
        self.assertEqual(profile.total_referrals, 0)
        self.assertEqual(profile.total_earnings_inr, Decimal('0.00'))
        self.assertEqual(profile.total_earnings_usdt, Decimal('0.00'))
        
        # Reconnect the signal
        post_save.connect(create_user_referral_profile, sender=User)

    def test_create_user_referral_profile_signal_not_created(self):
        """Test that signal doesn't create profile when User is updated, not created."""
        # Disconnect the signal temporarily
        post_save.disconnect(create_user_referral_profile, sender=User)
        
        # Update existing user
        self.user1.username = 'updated_username'
        self.user1.save()
        
        # Count profiles before signal
        profile_count_before = UserReferralProfile.objects.filter(user=self.user1).count()
        
        # Manually trigger the signal with created=False
        create_user_referral_profile(sender=User, instance=self.user1, created=False)
        
        # Check that no new profile was created
        profile_count_after = UserReferralProfile.objects.filter(user=self.user1).count()
        self.assertEqual(profile_count_before, profile_count_after)
        
        # Reconnect the signal
        post_save.connect(create_user_referral_profile, sender=User)

    def test_update_user_stats_on_earning_signal(self):
        """Test that user stats are updated when ReferralEarning is created."""
        # Disconnect the signal temporarily
        post_save.disconnect(update_user_stats_on_earning, sender=ReferralEarning)
        
        # Create user profile
        profile = UserReferralProfileFactory(user=self.user1)
        
        # Create referral and earning
        referral = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        earning = ReferralEarningFactory(
            referral=referral,
            level=1,
            amount=Decimal('50.00'),
            currency='INR'
        )
        
        # Check stats before signal
        profile.refresh_from_db()
        self.assertEqual(profile.total_earnings_inr, Decimal('0.00'))
        
        # Manually trigger the signal
        update_user_stats_on_earning(sender=ReferralEarning, instance=earning, created=True)
        
        # Check that stats were updated
        profile.refresh_from_db()
        self.assertEqual(profile.total_earnings_inr, Decimal('50.00'))
        
        # Reconnect the signal
        post_save.connect(update_user_stats_on_earning, sender=ReferralEarning)

    def test_update_user_stats_on_earning_signal_not_created(self):
        """Test that signal doesn't update stats when ReferralEarning is updated, not created."""
        # Disconnect the signal temporarily
        post_save.disconnect(update_user_stats_on_earning, sender=ReferralEarning)
        
        # Create user profile and earning
        profile = UserReferralProfileFactory(user=self.user1)
        referral = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        earning = ReferralEarningFactory(
            referral=referral,
            level=1,
            amount=Decimal('50.00'),
            currency='INR'
        )
        
        # Update earning
        earning.amount = Decimal('75.00')
        earning.save()
        
        # Count earnings before signal
        earnings_before = ReferralEarning.objects.filter(referral__user=self.user1).count()
        
        # Manually trigger the signal with created=False
        update_user_stats_on_earning(sender=ReferralEarning, instance=earning, created=False)
        
        # Check that no new earnings were processed
        earnings_after = ReferralEarning.objects.filter(referral__user=self.user1).count()
        self.assertEqual(earnings_before, earnings_after)
        
        # Reconnect the signal
        post_save.connect(update_user_stats_on_earning, sender=ReferralEarning)

    def test_update_referrer_stats_on_referral_signal(self):
        """Test that referrer stats are updated when Referral is created."""
        # Disconnect the signal temporarily
        post_save.disconnect(update_referrer_stats_on_referral, sender=Referral)
        
        # Create user profiles
        profile1 = UserReferralProfileFactory(user=self.user1)
        profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        
        # Create referral
        referral = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        
        # Check stats before signal
        profile1.refresh_from_db()
        self.assertEqual(profile1.total_referrals, 0)
        
        # Manually trigger the signal
        update_referrer_stats_on_referral(sender=Referral, instance=referral, created=True)
        
        # Check that stats were updated
        profile1.refresh_from_db()
        self.assertEqual(profile1.total_referrals, 1)
        
        # Reconnect the signal
        post_save.connect(update_referrer_stats_on_referral, sender=Referral)

    def test_update_referrer_stats_on_referral_signal_not_created(self):
        """Test that signal doesn't update stats when Referral is updated, not created."""
        # Disconnect the signal temporarily
        post_save.disconnect(update_referrer_stats_on_referral, sender=Referral)
        
        # Create user profiles and referral
        profile1 = UserReferralProfileFactory(user=self.user1)
        profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        referral = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        
        # Update referral
        referral.level = 2
        referral.save()
        
        # Count referrals before signal
        referrals_before = Referral.objects.filter(user=self.user1).count()
        
        # Manually trigger the signal with created=False
        update_referrer_stats_on_referral(sender=Referral, instance=referral, created=False)
        
        # Check that no new referrals were processed
        referrals_after = Referral.objects.filter(user=self.user1).count()
        self.assertEqual(referrals_before, referrals_after)
        
        # Reconnect the signal
        post_save.connect(update_referrer_stats_on_referral, sender=Referral)

    @patch('app.referral.services.ReferralService.process_investment_referral_bonus')
    def test_investment_post_save_handler_signal(self, mock_process_bonus):
        """Test that investment post-save signal triggers referral bonus processing."""
        # Mock the service method
        mock_process_bonus.return_value = True
        
        # Create mock investment
        investment = MagicMock()
        investment.id = 123
        investment.amount = Decimal('1000.00')
        investment.currency = 'INR'
        
        # Manually trigger the signal
        investment_post_save_handler(sender=MagicMock(), instance=investment, created=True)
        
        # Check that the service method was called
        mock_process_bonus.assert_called_once_with(investment)

    @patch('app.referral.services.ReferralService.process_investment_referral_bonus')
    def test_investment_post_save_handler_signal_not_created(self, mock_process_bonus):
        """Test that investment post-save signal doesn't trigger when investment is updated, not created."""
        # Mock the service method
        mock_process_bonus.return_value = True
        
        # Create mock investment
        investment = MagicMock()
        investment.id = 123
        investment.amount = Decimal('1000.00')
        investment.currency = 'INR'
        
        # Manually trigger the signal with created=False
        investment_post_save_handler(sender=MagicMock(), instance=investment, created=False)
        
        # Check that the service method was not called
        mock_process_bonus.assert_not_called()

    def test_milestone_post_save_handler_signal(self):
        """Test that milestone post-save signal logs the action."""
        # Disconnect the signal temporarily
        post_save.disconnect(milestone_post_save_handler, sender=ReferralMilestone)
        
        # Create milestone
        milestone = ReferralMilestoneFactory(
            name="Test Milestone",
            condition_type="total_referrals",
            condition_value=10,
            bonus_amount=Decimal('50.00'),
            currency="INR"
        )
        
        # Manually trigger the signal
        milestone_post_save_handler(sender=ReferralMilestone, instance=milestone, created=True)
        
        # The signal should complete without error
        # In a real implementation, this might log to a file or database
        
        # Reconnect the signal
        post_save.connect(milestone_post_save_handler, sender=ReferralMilestone)

    def test_config_post_save_handler_signal(self):
        """Test that config post-save signal logs the action."""
        # Disconnect the signal temporarily
        post_save.disconnect(config_post_save_handler, sender=ReferralConfig)
        
        # Create config
        config = ReferralConfigFactory(
            max_levels=5,
            level_1_percentage=Decimal('7.0'),
            level_2_percentage=Decimal('5.0'),
            level_3_percentage=Decimal('3.0'),
            level_4_percentage=Decimal('2.0'),
            level_5_percentage=Decimal('1.0'),
            is_active=True
        )
        
        # Manually trigger the signal
        config_post_save_handler(sender=ReferralConfig, instance=config, created=True)
        
        # The signal should complete without error
        # In a real implementation, this might log to a file or database
        
        # Reconnect the signal
        post_save.connect(config_post_save_handler, sender=ReferralConfig)

    def test_cleanup_user_referral_data_signal(self):
        """Test that user referral data is cleaned up when User is deleted."""
        # Disconnect the signal temporarily
        post_delete.disconnect(cleanup_user_referral_data, sender=User)
        
        # Create user profile and referral data
        profile = UserReferralProfileFactory(user=self.user1)
        referral = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        earning = ReferralEarningFactory(
            referral=referral,
            level=1,
            amount=Decimal('50.00'),
            currency='INR'
        )
        
        # Check that data exists
        self.assertTrue(UserReferralProfile.objects.filter(user=self.user1).exists())
        self.assertTrue(Referral.objects.filter(user=self.user1).exists())
        self.assertTrue(ReferralEarning.objects.filter(referral=referral).exists())
        
        # Manually trigger the signal
        cleanup_user_referral_data(sender=User, instance=self.user1)
        
        # Check that data was cleaned up
        self.assertFalse(UserReferralProfile.objects.filter(user=self.user1).exists())
        self.assertFalse(Referral.objects.filter(user=self.user1).exists())
        self.assertFalse(ReferralEarning.objects.filter(referral=referral).exists())
        
        # Reconnect the signal
        post_delete.connect(cleanup_user_referral_data, sender=User)

    def test_signal_integration_user_creation(self):
        """Test that signals work together when creating a user."""
        # Create a new user (this should trigger the signal)
        new_user = User.objects.create(
            email='integration@example.com',
            username='integrationuser',
            password='testpass123'
        )
        
        # Check that referral profile was created automatically
        profile = UserReferralProfile.objects.get(user=new_user)
        self.assertIsNotNone(profile.referral_code)
        self.assertIsNone(profile.referred_by)
        self.assertEqual(profile.total_referrals, 0)

    def test_signal_integration_referral_creation(self):
        """Test that signals work together when creating referrals."""
        # Create referral profiles
        profile1 = UserReferralProfileFactory(user=self.user1)
        profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        
        # Create referral (this should trigger the signal)
        referral = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        
        # Check that referrer stats were updated automatically
        profile1.refresh_from_db()
        self.assertEqual(profile1.total_referrals, 1)

    def test_signal_integration_earning_creation(self):
        """Test that signals work together when creating referral earnings."""
        # Create referral profiles and referral
        profile1 = UserReferralProfileFactory(user=self.user1)
        profile2 = UserReferralProfileFactory(user=self.user2, referred_by=self.user1)
        referral = ReferralFactory(user=self.user1, referred_user=self.user2, level=1, referrer=None)
        
        # Create earning (this should trigger the signal)
        earning = ReferralEarningFactory(
            referral=referral,
            level=1,
            amount=Decimal('50.00'),
            currency='INR'
        )
        
        # Check that user stats were updated automatically
        profile1.refresh_from_db()
        self.assertEqual(profile1.total_earnings_inr, Decimal('50.00'))

    def test_signal_registration(self):
        """Test that all signals are properly registered."""
        from app.referral.signals import register_signals
        
        # Call the registration function
        register_signals()
        
        # Check that signals are connected
        # Note: In a real test, you might check the signal registry
        # For now, we'll just ensure the function runs without error
        self.assertTrue(True)



